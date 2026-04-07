# analyze.py – Auswertung der Spritpreise

## Voraussetzungen

`DATABASE_URL` muss in der `.env`-Datei gesetzt sein (Neon Connection String).
Ohne `DATABASE_URL` verwendet das Script die lokale `prices.db` (SQLite).

```bash
# Abhängigkeiten installieren (einmalig)
pip install -r requirements.txt
```

---

## Befehle

### Letzte Einträge anzeigen

```bash
python analyze.py --show-recent
python analyze.py --show-recent --limit 50
```

Zeigt die neuesten Preiseinträge aus der Datenbank. Standard: 20 Einträge.

**Beispielausgabe:**
```
timestamp                   station                    fuel_type  price
--------------------------  -------------------------  ---------  -----
2026-04-08T14:30:00+00:00   AVIA Tankstelle Neufra     diesel     2.349
2026-04-08T14:30:00+00:00   AVIA Tankstelle Neufra     e5         2.199
2026-04-08T14:30:00+00:00   AVIA Tankstelle Neufra     e10        2.139
```

---

### Günstigste Tankstelle

```bash
python analyze.py --cheapest-station --fuel diesel
python analyze.py --cheapest-station --fuel e5 --days 14
python analyze.py --cheapest-station --fuel e10 --days 30
```

Vergleicht den Durchschnittspreis aller Tankstellen im gewählten Zeitraum.

| Option | Werte | Standard |
|---|---|---|
| `--fuel` | `diesel`, `e5`, `e10` | `diesel` |
| `--days` | Anzahl Tage rückwirkend | `7` |

**Beispielausgabe:**
```
Average diesel price per station (last 7 days):

station                     avg_price (€)  samples
--------------------------  -------------  -------
AVIA Tankstelle Neufra      2.319          420
ARAL Hauptstraße            2.339          418
Shell Bahnhof               2.359          415
```

---

### Günstigste Uhrzeit

Wann ist Tanken an einer bestimmten Station durchschnittlich am günstigsten?

```bash
python analyze.py --cheapest-time --fuel diesel --station <uuid>
python analyze.py --cheapest-time --fuel e5 --station <uuid> --days 30
```

Die UUID der Station findest du in der `stations`-Tabelle (Neon SQL Editor: `SELECT id, name FROM stations`).

**Beispielausgabe:**
```
Average diesel price by hour-of-day for AVIA Tankstelle Neufra (bd41cec8-...):

hour   avg_price (€)  samples
-----  -------------  -------
06:00  2.289          28
07:00  2.299          28
...
18:00  2.349          28

Cheapest hour: 06:00  (2.289 €)
```

---

### Günstigster Wochentag

An welchem Wochentag ist eine Station durchschnittlich am günstigsten?

```bash
python analyze.py --cheapest-weekday --fuel diesel --station <uuid>
python analyze.py --cheapest-weekday --fuel e5 --station <uuid>
```

**Beispielausgabe:**
```
Average diesel price by weekday for AVIA Tankstelle Neufra (bd41cec8-...):

weekday  avg_price (€)  samples
-------  -------------  -------
Mon      2.319          840
Tue      2.309          840
...
Sun      2.299          560

Cheapest day: Sun  (2.299 €)
```

---

## Alle Optionen auf einen Blick

| Option | Beschreibung | Standard |
|---|---|---|
| `--show-recent` | Letzte N Einträge anzeigen | — |
| `--cheapest-station` | Tankstellen nach Durchschnittspreis sortieren | — |
| `--cheapest-time` | Durchschnittspreis nach Uhrzeit | — |
| `--cheapest-weekday` | Durchschnittspreis nach Wochentag | — |
| `--fuel` | Kraftstofftyp: `diesel`, `e5`, `e10` | `diesel` |
| `--days` | Betrachtungszeitraum in Tagen | `7` |
| `--station` | Tankstellen-UUID (für `--cheapest-time` / `--cheapest-weekday`) | — |
| `--limit` | Anzahl Zeilen (für `--show-recent`) | `20` |

---

## Hinweis zur Datenqualität

- `NULL`-Preise bedeuten: Tankstelle war zum Zeitpunkt der Abfrage geschlossen. Diese Werte werden in allen Auswertungen automatisch ignoriert.
- Aussagekräftige Ergebnisse für `--cheapest-time` und `--cheapest-weekday` gibt es erst nach mehreren Wochen Datensammlung (mind. 2–4 Wochen empfohlen).
