import os
import json
import random
from build_caption import build_caption, clean_source

QUOTES_DB = "quotes_salaf.json"
TRACKER   = "tracker.json"

# ── 1. Charger la base de données dorar.net ──────────────────────────────────
if os.path.exists(QUOTES_DB):
    with open(QUOTES_DB, "r", encoding="utf-8") as f:
        db = json.load(f)

    # Éviter de répéter la même citation (suivi via tracker)
    if os.path.exists(TRACKER):
        with open(TRACKER, "r", encoding="utf-8") as f:
            tracker = json.load(f)
    else:
        tracker = {}

    # Clé anti-répétition : texte arabe si présent, sinon texte français
    # (les paroles tirées du livre français n'ont pas toujours de quote_ar)
    def qkey(q):
        return q.get("quote_ar") or q.get("quote", "")

    used = set(tracker.get("used_quotes", []))
    available = [q for q in db if qkey(q) not in used]

    if not available:
        # Tout a été utilisé — recommencer depuis le début
        available = db
        tracker["used_quotes"] = []

    quote_data = random.choice(available)

    # Marquer comme utilisé
    tracker.setdefault("used_quotes", []).append(qkey(quote_data))
    with open(TRACKER, "w", encoding="utf-8") as f:
        json.dump(tracker, f, ensure_ascii=False, indent=2)

    print(f"✅ Citation chargée depuis quotes_salaf.json (dorar.net)")
    print(f"   Nom        : {quote_data['name']}")
    print(f"   Génération : {quote_data.get('generation','?')} | Catégorie : {quote_data.get('category','?')}")
    print(f"   Source     : {quote_data['source']}")
    print(f"   Extrait    : {quote_data['quote'][:80]}…")

# ── 2. Base absente : arrêt net ──────────────────────────────────────────────
# Règle de rigueur : une parole du Salaf ne vient QUE de la base vérifiée
# (dorar.net / shamela.ws). On ne génère jamais de citation de mémoire : mieux
# vaut ne rien publier que publier une parole non authentifiée.
else:
    raise SystemExit(f"❌ {QUOTES_DB} introuvable — aucune citation vérifiée "
                     "disponible, publication annulée.")

# ── 3. Épurer la source (ouvrage seul) + régénérer la légende ────────────────
# On ne garde que l'ouvrage dans la source (site et chapitre retirés), pour
# l'image comme pour la légende. La caption est ensuite reconstruite avec des
# hashtags francophones variés (croissance organique).
quote_data["source"] = clean_source(quote_data.get("source", ""))
quote_data["caption"] = build_caption(quote_data)

# ── 4. Sauvegarder pour post_salaf.py ────────────────────────────────────────
with open("daily_quote.json", "w", encoding="utf-8") as f:
    json.dump(quote_data, f, ensure_ascii=False, indent=2)
