import sqlite3
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "offres.db")

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    now = datetime.utcnow().isoformat()
    c.execute(
        "INSERT OR IGNORE INTO offres (titre, lien, date_pub) VALUES (?, ?, ?)",
        ("Robot – nouveau contrat détecté", "https://example.com/robot", now)
    )

    conn.commit()
    conn.close()
    print("🤖 Robot exécuté")

if __name__ == "__main__":
    main()
