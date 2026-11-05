"""Gemmer jobansøgninger lokalt eller i Supabase."""

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
    ) -> Path:
        navn = lav_filnavn(virksomhed)
        tekstfil = self.mappe / f"{navn}.txt"
        tekstfil.write_text(ansøgning, encoding="utf-8")

        metadata = {
            "virksomhed": virksomhed,
            "stilling": stilling,
            "oprettet": datetime.now().isoformat(timespec="seconds"),
            "antal_ord": len(ansøgning.split()),
            "problemer": problemer,
        }
        (self.mappe / f"{navn}.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return tekstfil

    def liste(self) -> list[Path]:
        return sorted(self.mappe.glob("*.txt"))


class SupabaseStorage:
    """Gemmer jobansøgninger i Supabase-tabellen ``jobansogninger``.

    Secret key bruges kun på serveren og må aldrig lægges i HTML eller GitHub.
    """

    def __init__(self, url: str | None = None, key: str | None = None):
        from supabase import Client, create_client

        self.client: Client = create_client(
            url or os.environ["SUPABASE_URL"],
            key or os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )

    def gem(
        self,
        virksomhed: str,
        stilling: str,
        ansøgning: str,
        problemer: list[str],
        jobopslag: str = "",
        cv: str = "",
    ) -> Path:
        data = {
            "virksomhed": virksomhed,
            "stilling": stilling,
            "jobopslag": jobopslag,
            "cv": cv,
            "ansogning": ansøgning,
            "problemer": problemer,
        }
        self.client.table("jobansogninger").insert(data).execute()
        # Appen viser kun filens navn efter lagring. Her returnerer vi et tydeligt
        # cloud-navn, selv om dataene fysisk ligger i Supabase.
        return Path(f"supabase_{lav_filnavn(virksomhed)}.txt")

    def liste(self) -> list[dict]:
        return self.client.table("jobansogninger").select("*").execute().data


def hent_standard_storage():
    """Brug Supabase, når variablerne findes, ellers lokal lagring."""
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        return SupabaseStorage()
    return LocalStorage()
