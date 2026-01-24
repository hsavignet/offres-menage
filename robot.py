import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "offres.db")

def main():
    print("🚀 ROBOT LANCÉ")

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

    now = datetime.utcnow().isoformat()
    titre = "OFFRE TEST RENDER " + now
    lien = "https://example.com/test-" + now

    c.execute("""
        INSERT OR IGNORE INTO offres (titre, lien, date_pub)
        VALUES (?, ?, ?)
    """, (titre, lien, now))

    conn.commit()
    conn.close()

    print("✅ OFFRE TEST INSÉRÉE")

if __name__ == "__main__":
    main()
