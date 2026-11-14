#!/usr/bin/env python3
"""
post_reel.py — Publie le Reel du jour sur Instagram.

Reprend le mécanisme de post_salaf.py (renouvellement du token, hébergement via
GitHub Releases pour obtenir une URL publique, polling du container), factorisé
dans ig_publish_common.py à la racine du dépôt, mais pour une VIDÉO publiée en
tant que Reel (media_type=REELS).

Pré-requis (produits par les étapes précédentes du workflow) :
  reels/out/daily_reel.mp4   — vidéo rendue par Remotion
  reels/current_verse.json   — verset du jour (légende)

Met à jour reels/posted_reels.json en fin de publication.
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ig_publish_common import make_session, renew_token_and_persist, REPO, IG_API

from build_reel_caption import build_caption

ACCESS_TOKEN  = os.environ["INSTAGRAM_ACCESS_TOKEN"]
USER_ID       = os.environ["INSTAGRAM_USER_ID"]
GITHUB_TOKEN  = os.environ["GITHUB_TOKEN"]
SECRETS_TOKEN = os.environ.get("GH_PAT") or GITHUB_TOKEN
RELEASE_TAG   = "daily-reels"
VIDEO_NAME    = "daily_reel.mp4"

HERE       = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(HERE, "out", VIDEO_NAME)
CURRENT    = os.path.join(HERE, "current_verse.json")
TRACKER    = os.path.join(HERE, "posted_reels.json")

GH_HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
GH_SECRETS_HEADERS = {"Authorization": f"token {SECRETS_TOKEN}", "Accept": "application/vnd.github+json"}
TIMEOUT = (10, 120)

http = make_session()


# ── 0. Renouveler le token Instagram (expire tous les 60 jours) ──────────────
ACCESS_TOKEN = renew_token_and_persist(http, ACCESS_TOKEN, GH_SECRETS_HEADERS, TIMEOUT)


# ── 1. Charger le verset du jour + construire la légende ─────────────────────
if not os.path.exists(VIDEO_PATH):
    raise SystemExit(f"{VIDEO_PATH} introuvable — le rendu Remotion a-t-il réussi ?")
if not os.path.exists(CURRENT):
    raise SystemExit(f"{CURRENT} introuvable — pick_verse.py a-t-il été exécuté ?")

verse = json.load(open(CURRENT, encoding="utf-8"))
caption = build_caption(verse)
print(f"Verset : {verse['theme']} — {verse['ref']}")


# ── 2. Héberger la vidéo via GitHub Releases (URL publique) ──────────────────
print("Upload de la vidéo sur GitHub Releases...")
rel = http.get(f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}",
               headers=GH_HEADERS, timeout=TIMEOUT)
if rel.status_code == 404:
    rel = http.post(f"https://api.github.com/repos/{REPO}/releases",
                    headers=GH_HEADERS,
                    json={"tag_name": RELEASE_TAG, "name": "Daily reels", "body": "Auto-generated reels"},
                    timeout=TIMEOUT)
rel_data = rel.json()
if "id" not in rel_data:
    raise SystemExit(f"Release '{RELEASE_TAG}' inaccessible (HTTP {rel.status_code}) : {rel_data}")
release_id = rel_data["id"]

# Supprimer l'asset précédent (même nom) pour le remplacer.
assets = http.get(f"https://api.github.com/repos/{REPO}/releases/{release_id}/assets",
                  headers=GH_HEADERS, timeout=TIMEOUT)
for asset in assets.json():
    if asset["name"] == VIDEO_NAME:
        http.delete(f"https://api.github.com/repos/{REPO}/releases/assets/{asset['id']}",
                    headers=GH_HEADERS, timeout=TIMEOUT)

with open(VIDEO_PATH, "rb") as f:
    up = http.post(
        f"https://uploads.github.com/repos/{REPO}/releases/{release_id}/assets?name={VIDEO_NAME}",
        headers={**GH_HEADERS, "Content-Type": "video/mp4"}, data=f, timeout=TIMEOUT)
if up.status_code not in (200, 201):
    raise Exception(f"Erreur upload GitHub Release : {up.json()}")
video_url = up.json()["browser_download_url"]
print(f"URL publique : {video_url}")


# ── 3. Créer le container Reel ───────────────────────────────────────────────
print("Création du container Reel...")
create = http.post(f"{IG_API}/{USER_ID}/media",
                   data={"media_type": "REELS", "video_url": video_url,
                         "caption": caption, "share_to_feed": "true",
                         "access_token": ACCESS_TOKEN},
                   timeout=TIMEOUT)
create_data = create.json()
print("Create media response:", create_data)
if "id" not in create_data:
    raise Exception(f"Erreur création media : {create_data}")
creation_id = create_data["id"]


# ── 4. Attendre la fin du traitement vidéo (les Reels prennent du temps) ─────
print("Attente du traitement de la vidéo...")
MAX_ATTEMPTS, POLL_DELAY = 40, 10   # jusqu'à ~6,5 min
for attempt in range(1, MAX_ATTEMPTS + 1):
    st = http.get(f"{IG_API}/{creation_id}",
                  params={"fields": "status_code", "access_token": ACCESS_TOKEN},
                  timeout=TIMEOUT)
    status_code = st.json().get("status_code")
    print(f"   Tentative {attempt}/{MAX_ATTEMPTS} : status = {status_code}")
    if status_code == "FINISHED":
        break
    if status_code == "ERROR":
        raise Exception(f"Container Instagram en ERROR : {st.json()}")
    time.sleep(POLL_DELAY)
else:
    raise Exception("Container Reel non prêt après le délai maximum")


# ── 5. Publier ───────────────────────────────────────────────────────────────
print("Publication...")
pub = http.post(f"{IG_API}/{USER_ID}/media_publish",
                data={"creation_id": creation_id, "access_token": ACCESS_TOKEN},
                timeout=TIMEOUT)
pub_data = pub.json()
print("Publish response:", pub_data)
if "id" not in pub_data:
    raise Exception(f"Erreur publication : {pub_data}")
print(f"Publication réussie ! Reel ID : {pub_data['id']}")


# ── 6. Mettre à jour l'historique ────────────────────────────────────────────
posted = []
if os.path.exists(TRACKER):
    posted = json.load(open(TRACKER, encoding="utf-8")).get("posted", [])
if verse["ref"] not in posted:
    posted.append(verse["ref"])
json.dump({"posted": posted}, open(TRACKER, "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"Historique mis à jour ({len(posted)} reels publiés).")
