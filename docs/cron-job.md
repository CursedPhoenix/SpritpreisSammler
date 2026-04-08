# cron-job.org – Zuverlässiges Scheduling

## Warum cron-job.org?

GitHub's eingebauter Cron-Scheduler (`schedule:` in Workflows) ist bei öffentlichen Repositories unzuverlässig — Runs werden oft verzögert oder übersprungen. cron-job.org triggert den GitHub Actions Workflow von außen per HTTP-Request, was deutlich zuverlässiger funktioniert.

---

## Wie es funktioniert

Alle 15 Minuten sendet cron-job.org einen `POST`-Request an die GitHub API:

```
POST https://api.github.com/repos/CursedPhoenix/SpritpreisSammler/actions/workflows/collect.yml/dispatches
```

GitHub startet daraufhin den Workflow `collect.yml`, der `main.py` ausführt und die Preise sammelt.

---

## Einrichtung (Referenz)

### 1. GitHub Personal Access Token

GitHub → Profilbild → **Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token**

- Scope: **`workflow`**
- Token beginnt mit `ghp_...`

Das Token verfällt je nach gewählter Laufzeit — bei Ablauf muss ein neues erstellt und in cron-job.org hinterlegt werden.

### 2. cron-job.org Konfiguration

| Feld | Wert |
|---|---|
| URL | `https://api.github.com/repos/CursedPhoenix/SpritpreisSammler/actions/workflows/collect.yml/dispatches` |
| Request method | `POST` |
| Execution schedule | Every 15 minutes |
| Request body | `{"ref":"main"}` |

**Request Headers:**

| Key | Value |
|---|---|
| `Authorization` | `Bearer <GitHub PAT>` |
| `Accept` | `application/vnd.github+json` |
| `Content-Type` | `application/json` |

### 3. Erfolgskontrolle

Ein erfolgreicher Request gibt HTTP **204 No Content** zurück. In cron-job.org unter **"Logs"** ist der Status jedes Runs einsehbar.

Gleichzeitig erscheint in **GitHub → Actions** ein neuer Run unter "Collect fuel prices".

---

## Laufende Wartung

### Token abgelaufen

1. Neues Token auf GitHub erstellen (Scope: `workflow`)
2. cron-job.org → Job bearbeiten → Header `Authorization` aktualisieren
3. Testlauf starten und auf HTTP 204 prüfen

### Job pausieren

cron-job.org → Job → **"Disable"** — der Job bleibt erhalten, wird aber nicht mehr ausgeführt.

### Intervall ändern

cron-job.org → Job bearbeiten → Execution schedule anpassen.

Mögliche Werte: 15 Minuten, 30 Minuten, stündlich etc.
Bei einer Änderung auf 20 Minuten spart man GitHub-Actions-Minuten (relevant nur bei privaten Repos).

---

## Troubleshooting

| Problem | Mögliche Ursache | Lösung |
|---|---|---|
| HTTP 401 | Token falsch oder abgelaufen | Neues Token erstellen, `Bearer` gehört in den **Value**, nicht den Key |
| HTTP 404 | URL falsch | Repo-Name / Workflow-Dateiname prüfen |
| HTTP 204, aber kein GitHub Run | Workflow hat keinen `workflow_dispatch` Trigger | `collect.yml` prüfen |
| Runs unregelmäßig | cron-job.org Ausfall | Log auf cron-job.org prüfen |
