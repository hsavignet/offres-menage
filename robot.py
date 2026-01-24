import sqlite3
import requests
from datetime import datetime

DB = "offres.db"

# mots-clés B2B entretien ménager
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

# SOURCE EXEMPLE (POUR L’INSTANT)
# 👉 plus tard on branchera SEAO / vraies sources
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


def matches_keywords(text):
    t = text.lower()
    return any(k in t for k in KEYWORDS)


def main():
    print("🔄 Rafraîchissement des offres…")
    init_db()

    try:
        r = requests.get(SOURCE_URL, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("❌ Erreur récupération source:", e)
        return

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    added = 0

    for item in data:
        title = item.get("title", "")
        body = item.get("body", "")
        url = f"https://example.com/offre/{item.get('id')}"

        if not title:
            continue

        # filtre B2B ménage
        if not matches_keywords(title + " " + body):
            continue

        c.execute("""
            INSERT OR IGNORE INTO offres (titre, lien, date_pub)
            VALUES (?, ?, ?)
        """, (
            title.strip().capitalize(),
            url,
            datetime.utcnow().isoformat()
        ))

        if c.rowcount == 1:
            added += 1
            print("➕ Nouvelle offre :", title)

    conn.commit()
    conn.close()

    print(f"✅ Rafraîchissement terminé — {added} nouvelle(s) offre(s)")


if __name__ == "__main__":
    main()
