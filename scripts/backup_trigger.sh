#!/usr/bin/env bash
#
# Filet de sécurité local pour la publication Instagram quotidienne.
#
# Pourquoi : le planificateur `schedule` de GitHub Actions est best-effort et
# saute parfois TOUS les créneaux d'une journée (retards de charge, instabilité
# après une édition du cron). Ce script, lancé chaque soir par launchd
# (voir ~/Library/LaunchAgents/com.najim.salaf-backup.plist), vérifie si la
# publication du jour est bien partie et la déclenche manuellement sinon.
#
# Aucun secret ici : on réutilise le `gh` déjà authentifié (trousseau macOS).
# Le garde-fou anti-doublon des workflows + le groupe `concurrency` garantissent
# qu'un déclenchement de secours ne peut jamais produire un double post.

set -euo pipefail

REPO="realnajim-eng/un_jour_un_salaf"
GH="/Users/najim/.local/bin/gh"
export GH_PAGER=""

# On raisonne en heure de Paris (fournie par launchd, correcte été/hiver).
# On n'agit qu'en soirée : les deux cibles (17h17 post, 19h19 reel) sont alors
# largement passées. Si le Mac se réveille le matin sur un job manqué, l'heure
# est < 20h → on ne déclenche pas prématurément une publication du jour.
HOUR=$(date +%H)
if [ "$((10#$HOUR))" -lt 20 ]; then
  echo "$(date '+%F %T') · Avant 20h Paris ($HOUR h) — on laisse GitHub publier. Fin."
  exit 0
fi

# Les workflows raisonnent en UTC pour la date « du jour ».
TODAY=$(date -u +%Y-%m-%d)

# Signal « publié » = un commit du jour (UTC) sur le tracker, exactement comme
# le garde-fou anti-doublon des workflows. (Un run « success » ne prouve rien :
# un run ignoré par le garde-fou se termine lui aussi en success.)
check_and_trigger() {
  local wf="$1" label="$2" tracker="$3"
  local n
  n=$("$GH" api "repos/$REPO/commits?path=$tracker&since=${TODAY}T00:00:00Z&per_page=1" --jq 'length') \
    || { echo "$(date '+%F %T') · [$label] gh injoignable — abandon."; return 0; }

  if [ "${n:-0}" -gt 0 ]; then
    echo "$(date '+%F %T') · [$label] déjà publié aujourd'hui — rien à faire."
  else
    echo "$(date '+%F %T') · [$label] AUCUNE publication aujourd'hui — déclenchement de secours."
    "$GH" workflow run "$wf" --repo "$REPO" \
      && echo "$(date '+%F %T') · [$label] déclenché." \
      || echo "$(date '+%F %T') · [$label] échec du déclenchement."
  fi
}

check_and_trigger daily_post.yml "post" "tracker.json"
check_and_trigger daily_reel.yml "reel" "reels/posted_reels.json"
