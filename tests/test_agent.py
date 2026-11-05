"""Unit tests. Kør med:  pytest

Testene bruger en falsk AI (FakeLLM), så de er hurtige, gratis og
giver samme resultat hver gang.
"""

import json

import pytest

from jobagent.agent import JobApplicationAgent, JobInfo, parse_jobinfo
from jobagent.reader import read_text
from jobagent.storage import LocalStorage, lav_filnavn

GOD_ANSØGNING = "Kære Netto. " + "Jeg har erfaring med Python og test. " * 30
JOB_JSON = json.dumps({"virksomhed": "Netto", "stilling": "Udvikler", "krav": ["Python", "Test"]})


class FakeLLM:
    """Returnerer faste svar i rækkefølge og husker, hvad den blev spurgt om."""

    def __init__(self, svar: list[str]):
        self.svar = list(svar)
        self.prompts: list[str] = []

    def chat(self, system: str, user: str) -> str:
        self.prompts.append(user)
        return self.svar.pop(0)


# parse_jobinfo 
def test_parse_jobinfo_ren_json():
    info = parse_jobinfo(JOB_JSON)
    assert info.virksomhed == "Netto"
    assert info.stilling == "Udvikler"
    assert info.krav == ["Python", "Test"]


def test_parse_jobinfo_med_tekst_omkring():
    info = parse_jobinfo(f"Her er svaret:\n```json\n{JOB_JSON}\n```")
    assert info.virksomhed == "Netto"


def test_parse_jobinfo_uden_json_fejler():
    with pytest.raises(ValueError):
        parse_jobinfo("Jeg ved det ikke")


# Kvalitetstjek 
@pytest.fixture
def agent():
    return JobApplicationAgent(FakeLLM([]), min_ord=50, max_ord=300)


@pytest.fixture
def info():
    return JobInfo("Netto", "Udvikler", ["Python"])


def test_god_ansøgning_godkendes(agent, info):
    assert agent.tjek_kvalitet(GOD_ANSØGNING, info) == []


def test_for_kort_ansøgning(agent, info):
    problemer = agent.tjek_kvalitet("Kære Netto, ansæt mig.", info)
    assert any("For kort" in p for p in problemer)


def test_for_lang_ansøgning(agent, info):
    problemer = agent.tjek_kvalitet("Netto " + "ord " * 400, info)
    assert any("For lang" in p for p in problemer)


def test_mangler_virksomhedsnavn(agent, info):
    tekst = GOD_ANSØGNING.replace("Netto", "jer")
    assert any("nævnes ikke" in p for p in agent.tjek_kvalitet(tekst, info))


def test_finder_pladsholder(agent, info):
    tekst = GOD_ANSØGNING + " Med venlig hilsen [Dit navn]"
    assert any("pladsholdere" in p for p in agent.tjek_kvalitet(tekst, info))


# Hele forløbet 
def test_kør_godkendt_første_gang():
    llm = FakeLLM([JOB_JSON, GOD_ANSØGNING])
    resultat = JobApplicationAgent(llm, min_ord=50).kør("Jobopslag", "Mit CV")
    assert resultat.problemer == []
    assert len(llm.prompts) == 2  # analyse + skriv, ingen rettelse


def test_kør_retter_dårligt_udkast():
    llm = FakeLLM([JOB_JSON, "For kort.", GOD_ANSØGNING])
    resultat = JobApplicationAgent(llm, min_ord=50).kør("Jobopslag", "Mit CV")
    assert resultat.ansøgning == GOD_ANSØGNING.strip()
    assert resultat.problemer == []
    assert "For kort" in llm.prompts[2]  # agenten fortalte AI'en, hvad der var galt


def test_kør_stopper_efter_max_forsøg():
    llm = FakeLLM([JOB_JSON, "kort", "kort", "kort"])
    resultat = JobApplicationAgent(llm, min_ord=50, max_forsøg=2).kør("Jobopslag", "Mit CV")
    assert resultat.problemer  # stadig problemer, men ingen uendelig løkke
    assert len(llm.prompts) == 4


def test_cv_sendes_med_til_ai():
    llm = FakeLLM([JOB_JSON, GOD_ANSØGNING])
    JobApplicationAgent(llm, min_ord=50).kør("Jobopslag", "Python-kursus på Zealand")
    assert "Python-kursus på Zealand" in llm.prompts[1]


def test_tomt_cv_fejler():
    with pytest.raises(ValueError):
        JobApplicationAgent(FakeLLM([])).kør("Jobopslag", "   ")


# Filer og lagring 
def test_read_text_txt(tmp_path):
    fil = tmp_path / "cv.txt"
    fil.write_text("Mit CV", encoding="utf-8")
    assert read_text(fil) == "Mit CV"


def test_read_text_manglende_fil():
    with pytest.raises(FileNotFoundError):
        read_text("findes_ikke.txt")


def test_read_text_ukendt_filtype(tmp_path):
    fil = tmp_path / "cv.xyz"
    fil.write_text("x")
    with pytest.raises(ValueError):
        read_text(fil)


def test_filnavn_er_sikkert():
    navn = lav_filnavn("Føtex A/S & Co.")
    assert "/" not in navn and " " not in navn
    assert navn.endswith("føtex-a-s-co")


def test_gem_udkast(tmp_path):
    storage = LocalStorage(tmp_path)
    fil = storage.gem("Netto", "Udvikler", GOD_ANSØGNING, [])
    assert fil.read_text(encoding="utf-8") == GOD_ANSØGNING
    metadata = json.loads(fil.with_suffix(".json").read_text(encoding="utf-8"))
    assert metadata["virksomhed"] == "Netto"
    assert storage.liste() == [fil]