import os
import sqlite3
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "offres.db")

KEYWORDS = [
    "entretien", "ménage", "menage", "nettoyage",
    "conciergerie", "janitorial", "désinfection", "desinfection"
]

CKAN_URL = "https://www.donneesquebec.ca/recherche/api/3/action/package_show"
DATASET_ID = "d23b2e02-085d-43e5-9e6e-e1d558ebfdd5"


def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS offres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT,
            lien TEXT UNIQUE,
            date_pub TEXT
        )
    """)
    conn.commit()
    conn.close()


def matches_keywords(text):
    t = (text or "").lower()
    return any(k in t for k in KEYWORDS)


def get_latest_json_url():
    r = requests.get(CKAN_URL, params={"id": DATASET_ID}, timeout=30)
    r.raise_for_status()
    data = r.json()
    resources = data["result"]["resources"]

    json_files = [r for r in resources if r.get("format","").lower() == "json"]
    json_files.sort(key=lambda r: r.get("last_modified",""), reverse=True)
    return json_files[0]["url"]


def main():
    init_db()

    try:
        url = get_latest_json_url()
        data = requests.get(url, timeout=60).json()
    except Exception as e:
        print("SEAO error:", e)
        return

    releases = data.get("releases", [])

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    for rel in releases:
        tender = rel.get("tender", {})
        title = tender.get("title", "")
        desc = tender.get("description", "")

        if not title or not matches_keywords(title + " " + desc):
            continue

        link = tender.get("url") or rel.get("links", {}).get("html")
        if not link:
            continue

        c.execute("""
            INSERT OR IGNORE INTO offres (titre, lien, date_pub)
            VALUES (?, ?, ?)
        """, (
            title.strip(),
            link,
            datetime.utcnow().isoformat()
        ))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
