import os
import sqlite3
from datetime import datetime
from flask import Flask, request, redirect, render_template_string
import stripe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "offres.db")

app = Flask(__name__)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")


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


def is_active(email):
    if email == "hsavignet@gmail.com":
        return True
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status FROM subscribers WHERE email=?", (email,))
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


init_db()

BASE_STYLE = """
<style>
body{font-family:Arial;background:#f3f4f6;margin:0}
.container{max-width:1100px;margin:auto;padding:80px 24px}
.card{background:white;padding:24px;border-radius:14px;margin-bottom:20px}
.btn{padding:12px 22px;border-radius:8px;background:#111827;color:white;text-decoration:none;font-weight:700}
</style>
"""

HOME = """
<html><head>""" + BASE_STYLE + """</head><body>
<div class="container">
<h1>Contrats d’entretien ménager</h1>
<a class="btn" href="/pricing">S’abonner</a>
</div>
</body></html>
"""

PRICING = """
<html><head>""" + BASE_STYLE + """</head><body>
<div class="container">
<div class="card">
<h2>Abonnement</h2>
<form method="post" action="/create-checkout-session">
<input name="email" placeholder="Email" required>
<button class="btn">Payer</button>
</form>
</div>
</div>
</body></html>
"""

APP = """
<html><head>""" + BASE_STYLE + """</head><body>
<div class="container">
<h2>Contrats</h2>
<a class="btn" href="/refresh?email={{email}}">🔄 Rafraîchir</a>
<br><br>
{% for t,l,d in offres %}
<div class="card">
<strong>{{t}}</strong><br>
<a href="{{l}}" target="_blank">Voir</a>
</div>
{% endfor %}
</div>
</body></html>
"""


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
