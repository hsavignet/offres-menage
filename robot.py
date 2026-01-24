import os
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "offres.db")

SOURCES = [
    "https://www.longueuil.quebec/fr/appels-doffres",
    "https://www.laval.ca/Pages/Fr/Citoyens/appels-offres.aspx",
]

KEYWORDS = [
    "entretien", "ménage", "menage",
    "nettoyage", "conciergerie", "maintenance"
]

def main():
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

    headers = {"User-Agent": "Mozilla/5.0"}

    for source in SOURCES:
        try:
            r = requests.get(source, headers=headers, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            for a in soup.find_all("a"):
                title = a.get_text(strip=True)
                link = a.get("href")

                if not title or not link:
                    continue

                if not any(k in title.lower() for k in KEYWORDS):
                    continue

                if link.startswith("/"):
                    link = source.split("/")[0] + "//" + source.split("/")[2] + link

                c.execute("""
                    INSERT OR IGNORE INTO offres (titre, lien, date_pub)
                    VALUES (?, ?, ?)
                """, (
                    title,
                    link,
                    datetime.utcnow().isoformat()
                ))
        except Exception as e:
            print("Source error:", source, e)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
