"""Selve AI-agenten.

Agenten arbejder i tre trin:
  1. Analyserer jobopslaget (virksomhed, stilling, krav)
  2. Skriver et udkast til en ansøgning ud fra jobopslag + CV
  3. Kvalitetstjekker udkastet og beder AI'en rette det, hvis der er problemer
"""

import json
import re
from dataclasses import dataclass, field

from .llm import LLM

SYSTEM_PROMPT = (
    "Du er en erfaren dansk karriererådgiver. Du skriver klare, personlige og "
    "professionelle jobansøgninger på dansk. Du opfinder aldrig erfaring, "
    "uddannelse eller kompetencer, som ikke står i CV'et."
)

PLADSHOLDER_MØNSTER = re.compile(r"\[[^\]]+\]|<[^>]+>|XXX", re.IGNORECASE)


@dataclass
class JobInfo:
    virksomhed: str
    stilling: str
    krav: list[str] = field(default_factory=list)


@dataclass
class Resultat:
    jobinfo: JobInfo
    ansøgning: str
    problemer: list[str]


class JobApplicationAgent:
    def __init__(self, llm: LLM, min_ord: int = 150, max_ord: int = 500, max_forsøg: int = 2):
        self.llm = llm
        self.min_ord = min_ord
        self.max_ord = max_ord
        self.max_forsøg = max_forsøg

    # Trin 1
    def analyser_jobopslag(self, jobopslag: str) -> JobInfo:
        prompt = (
            "Læs jobopslaget og svar KUN med JSON i dette format:\n"
            '{"virksomhed": "...", "stilling": "...", "krav": ["...", "..."]}\n\n'
            f"Jobopslag:\n{jobopslag}"
        )
        svar = self.llm.chat(SYSTEM_PROMPT, prompt)
        return parse_jobinfo(svar)

    # Trin 2 
    def skriv_ansøgning(self, jobopslag: str, cv: str, jobinfo: JobInfo) -> str:
        krav = "\n".join(f"- {k}" for k in jobinfo.krav) or "- (ingen fundet)"
        prompt = (
            f"Skriv en jobansøgning til stillingen som {jobinfo.stilling} hos {jobinfo.virksomhed}.\n"
            f"Ansøgningen skal være mellem {self.min_ord} og {self.max_ord} ord.\n"
            "Nævn virksomhedens navn, og forklar hvordan erfaringen i CV'et matcher kravene.\n"
            "Brug ikke pladsholdere som [Navn] eller [Dato].\n\n"
            f"Vigtigste krav:\n{krav}\n\n"
            f"Jobopslag:\n{jobopslag}\n\n"
            f"CV:\n{cv}"
        )
        return self.llm.chat(SYSTEM_PROMPT, prompt).strip()

    # Trin 3 
    def tjek_kvalitet(self, ansøgning: str, jobinfo: JobInfo) -> list[str]:
        """Returnerer en liste over problemer. Tom liste = godkendt."""
        problemer = []
        antal_ord = len(ansøgning.split())

        if antal_ord < self.min_ord:
            problemer.append(f"For kort: {antal_ord} ord (minimum {self.min_ord})")
        if antal_ord > self.max_ord:
            problemer.append(f"For lang: {antal_ord} ord (maksimum {self.max_ord})")
        if jobinfo.virksomhed and jobinfo.virksomhed.lower() not in ansøgning.lower():
            problemer.append(f"Virksomhedens navn '{jobinfo.virksomhed}' nævnes ikke")
        if PLADSHOLDER_MØNSTER.search(ansøgning):
            problemer.append("Indeholder pladsholdere som [Navn] eller <dato>")
        return problemer

    def ret_ansøgning(self, ansøgning: str, problemer: list[str]) -> str:
        prompt = (
            "Ret denne ansøgning, så følgende problemer løses. Svar kun med den rettede ansøgning.\n\n"
            "Problemer:\n" + "\n".join(f"- {p}" for p in problemer) + f"\n\nAnsøgning:\n{ansøgning}"
        )
        return self.llm.chat(SYSTEM_PROMPT, prompt).strip()

    # Hele forløbet 
    def kør(self, jobopslag: str, cv: str) -> Resultat:
        if not jobopslag.strip() or not cv.strip():
            raise ValueError("Både jobopslag og CV skal indeholde tekst")

        jobinfo = self.analyser_jobopslag(jobopslag)
        ansøgning = self.skriv_ansøgning(jobopslag, cv, jobinfo)
        problemer = self.tjek_kvalitet(ansøgning, jobinfo)

        forsøg = 0
        while problemer and forsøg < self.max_forsøg:
            ansøgning = self.ret_ansøgning(ansøgning, problemer)
            problemer = self.tjek_kvalitet(ansøgning, jobinfo)
            forsøg += 1

        return Resultat(jobinfo=jobinfo, ansøgning=ansøgning, problemer=problemer)


def parse_jobinfo(svar: str) -> JobInfo:
    """Finder JSON i AI'ens svar, også hvis der står tekst eller ```json omkring."""
    match = re.search(r"\{.*\}", svar, re.DOTALL)
    if not match:
        raise ValueError(f"AI'en svarede ikke med JSON: {svar[:200]}")
    data = json.loads(match.group(0))
    return JobInfo(
        virksomhed=str(data.get("virksomhed", "")).strip(),
        stilling=str(data.get("stilling", "")).strip(),
        krav=[str(k).strip() for k in data.get("krav", []) if str(k).strip()],
    )