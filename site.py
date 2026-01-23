import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, redirect, render_template_string, abort
import stripe
from robot import main as run_robot


# =====================================================
# CONFIG
# =====================================================
app = Flask(__name__)
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "offres.db")


stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

if not stripe.api_key or not STRIPE_PRICE_ID:
    raise RuntimeError("Stripe keys not configured in environment variables")

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

def set_subscriber(email, status):
    conn = sqlite3.connect(DB)
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
    if not email:
        return False

    # 🔑 ACCÈS ADMIN (TON EMAIL)
    if email.lower() in [
        "hsavignet@gmail.com",   # <-- mets TON email ici
    ]:
        return True

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT status FROM subscribers WHERE email=?", (email.lower(),))
    row = c.fetchone()
    conn.close()
    return row and row[0] == "active"


def search_offres(q, days):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    sql = """
        SELECT titre, lien, date_pub
        FROM offres
        WHERE 1=1
    """
    params = []

    if q:
        sql += " AND lower(titre) LIKE ?"
        params.append(f"%{q.lower()}%")

    sql += " ORDER BY date_pub DESC LIMIT 200"

    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    return rows


# =====================================================
# TEMPLATES
# =====================================================
BASE_STYLE = """
<style>
body{
  margin:0;
  font-family:Arial, sans-serif;
  background:#f3f4f6;
  color:#111827;
}
a{text-decoration:none;color:inherit}
.container{max-width:1200px;margin:auto;padding:64px 24px}
.btn{
  padding:14px 26px;
  border-radius:8px;
  font-weight:700;
  display:inline-block;
}
.btn-dark{background:#111827;color:white}
.btn-light{background:white;color:#111827;border:1px solid #e5e7eb}
.card{
  background:white;
  border-radius:16px;
  padding:32px;
  box-shadow:0 20px 40px rgba(0,0,0,.08);
}
.grid{display:grid;gap:24px}
.grid-3{grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
input,select{
  padding:12px;
  border-radius:8px;
  border:1px solid #d1d5db;
  width:100%;
}
header{
  background:
    linear-gradient(rgba(17,24,39,.75),rgba(17,24,39,.75)),
    url("https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=1600&q=80");
  background-size:cover;
  color:white;
}
header .container{padding:120px 24px}
h1{font-size:42px;margin-bottom:16px}
h2{font-size:28px;margin-bottom:16px}
p{color:#374151;font-size:18px}
small{color:#6b7280}
</style>
"""

LANDING = """
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Veille contrats entretien ménager</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + BASE_STYLE + """
</head>
<body>

<header>
  <div class="container">
    <h1>Veille de contrats d’entretien ménager</h1>
    <p>Les appels d’offres publics regroupés pour les entreprises de nettoyage.</p>
    <br>
    <a class="btn btn-dark" href="/pricing">S’abonner</a>
    <a class="btn btn-light" href="/login">Déjà client</a>
  </div>
</header>

<div class="container">
  <h2>Aperçu de la plateforme</h2>
  <div class="grid grid-3">
    <div class="card">Appels d’offres centralisés</div>
    <div class="card">Recherche simple par mots-clés</div>
    <div class="card">Mises à jour continues</div>
  </div>
</div>

</body>
</html>
"""

PRICING = """
<!doctype html>
<html>
<head>
<title>Abonnement</title>
""" + BASE_STYLE + """
</head>
<body>
<div class="container">
  <div class="card" style="max-width:480px;margin:auto">
    <h2>Abonnement Premium</h2>
    <p>29 $ / mois</p>
    <form method="post" action="/create-checkout-session">
      <input name="email" placeholder="Email professionnel" required>
      <br><br>
      <button class="btn btn-dark" style="width:100%">Continuer vers le paiement</button>
    </form>
  </div>
</div>
</body>
</html>
"""

LOGIN = """
<!doctype html>
<html>
<head><title>Accès client</title>""" + BASE_STYLE + """</head>
<body>
<div class="container">
  <div class="card" style="max-width:480px;margin:auto">
    <h2>Accès client</h2>
    <form method="get" action="/app">
      <input name="email" placeholder="Email utilisé lors du paiement" required>
      <br><br>
      <button class="btn btn-dark" style="width:100%">Accéder</button>
    </form>
  </div>
</div>
</body>
</html>
"""

APP = """
<!doctype html>
<html>
<head><title>Contrats</title>""" + BASE_STYLE + """</head>
<body>
<div class="container">
<h2>Contrats disponibles</h2>

<form method="get">
<div class="grid" style="grid-template-columns:2fr 1fr auto">
  <input name="q" value="{{q}}" placeholder="Recherche">
  <select name="days">
    {% for d in [7,30,90,180] %}
      <option value="{{d}}" {% if d==days %}selected{% endif %}>{{d}} jours</option>
    {% endfor %}
  </select>
  <button class="btn btn-dark">Filtrer</button>
</div>
</form>

<br>

{% for t,l,d in offres %}
<div class="card" style="margin-bottom:16px">
  <strong>{{t}}</strong><br>
  <small>{{d}}</small><br><br>
  <a class="btn btn-light" href="{{l}}" target="_blank">Voir</a>
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
@app.route("/")
def landing():
    return render_template_string(LANDING)

@app.route("/pricing")
def pricing():
    return render_template_string(PRICING)

@app.route("/login")
def login():
    return render_template_string(LOGIN)

@app.route("/create-checkout-session", methods=["POST"])
def checkout():
    email = request.form["email"].strip().lower()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        customer_email=email,
        success_url=request.host_url + "login",
        cancel_url=request.host_url + "pricing",
    )
    return redirect(session.url, code=303)

@app.route("/app")
def app_page():
    email = request.args.get("email","").lower()
    if not is_active(email):
        return redirect("/login")

    q = request.args.get("q","")
    days = int(request.args.get("days",30))
    offres = search_offres(q, days)

    return render_template_string(APP, offres=offres, q=q, days=days)

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

# =====================================================
if __name__ == "__main__":
    init_db()

    # 🔥 LANCEMENT DU ROBOT SI LA DB EST VIDE
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM offres")
        count = c.fetchone()[0]
        conn.close()

        if count == 0:
            print("📦 DB vide → lancement du robot")
            run_robot()
        else:
            print(f"✅ DB déjà remplie ({count} offres)")
    except Exception as e:
        print("❌ Erreur robot :", e)

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

