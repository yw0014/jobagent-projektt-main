"""Læser tekst fra filer (.txt, .md, .pdf, .docx)."""

from pathlib import Path


def read_text(path: str | Path) -> str:
    """Returnerer al tekst fra en fil. Fejler, hvis filen ikke findes eller er tom."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Filen findes ikke: {path}")

    suffix = path.suffix.lower()

    if suffix in (".txt", ".md"):
        text = path.read_text(encoding="utf-8")
    elif suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif suffix == ".docx":
        from docx import Document

        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError(f"Filtypen {suffix} understøttes ikke. Brug .txt, .md, .pdf eller .docx")

    text = text.strip()
    if not text:
        raise ValueError(f"Filen er tom: {path}")
    return text