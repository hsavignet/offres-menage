import os
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "offres.db")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

KEYWORDS = [
    "entretien",
    "nettoyage",
    "ménager",
    "menager",
    "conciergerie",
    "sanitation",
    "maintenance"
]

SEARCH_URL = "https://www.seao.ca/Recherche/recherche.aspx"


def get_db():
    return sqlite3.connect(DB)


def matches_keywords(text):
    t = (text or "").lower()
    return any(k in t for k in KEYWORDS)


def fetch_seao():
    conn = get_db()
    c = conn.cursor()

    for page in range(1, 6):  # pages 1 à 5
        params = {
            "keyword": "entretien",
            "type": "Services",
            "page": page
        }

        try:
            r = requests.get(SEARCH_URL, headers=HEADERS, params=params, timeout=30)
            soup = BeautifulSoup(r.text, "html.parser")

            results = soup.select(".result-item")

            for item in results:
                title_el = item.select_one("a")
                date_el = item.select_one(".date")

                if not title_el:
                    continue

                titre = title_el.get_text(strip=True)
                lien = "https://www.seao.ca" + title_el.get("href", "")
                date_pub = date_el.get_text(strip=True) if date_el else ""

                if not matches_keywords(titre):
                    continue

                c.execute("""
                    INSERT OR IGNORE INTO offres (titre, lien, source, date_pub)
                    VALUES (?, ?, ?, ?)
                """, (
                    titre,
                    lien,
                    "SEAO",
                    date_pub or datetime.utcnow().isoformat()
                ))

        except Exception as e:
            print("SEAO error page", page, e)

    conn.commit()
    conn.close()
    print("✅ SEAO refresh terminé")


def main():
    fetch_seao()


if __name__ == "__main__":
    main()
