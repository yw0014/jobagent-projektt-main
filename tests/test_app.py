"""Tests af hjemmesiden. Flask har en indbygget test-klient, så vi ikke skal åbne en browser."""

import io
import json

from app import create_app
from jobagent.storage import LocalStorage

GOD_ANSØGNING = "Kære Netto. " + "Jeg har erfaring med Python og test. " * 30
JOB_JSON = json.dumps({"virksomhed": "Netto", "stilling": "Udvikler", "krav": ["Python"]})


class FakeLLM:
    def __init__(self, svar):
        self.svar = list(svar)
        self.prompts = []

    def chat(self, system, user):
        self.prompts.append(user)
        return self.svar.pop(0)


class FejlendeLLM:
    def chat(self, system, user):
        raise ConnectionError("Connection refused")


def lav_klient(llm, tmp_path):
    app = create_app(llm=llm, storage=LocalStorage(tmp_path))
    app.config["TESTING"] = True
    return app.test_client()


def test_forsiden_vises(tmp_path):
    svar = lav_klient(FakeLLM([]), tmp_path).get("/")
    assert svar.status_code == 200
    assert "Skriv ansøgning" in svar.get_data(as_text=True)


def test_skriver_ansøgning_og_gemmer(tmp_path):
    klient = lav_klient(FakeLLM([JOB_JSON, GOD_ANSØGNING]), tmp_path)
    svar = klient.post("/", data={"jobopslag": "Vi søger en udvikler", "cv": "Mit CV"})
    html = svar.get_data(as_text=True)
    assert svar.status_code == 200
    assert "<h2>Udvikler</h2>" in html
    assert "Netto" in html
    assert "Jeg har erfaring med Python" in html
    assert len(list(tmp_path.glob("*.txt"))) == 1


def test_manglende_cv_giver_fejl(tmp_path):
    llm = FakeLLM([])
    svar = lav_klient(llm, tmp_path).post("/", data={"jobopslag": "Vi søger", "cv": ""})
    assert "Indsæt både et jobopslag og et CV" in svar.get_data(as_text=True)
    assert llm.prompts == []  # AI'en bliver ikke kaldt


def test_upload_af_cv_fil(tmp_path):
    llm = FakeLLM([JOB_JSON, GOD_ANSØGNING])
    data = {"jobopslag": "Vi søger", "cv": "", "cv_fil": (io.BytesIO("CV fra fil".encode()), "cv.txt")}
    svar = lav_klient(llm, tmp_path).post("/", data=data, content_type="multipart/form-data")
    assert svar.status_code == 200
    assert "CV fra fil" in llm.prompts[1]


def test_forkert_filtype_giver_fejl(tmp_path):
    data = {"jobopslag": "Vi søger", "cv": "", "cv_fil": (io.BytesIO(b"x"), "cv.exe")}
    svar = lav_klient(FakeLLM([]), tmp_path).post("/", data=data, content_type="multipart/form-data")
    assert "understøttes ikke" in svar.get_data(as_text=True)


def test_ai_fejl_vises_pænt(tmp_path):
    svar = lav_klient(FejlendeLLM(), tmp_path).post("/", data={"jobopslag": "Vi søger", "cv": "Mit CV"})
    assert svar.status_code == 200
    assert "Kunne ikke kontakte AI" in svar.get_data(as_text=True)


def test_html_i_input_escapes(tmp_path):
    svar = lav_klient(FakeLLM([]), tmp_path).post("/", data={"jobopslag": "<script>x</script>", "cv": ""})
    assert "<script>x</script>" not in svar.get_data(as_text=True)

def test_log_vises_efter_ansøgning(tmp_path):
    klient = lav_klient(FakeLLM([JOB_JSON, GOD_ANSØGNING]), tmp_path)
    html = klient.post("/", data={"jobopslag": "Vi søger", "cv": "Mit CV"}).get_data(as_text=True)
    assert "Agentens log" in html
    assert "Analyse" in html and "Kvalitetstjek" in html


def test_seneste_ansøgninger_på_forsiden(tmp_path):
    klient = lav_klient(FakeLLM([JOB_JSON, GOD_ANSØGNING]), tmp_path)
    klient.post("/", data={"jobopslag": "Vi søger", "cv": "Mit CV"})
    html = klient.get("/").get_data(as_text=True)
    assert "Seneste ansøgninger" in html
    assert "Udvikler" in html


def test_historik_og_detaljeside(tmp_path):
    klient = lav_klient(FakeLLM([JOB_JSON, GOD_ANSØGNING]), tmp_path)
    klient.post("/", data={"jobopslag": "Vi søger", "cv": "Mit CV"})
    historik = klient.get("/historik").get_data(as_text=True)
    assert "Netto" in historik

    id = next(tmp_path.glob("*.txt")).stem
    detalje = klient.get(f"/ansoegning/{id}")
    assert detalje.status_code == 200
    html = detalje.get_data(as_text=True)
    assert "Jeg har erfaring med Python" in html
    assert "Agentens log" in html


def test_ukendt_ansøgning_giver_404(tmp_path):
    svar = lav_klient(FakeLLM([]), tmp_path).get("/ansoegning/findes-ikke")
    assert svar.status_code == 404


class FejlendeStorage(LocalStorage):
    def seneste(self, antal=10):
        raise ConnectionError("Supabase svarer ikke")


def test_siden_virker_selvom_historik_fejler(tmp_path):
    app = create_app(llm=FakeLLM([]), storage=FejlendeStorage(tmp_path))
    svar = app.test_client().get("/")
    assert svar.status_code == 200
    assert "Kunne ikke hente historikken" in svar.get_data(as_text=True)