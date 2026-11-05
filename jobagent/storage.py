"""Gemmer jobansøgninger lokalt eller i Supabase.

Begge klasser har de samme tre metoder, så app.py ikke skal vide, hvor dataene ligger:
  gem(...)        -> gemmer en ansøgning og returnerer dens id
  seneste(antal)  -> de nyeste ansøgninger (til historikken)
  hent(id)        -> én ansøgning (til detaljesiden)
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path


def lav_filnavn(virksomhed: str, tidspunkt: datetime | None = None) -> str:
    tidspunkt = tidspunkt or datetime.now()
    navn = re.sub(r"[^a-z0-9æøå]+", "-", virksomhed.lower()).strip("-") or "ukendt"
    return f"{tidspunkt:%Y%m%d-%H%M%S}_{navn}"


class LocalStorage:
    """Gemmer i mappen udkast/: en .txt med ansøgningen og en .json med resten."""

    def __init__(self, mappe: str | Path = "udkast"):
        self.mappe = Path(mappe)
        self.mappe.mkdir(parents=True, exist_ok=True)

    def gem(
        self,
        virksomhed: str,
        stilling: str,
        ansøgning: str,
        problemer: list[str],
        jobopslag: str = "",
        cv: str = "",
        log: list[dict] | None = None,
    ) -> str:
        navn = lav_filnavn(virksomhed)
        (self.mappe / f"{navn}.txt").write_text(ansøgning, encoding="utf-8")

        metadata = {
            "virksomhed": virksomhed,
            "stilling": stilling,
            "oprettet": datetime.now().isoformat(timespec="seconds"),
            "antal_ord": len(ansøgning.split()),
            "problemer": problemer,
            "jobopslag": jobopslag,
            "cv": cv,
            "log": log or [],
        }
        (self.mappe / f"{navn}.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return navn

    def liste(self) -> list[Path]:
        return sorted(self.mappe.glob("*.txt"))

    def hent(self, id: str) -> dict | None:
        # Kun bogstaver, tal, - og _ er tilladt, så ingen kan hente filer uden for mappen
        if not re.fullmatch(r"[\w\-]+", id):
            return None
        tekstfil = self.mappe / f"{id}.txt"
        if not tekstfil.exists():
            return None
        jsonfil = tekstfil.with_suffix(".json")
        data = json.loads(jsonfil.read_text(encoding="utf-8")) if jsonfil.exists() else {}
        data["id"] = id
        data["ansogning"] = tekstfil.read_text(encoding="utf-8")
        return data

    def seneste(self, antal: int = 10) -> list[dict]:
        nyeste_først = sorted(self.liste(), reverse=True)[:antal]
        return [self.hent(fil.stem) for fil in nyeste_først]


class SupabaseStorage:
    """Gemmer jobansøgninger i Supabase-tabellen ``jobansogninger``.

    Secret key bruges kun på serveren og må aldrig lægges i HTML eller GitHub.
    """

    TABEL = "jobansogninger"

    def __init__(self, url: str | None = None, key: str | None = None, client=None):
        if client is None:
            from supabase import create_client

            client = create_client(
                url or os.environ["SUPABASE_URL"],
                key or os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            )
        self.client = client

    def gem(
        self,
        virksomhed: str,
        stilling: str,
        ansøgning: str,
        problemer: list[str],
        jobopslag: str = "",
        cv: str = "",
        log: list[dict] | None = None,
    ) -> str:
        data = {
            "virksomhed": virksomhed,
            "stilling": stilling,
            "jobopslag": jobopslag,
            "cv": cv,
            "ansogning": ansøgning,
            "problemer": problemer,
            "log": log or [],
        }
        svar = self.client.table(self.TABEL).insert(data).execute()
        return str(svar.data[0]["id"])

    def seneste(self, antal: int = 10) -> list[dict]:
        svar = (
            self.client.table(self.TABEL)
            .select("id, virksomhed, stilling, problemer, ansogning, created_at")
            .order("created_at", desc=True)
            .limit(antal)
            .execute()
        )
        return [self._tilpas(række) for række in svar.data]

    def hent(self, id: str) -> dict | None:
        svar = self.client.table(self.TABEL).select("*").eq("id", id).limit(1).execute()
        return self._tilpas(svar.data[0]) if svar.data else None

    @staticmethod
    def _tilpas(række: dict) -> dict:
        """Giver Supabase-rækker samme form som de lokale data."""
        række = dict(række)
        række["id"] = str(række["id"])
        række["oprettet"] = str(række.get("created_at", ""))[:19]
        række["antal_ord"] = len((række.get("ansogning") or "").split())
        række.setdefault("log", [])
        return række


def hent_standard_storage():
    """Brug Supabase, når variablerne findes, ellers lokal lagring."""
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        return SupabaseStorage()
    return LocalStorage()