# FantasyHelper

Helper to your NBA fantasy, from draft to day-to-day.

## Run locally

Use Python 3.10 or newer. From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
streamlit run app.py
```

Open the local URL Streamlit prints. It is usually http://localhost:8501.

The screen says that no league is loaded until you create one. You can add, edit, and remove leagues. Edit and create open over the screen. Choosing a league or a dataset holds until you refresh the browser or stop the app. Opening the app again starts on the first league and the first dataset, and skips files that were already imported.

The database is `data/fantasyhelper.sqlite3`. The inbox and the database stay on this machine.
