// Alerte e-mail si la publication Instagram du jour n'est pas partie.
//
// Pourquoi : les filets existants (crons de rattrapage, cron-job.org,
// backup_trigger.sh) RELANCENT la publication, mais aucun ne PRÉVIENT quand
// elle échoue malgré tout (token Instagram expiré, API Meta en panne…). Ce
// script, lancé en fin de soirée, vérifie le même signal que le garde-fou
// anti-doublon des workflows — un commit du jour (UTC) sur le tracker — et
// envoie un e-mail à soi-même si un des deux trackers n'a pas bougé.
//
// Exécution : composio run -f publish_alert.js [-- --force | --test | --print]
//   --force : ignore la garde horaire (vérifie même avant 20h Paris)
//   --test  : envoie l'e-mail même si tout est publié (test de bout en bout)
//   --print : affiche l'e-mail au lieu de l'envoyer (implique --force)
//
// Aucun secret ici : GitHub et Outlook passent par les comptes liés à la CLI
// Composio (`composio link github`, `composio link outlook`).

const OWNER = "realnajim-eng";
const REPO = "un_jour_un_salaf";
const TARGETS = [
  { label: "Post Salaf", workflow: "daily_post.yml", tracker: "tracker.json" },
  { label: "Reel verset", workflow: "daily_reel.yml", tracker: "reels/posted_reels.json" },
];

const print = process.argv.includes("--print");
const force = print || process.argv.includes("--force");
const test = process.argv.includes("--test");
const log = (msg) => console.log(`${new Date().toISOString()} · ${msg}`);

// Même garde que backup_trigger.sh : si launchd rattrape un job manqué le
// matin, la journée UTC vient de commencer et rien n'est encore publié.
const hour = new Date().getHours();
if (hour < 20 && !force && !test) {
  log(`Avant 20h Paris (${hour} h) — trop tôt pour conclure. Fin.`);
  process.exit(0);
}

// Les workflows raisonnent en UTC pour la date « du jour ».
const today = new Date().toISOString().slice(0, 10);
const since = `${today}T00:00:00Z`;

const failed = await execute("GITHUB_LIST_WORKFLOW_RUNS_FOR_A_REPOSITORY", {
  owner: OWNER,
  repo: REPO,
  status: "failure",
  created: `>=${today}`,
  per_page: 30,
});
const failedRuns = failed.data?.workflow_runs ?? [];

const report = [];
for (const t of TARGETS) {
  const res = await execute("GITHUB_LIST_COMMITS", {
    owner: OWNER,
    repo: REPO,
    path: t.tracker,
    since,
    per_page: 1,
  });
  const published = (res.data?.commits ?? []).length > 0;
  const failures = failedRuns.filter((r) => r.path?.endsWith(`/${t.workflow}`));
  report.push({ ...t, published, failures });
  log(`[${t.label}] ${published ? "publié aujourd'hui" : "NON publié"} · ${failures.length} run(s) en échec`);
}

const missing = report.filter((r) => !r.published);
if (missing.length === 0 && !test) {
  log("Tout est publié — aucun e-mail.");
  process.exit(0);
}

const lines = [];
if (test) lines.push("TEST : cet e-mail vérifie seulement que l'alerte arrive.", "");
lines.push(`État des publications du ${today} (date UTC) :`);
lines.push("");
for (const r of report) {
  lines.push(`• ${r.label} : ${r.published ? "publié" : "NON PUBLIÉ"}`);
  for (const f of r.failures) lines.push(`    échec : ${f.html_url}`);
  if (!r.published && r.failures.length === 0) {
    lines.push("    aucun run en échec aujourd'hui — le workflow ne s'est peut-être pas déclenché");
  }
}
lines.push("");
lines.push(`Historique : https://github.com/${OWNER}/${REPO}/actions`);
lines.push(`Relancer : gh workflow run <daily_post.yml|daily_reel.yml> --repo ${OWNER}/${REPO}`);

const profile = await execute("OUTLOOK_GET_PROFILE", {});
const to = profile.data?.mail ?? profile.data?.userPrincipalName;
if (!to) {
  log("Adresse Outlook introuvable dans le profil — e-mail non envoyé.");
  process.exit(1);
}

const subject = test
  ? "Un Jour Un Salaf — test de l'alerte de publication"
  : `Un Jour Un Salaf — ${missing.map((r) => r.label).join(" + ")} non publié (${today})`;

if (print) {
  console.log(`\n--- e-mail (non envoyé) ---\nObjet : ${subject}\n\n${lines.join("\n")}`);
  process.exit(0);
}

await execute("OUTLOOK_SEND_EMAIL", { to, subject, body: lines.join("\n") });
log(`E-mail d'alerte envoyé (${missing.length} publication(s) manquante(s)).`);
