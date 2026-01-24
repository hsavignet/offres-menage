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

ADMIN_EMAIL = "hsavignet@gmail.com"

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

init_db()

# =====================================================
# LOGIQUE ACCÈS
# =====================================================
def is_active(email):
    if not email:
        return False

    # 🔓 ACCÈS GRATUIT POUR TOI
    if email.lower() == ADMIN_EMAIL:
        return True

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status FROM subscribers WHERE email=?", (email.lower(),))
    row = c.fetchone()
    conn.close()
    return row and row[0] == "active"

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
a{text-decoration:none}
.container{max-width:1200px;margin:auto;padding:80px 24px}
.btn{padding:14px 28px;border-radius:10px;font-weight:700;display:inline-block}
.btn-dark{background:#111827;color:white}
.btn-light{background:white;color:#111827;border:1px solid #e5e7eb}
.card{background:white;border-radius:16px;padding:32px;margin-bottom:20px;
box-shadow:0 20px 40px rgba(0,0,0,.08)}
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
    <p>Appels d’offres B2B pour entreprises de nettoyage</p><br>

    <a class="btn btn-dark" href="/pricing">S’abonner</a>
    <a class="btn btn-light" href="/app?email=hsavignet@gmail.com">
      Déjà abonné
    </a>
  </div>
</header>

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
<p>29 $ / mois</p>
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

<a class="btn btn-dark" href="/refresh?email={{email}}">
  🔄 Rafraîchir les offres
</a>
<br><br>

{% for t,l,d in offres %}
<div class="card">
<strong>{{t}}</strong><br>
<small>{{d}}</small><br><br>
<a class="btn btn-light" href="{{l}}" target="_blank">Voir</a>
</div>
{% else %}
<p>Aucune offre pour le moment</p>
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
    return render_template_string(APP, offres=get_offres(), email=email)

@app.route("/refresh")
def refresh():
    email = request.args.get("email","")
    if not is_active(email):
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
