# Neon DB – Einrichtung und Verwendung

## Was ist Neon?

Neon ist eine kostenlose PostgreSQL-Datenbank in der Cloud. Alle gesammelten Spritpreise landen hier. Der Zugriff erfolgt über einen Connection String, der als Umgebungsvariable `DATABASE_URL` gesetzt wird.

---

## Verbindung einrichten

### Lokal (PC)

In der Datei `.env` im Projektverzeichnis:

```
DATABASE_URL=postgresql://neondb_owner:<passwort>@<host>/neondb?sslmode=require&channel_binding=require
```

Den vollständigen Connection String findest du im Neon Dashboard unter:
**Project → Connection Details → Connection string**

Sobald `DATABASE_URL` gesetzt ist, verbinden sich `main.py` und `analyze.py` automatisch mit Neon statt mit SQLite.

### GitHub Actions

Der Connection String ist als Secret `DATABASE_URL` im GitHub Repository hinterlegt:
**GitHub → Repository → Settings → Secrets and variables → Actions**

---

## Daten einsehen

### Option 1: Neon SQL Editor (Browser)

Neon Dashboard → **SQL Editor**

Nützliche Abfragen:

```sql
-- Anzahl gesammelter Preise gesamt
SELECT COUNT(*) FROM prices;

-- Letzte 20 Einträge
SELECT * FROM prices ORDER BY timestamp DESC LIMIT 20;

-- Alle bekannten Tankstellen
SELECT id, name, brand, street, city FROM stations;

-- Durchschnittlicher Dieselpreis pro Tankstelle (letzte 7 Tage)
SELECT s.name, ROUND(AVG(p.price)::numeric, 3) AS avg_price, COUNT(*) AS samples
FROM prices p
LEFT JOIN stations s ON s.id = p.station_id
WHERE p.fuel_type = 'diesel'
  AND p.timestamp >= NOW() - INTERVAL '7 days'
  AND p.price IS NOT NULL
GROUP BY s.name
ORDER BY avg_price;
```

### Option 2: DBeaver / DataGrip / TablePlus

Verbindungstyp: **PostgreSQL**
Connection String direkt einfügen, oder manuell:
- Host: aus dem Connection String (der Teil nach `@`, vor `/neondb`)
- Port: `5432`
- Database: `neondb`
- User/Password: aus dem Connection String

### Option 3: analyze.py (lokal)

Siehe [analyze.md](analyze.md).

---

## Datenmigration (SQLite → Neon)

Falls neue lokale SQLite-Daten in Neon importiert werden sollen:

```bash
# DATABASE_URL muss in .env gesetzt sein
python migrate.py

# Alternativer SQLite-Pfad:
python migrate.py --sqlite-path /pfad/zu/prices.db
```

Das Script ist idempotent — es kann mehrfach ausgeführt werden, bereits vorhandene Einträge werden übersprungen.

---

## Kosten

Der Neon Free Tier ist dauerhaft kostenlos:
- 0.5 GB Speicher
- 1 Projekt
- Unbegrenzte Abfragen

Bei ~39 Rows pro Abruf × 96 Abrufe/Tag × 365 Tage ≈ 1,4 Mio. Rows/Jahr — das liegt im kostenlosen Bereich.
