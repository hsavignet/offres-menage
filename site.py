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

ADMIN_EMAIL = "hsavignet@gmail.com"

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
            lien TEXT UNIQUE,
            source TEXT,
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
        demo = [
            ("Entretien ménager – École primaire", "https://www.seao.ca", "SEAO", now),
            ("Nettoyage centre sportif municipal", "https://www.seao.ca", "SEAO", now),
            ("Contrat de conciergerie – Hôpital", "https://www.seao.ca", "SEAO", now),
            ("Entretien immeuble administratif", "https://www.seao.ca", "SEAO", now),
            ("Services de nettoyage – Université", "https://www.seao.ca", "SEAO", now),
        ]

        c.executemany("""
            INSERT OR IGNORE INTO offres (titre, lien, source, date_pub)
            VALUES (?, ?, ?, ?)
        """, demo)

    conn.commit()
    conn.close()

init_db()
seed_if_empty()

# =====================================================
# LOGIQUE
# =====================================================
def is_admin(email):
    return email.lower() == ADMIN_EMAIL

def is_active(email):
    return True


def get_offres(q=None, source=None):
    conn = get_db()
    c = conn.cursor()

    sql = """
        SELECT titre, lien, source, date_pub
        FROM offres
        WHERE 1=1
    """
    params = []

    if q:
        sql += " AND lower(titre) LIKE ?"
        params.append(f"%{q.lower()}%")

    if source:
        sql += " AND source = ?"
        params.append(source)

    sql += " ORDER BY date_pub DESC"

    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return rows

# =====================================================
# UI
# =====================================================
BASE_STYLE = """
<style>
body{margin:0;font-family:Arial;background:#f3f4f6;color:#111827}
a{text-decoration:none}
.container{max-width:1100px;margin:auto;padding:80px 24px}
.btn{padding:12px 24px;border-radius:8px;font-weight:700;display:inline-block}
.btn-dark{background:#111827;color:white}
.btn-light{background:white;color:#111827;border:1px solid #e5e7eb}
.card{background:white;border-radius:14px;padding:28px;margin-bottom:20px;
box-shadow:0 12px 30px rgba(0,0,0,.08)}
input,select{padding:12px;border-radius:8px;border:1px solid #d1d5db}
header{
background:
linear-gradient(rgba(17,24,39,.75),rgba(17,24,39,.75)),
url("https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=1600&q=80");
background-size:cover;color:white
}
header .container{padding:140px 24px}
</style>
"""

HOME = """
<!doctype html>
<html><head><title>Contrats entretien ménager</title>
""" + BASE_STYLE + """
</head>
<body>
<header>
  <div class="container">
    <h1>Contrats d’entretien ménager</h1>
    <p>
      Tous les appels d’offres en nettoyage au Québec,
      regroupés automatiquement.
    </p><br>
    <a class="btn btn-dark" href="/pricing">S’abonner</a>
    <a class="btn btn-light" href="/login">Déjà abonné</a>
  </div>
</header>
</body></html>
"""

LOGIN = """
<!doctype html>
<html><head><title>Accès abonné</title>
""" + BASE_STYLE + """
</head>
<body>
<div class="container">
<div class="card" style="max-width:420px;margin:auto">
<h2>Accès abonné</h2>
<form method="get" action="/app">
<input name="email" placeholder="Email d’abonnement" required style="width:100%"><br><br>
<button class="btn btn-dark" style="width:100%">Accéder</button>
</form>
</div>
</div>
</body></html>
"""

PRICING = """
<!doctype html>
<html><head><title>Abonnement</title>
""" + BASE_STYLE + """
</head>
<body>
<div class="container">
<div class="card" style="max-width:420px;margin:auto;text-align:center">
<h2>Abonnement Premium</h2>
<p>39 $ / mois</p>
<form method="post" action="/create-checkout-session">
<input name="email" placeholder="Email professionnel" required><br><br>
<button class="btn btn-dark" style="width:100%">Continuer</button>
</form>
</div>
</div>
</body></html>
"""

APP = """
<!doctype html>
<html><head><title>Contrats</title>
""" + BASE_STYLE + """
</head>
<body>
<div class="container">

<h2>Contrats disponibles</h2>

<form method="get" style="margin-bottom:30px">
<input type="hidden" name="email" value="{{email}}">
<input name="q" value="{{q}}" placeholder="Recherche (école, hôpital…)" style="width:50%">
<select name="source">
<option value="">Toutes les sources</option>
<option value="SEAO" {% if source=="SEAO" %}selected{% endif %}>SEAO</option>
</select>
<button class="btn btn-dark">Rechercher</button>
</form>

{% if admin %}
<a class="btn btn-dark" href="/refresh?email={{email}}">🔄 Rafraîchir les offres</a>
<br><br>
{% endif %}

{% for t,l,s,d in offres %}
<div class="card">
<strong>{{t}}</strong><br>
<small>Source : <strong>{{s}}</strong> — {{d[:10]}}</small><br><br>
<a class="btn btn-light" href="{{l}}" target="_blank">Voir l’appel d’offres</a>
</div>
{% else %}
<p>Aucune offre trouvée.</p>
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

@app.route("/login")
def login():
    return render_template_string(LOGIN)

@app.route("/pricing")
def pricing():
    return render_template_string(PRICING)

@app.route("/create-checkout-session", methods=["POST"])
def checkout():
    email = request.form["email"]
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        customer_email=email,
        success_url=request.host_url + "app?email=" + email,
        cancel_url=request.host_url + "pricing",
    )
    return redirect(session.url, 303)

@app.route("/app")
def app_page():
    email = request.args.get("email","")
    if not is_active(email):
        return redirect("/pricing")

    q = request.args.get("q","")
    source = request.args.get("source","")

    return render_template_string(
        APP,
        offres=get_offres(q, source),
        email=email,
        admin=is_admin(email),
        q=q,
        source=source
    )

@app.route("/refresh")
def refresh():
    email = request.args.get("email","")
    if not is_admin(email):
        return redirect("/pricing")

    from robot import main
    main()
    return redirect("/app?email=" + email)

@app.route("/webhook", methods=["POST"])
def webhook():
    event = stripe.Webhook.construct_event(
        request.data,
        request.headers.get("Stripe-Signature"),
        STRIPE_WEBHOOK_SECRET
    )
    if event["type"] == "checkout.session.completed":
        email = event["data"]["object"]["customer_email"]
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO subscribers VALUES (?,?,?)
        """, (email, "active", datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
    return "ok", 200

# =====================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
