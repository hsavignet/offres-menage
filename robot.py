import os
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "offres.db")

KEYWORDS = [
    "entretien", "ménage", "menage", "nettoyage",
    "conciergerie", "maintenance", "bâtiment", "batiment",
    "hygiène", "hygiene", "sanitation"
]

# =====================================================
# SOURCES MUNICIPALES (VOLUME)
# =====================================================
MUNICIPAL_SOURCES = [
    ("Municipal", "https://www.montreal.ca/appels-offres"),
    ("Municipal", "https://www.ville.quebec.qc.ca/apropos/affaires/appels_offres.aspx"),
    ("Municipal", "https://www.laval.ca/Pages/Fr/Citoyens/appels-offres.aspx"),
    ("Municipal", "https://www.longueuil.quebec/fr/appels-doffres"),
    ("Municipal", "https://www.gatineau.ca/portail/default.aspx?p=guichet_municipal/appels_offres"),
    ("Municipal", "https://www.sherbrooke.ca/fr/ville-et-administration/appels-doffres"),
    ("Municipal", "https://www.trois-rivieres.ca/appels-offres"),
    ("Municipal", "https://www.levis.ca/ville-de-levis/appels-offres.aspx"),
    ("Municipal", "https://www.saguenay.ca/ville-et-services/appels-doffres"),
]

# =====================================================
# SEAO (GROS VOLUME OFFICIEL)
# =====================================================
CKAN_URL = "https://www.donneesquebec.ca/recherche/api/3/action/package_show"
DATASET_ID = "d23b2e02-085d-43e5-9e6e-e1d558ebfdd5"


def init_db(c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS offres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT,
            lien TEXT UNIQUE,
            source TEXT,
            date_pub TEXT
        )
    """)


def matches_keywords(text):
    t = (text or "").lower()
    return any(k in t for k in KEYWORDS)


# =====================================================
# MUNICIPAL SCRAPER
# =====================================================
def fetch_municipal(c):
    headers = {"User-Agent": "Mozilla/5.0"}

    for source_name, url in MUNICIPAL_SOURCES:
        try:
            r = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")

            for a in soup.find_all("a"):
                titre = a.get_text(strip=True)
                lien = a.get("href")

                if not titre or not lien:
                    continue
                if not matches_keywords(titre):
                    continue

                if lien.startswith("/"):
                    lien = url.split("/")[0] + "//" + url.split("/")[2] + lien

                c.execute("""
                    INSERT OR IGNORE INTO offres (titre, lien, source, date_pub)
                    VALUES (?, ?, ?, ?)
                """, (
                    titre,
                    lien,
                    source_name,
                    datetime.utcnow().isoformat()
                ))
        except Exception as e:
            print("Municipal error:", url, e)


# =====================================================
# SEAO (JSON OFFICIEL)
# =====================================================
def fetch_seao(c):
    try:
        r = requests.get(CKAN_URL, params={"id": DATASET_ID}, timeout=30)
        data = r.json()
        resources = data["result"]["resources"]
        jsons = [r for r in resources if r.get("format","").lower() == "json"]
        jsons.sort(key=lambda r: r.get("last_modified",""), reverse=True)

        url = jsons[0]["url"]
        data = requests.get(url, timeout=60).json()

        releases = data.get("releases", [])
        for rel in releases:
            tender = rel.get("tender", {})
            titre = tender.get("title", "")
            desc = tender.get("description", "")
            lien = tender.get("url") or rel.get("links", {}).get("html")

            if not titre or not lien:
                continue
            if not matches_keywords(titre + " " + desc):
                continue

            c.execute("""
                INSERT OR IGNORE INTO offres (titre, lien, source, date_pub)
                VALUES (?, ?, ?, ?)
            """, (
                titre,
                lien,
                "SEAO",
                datetime.utcnow().isoformat()
            ))
    except Exception as e:
        print("SEAO error:", e)


# =====================================================
def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    init_db(c)

    fetch_municipal(c)
    fetch_seao(c)

    conn.commit()
    conn.close()
    print("✅ Rafraîchissement terminé (municipal + SEAO)")


if __name__ == "__main__":
    main()
