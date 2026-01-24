import os
import sqlite3
import requests
from datetime import datetime
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "offres.db")

KEYWORDS = [
    "entretien", "ménage", "menage", "nettoyage",
    "conciergerie", "janitorial", "maintenance",
    "services", "bâtiment", "batiment"
]

# ===============================
# SOURCE 1 — SEAO (officiel)
# ===============================
CKAN_URL = "https://www.donneesquebec.ca/recherche/api/3/action/package_show"
DATASET_ID = "d23b2e02-085d-43e5-9e6e-e1d558ebfdd5"

# ===============================
# SOURCE 2 — MUNICIPAL (HTML)
# ===============================
MUNICIPAL_URLS = [
    "https://www.ville.quebec.qc.ca/apropos/affaires/appels_offres.aspx",
    "https://www.longueuil.quebec/fr/appels-doffres",
    "https://www.laval.ca/Pages/Fr/Citoyens/appels-offres.aspx",
]

# ===============================
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS offres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT,
            lien TEXT UNIQUE,
            source TEXT,
            date_pub TEXT
        )
    """)
    conn.commit()
    conn.close()


def matches_keywords(text):
    t = (text or "").lower()
    return any(k in t for k in KEYWORDS)


# ===============================
# SEAO
# ===============================
def fetch_seao(c):
    try:
        r = requests.get(CKAN_URL, params={"id": DATASET_ID}, timeout=30)
        r.raise_for_status()
        data = r.json()
        resources = data["result"]["resources"]
        jsons = [r for r in resources if r.get("format","").lower() == "json"]
        jsons.sort(key=lambda r: r.get("last_modified",""), reverse=True)
        url = jsons[0]["url"]

        data = requests.get(url, timeout=60).json()
        releases = data.get("releases", [])

        for rel in releases:
            tender = rel.get("tender", {})
            title = tender.get("title", "")
            desc = tender.get("description", "")
            link = tender.get("url") or rel.get("links", {}).get("html")

            if not title or not link:
                continue
            if not matches_keywords(title + " " + desc):
                continue

            c.execute("""
                INSERT OR IGNORE INTO offres (titre, lien, source, date_pub)
                VALUES (?, ?, ?, ?)
            """, (
                title.strip(),
                link,
                "SEAO",
                datetime.utcnow().isoformat()
            ))
    except Exception as e:
        print("SEAO error:", e)


# ===============================
# MUNICIPAL (HTML simple)
# ===============================
def fetch_municipal(c):
    headers = {"User-Agent": "Mozilla/5.0"}

    for url in MUNICIPAL_URLS:
        try:
            r = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")

            for a in soup.find_all("a"):
                title = a.get_text(strip=True)
                link = a.get("href")

                if not title or not link:
                    continue
                if not matches_keywords(title):
                    continue

                if link.startswith("/"):
                    link = url.split("/")[0] + "//" + url.split("/")[2] + link

                c.execute("""
                    INSERT OR IGNORE INTO offres (titre, lien, source, date_pub)
                    VALUES (?, ?, ?, ?)
                """, (
                    title,
                    link,
                    "Municipal",
                    datetime.utcnow().isoformat()
                ))
        except Exception as e:
            print("Municipal error:", e)


# ===============================
def main():
    init_db()
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    fetch_seao(c)
    fetch_municipal(c)

    conn.commit()
    conn.close()
    print("✅ Rafraîchissement terminé")


if __name__ == "__main__":
    main()
