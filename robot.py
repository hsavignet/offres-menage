import sqlite3
import requests
from datetime import datetime

DB = "offres.db"

KEYWORDS = [
    "entretien",
    "ménage",
    "menage",
    "nettoyage",
    "conciergerie",
    "janitorial"
]

SOURCE_URL = "https://jsonplaceholder.typicode.com/posts"


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


def main():
    init_db()

    r = requests.get(SOURCE_URL)
    data = r.json()

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    for item in data:
        titre = item["title"]
        lien = f"https://example.com/offre/{item['id']}"

        if not any(k in titre.lower() for k in KEYWORDS):
            continue

        c.execute("""
            INSERT OR IGNORE INTO offres (titre, lien, date_pub)
            VALUES (?, ?, ?)
        """, (
            titre,
            lien,
            datetime.utcnow().isoformat()
        ))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
