import sqlite3
import os
from datetime import datetime
from flask import Flask, request, redirect, render_template_string
import stripe

# ================= CONFIG =================
DB = "offres.db"
app = Flask(__name__)

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
    raise RuntimeError("Stripe keys missing in environment variables")

stripe.api_key = STRIPE_SECRET_KEY

# ================= DB =================
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            email TEXT PRIMARY KEY,
            status TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def set_subscriber(email):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        INSERT INTO subscribers (email, status, updated_at)
        VALUES (?, 'active', ?)
        ON CONFLICT(email) DO UPDATE SET
        status='active',
        updated_at=excluded.updated_at
    """, (email, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def is_active(email):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT status FROM subscribers WHERE email=?", (email,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == "active"

# ================= TEMPLATES =================
TEMPLATE_LANDING = """
<!doctype html>
<html>
<head>
<title>Contrats d’entretien ménager</title>
<style>
body{margin:0;font-family:Arial;background:#111827;color:white;padding:80px}
.btn{background:white;color:#111827;padding:14px 26px;border-radius:8px;text-decoration:none;font-weight:bold}
</style>
</head>
<body>
<h1>Veille de contrats d’entretien ménager</h1>
<p>Appels d’offres publics regroupés pour les entreprises de nettoyage.</p>
<a class="btn" href="/pricing">Accéder aux opportunités</a>
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
    email = request.form["email"].strip().lower()

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{
            "price": STRIPE_PRICE_ID,
            "quantity": 1
        }],
        customer_email=email,
        success_url=request.host_url + "success",
        cancel_url=request.host_url + "pricing",
    )

    return redirect(session.url, code=303)

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
        checked=checked,
        allowed=allowed
    )

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        event = stripe.Webhook.construct_event(
            request.data,
            request.headers.get("Stripe-Signature"),
            STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        return "Invalid webhook", 400

    if event["type"] == "checkout.session.completed":
        email = event["data"]["object"]["customer_email"]
        if email:
            set_subscriber(email.lower())

    return "ok", 200

# ================= START =================
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
