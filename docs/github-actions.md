# GitHub Actions – Automatische Datensammlung

## Wie funktioniert es?

GitHub Actions führt alle 15 Minuten `python main.py` aus. Das Script ruft die aktuellen Spritpreise über die Tankerkönig API ab und speichert sie in der Neon-Datenbank. Der eigene Computer muss dabei nicht laufen.

---

## Workflow-Datei

Der Workflow liegt unter `.github/workflows/collect.yml` und wird automatisch von GitHub erkannt.

```yaml
on:
  schedule:
    - cron: "*/15 * * * *"   # alle 15 Minuten
  workflow_dispatch:          # manueller Start möglich
```

**Hinweis:** GitHub garantiert keine sekundengetreue Ausführung — Verzögerungen von 1–5 Minuten sind normal, besonders bei hoher Last auf den GitHub-Servern.

---

## Secrets einrichten

Die Zugangsdaten werden als verschlüsselte Secrets im Repository gespeichert — nie direkt im Code.

**GitHub → Repository → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Inhalt |
|---|---|
| `TANKERKOENIG_API_KEY` | API-Key von tankerkoenig.de |
| `DATABASE_URL` | Neon Connection String |

Secrets können jederzeit aktualisiert werden — der nächste Workflow-Run verwendet automatisch den neuen Wert.

---

## Workflow überwachen

**GitHub → Repository → Actions**

Dort siehst du jeden einzelnen Run mit Status (grün = OK, rot = Fehler) und den vollständigen Log-Output.

### Manueller Start

Auf der Actions-Seite:
1. Links "Collect fuel prices" auswählen
2. **"Run workflow"** → **"Run workflow"**

Nützlich zum Testen oder wenn ein Abruf manuell angestoßen werden soll.

---

## Neue Tankstelle hinzufügen

1. UUID der Tankstelle auf [tankerkoenig.de](https://tankerkoenig.de) suchen
2. In `config.json` unter `tankerkoenig_stations` eintragen
3. Committen und pushen — beim nächsten Run wird die Station automatisch erkannt und in die DB eingetragen

```bash
git add config.json
git commit -m "Add new station"
git push
```

---

## Kosten

GitHub Actions ist kostenlos:
- **Public Repositories:** unbegrenzte Minuten
- **Private Repositories:** 2.000 Minuten/Monat gratis

Ein einzelner Run dauert ca. 30–60 Sekunden → ~3 Minuten/Stunde → ~2.200 Minuten/Monat.
Bei einem **privaten** Repo liegt man knapp über dem Limit — entweder das Repo öffentlich lassen oder auf 20-Minuten-Intervall wechseln (`*/20 * * * *` in `collect.yml`).
