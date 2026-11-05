# Jobansøgnings-agent

## Cloudlagring med Supabase

Appen bruger Supabase, hvis `.env` indeholder `SUPABASE_URL` og
`SUPABASE_SERVICE_ROLE_KEY`. Ellers bruger den den lokale mappe `udkast`.

Kør filen `supabase.sql` i Supabase (SQL Editor -> New query -> Run). Den opretter
tabellen `jobansogninger` med kolonner til log og dato. Tilføj derefter
værdierne fra `.env.example` til din lokale `.env`-fil.

En hjemmeside, hvor man indsætter et jobopslag og et CV, og en AI-agent skriver et udkast til en ansøgning.

## Det skal du have installeret
- Python 3.11 eller nyere (https://www.python.org/downloads/)
- Ollama (https://ollama.com/download)

## Sådan starter du
1. Hent AI-modellen:
   ```
   ollama pull llama3.2
   ```
2. Åbn en terminal i projektmappen og skriv:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   (På Mac: `source .venv/bin/activate`)
3. Kopiér `.env.example` og kald kopien `.env`.
4. Start hjemmesiden:
   ```
   python app.py
   ```
5. Åbn http://127.0.0.1:5000 i browseren.

## Sider
- `/` Skriv en ny ansøgning. Viser agentens log og de seneste ansøgninger.
- `/historik` Alle tidligere ansøgninger.
- `/ansoegning/<id>` Én gemt ansøgning med log, jobopslag og CV.

## Kør testene
```
python -m pytest
```
