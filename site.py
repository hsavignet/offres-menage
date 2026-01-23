import os
import sqlite3
from datetime import datetime
from flask import Flask, request, redirect, render_template_string
import stripe

# =====================================================
# CONFIG
# =====================================================
app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "offres.db")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

# =====================================================
# DATABASE
# =====================================================
def get_db():
    return sqlite3.connect(DB)

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS offres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT,
            lien TEXT,
            date_pub TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            email TEXT PRIMARY KEY,
            status TEXT,
            updated_at TEXT
        )
    """)

    conn.commit()
    conn.close()

def seed_if_empty():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM offres")
    count = c.fetchone()[0]

    if count == 0:
        now = datetime.utcnow().isoformat()
        c.executemany(
            "INSERT INTO offres (titre, lien, date_pub) VALUES (?, ?, ?)",
            [
                ("Contrat entretien école primaire", "https://example.com/contrat1", now),
                ("Nettoyage immeuble municipal", "https://example.com/contrat2", now),
                ("Entretien centre sportif", "https://example.com/contrat3", now),
            ]
        )
        print("✅ Offres de test insérées")

    conn.commit()
    conn.close()

# 👉 CES LIGNES S’EXÉCUTENT SUR RENDER
init_db()
seed_if_empty()

# =====================================================
# LOGIQUE
# =====================================================
def is_active(email):
    return email.lower() == "hsavignet@gmail.com"

def get_offres():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT titre, lien, date_pub FROM offres ORDER BY date_pub DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# =====================================================
# UI
# =====================================================
BASE_STYLE = """
<style>
body{font-family:Arial;background:#f3f4f6;margin:0}
.container{max-width:900px;margin:auto;padding:60px}
.card{background:white;padding:24px;border-radius:12px;margin-bottom:16px}
.btn{padding:10px 16px;background:#111827;color:white;border-radius:6px;text-decoration:none}
</style>
"""

APP = """
<!doctype html>
<html>
<head><title>Contrats</title>""" + BASE_STYLE + """</head>
<body>
<div class="container">
<h2>Contrats disponibles</h2>

{% for t,l,d in offres %}
<div class="card">
  <strong>{{t}}</strong><br>
  <small>{{d}}</small><br><br>
  <a class="btn" href="{{l}}" target="_blank">Voir</a>
</div>
{% else %}
<p>Aucun résultat</p>
{% endfor %}

</div>
</body>
</html>
"""

# =====================================================
# ROUTES
# =====================================================
@app.route("/app")
def app_page():
    email = request.args.get("email","")
    if not is_active(email):
        return "Accès refusé", 403

    return render_template_string(APP, offres=get_offres())

@app.route("/debug/db")
def debug_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM offres")
    count = c.fetchone()[0]
    conn.close()
    return {"count": count}

# =====================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

