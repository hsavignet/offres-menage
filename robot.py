import os
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "offres.db")

SOURCES = [
    ("Municipal", "https://www.longueuil.quebec/fr/appels-doffres"),
    ("Municipal", "https://www.laval.ca/Pages/Fr/Citoyens/appels-offres.aspx"),
]

KEYWORDS = [
    "entretien",
    "ménage",
    "menage",
    "nettoyage",
    "conciergerie",
    "maintenance",
]

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # ⚠️ TABLE AVEC SOURCE (IMPORTANT)
    c.execute("""
        CREATE TABLE IF NOT EXISTS offres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT,
            lien TEXT UNIQUE,
            source TEXT,
            date_pub TEXT
        )
    """)

    headers = {"User-Agent": "Mozilla/5.0"}

    for source_name, url in SOURCES:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            for a in soup.find_all("a"):
                titre = a.get_text(strip=True)
                lien = a.get("href")

                if not titre or not lien:
                    continue

                if not any(k in titre.lower() for k in KEYWORDS):
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
            print("Erreur source", url, e)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
