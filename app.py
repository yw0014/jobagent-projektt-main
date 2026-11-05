"""Hjemmesiden. Start den med:

    python app.py

Åbn derefter http://127.0.0.1:5000 i din browser.
"""

import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request

from jobagent.agent import JobApplicationAgent
from jobagent.reader import read_text
from jobagent.storage import hent_standard_storage


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

    @app.route("/", methods=["GET", "POST"])
    def forside():
        if request.method == "GET":
            return render_template("index.html")

        jobopslag = request.form.get("jobopslag", "").strip()
        cv = request.form.get("cv", "").strip()
        side = {"jobopslag": jobopslag, "cv": cv}

        try:
            cv_fil = request.files.get("cv_fil")
            if cv_fil and cv_fil.filename:
                cv = læs_upload(cv_fil)
                side["cv"] = cv

            if not jobopslag or not cv:
                return render_template("index.html", fejl="Indsæt både et jobopslag og et CV.", **side)

            resultat = agent.kør(jobopslag, cv)
        except ValueError as e:
            return render_template("index.html", fejl=str(e), **side)
        except Exception as e:  # fx hvis Ollama ikke kører
            return render_template("index.html", fejl=f"Kunne ikke kontakte AI'en: {e}", **side)

        fil = storage.gem(
            resultat.jobinfo.virksomhed,
            resultat.jobinfo.stilling,
            resultat.ansøgning,
            resultat.problemer,
            jobopslag=jobopslag,
            cv=cv,
        )
        return render_template("index.html", resultat=resultat, gemt_som=fil.name, **side)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
