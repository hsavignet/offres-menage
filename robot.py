import json
import sqlite3
from datetime import datetime
import requests

# === SEAO / Données Québec (CKAN) ===
DATASET_ID = "d23b2e02-085d-43e5-9e6e-e1d558ebfdd5"
CKAN_PACKAGE_SHOW = "https://www.donneesquebec.ca/recherche/api/3/action/package_show"

# Mots-clés pour contrats d’entretien ménager
KEYWORDS = [
    "entretien", "ménage", "menage", "nettoyage", "conciergerie",
    "janitorial", "lavage", "désinfection", "desinfection", "sanitize", "sanitation"
]

DB = "offres.db"


# =====================================================
# DATABASE
# =====================================================
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


def offre_existe(lien):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT 1 FROM offres WHERE lien = ?", (lien,))
    existe = c.fetchone() is not None
    conn.close()
    return existe


def ajouter_offre(titre, lien):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO offres (titre, lien, date_pub) VALUES (?, ?, ?)",
        (titre, lien, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


# =====================================================
# SEAO
# =====================================================
def get_latest_seao_weekly_url():
    r = requests.get(CKAN_PACKAGE_SHOW, params={"id": DATASET_ID}, timeout=30)
    r.raise_for_status()
    data = r.json()

    resources = data["result"].get("resources", [])

    hebdo = []
    for res in resources:
        name = (res.get("name") or "").lower()
        fmt = (res.get("format") or "").lower()
        url = res.get("url") or ""
        last_mod = res.get("last_modified") or res.get("metadata_modified") or res.get("created") or ""
        if fmt == "json" and "hebdo_" in name and url:
            hebdo.append((last_mod, name, url))

    hebdo.sort(key=lambda x: x[0] or "", reverse=True)
    return hebdo[0][2]


def matches_keywords(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in KEYWORDS)


def extract_contracts(obj):
    releases = obj.get("releases", []) if isinstance(obj, dict) else obj

    items = []
    for rel in releases:
        tender = rel.get("tender", {})
        title = tender.get("title") or rel.get("title") or ""
        desc = tender.get("description") or rel.get("description") or ""

        url = (
            tender.get("url")
            or rel.get("links", {}).get("html")
            or ""
        )

        if not title or not url:
            continue

        if not matches_keywords(title + " " + desc):
            continue

        clean = " ".join(title.split())
        if len(clean) > 100:
            clean = clean[:97] + "..."

        items.append((clean, url))

    return items


# =====================================================
# MAIN
# =====================================================
def main():
    print("🔎 SEAO — récupération du dernier fichier hebdo")
    init_db()

    weekly_url = get_latest_seao_weekly_url()
    r = requests.get(weekly_url, timeout=120)
    r.raise_for_status()

    data = r.json()
    contracts = extract_contracts(data)

    print(f"📦 Contrats trouvés : {len(contracts)}")

    new = 0
    for titre, lien in contracts:
        if not offre_existe(lien):
            ajouter_offre(titre, lien)
            new += 1
            print("🆕", titre)

    print(f"✅ Terminé — {new} nouvelle(s) offre(s)")


if __name__ == "__main__":
    main()
