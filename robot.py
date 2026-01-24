import sqlite3
import requests
from datetime import datetime

DB = "offres.db"

# mots-clés entretien ménager (B2B)
KEYWORDS = [
    "entretien",
    "ménage",
    "menage",
    "nettoyage",
    "conciergerie",
    "janitorial",
    "désinfection",
    "desinfection"
]

# Données ouvertes Québec – SEAO (API CKAN)
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
    t = text.lower()
    return any(k in t for k in KEYWORDS)


def get_latest_json_url():
    r = requests.get(CKAN_URL, params={"id": DATASET_ID}, timeout=30)
    r.raise_for_status()
    data = r.json()

    resources = data["result"]["resources"]
    json_files = [r for r in resources if r.get("format","").lower() == "json"]

    if not json_files:
        raise RuntimeError("Aucun fichier JSON SEAO trouvé")

    json_files.sort(key=lambda r: r.get("last_modified",""), reverse=True)
    return json_files[0]["url"]


def main():
    print("🔄 Rafraîchissement SEAO…")
    init_db()

    try:
        json_url = get_latest_json_url()
        r = requests.get(json_url, timeout=60)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("❌ Erreur SEAO:", e)
        return

    releases = data.get("releases", [])
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    added = 0

    for rel in releases:
        tender = rel.get("tender", {})
        title = tender.get("title", "")
        desc = tender.get("description", "")

        if not title:
            continue
        if not matches_keywords(title + " " + desc):
            continue

        url = (
            tender.get("url")
            or rel.get("links", {}).get("html")
            or ""
        )

        if not url:
            continue

        c.execute("""
            INSERT OR IGNORE INTO offres (titre, lien, date_pub)
            VALUES (?, ?, ?)
        """, (
            title.strip(),
            url,
            datetime.utcnow().isoformat()
        ))

        if c.rowcount == 1:
            added += 1
            print("➕", title)

    conn.commit()
    conn.close()
    print(f"✅ {added} nouvelles offres ajoutées")


if __name__ == "__main__":
    main()
