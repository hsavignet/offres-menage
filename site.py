import sqlite3
import subprocess
from datetime import datetime
from flask import Flask, request, redirect, url_for, render_template_string
import stripe

DB = "offres.db"
app = Flask(__name__)

# ==== STRIPE (MET TES VALEURS) ====
STRIPE_SECRET_KEY = "STRIPE_SECRET_KEY"
STRIPE_PRICE_ID = "price_1SsD4aD9VcM8553iREADnsVv"

# IMPORTANT: webhook secret (tu vas le mettre après avec Stripe CLI)
STRIPE_WEBHOOK_SECRET = "STRIPE_WEBHOOK_SECRET"

stripe.api_key = STRIPE_SECRET_KEY


TEMPLATE_HOME = """
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Contrats — Entretien ménager</title>
  <style>
    body{font-family:system-ui,Arial;margin:0;background:#f6f7fb;color:#111827}
    .wrap{max-width:980px;margin:auto;padding:18px}
    .top{display:flex;justify-content:space-between;align-items:center;gap:12px;
         padding:14px 0 10px;border-bottom:1px solid #e6e8ef;margin-bottom:16px}
    h1{margin:0;font-size:18px}
    .sub{color:#6b7280;margin:0 0 14px 0}
    .btn{padding:10px 14px;border-radius:12px;border:1px solid #e6e8ef;
         background:#fff;cursor:pointer;font-weight:800;text-decoration:none;display:inline-block}
    .btn-primary{border:none;color:#fff;background:linear-gradient(180deg,#2563eb,#1d4ed8)}
    .filters{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
    input,select{padding:10px 12px;border-radius:12px;border:1px solid #e6e8ef;background:#fff}
    .grid{display:grid;grid-template-columns:1fr;gap:12px}
    .card{background:#fff;border:1px solid #e6e8ef;border-radius:16px;padding:14px;
          box-shadow:0 10px 26px rgba(17,24,39,0.06)}
    .row{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
    .title{font-weight:900;margin-bottom:8px}
    .meta{color:#6b7280;font-size:13px}
    .pill{padding:4px 8px;border-radius:999px;border:1px solid #e6e8ef;background:#f9fafb;font-size:12px;color:#374151}
    .right{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <h1>🧾 Contrats — Entretien ménager</h1>
      <div class="right">
        <a class="btn" href="/pricing">💳 Pricing</a>
        <a class="btn btn-primary" href="/premium">🔒 Premium</a>
        <form action="/update" method="post" style="margin:0;">
          <button class="btn" type="submit">🔄 Actualiser</button>
        </form>
      </div>
    </div>

    <p class="sub">
      Filtre par mots-clés + période.
      <span class="pill">Résultats: <b>{{ count }}</b></span>
    </p>

    <form class="filters" method="get" action="/">
      <input name="q" value="{{ q }}" placeholder="mots-clés (ex: nettoyage école)" />

      <select name="mode">
        <option value="all" {% if mode == "all" %}selected{% endif %}>TOUS les mots</option>
        <option value="any" {% if mode == "any" %}selected{% endif %}>AU MOINS UN</option>
      </select>

      <select name="days">
        {% for d in day_list %}
          <option value="{{ d }}" {% if d == days %}selected{% endif %}>{{ d }} jours</option>
        {% endfor %}
      </select>

      <select name="limit">
        {% for l in limit_list %}
          <option value="{{ l }}" {% if l == limit %}selected{% endif %}>{{ l }}</option>
        {% endfor %}
      </select>

      <button class="btn" type="submit">🔎 Filtrer</button>
      <a class="btn" href="/">🧼 Reset</a>
    </form>

    <div class="grid">
      {% for titre, lien, date_ajout in items %}
        <div class="card">
          <div class="row">
            <div>
              <div class="title">{{ clean_title(titre) }}</div>
              <div class="meta">🕒 {{ format_date(date_ajout) }}</div>
            </div>
            <a class="btn btn-primary" href="{{ lien }}" target="_blank">Voir le contrat →</a>
          </div>
        </div>
      {% endfor %}

      {% if items|length == 0 %}
        <div class="card">
          <div class="title">Aucun résultat</div>
          <div class="meta">Essaie d’autres mots-clés ou augmente “jours”.</div>
        </div>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""


TEMPLATE_PRICING = """
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pricing</title>
  <style>
    body{font-family:system-ui,Arial;margin:0;background:#f6f7fb;color:#111827}
    .wrap{max-width:780px;margin:auto;padding:22px}
    .card{background:#fff;border:1px solid #e6e8ef;border-radius:16px;padding:18px;
          box-shadow:0 10px 26px rgba(17,24,39,0.06)}
    .btn{padding:10px 14px;border-radius:12px;border:1px solid #e6e8ef;background:#fff;cursor:pointer;font-weight:800}
    .btn-primary{border:none;color:#fff;background:linear-gradient(180deg,#2563eb,#1d4ed8)}
    input{padding:10px 12px;border-radius:12px;border:1px solid #e6e8ef;background:#fff;width:min(420px,100%)}
    .muted{color:#6b7280}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>💳 Premium (abonnement)</h1>
    <p class="muted">Accès aux nouvelles opportunités + alertes (bientôt).</p>

    <div class="card">
      <h2 style="margin-top:0;">Plan Premium</h2>
      <ul>
        <li>Accès Premium</li>
        <li>Filtres avancés</li>
        <li>Alertes (prochaine étape)</li>
      </ul>

      <form action="/create-checkout-session" method="post">
        <p class="muted">Email (celui de ton compte Premium) :</p>
        <input name="email" placeholder="ex: toi@entreprise.com" required />
        <div style="height:12px;"></div>
        <button class="btn btn-primary" type="submit">S’abonner →</button>
        <a class="btn" href="/" style="text-decoration:none;display:inline-block;margin-left:8px;">Retour</a>
      </form>
    </div>
  </div>
</body>
</html>
"""


TEMPLATE_PREMIUM = """
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Premium</title>
  <style>
    body{font-family:system-ui,Arial;margin:0;background:#f6f7fb;color:#111827}
    .wrap{max-width:780px;margin:auto;padding:22px}
    .card{background:#fff;border:1px solid #e6e8ef;border-radius:16px;padding:18px;
          box-shadow:0 10px 26px rgba(17,24,39,0.06)}
    .btn{padding:10px 14px;border-radius:12px;border:1px solid #e6e8ef;background:#fff;cursor:pointer;font-weight:800;text-decoration:none;display:inline-block}
    .btn-primary{border:none;color:#fff;background:linear-gradient(180deg,#2563eb,#1d4ed8)}
    input{padding:10px 12px;border-radius:12px;border:1px solid #e6e8ef;background:#fff;width:min(420px,100%)}
    .muted{color:#6b7280}
    .ok{color:#0f766e;font-weight:900}
    .bad{color:#b91c1c;font-weight:900}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>🔒 Premium</h1>

    <div class="card">
      <p class="muted">Entre ton email Premium pour vérifier l’accès :</p>
      <form method="get" action="/premium">
        <input name="email" placeholder="toi@entreprise.com" value="{{ email }}" required />
        <div style="height:12px;"></div>
        <button class="btn btn-primary" type="submit">Vérifier</button>
        <a class="btn" href="/pricing">S’abonner</a>
        <a class="btn" href="/">Retour</a>
      </form>

      <div style="height:14px;"></div>

      {% if checked %}
        {% if allowed %}
          <div class="ok">✅ Accès autorisé (abonnement actif)</div>
          <p class="muted">Ici tu mettras les features Premium (ex: nouvelles opportunités, alertes…).</p>
        {% else %}
          <div class="bad">❌ Pas d’accès (pas d’abonnement actif trouvé)</div>
          <p class="muted">Si tu viens de payer, attends le webhook (test) ou vérifie l’email utilisé.</p>
        {% endif %}
      {% endif %}
    </div>
  </div>
</body>
</html>
"""


def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # table contrats (déjà)
    c.execute("""
        CREATE TABLE IF NOT EXISTS offres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT,
            lien TEXT UNIQUE,
            date_ajout TEXT
        )
    """)
    # table abonnés
    c.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            email TEXT PRIMARY KEY,
            status TEXT,
            customer_id TEXT,
            subscription_id TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def set_subscriber(email, status, customer_id=None, subscription_id=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        INSERT INTO subscribers (email, status, customer_id, subscription_id, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
          status=excluded.status,
          customer_id=excluded.customer_id,
          subscription_id=excluded.subscription_id,
          updated_at=excluded.updated_at
    """, (email.lower().strip(), status, customer_id, subscription_id, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()


def is_active(email):
    if not email:
        return False
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT status FROM subscribers WHERE email=?", (email.lower().strip(),))
    row = c.fetchone()
    conn.close()
    return (row is not None) and (row[0] == "active")


def format_date(date_ajout):
    try:
        d = datetime.fromisoformat(date_ajout)
        return d.strftime("%d %b %Y")
    except Exception:
        return (date_ajout or "")[:10]


def clean_title(titre):
    t = (titre or "").replace("\n", " ").replace("  ", " ").strip()
    if len(t) > 90:
        t = t[:87] + "..."
    return t


def get_items(q, days, limit, mode):
    try:
        days = int(days)
    except Exception:
        days = 30
    try:
        limit = int(limit)
    except Exception:
        limit = 200

    days = max(1, min(days, 365))
    limit = max(10, min(limit, 500))

    words = [w.strip().lower() for w in (q or "").split() if w.strip()]

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    where = ["date(date_ajout) >= date('now', '-' || ? || ' day')"]
    params = [str(days)]

    if words:
        if mode == "any":
            where.append("(" + " OR ".join(["lower(titre) LIKE ?"] * len(words)) + ")")
            params.extend(["%" + w + "%" for w in words])
        else:
            for w in words:
                where.append("lower(titre) LIKE ?")
                params.append("%" + w + "%")

    sql = """
        SELECT titre, lien, date_ajout
        FROM offres
        WHERE {where}
        ORDER BY id DESC
        LIMIT ?
    """.format(where=" AND ".join(where))

    c.execute(sql, (*params, limit))
    rows = c.fetchall()
    conn.close()
    return rows, days, limit


from flask import redirect

@app.route("/")
def home():
    return redirect("/landing")

    init_db()
    q = request.args.get("q", "")
    days = request.args.get("days", "30")
    limit = request.args.get("limit", "200")
    mode = request.args.get("mode", "all")

    items, days_i, limit_i = get_items(q, days, limit, mode)

    return render_template_string(
        TEMPLATE_HOME,
        items=items,
        q=q.replace("<", "").replace(">", "").replace('"', ""),
        mode=mode,
        days=days_i,
        limit=limit_i,
        count=len(items),
        day_list=[1, 3, 7, 14, 30, 60, 90, 180, 365],
        limit_list=[50, 100, 200, 300, 500],
        clean_title=clean_title,
        format_date=format_date,
    )


@app.route("/update", methods=["POST"])
def update():
    subprocess.run(["python", "robot.py"])
    return redirect(url_for("home"))


@app.route("/pricing")
def pricing():
    init_db()
    return render_template_string(TEMPLATE_PRICING)


@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    init_db()
    email = (request.form.get("email") or "").strip().lower()

    # Crée une session Checkout en mode abonnement (subscription)
    # Stripe: mode='subscription' + line_items avec price=PRICE_ID :contentReference[oaicite:2]{index=2}
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        customer_email=email,
        success_url="http://127.0.0.1:5000/success",
        cancel_url="http://127.0.0.1:5000/cancel",
    )
    return redirect(session.url, code=303)


@app.route("/success")
def success():
    return '<p>✅ Paiement lancé/terminé. Retourne sur <a href="/premium">/premium</a> et mets le même email.</p>'


@app.route("/cancel")
def cancel():
    return '<p>❌ Paiement annulé. Retour sur <a href="/pricing">/pricing</a>.</p>'


@app.route("/premium")
def premium():
    init_db()
    email = (request.args.get("email") or "").strip().lower()
    checked = bool(email)
    allowed = is_active(email) if checked else False

    return render_template_string(
        TEMPLATE_PREMIUM,
        email=email,
        checked=checked,
        allowed=allowed,
    )


@app.route("/webhook", methods=["POST"])
def webhook():
    # Webhooks Stripe: on vérifie la signature avec le secret whsec :contentReference[oaicite:3]{index=3}
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        return f"Webhook error: {str(e)}", 400

    # Event clé: checkout.session.completed (Checkout réussi) :contentReference[oaicite:4]{index=4}
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = (session.get("customer_email") or "").strip().lower()
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        if email:
            # On marque actif. (Pour MVP test c’est OK. En prod on vérifiera status subscription.)
            set_subscriber(email, "active", customer_id=customer_id, subscription_id=subscription_id)

    # Optionnel: si abonnement annulé, Stripe envoie customer.subscription.deleted (et autres) :contentReference[oaicite:5]{index=5}
    if event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        customer_id = sub.get("customer")
        # MVP: on ne retrouve pas l'email ici facilement sans API call -> on laisse pour plus tard.

    return "ok", 200

@app.route("/landing")
def landing():
    return render_template_string("""
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Contrats d’entretien ménager</title>
  <style>
    body{font-family:system-ui,Arial;margin:0;background:#f6f7fb;color:#111827}
    .wrap{max-width:980px;margin:auto;padding:24px}
    .hero{padding:60px 0;text-align:center}
    h1{font-size:36px;margin-bottom:16px}
    h2{font-size:24px;margin:48px 0 16px}
    p{color:#374151;font-size:18px}
    .btn{display:inline-block;padding:14px 22px;border-radius:14px;
         background:linear-gradient(180deg,#2563eb,#1d4ed8);
         color:#fff;text-decoration:none;font-weight:800}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
          gap:20px;margin-top:24px}
    .card{background:#fff;border-radius:16px;padding:20px;
          box-shadow:0 10px 26px rgba(17,24,39,0.08)}
    .price{font-size:32px;font-weight:900;margin:16px 0}
    .center{text-align:center}
    .muted{color:#6b7280}
  </style>
</head>
<body>

<div class="wrap">

  <!-- HERO -->
  <section class="hero">
    <h1>Trouvez des contrats d’entretien ménager<br>avant vos concurrents</h1>
    <p>Les appels d’offres publics regroupés en un seul endroit.<br>
       Pensé pour les entreprises de ménage.</p>
    <br>
    <a class="btn" href="/pricing">🔒 Voir les opportunités</a>
  </section>

  <!-- PROBLÈME -->
  <section>
    <h2>Vous perdez des contrats sans le savoir</h2>
    <div class="grid">
      <div class="card">📄 Les appels d’offres sont dispersés sur plusieurs sites</div>
      <div class="card">⏱️ Vous arrivez trop tard sur les bonnes opportunités</div>
      <div class="card">❌ Vous perdez du temps à chercher au lieu de soumissionner</div>
    </div>
  </section>

  <!-- SOLUTION -->
  <section>
    <h2>Une veille automatique pour les entreprises de ménage</h2>
    <div class="grid">
      <div class="card">🧾 Tous les contrats regroupés</div>
      <div class="card">🔎 Filtres par mots-clés et période</div>
      <div class="card">⚡ Accès rapide aux nouvelles opportunités</div>
    </div>
  </section>

  <!-- COMMENT ÇA MARCHE -->
  <section>
    <h2>Comment ça fonctionne</h2>
    <div class="grid">
      <div class="card">1️⃣ Nous surveillons les sources officielles</div>
      <div class="card">2️⃣ Nous détectons les contrats pertinents</div>
      <div class="card">3️⃣ Vous accédez aux opportunités immédiatement</div>
    </div>
  </section>

  <!-- PRIX -->
  <section class="center">
    <h2>Accès Premium</h2>
    <div class="card" style="max-width:360px;margin:24px auto;">
      <p>Accès aux opportunités<br>Filtres avancés<br>Données mises à jour</p>
      <div class="price">29 $ / mois</div>
      <a class="btn" href="/pricing">S’abonner</a>
    </div>
    <p class="muted">Sans engagement • Annulable à tout moment</p>
  </section>

  <!-- CTA FINAL -->
  <section class="hero">
    <h2>Ne ratez plus un contrat rentable</h2>
    <a class="btn" href="/pricing">🔒 Accéder aux opportunités</a>
  </section>

</div>

</body>
</html>
""")


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


