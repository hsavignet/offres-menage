import os
import sqlite3
from datetime import datetime
from flask import Flask, request, redirect, render_template_string, abort
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

    conn.commit()
    conn.close()

def set_subscriber(email, status):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO subscribers (email, status, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
        status=excluded.status,
        updated_at=excluded.updated_at
    """, (email.lower(), status, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def is_active(email):
    if email.lower() == "hsavignet@gmail.com":
        return True

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status FROM subscribers WHERE email=?", (email.lower(),))
    row = c.fetchone()
    conn.close()
    return row and row[0] == "active"

init_db()
seed_if_empty()

# =====================================================
# LOGIQUE
# =====================================================
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
body{margin:0;font-family:Arial;background:#f3f4f6;color:#111827}
.container{max-width:1200px;margin:auto;padding:80px 24px}
.btn{padding:14px 28px;border-radius:10px;font-weight:700;display:inline-block}
.btn-dark{background:#111827;color:white}
.btn-light{background:white;color:#111827;border:1px solid #e5e7eb}
.card{background:white;border-radius:16px;padding:32px;box-shadow:0 20px 40px rgba(0,0,0,.08)}
.grid{display:grid;gap:24px}
.grid-3{grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
</style>
"""

HOME = HOME = """
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Veille contrats entretien ménager</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + BASE_STYLE + """
<style>
.hero{
  background:
    linear-gradient(rgba(17,24,39,.75),rgba(17,24,39,.75)),
    url("https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=1600&q=80");
  background-size:cover;
  background-position:center;
  color:white;
}
.hero .container{padding:140px 24px}
.hero p{color:#e5e7eb;font-size:20px}
.actions{margin-top:40px;display:flex;gap:16px;flex-wrap:wrap}
</style>
</head>
<body>

<header class="hero">
  <div class="container">
    <h1>Contrats d’entretien ménager</h1>
    <p>
      Tous les appels d’offres publics réunis<br>
      pour les entreprises de nettoyage.
    </p>

    <div class="actions">
      <a class="btn btn-dark" href="/pricing">S’abonner</a>
      <a class="btn btn-light" href="/app?email=hsavignet@gmail.com">
        Déjà abonné
      </a>
    </div>
  </div>
</header>

<div class="container">
  <h2>Pourquoi utiliser la plateforme ?</h2>
  <div class="grid grid-3">
    <div class="card">📄 Appels d’offres centralisés</div>
    <div class="card">⏱️ Gain de temps énorme</div>
    <div class="card">📈 Plus d’opportunités</div>
  </div>
</div>

</body>
</html>
"""


PRICING = """
<!doctype html>
<html><head><title>Abonnement</title>""" + BASE_STYLE + """</head>
<body>
<div class="container">
<div class="card" style="max-width:420px;margin:auto">
<h2>Abonnement Premium</h2>
<p>29 $ / mois</p>
<form method="post" action="/create-checkout-session">
<input name="email" placeholder="Email professionnel" required><br><br>
<button class="btn btn-dark" style="width:100%">Continuer vers le paiement</button>
</form>
</div>
</div>
</body></html>
"""

APP = """
<!doctype html>
<html><head><title>Contrats</title>""" + BASE_STYLE + """</head>
<body>
<div class="container">
<h2>Contrats disponibles</h2>
{% for t,l,d in offres %}
<div class="card" style="margin-bottom:20px">
<strong>{{t}}</strong><br>
<small>{{d}}</small><br><br>
<a class="btn btn-light" href="{{l}}" target="_blank">Voir</a>
</div>
{% endfor %}
</div>
</body></html>
"""

# =====================================================
# ROUTES
# =====================================================
@app.route("/")
def home():
    return render_template_string(HOME)

@app.route("/pricing")
def pricing():
    return render_template_string(PRICING)

@app.route("/create-checkout-session", methods=["POST"])
def checkout():
    email = request.form["email"].lower()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        customer_email=email,
        success_url=request.host_url + "app?email=" + email,
        cancel_url=request.host_url + "pricing",
    )
    return redirect(session.url, code=303)

@app.route("/app")
def app_page():
    email = request.args.get("email","").lower()
    if not is_active(email):
        return redirect("/pricing")
    return render_template_string(APP, offres=get_offres())

@app.route("/webhook", methods=["POST"])
def webhook():
    event = stripe.Webhook.construct_event(
        request.data,
        request.headers.get("Stripe-Signature"),
        STRIPE_WEBHOOK_SECRET
    )
    if event["type"] == "checkout.session.completed":
        email = event["data"]["object"]["customer_email"]
        set_subscriber(email, "active")
    return "ok", 200

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
