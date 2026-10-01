# CLAUDE.md — Un Jour Un Salaf

Bot Instagram qui publie du contenu islamique authentique : **paroles des Salaf**
(posts image) et **versets coraniques** (Reels vidéo). Rendu + publication via
GitHub Actions. Langue de travail : **français**.

## Deux pipelines

### 1. Posts Salaf (racine du dépôt) — Python + Pillow
Citation authentifiée (dorar.net) → image → publication Instagram.

| Fichier | Rôle |
|---|---|
| `fetch_caption.py` | Choisit la citation du jour dans `quotes_salaf.json`, évite les répétitions via `tracker.json`, écrit `daily_quote.json` |
| `build_caption.py` | Construit la légende (texte + hashtags + handle) |
| `generate_image.py` | Compose l'image (fond `images/` + texte arabe + logo) → `output.jpg` |
| `post_salaf.py` | Renouvelle le token IG, héberge l'image en GitHub Release, crée le container média, publie |
| `quotes_salaf.json` | Base de paroles (source : dorar.net / shamela.ws) |
| `tracker.json` | `used_quotes` déjà publiées |

### 2. Reels versets (`reels/`) — Remotion (React/TS) + Python
Référence sourate:verset → texte récupéré d'une source authentifiée → vidéo verticale.

| Fichier | Rôle |
|---|---|
| `reels/build_verses.py` | (Re)construit `public/verses.json` depuis les **références** REFS. **Ne saisit jamais le texte coranique de mémoire** — télécharge rasm ʿuthmānī + traduction Hamidullah via alquran.cloud |
| `reels/pick_verse.py` | Choisit le verset du jour (round-robin par thème) ; une fois les 250 publiés, boucle depuis le début, écrit `render_props.json` + `current_verse.json` |
| `reels/prune_verses.py` | Élague le réservoir de versets |
| `reels/build_reel_caption.py` | Légende du reel |
| `reels/post_reel.py` | Publie le reel sur Instagram |
| `reels/src/` | Composition Remotion (`Verse`) |
| `reels/public/` | Fonds (`.jpg`/`.png`), `audio/`, `fonts/`, `verses.json` |
| `reels/posted_reels.json` | Historique des reels publiés |

**Réservoir actuel : 248 versets, 17 thèmes** (paradis, enfer, temps, tawhid,
patience, jugement, coran, rahma, tawba, shukr, tawakkul, birr, tafakkur, mort,
taqwa, faraj, rappel).

Commandes reels (depuis `reels/`) :
```bash
python3 build_verses.py <theme>        # (re)construit un thème ; sans arg = tous
python3 pick_verse.py                  # sélectionne le verset du jour
node_modules/.bin/remotion render Verse out/reel.mp4 --props=render_props.json
npx remotion studio                    # aperçu interactif
```
> Les **17 thèmes** utilisent désormais un **fond image fixe** présent dans
> `reels/public/` (zoom lent continu via `STILL_IMAGE` dans `QuoteReel.tsx`),
> `paradis` (`Paradis.jpg`) et `enfer` (`Enfer.jpg`) compris → tous rendables
> dans le cloud automatique, plus aucune vidéo de fond locale requise.

## Automatisation — ACTIVE depuis 2026-07-05
Deux publications indépendantes **chaque jour** (pas d'alternance) :
- `daily_post.yml` : parole de Salaf à **17h17 Paris** (cron cible `17 15 * * *` UTC).
- `daily_reel.yml` : reel verset à **19h19 Paris** (cron cible `19 17 * * *` UTC).

Horaires volontairement décalés hors pile-heure (`:17`/`:19` plutôt que `:00`)
car les crons GitHub Actions subissent des retards de charge (observé : 3h à
6h de retard les 5-7 juillet 2026). Depuis 2026-07-07 (fenêtre élargie le soir
même), chaque workflow a en plus des **crons de rattrapage toutes les 30 min
sur ~5h30 après la cible** (post jusqu'à 22h47 Paris été, reel jusqu'à 23h49) : le
garde-fou anti-doublon (date du dernier commit du tracker) fait que seul le
premier run du jour publie, les suivants s'arrêtent en ~15s (runs « skip »
normaux dans l'historique, certains peuvent apparaître « cancelled » à cause du
groupe `concurrency: instagram-publish` partagé qui sérialise toutes les
publications). Les crons sont en UTC fixe → dérive d'1h en heure d'hiver (CET)
sans ajustement.
`daily_alternate.yml` (ancienne alternance Salaf/reel via `post_state.json`) est
remplacé et **entièrement désactivé** depuis le 2026-07-08 (`gh workflow disable`,
état `disabled_manually`) : il ne peut plus se déclencher, ni par schedule ni
manuellement. Pour le réactiver un jour : `gh workflow enable daily_alternate.yml`
(mais ne jamais réactiver son schedule → double post). Secrets requis : `INSTAGRAM_ACCESS_TOKEN`,
`INSTAGRAM_USER_ID`, `INSTAGRAM_CLIENT_SECRET`, `ANTHROPIC_API_KEY`.

### Fiabilisation — horloge externe au planificateur GitHub (depuis 2026-07-08)
Le planificateur `schedule` de GitHub est best-effort et peut sauter TOUS les
créneaux d'un jour (le 2026-07-08 : 0 déclenchement, cron modifié la veille →
GitHub a « oublié » le cycle suivant). Deux filets **indépendants du
planificateur GitHub** garantissent la publication :

1. **Filet macOS (`launchd`)** — `scripts/backup_trigger.sh` (copie de référence
   versionnée). Copie **opérationnelle** exécutée : `~/.local/bin/salaf_backup_trigger.sh`
   (hors dossier protégé macOS/TCC — `launchd` ne peut pas lire `~/Desktop`).
   Planifié par `~/Library/LaunchAgents/com.najim.salaf-backup.plist` à 20h30 et
   22h15 Paris. Chaque soir : si aucun run réussi du jour, déclenche
   `gh workflow run`. Aucun secret (réutilise le `gh` du trousseau). Log :
   `~/Library/Logs/salaf-backup.log`. Ne marche que si le Mac est allumé le soir.
   - Après modif du script : `cp scripts/backup_trigger.sh ~/.local/bin/salaf_backup_trigger.sh`
   - Désactiver : `launchctl unload ~/Library/LaunchAgents/com.najim.salaf-backup.plist`
   - Recharger : `launchctl load ~/Library/LaunchAgents/com.najim.salaf-backup.plist`
   - Tester : `launchctl kickstart -k gui/$(id -u)/com.najim.salaf-backup` puis lire le log

2. **Déclencheur externe (cron-job.org)** — EN PLACE ET VÉRIFIÉ depuis le
   2026-07-08 (compte `realnajim@hotmail.com`). Appelle l'API `workflow_dispatch`
   de GitHub à l'heure pile, indépendamment du Mac (garantie maximale). Deux
   tâches, fuseau Europe/Brussels (= Paris) :
   - « Salaf post 17h17 » → POST `…/actions/workflows/daily_post.yml/dispatches`
   - « Salaf reel 19h19 » → POST `…/actions/workflows/daily_reel.yml/dispatches`
   Corps `{"ref":"main"}` ; en-têtes `Authorization: Bearer <PAT>`,
   `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`,
   `Content-Type: application/json`. Token GitHub restreint (fine-grained,
   `Actions: read/write`, dépôt `un_jour_un_salaf` seul — renommé depuis
   `salaf-instagram` le 2026-07-30, l'accès du token suit le renommage —, sans expiration) stocké
   UNIQUEMENT dans le champ Authorization de cron-job.org — jamais dans un fichier.
   - **Piège cron-job.org** : à la CRÉATION, son test d'URL fait un GET anonyme →
     GitHub répond 404 → « URL invalide » qui BLOQUE l'enregistrement. Contournement :
     créer/éditer avec le token déjà présent (le test passe alors), ou passer d'abord
     par `https://api.github.com` puis rééditer l'URL. Le clonage d'une tâche
     fonctionnelle (menu ACTIONS → Cloner) reprend le token et évite de le recoller.
   - Token actuel : « cron-job.org - salaf publish v2 » (le v1 a été révoqué le
     2026-07-08 après exposition à l'écran). Révoquer/renouveler : GitHub →
     Settings → Developer settings → Fine-grained tokens, régénérer, puis
     recoller le MÊME token dans les **2** tâches cron-job.org (ne pas en oublier
     une : chacune a son propre en-tête Authorization) et retester chacune
     (« Test de fonctionnement » → 204 attendu).

> Ne PAS ré-éditer les crons `schedule` sans raison : chaque édition peut faire
> sauter à GitHub le cycle suivant. Le garde-fou anti-doublon rend tout
> déclenchement supplémentaire (manuel, filet, externe) sans danger.

### Alerte de publication manquante (depuis 2026-10-01)
Les filets ci-dessus RELANCENT la publication ; `scripts/publish_alert.js`
PRÉVIENT quand elle n'est pas partie malgré tout (token Instagram expiré, API
Meta en panne…). Il vérifie le même signal que le garde-fou anti-doublon — un
commit du jour (UTC) sur `tracker.json` (post) et `reels/posted_reels.json`
(reel) — et, si l'un manque, envoie un e-mail à soi-même via Outlook avec les
liens des runs en échec du jour.

- Passe par la CLI **Composio** (`~/.local/bin/composio`, compte
  `realnajim@hotmail.com`) avec deux comptes liés : `composio link github` et
  `composio link outlook`. Aucun secret dans le dépôt ; les accès OAuth sont
  gérés côté Composio. État des liaisons : `composio connections list`.
- **Lancement manuel uniquement** (pas de planification, choix du 2026-10-01),
  depuis la racine du dépôt :
  ```bash
  composio run -f scripts/publish_alert.js              # le soir (≥ 20h Paris)
  composio run -f scripts/publish_alert.js -- --print   # aperçu, sans envoi
  composio run -f scripts/publish_alert.js -- --force   # ignore la garde horaire
  composio run -f scripts/publish_alert.js -- --test    # envoie un e-mail de test
  ```
- Garde horaire : avant 20h Paris le script s'arrête sans rien faire (les
  publications ne sont pas encore censées être parties) ; `--print` l'ignore aussi.
- Si tout est publié : aucun e-mail, juste une ligne de log.

## Règles de travail (IMPORTANT)
- **Rigueur islamique** : ne jamais inventer ni saisir de mémoire un verset, un
  hadith ou une parole du Salaf. Toujours passer par une source authentifiée
  (dorar.net, shamela.ws, API Coran) ou le skill `aqwal-salaf` / `islamic-sciences`.
  Cette règle prime sur tout, y compris la gestion autonome ci-dessous.
- **Gestion autonome de la publication quotidienne (depuis 2026-07-05)** :
  l'utilisateur a demandé de tout gérer sans confirmation. La publication
  elle-même est déjà 100% automatique via GitHub Actions (aucune action de ma
  part n'est nécessaire au quotidien). Pour la maintenance du pipeline
  (réapprovisionnement du réservoir, correction de bugs bloquant une
  publication, mise à jour de `tracker.json`/`posted_reels.json`/
  `post_state.json`), j'agis directement **sans demander confirmation**,
  y compris pour committer et **pousser sur GitHub** (`git push`) — car sans
  ça la publication automatique reste bloquée sur le commit précédent.
  Reste couvert par la prudence habituelle (à ne jamais faire sans demander) :
  force-push, `reset --hard`, suppression de workflows/secrets/branches, ou
  toute action destructive/irréversible sans rapport direct avec le maintien
  de la publication quotidienne.
- **Reels un par un** (hors automatisation) : si l'utilisateur demande un reel
  en interactif, en générer un seul à la fois + aperçu, jamais en lot.
- **Toujours ouvrir l'aperçu** (hors automatisation) : après génération
  interactive d'une image/vidéo, `open <fichier>`.
- **Boucle infinie (depuis 2026-07-05)** : les deux réservoirs (citations Salaf,
  versets) recommencent automatiquement depuis le début une fois entièrement
  épuisés (`tracker.json` / `posted_reels.json` remis à zéro), au lieu de
  bloquer la publication. Le réapprovisionnement (ajout de nouvelles citations
  ou versets vérifiés) reste bienvenu à tout moment pour retarder les
  répétitions, mais n'est plus une condition requise pour que la publication
  continue.
- **Aucun secret dans le code** : tout passe par les secrets GitHub.

## Environnement
- macOS · Python 3 (`pip install -r requirements.txt`) · Node/npm pour `reels/`.
- `ffmpeg`/`ffprobe` dispo pour l'inspection vidéo.
