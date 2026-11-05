"""Hjemmesiden. Start den med:

    python app.py

Åbn derefter http://127.0.0.1:5000 i din browser.

Sider:
  /                   Skriv en ny ansøgning
  /historik           Alle tidligere ansøgninger
  /ansoegning/<id>    Én gemt ansøgning med agentens log
"""

import logging
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, render_template, request

from jobagent.agent import JobApplicationAgent
from jobagent.reader import read_text
from jobagent.storage import hent_standard_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("jobagent")


def læs_upload(fil) -> str:
    """Gemmer den uploadede fil midlertidigt og læser teksten fra den."""
    endelse = Path(fil.filename).suffix.lower()
    with tempfile.TemporaryDirectory() as mappe:
        sti = Path(mappe) / f"upload{endelse}"
        fil.save(sti)
        return read_text(sti)


def create_app(llm=None, storage=None) -> Flask:
    """Laver hjemmesiden. I testene sender vi en falsk AI og en test-mappe med."""
    load_dotenv()
    if llm is None:
        from jobagent.llm import OpenAICompatibleLLM

        llm = OpenAICompatibleLLM()

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # højst 5 MB pr. upload
    agent = JobApplicationAgent(llm)
    storage = storage or hent_standard_storage()
    lagring_navn = type(storage).__name__.replace("Storage", "")  # "Local" eller "Supabase"

    def hent_seneste(antal: int) -> tuple[list[dict], str | None]:
        """Henter historikken. Går det galt (fx Supabase er nede), virker siden stadig."""
        try:
            return storage.seneste(antal), None
        except Exception as e:
            log.warning("Kunne ikke hente historik: %s", e)
            return [], f"Kunne ikke hente historikken: {e}"

    @app.context_processor
    def fælles_data():
        return {"lagring_navn": lagring_navn}

    def vis_forside(**data):
        seneste, historik_fejl = hent_seneste(5)
        return render_template("index.html", seneste=seneste, historik_fejl=historik_fejl, **data)

    @app.route("/", methods=["GET", "POST"])
    def forside():
        if request.method == "GET":
            return vis_forside()

        jobopslag = request.form.get("jobopslag", "").strip()
        cv = request.form.get("cv", "").strip()
        side = {"jobopslag": jobopslag, "cv": cv}

        try:
            cv_fil = request.files.get("cv_fil")
            if cv_fil and cv_fil.filename:
                cv = læs_upload(cv_fil)
                side["cv"] = cv

            if not jobopslag or not cv:
                return vis_forside(fejl="Indsæt både et jobopslag og et CV.", **side)

            log.info("Starter agenten (jobopslag: %d tegn, CV: %d tegn)", len(jobopslag), len(cv))
            resultat = agent.kør(jobopslag, cv)
        except ValueError as e:
            return vis_forside(fejl=str(e), **side)
        except Exception as e:  # fx hvis Ollama ikke kører
            log.error("AI-fejl: %s", e)
            return vis_forside(fejl=f"Kunne ikke kontakte AI'en: {e}", **side)

        try:
            gemt_id = storage.gem(
                resultat.jobinfo.virksomhed,
                resultat.jobinfo.stilling,
                resultat.ansøgning,
                resultat.problemer,
                jobopslag=jobopslag,
                cv=cv,
                log=resultat.log,
            )
            log.info("Gemt ansøgning %s i %s", gemt_id, lagring_navn)
        except Exception as e:
            log.error("Kunne ikke gemme: %s", e)
            gemt_id = None
            resultat.log.append(
                {"tid": "", "sekunder": 0, "trin": "Gem", "besked": f"Kunne ikke gemme: {e}", "status": "fejl"}
            )

        return vis_forside(resultat=resultat, gemt_id=gemt_id, **side)

    @app.route("/historik")
    def historik():
        ansøgninger, historik_fejl = hent_seneste(50)
        return render_template("historik.html", ansøgninger=ansøgninger, historik_fejl=historik_fejl)

    @app.route("/ansoegning/<id>")
    def vis_ansøgning(id):
        try:
            ansøgning = storage.hent(id)
        except Exception as e:
            log.warning("Kunne ikke hente %s: %s", id, e)
            ansøgning = None
        if ansøgning is None:
            abort(404)
        return render_template("ansoegning.html", a=ansøgning)

    @app.errorhandler(404)
    def ikke_fundet(e):
        return render_template("fejl.html", besked="Siden eller ansøgningen findes ikke."), 404

    return app


if __name__ == "__main__":
    create_app().run(debug=True)