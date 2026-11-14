# Un Jour Un Salaf — bot Instagram

Bot Instagram islamique qui publie chaque jour, de façon **100% automatisée**,
deux contenus indépendants :

- une **parole authentique des Salaf as-Salih** (Compagnons, Tābiʿūn, Atbāʿ
  al-Tābiʿīn), sous forme d'**image** générée avec sa source ;
- un **verset coranique**, sous forme de **Reel vidéo** (texte arabe + traduction
  + récitation).

## Fonctionnement

### 1. Posts Salaf — chaque jour à 17h17 Paris

`.github/workflows/daily_post.yml` exécute :

1. **`fetch_caption.py`** — choisit une citation dans `quotes_salaf.json`
   (229 paroles, source [dorar.net](https://dorar.net)), en évitant les
   répétitions grâce à `tracker.json`, et écrit `daily_quote.json`.
   Si `quotes_salaf.json` est absent, le script s'arrête sans rien publier :
   aucune citation n'est jamais générée de mémoire.
2. **`post_salaf.py`** —
   - renouvelle automatiquement le token Instagram (valable 60 jours) et met à
     jour le secret GitHub correspondant ;
   - génère l'image (`generate_image.py`, Pillow) ;
   - héberge l'image en pièce jointe d'une *GitHub Release* (URL publique, sans
     commit) ;
   - crée le container média Instagram, attend qu'il soit `FINISHED` (polling),
     puis publie.

Une fois les 150 citations publiées, le réservoir recommence depuis le début
(`tracker.json` remis à zéro) — la publication ne se bloque jamais.

### 2. Reels versets — chaque jour à 19h19 Paris

`.github/workflows/daily_reel.yml` exécute (depuis `reels/`) :

1. **`pick_verse.py`** — choisit le verset du jour parmi les 250 versets /
   17 thèmes (round-robin par thème), écrit `render_props.json` +
   `current_verse.json`.
2. **Remotion** (`npx remotion render Verse out/daily_reel.mp4`) — rend la
   vidéo verticale (fond image fixe + texte arabe + traduction).
3. **`post_reel.py`** — même mécanisme que `post_salaf.py` (renouvellement du
   token, hébergement via GitHub Release, publication en tant que Reel).

Comme pour les citations, une fois les 250 versets publiés, le réservoir
recommence depuis le début (`posted_reels.json` remis à zéro).

Le texte coranique n'est **jamais saisi de mémoire** : `build_verses.py`
télécharge le rasm ʿuthmānī et la traduction Hamidullah depuis alquran.cloud.

Les deux publications sont **indépendantes** (pas d'alternance) ; un garde-fou
dans chaque workflow évite un doublon si le job tourne deux fois le même jour.

## Structure

| Fichier / dossier             | Rôle                                                      |
|--------------------------------|------------------------------------------------------------|
| `fetch_caption.py`             | Sélection de la citation Salaf du jour                     |
| `build_caption.py`             | Construction de la légende (hashtags variés)               |
| `generate_image.py`            | Composition de l'image (fond + texte arabe + logo)         |
| `post_salaf.py`                | Token, hébergement image, publication Instagram             |
| `quotes_salaf.json`            | Base de citations (150 paroles, dorar.net)                  |
| `tracker.json`                 | Suivi des citations déjà publiées (`used_quotes`)           |
| `images/`, `fonts/`            | Fond, logo Instagram, polices embarquées                    |
| `reels/build_verses.py`        | (Re)construit `public/verses.json` depuis des références    |
| `reels/pick_verse.py`          | Choix du verset du jour (round-robin par thème)             |
| `reels/prune_verses.py`        | Élagage du réservoir de versets                             |
| `reels/build_reel_caption.py`  | Légende du reel                                             |
| `reels/post_reel.py`           | Publication du reel sur Instagram                           |
| `reels/src/`                   | Composition Remotion (`Verse`)                              |
| `reels/public/`                | Fonds, audio, polices, `verses.json` (250 versets)          |
| `reels/posted_reels.json`      | Historique des reels publiés                                |
| `.github/workflows/`           | `daily_post.yml`, `daily_reel.yml`, `get_token.yml`         |

Détails complets (architecture, règles de rigueur islamique, automatisation) :
voir [`CLAUDE.md`](CLAUDE.md).

## Secrets GitHub requis

À définir dans **Settings → Secrets and variables → Actions** :

| Secret                      | Description                                              |
|-----------------------------|-----------------------------------------------------------|
| `INSTAGRAM_ACCESS_TOKEN`    | Token longue durée (renouvelé automatiquement)             |
| `INSTAGRAM_USER_ID`         | Identifiant du compte Instagram professionnel              |
| `INSTAGRAM_CLIENT_SECRET`   | Secret de l'app Meta (pour l'échange de token)             |
| `GH_PAT`                    | *Optionnel* — PAT avec droit `Secrets: read & write`, pour persister le token Instagram renouvelé (sinon le `GITHUB_TOKEN` automatique est utilisé, sans ce droit) |

> `GITHUB_TOKEN` est fourni automatiquement par GitHub Actions.

## Obtenir le token Instagram (première installation)

1. Récupérer un **token courte durée** depuis le
   [Graph API Explorer](https://developers.facebook.com/tools/explorer/) de Meta.
2. Lancer manuellement le workflow **Get Instagram Token**
   (`get_token.yml`) en collant ce token dans le champ `short_token`.
3. Le token longue durée est automatiquement chiffré et sauvegardé dans le
   secret `INSTAGRAM_ACCESS_TOKEN`. Il sera ensuite renouvelé automatiquement à
   chaque publication.

## Exécution locale (test)

```bash
pip install -r requirements.txt

# Posts Salaf
python generate_image.py        # produit output.jpg (données de démo)
python fetch_caption.py         # puis
python post_salaf.py            # nécessite les variables d'environnement ci-dessus

# Reels versets (depuis reels/)
cd reels
npm install
python3 pick_verse.py
npx remotion render Verse out/daily_reel.mp4 --props=render_props.json
npx remotion studio             # aperçu interactif
```

## Sécurité

Aucun secret ne doit figurer dans le code ou les workflows. Tout identifiant
(token, client secret, clé API) passe exclusivement par les secrets GitHub.
