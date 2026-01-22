import sqlite3
import os
from datetime import datetime
from flask import Flask, request, redirect, url_for, render_template_string
import stripe

# ================= CONFIG =================
DB = "offres.db"
app = Flask(__name__)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

# ================= DB =================
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            email TEXT PRIMARY KEY,
            status TEXT,
            updated_at TEXT
        )
    """)

    conn.commit()
    conn.close()

def set_subscriber(email, status):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        INSERT INTO subscribers (email, status, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
        status=excluded.status,
        updated_at=excluded.updated_at
    """, (email.lower(), status, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def is_active(email):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT status FROM subscribers WHERE email=?", (email.lower(),))
    row = c.fetchone()
    conn.close()
    return row and row[0] == "active"

# ================= UTILS =================
def format_date(d):
    try:
        return datetime.fromisoformat(d).strftime("%d %b %Y")
    except:
        return d

def clean_title(t):
    return (t or "").strip()[:120]

# ================= PAGES =================
TEMPLATE_LANDING = """
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Contrats d’entretien ménager</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{
  margin:0;
  font-family:Arial, sans-serif;
  background:
    linear-gradient(rgba(17,24,39,.75),rgba(17,24,39,.75)),
    url("https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=1600&q=80");
  background-size:cover;
  color:white;
}
.wrap{max-width:1100px;margin:auto;padding:80px 24px}
h1{font-size:42px}
p{color:#e5e7eb;font-size:18px}
.btn{
  background:#111827;
  color:white;
  padding:14px 26px;
  border-radius:8px;
  text-decoration:none;
  font-weight:700;
}
.section{
  background:white;
  color:#111827;
  margin-top:80px;
  padding:48px;
  border-radius:20px;
}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:24px}
.card{background:#f9fafb;padding:24px;border-radius:14px}
.center{text-align:center}
.price{font-size:36px;font-weight:900}
</style>
</head>

<body>
<div class="wrap">

<h1>Veille de contrats d’entretien ménager</h1>
<p>Appels d’offres publics regroupés pour les entreprises de nettoyage.</p>
<br>
<a class="btn" href="/pricing">Accéder aux opportunités</a>

<div class="section">
<h2>Pourquoi utiliser la plateforme</h2>
<div class="grid">
<div class="card">Les appels d’offres sont dispersés</div>
<div class="card">Les meilleures opportunités disparaissent vite</div>
<div class="card">La veille manuelle coûte du temps</div>
</div>
</div>

<div class="section center">
<h2>Accès Premium</h2>
<p>Accès complet aux opportunités</p>
<div class="price">29 $ / mois</div>
<br>
<a class="btn" href="/pricing">S’abonner</a>
</div>

</div>
</body>
</html>
"""

TEMPLATE_PRICING = """
<!doctype html>
<html>
<head>
<title>Abonnement</title>
<style>
body{font-family:Arial;background:#f3f4f6;padding:40px}
.card{max-width:420px;margin:auto;background:white;padding:32px;border-radius:16px}
.btn{background:#111827;color:white;padding:12px;border-radius:8px;border:none;width:100%}
input{width:100%;padding:10px;margin:12px 0}
</style>
</head>
<body>
<div class="card">
<h2>Abonnement Premium</h2>
<p>29 $ / mois</p>
<form method="post" action="/create-checkout-session">
<input name="email" placeholder="Email professionnel" required>
<button class="btn">Continuer vers le paiement</button>
</form>
</div>
</body>
</html>
"""

TEMPLATE_PREMIUM = """
<!doctype html>
<html>
<head>
<title>Premium</title>
<style>
body{font-family:Arial;background:#f3f4f6;padding:40px}
.card{max-width:520px;margin:auto;background:white;padding:32px;border-radius:16px}
.ok{color:green;font-weight:bold}
.no{color:red;font-weight:bold}
</style>
</head>
<body>
<div class="card">
<h2>Accès Premium</h2>
<form>
<input name="email" placeholder="Email utilisé lors du paiement">
<button>Vérifier</button>
</form>

{% if checked %}
  {% if allowed %}
    <p class="ok">Accès autorisé</p>
  {% else %}
    <p class="no">Accès refusé</p>
  {% endif %}
{% endif %}
</div>
</body>
</html>
"""

# ================= ROUTES =================
@app.route("/")
def landing():
    return render_template_string(TEMPLATE_LANDING)

@app.route("/pricing")
def pricing():
    return render_template_string(TEMPLATE_PRICING)

@app.route("/create-checkout-session", methods=["POST"])
def checkout():
    try:
        email = request.form["email"]

        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            customer_email=email,
            success_url=request.host_url + "success",
            cancel_url=request.host_url + "pricing",
        )

        return redirect(session.url, code=303)

    except Exception as e:
        return f"<h1>Stripe error</h1><pre>{str(e)}</pre>", 500


@app.route("/success")
def success():
    return redirect("/premium")

@app.route("/premium")
def premium():
    email = request.args.get("email", "")
    checked = bool(email)
    allowed = is_active(email) if checked else False
    return render_template_string(
        TEMPLATE_PREMIUM,
        email=email,
        checked=checked,
        allowed=allowed
    )

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

# ================= START =================
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
