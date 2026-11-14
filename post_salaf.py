import os
import json
import time
from generate_image import generate
from ig_publish_common import make_session, renew_token_and_persist, REPO, IG_API

ACCESS_TOKEN   = os.environ["INSTAGRAM_ACCESS_TOKEN"]
USER_ID        = os.environ["INSTAGRAM_USER_ID"]
GITHUB_TOKEN   = os.environ["GITHUB_TOKEN"]
# Token utilisé pour écrire les secrets (le GITHUB_TOKEN automatique n'a pas ce
# droit) : on préfère un PAT dédié s'il est fourni, sinon on retombe dessus.
SECRETS_TOKEN  = os.environ.get("GH_PAT") or GITHUB_TOKEN
RELEASE_TAG    = "daily-images"
IMAGE_FILENAME = "temp_post.jpg"

GH_HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

GH_SECRETS_HEADERS = {
    "Authorization": f"token {SECRETS_TOKEN}",
    "Accept": "application/vnd.github+json",
}

# Timeout par défaut (connexion, lecture) pour tous les appels réseau
TIMEOUT = (10, 60)

http = make_session()

# ── 0. Renouveler le token Instagram (expire tous les 60 jours) ─────────────
ACCESS_TOKEN = renew_token_and_persist(http, ACCESS_TOKEN, GH_SECRETS_HEADERS, TIMEOUT)

# ── 1. Charger la citation du jour (produite par fetch_caption.py) ───────────
if not os.path.exists("daily_quote.json"):
    raise SystemExit("daily_quote.json introuvable — fetch_caption.py a-t-il été exécuté ?")

with open("daily_quote.json", "r", encoding="utf-8") as f:
    quote_data = json.load(f)
print("Citation chargée depuis daily_quote.json")

name    = quote_data["name"]
quote   = quote_data["quote"]
source  = quote_data["source"]
caption = quote_data.get("caption", f"« {quote} »\n\n— {name}\n📖 {source}\n\n#salaf #sunnah #islam #ilm")

print(f"   Nom    : {name}")
print(f"   Source : {source}")

# ── 2. Générer l'image ──────────────────────────────────────────────────────
image_path = generate(name=name, quote=quote, source=source, output_path=IMAGE_FILENAME,
                      generation=quote_data.get("generation", ""))

# ── 3. Héberger l'image via GitHub Releases (aucun commit, URL publique) ────
print("Upload de l'image sur GitHub Releases...")

# S'assurer que la release "daily-images" existe
rel_resp = http.get(
    f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}",
    headers=GH_HEADERS,
    timeout=TIMEOUT,
)
if rel_resp.status_code == 404:
    rel_resp = http.post(
        f"https://api.github.com/repos/{REPO}/releases",
        headers=GH_HEADERS,
        json={"tag_name": RELEASE_TAG, "name": "Daily images", "body": "Auto-generated images"},
        timeout=TIMEOUT,
    )
rel_data = rel_resp.json()
if "id" not in rel_data:
    raise SystemExit(f"Release '{RELEASE_TAG}' inaccessible (HTTP {rel_resp.status_code}) : {rel_data}")
release_id = rel_data["id"]

# Supprimer l'asset existant s'il y en a un (même nom)
assets_resp = http.get(
    f"https://api.github.com/repos/{REPO}/releases/{release_id}/assets",
    headers=GH_HEADERS,
    timeout=TIMEOUT,
)
for asset in assets_resp.json():
    if asset["name"] == IMAGE_FILENAME:
        http.delete(
            f"https://api.github.com/repos/{REPO}/releases/assets/{asset['id']}",
            headers=GH_HEADERS,
            timeout=TIMEOUT,
        )

# Uploader l'image comme asset de la release
with open(image_path, "rb") as f:
    upload_resp = http.post(
        f"https://uploads.github.com/repos/{REPO}/releases/{release_id}/assets?name={IMAGE_FILENAME}",
        headers={**GH_HEADERS, "Content-Type": "image/jpeg"},
        data=f,
        timeout=TIMEOUT,
    )

if upload_resp.status_code not in (200, 201):
    raise Exception(f"Erreur upload GitHub Release : {upload_resp.json()}")

image_url = upload_resp.json()["browser_download_url"]
print(f"URL publique : {image_url}")

# ── 4. Créer le container media Instagram ───────────────────────────────────
print("Création du container Instagram...")
create_resp = http.post(
    f"{IG_API}/{USER_ID}/media",
    data={
        "image_url": image_url,
        "caption": caption,
        "access_token": ACCESS_TOKEN,
    },
    timeout=TIMEOUT,
)
create_data = create_resp.json()
print("Create media response:", create_data)

if "id" not in create_data:
    raise Exception(f"Erreur création media : {create_data}")

creation_id = create_data["id"]

# ── 5. Attendre que le container soit prêt (polling du statut) ───────────────
print("Attente de la préparation du media...")
MAX_ATTEMPTS = 20      # ~ jusqu'à 100s (20 × 5s)
POLL_DELAY   = 5
for attempt in range(1, MAX_ATTEMPTS + 1):
    status_resp = http.get(
        f"{IG_API}/{creation_id}",
        params={"fields": "status_code", "access_token": ACCESS_TOKEN},
        timeout=TIMEOUT,
    )
    status_code = status_resp.json().get("status_code")
    print(f"   Tentative {attempt}/{MAX_ATTEMPTS} : status = {status_code}")

    if status_code == "FINISHED":
        break
    if status_code == "ERROR":
        raise Exception(f"Container Instagram en ERROR : {status_resp.json()}")
    time.sleep(POLL_DELAY)
else:
    raise Exception("Container Instagram non prêt après le délai maximum")

# ── 6. Publier ──────────────────────────────────────────────────────────────
print("Publication...")
publish_resp = http.post(
    f"{IG_API}/{USER_ID}/media_publish",
    data={
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN,
    },
    timeout=TIMEOUT,
)
publish_data = publish_resp.json()
print("Publish response:", publish_data)

if "id" not in publish_data:
    raise Exception(f"Erreur publication : {publish_data}")

print(f"Publication réussie ! Post ID : {publish_data['id']}")

# ── 7. Nettoyage ─────────────────────────────────────────────────────────────
if os.path.exists("daily_quote.json"):
    os.remove("daily_quote.json")
if os.path.exists(IMAGE_FILENAME):
    os.remove(IMAGE_FILENAME)
