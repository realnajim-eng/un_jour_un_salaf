"""
ig_publish_common.py — Code partagé par post_salaf.py et reels/post_reel.py :
session HTTP avec reprise automatique, renouvellement du token Instagram
(expire tous les 60 jours) et persistance du nouveau token dans un secret
GitHub (pour que le renouvellement survive au run suivant).
"""
import base64
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from nacl import encoding, public

REPO = "realnajim-eng/un_jour_un_salaf"

# Version de l'API Graph utilisée pour publier — UN SEUL endroit à changer.
# v21.0 expirait le 2027-01-21 ; passage à v26.0 le 2026-11-14 (changelog Meta :
# https://developers.facebook.com/docs/graph-api/changelog/versions).
IG_API = "https://graph.instagram.com/v26.0"


def make_session():
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=2,                       # 2s, 4s, 8s, 16s
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST", "PUT", "DELETE"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def refresh_instagram_token(http, token, timeout):
    resp = http.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=timeout,
    )
    data = resp.json()
    if "access_token" in data:
        new_token = data["access_token"]
        expires_in = data.get("expires_in", 0)
        print(f"✅ Token Instagram renouvelé (expire dans {expires_in // 86400} jours)")
        return new_token
    print(f"⚠️  Renouvellement token échoué : {data}")
    return token


def update_github_secret(http, secret_name, secret_value, gh_secrets_headers, timeout):
    # Récupérer la clé publique du dépôt
    key_resp = http.get(
        f"https://api.github.com/repos/{REPO}/actions/secrets/public-key",
        headers=gh_secrets_headers,
        timeout=timeout,
    )
    key_data = key_resp.json()
    if "key" not in key_data:
        raise RuntimeError(
            f"Clé publique inaccessible (HTTP {key_resp.status_code}) : {key_data}. "
            "Le token n'a probablement pas le droit d'écrire les secrets — "
            "fournis un PAT dans le secret GH_PAT (permission Secrets: read & write)."
        )
    public_key = public.PublicKey(key_data["key"].encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = base64.b64encode(sealed_box.encrypt(secret_value.encode("utf-8"))).decode("utf-8")

    put_resp = http.put(
        f"https://api.github.com/repos/{REPO}/actions/secrets/{secret_name}",
        headers=gh_secrets_headers,
        json={"encrypted_value": encrypted, "key_id": key_data["key_id"]},
        timeout=timeout,
    )
    if put_resp.status_code in (201, 204):
        print(f"✅ Secret GitHub '{secret_name}' mis à jour")
    else:
        raise RuntimeError(f"Mise à jour secret échouée : {put_resp.status_code} {put_resp.text}")


def renew_token_and_persist(http, access_token, gh_secrets_headers, timeout):
    """Renouvelle le token Instagram et persiste le nouveau token dans le secret
    GitHub INSTAGRAM_ACCESS_TOKEN s'il a changé. Ne lève jamais : en cas
    d'échec (renouvellement ou persistance), la publication se poursuit avec
    le meilleur token disponible."""
    try:
        new_token = refresh_instagram_token(http, access_token, timeout)
        if new_token != access_token:
            try:
                update_github_secret(http, "INSTAGRAM_ACCESS_TOKEN", new_token,
                                     gh_secrets_headers, timeout)
            except Exception as e:
                print(f"⚠️  Persistance du nouveau token échouée (publication poursuivie) : {e}")
            return new_token
        return access_token
    except Exception as e:
        print(f"⚠️  Renouvellement du token échoué (publication avec l'ancien token) : {e}")
        return access_token
