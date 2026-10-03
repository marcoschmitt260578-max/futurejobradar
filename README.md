# Future Job Radar

Jobs that don't exist yet. Part fact, part fiction, all imagination.
Live: https://futurejobradar.com · Edited by Marco Schmitt (eventm.com)

## So funktioniert es

- `docs/jobs.json`: alle Jobs, Scans, Berufe-Zuordnung und die Cover-Story (die einzige Datenquelle)
- `scripts/page_body.html`: die Magazinseite
- `scripts/build_site.py`: baut daraus `docs/index.html`, eine Teilen-Seite pro Job (`/jobs/<id>/`) mit eigenem LinkedIn-Vorschaubild (`/og/<id>.png`), sitemap und robots
- `scripts/weekly_scan.py`: die wöchentliche Recherche mit Claude und Websuche. Sie fügt 3–5 neue Jobs hinzu, verschiebt bestehende Jobs bei klaren Belegen und schreibt einen deutschen Bericht nach `reports/scan-NNN.md`
- `.github/workflows/site.yml`: läuft jeden Montag um 06:50 Uhr (Kapstadt). Der Workflow recherchiert, baut die Seite, speichert die Daten und veröffentlicht auf GitHub Pages. Er läuft auch bei jeder Änderung auf `main`, dann ohne Recherche.

## Einmalige Einrichtung

1. **Secret:** Unter Settings → Secrets and variables → Actions → New repository secret einen Eintrag `ANTHROPIC_API_KEY` mit deinem Key von console.anthropic.com anlegen.
2. **Pages:** Unter Settings → Pages → Source „GitHub Actions“ auswählen.
3. **Domain:** Unter Settings → Pages → Custom domain `futurejobradar.com` eintragen und danach „Enforce HTTPS“ aktivieren.
4. **DNS bei IONOS** für futurejobradar.com setzen:
   - A-Records für `@`: 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153
   - CNAME für `www`: `<dein-github-name>.github.io`
5. **Umleitung:** jobsthatdontexistyet.com bei IONOS per Weiterleitung auf https://futurejobradar.com zeigen lassen.
6. **Erster Lauf:** Unter Actions → „Weekly scan & publish“ → Run workflow starten.

## Optional

- **Modell:** Unter Variables `SCAN_MODEL` setzen. Standard ist `claude-sonnet-5-5`.
- **Kosten:** Ein Scan kostet grob unter 1 $ (Tokens plus Websuche, 10 $ pro 1.000 Suchen).
- **Manuelle Änderungen:** `docs/jobs.json` direkt auf GitHub bearbeiten. Nach dem Speichern wird die Seite automatisch neu gebaut.
