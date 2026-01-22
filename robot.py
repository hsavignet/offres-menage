import json
import sqlite3
import hashlib
from datetime import datetime
import requests

# === SEAO / Données Québec (CKAN) ===
DATASET_ID = "d23b2e02-085d-43e5-9e6e-e1d558ebfdd5"  # SEAO sur Données Québec
CKAN_PACKAGE_SHOW = "https://www.donneesquebec.ca/recherche/api/3/action/package_show"

# Mots-clés pour contrats d’entretien ménager (tu peux en ajouter)
KEYWORDS = [
    "entretien", "ménage", "menage", "nettoyage", "conciergerie",
    "janitorial", "lavage", "désinfection", "desinfection", "sanitize", "sanitation"
]

DB = "offres.db"


def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS offres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT,
            lien TEXT UNIQUE,
            date_ajout TEXT
        )
    """)
    conn.commit()
    conn.close()


def stable_id(title: str, url: str) -> str:
    raw = (title.strip() + "|" + url.strip()).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
        "INSERT OR IGNORE INTO offres (titre, lien, date_ajout) VALUES (?, ?, ?)",
        (titre, lien, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()


def get_latest_seao_weekly_url():
    # 1) Lire les ressources via l’API CKAN (package_show)
    r = requests.get(CKAN_PACKAGE_SHOW, params={"id": DATASET_ID}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError("CKAN package_show a échoué")

    resources = data["result"].get("resources", [])

    # 2) Garder juste les fichiers hebdo JSON
    hebdo = []
    for res in resources:
        name = (res.get("name") or "").lower()
        fmt = (res.get("format") or "").lower()
        url = res.get("url") or ""
        last_mod = res.get("last_modified") or res.get("metadata_modified") or res.get("created") or ""
        if fmt == "json" and "hebdo_" in name and url:
            hebdo.append((last_mod, name, url))

    if not hebdo:
        raise RuntimeError("Aucun fichier hebdo JSON trouvé dans les ressources SEAO")

    # 3) Prendre le plus récent (tri sur last_modified/metadata_modified/created)
    hebdo.sort(key=lambda x: x[0] or "", reverse=True)
    return hebdo[0][2], hebdo[0][1], hebdo[0][0]


def matches_keywords(text: str) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in KEYWORDS)


def extract_contracts(obj):
    """
    Le JSON SEAO est inspiré d’Open Contracting (OCDS).
    On essaye d’être robuste : on cherche une liste de 'releases' ou on traite directement une liste.
    """
    if isinstance(obj, dict) and isinstance(obj.get("releases"), list):
        releases = obj["releases"]
    elif isinstance(obj, list):
        releases = obj
    else:
        releases = []

    items = []
    for rel in releases:
        if not isinstance(rel, dict):
            continue

        tender = rel.get("tender", {}) if isinstance(rel.get("tender"), dict) else {}
        title = tender.get("title") or rel.get("title") or ""
        desc = tender.get("description") or rel.get("description") or ""

        # Lien: on tente plusieurs champs possibles
        url = (
            tender.get("url")
            or (rel.get("links", {}) or {}).get("self")
            or (rel.get("links", {}) or {}).get("html")
            or ""
        )

        # Si pas d’url, parfois il y a des documents avec url
        if not url:
            docs = tender.get("documents") if isinstance(tender.get("documents"), list) else []
            if docs:
                d0 = docs[0] if isinstance(docs[0], dict) else {}
                url = d0.get("url") or ""

        # Si on a ni titre ni url => skip
        if not title or not url:
            continue

        # Filtre mots-clés (sur titre + description)
        if not matches_keywords(title + " " + desc):
            continue

        # Nettoyage titre (court)
        clean = " ".join(title.split())
        if len(clean) > 100:
            clean = clean[:97] + "..."

        items.append((clean, url))

    return items


def main():
    print("🔎 SEAO — recherche du dernier fichier hebdo…")
    init_db()

    weekly_url, weekly_name, weekly_lastmod = get_latest_seao_weekly_url()
    print(f"✅ Fichier: {weekly_name} ({weekly_lastmod})")
    print("⬇️ Téléchargement… (ça peut prendre un peu de temps)")

    r = requests.get(weekly_url, timeout=120)
    r.raise_for_status()

    print("🧠 Lecture du JSON…")
    data = r.json()

    contracts = extract_contracts(data)
    print(f"📦 Contrats trouvés (après filtre mots-clés): {len(contracts)}")

    nouvelles = 0
    for titre, lien in contracts:
        if not offre_existe(lien):
            ajouter_offre(titre, lien)
            nouvelles += 1
            print("🆕 NOUVEAU CONTRAT :", titre)

    print(f"✅ Terminé — {nouvelles} nouveau(x) contrat(s)")


if __name__ == "__main__":
    main()
