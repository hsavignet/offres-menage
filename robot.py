import os
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime

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
    "sanitation"
]


def get_db():
    return sqlite3.connect(DB)


def matches_keywords(text):
    t = (text or "").lower()
    return any(k in t for k in KEYWORDS)


def fetch_indeed():

    conn = get_db()
    c = conn.cursor()

    url = "https://ca.indeed.com/jobs?q=entretien+menager&l=Quebec"

    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")

    jobs = soup.select("a.tapItem")

    for j in jobs:

        title = j.get_text(strip=True)

        if not matches_keywords(title):
            continue

        link = j.get("href")

        if not link:
            continue

        link = "https://ca.indeed.com" + link

        try:

            c.execute("""
            INSERT OR IGNORE INTO offres
            (titre,lien,source,date_pub)
            VALUES (?,?,?,?)
            """, (
                title,
                link,
                "Indeed",
                datetime.utcnow().isoformat()
            ))

        except:
            pass

    conn.commit()
    conn.close()

    print("Indeed terminé")


def main():

    fetch_indeed()


if __name__ == "__main__":
    main()