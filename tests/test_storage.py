"""Tests af lagringen: lokal mappe og Supabase (med en falsk Supabase-klient)."""

from jobagent.storage import LocalStorage, SupabaseStorage

LOG = [{"tid": "10:00:00", "sekunder": 1.0, "trin": "Analyse", "besked": "ok", "status": "ok"}]


# Lokal lagring
def test_lokal_hent_giver_alt_tilbage(tmp_path):
    storage = LocalStorage(tmp_path)
    id = storage.gem("Netto", "Udvikler", "Kære Netto", ["For kort"], jobopslag="Opslag", cv="CV", log=LOG)
    data = storage.hent(id)
    assert data["ansogning"] == "Kære Netto"
    assert data["stilling"] == "Udvikler"
    assert data["jobopslag"] == "Opslag"
    assert data["log"] == LOG


def test_lokal_seneste_nyeste_først(tmp_path):
    storage = LocalStorage(tmp_path)
    (tmp_path / "20260101-100000_a.txt").write_text("A", encoding="utf-8")
    (tmp_path / "20260301-100000_c.txt").write_text("C", encoding="utf-8")
    (tmp_path / "20260201-100000_b.txt").write_text("B", encoding="utf-8")
    assert [a["ansogning"] for a in storage.seneste()] == ["C", "B", "A"]
    assert len(storage.seneste(antal=2)) == 2


def test_lokal_hent_ukendt_id(tmp_path):
    assert LocalStorage(tmp_path).hent("findes-ikke") is None


def test_lokal_hent_afviser_farlige_stier(tmp_path):
    assert LocalStorage(tmp_path).hent("../hemmelig") is None


# Supabase (falsk klient, så testene ikke kræver internet)
class FalskTabel:
    def __init__(self, rækker):
        self.rækker = rækker
        self._filter = None
        self._omvendt = False
        self._antal = None

    def insert(self, data):
        række = dict(data, id=len(self.rækker) + 1, created_at=f"2026-11-05T10:0{len(self.rækker)}:00")
        self.rækker.append(række)
        self._svar = [række]
        return self

    def select(self, *_):
        self._svar = None
        return self

    def eq(self, kolonne, værdi):
        self._filter = (kolonne, værdi)
        return self

    def order(self, kolonne, desc=False):
        self._omvendt = desc
        return self

    def limit(self, antal):
        self._antal = antal
        return self

    def execute(self):
        if self._svar is None:
            data = list(self.rækker)
            if self._filter:
                k, v = self._filter
                data = [r for r in data if str(r[k]) == str(v)]
            if self._omvendt:
                data.reverse()
            self._svar = data[: self._antal]
        return type("Svar", (), {"data": self._svar})()


class FalskKlient:
    def __init__(self):
        self.rækker = []

    def table(self, navn):
        assert navn == "jobansogninger"
        return FalskTabel(self.rækker)


def test_supabase_gem_og_hent():
    storage = SupabaseStorage(client=FalskKlient())
    id = storage.gem("Netto", "Udvikler", "Kære Netto", [], jobopslag="Opslag", cv="CV", log=LOG)
    data = storage.hent(id)
    assert data["ansogning"] == "Kære Netto"
    assert data["log"] == LOG
    assert data["antal_ord"] == 2


def test_supabase_seneste_nyeste_først():
    storage = SupabaseStorage(client=FalskKlient())
    storage.gem("A", "Første", "a", [])
    storage.gem("B", "Anden", "b", [])
    assert [a["stilling"] for a in storage.seneste()] == ["Anden", "Første"]


def test_supabase_hent_ukendt_id():
    assert SupabaseStorage(client=FalskKlient()).hent("999") is None