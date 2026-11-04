# OddsGeneratoren3000 v1.2 – Flere statistiske spillmarkeder

Dette er en **målrettet kodeoppdatering**, ikke en ny nettside og **ikke** en ny dagsanalyse. Design, state-filer, API Secrets og dagens lagrede tips beholdes. Neste automatiske dagsanalyse bruker den utvidede modellen.

## Nye betmarkeder

- Hele kampen: over/under 1,5 og 2,5 mål, over/under 3,5 mål og begge lag scorer når prissatt.
- Lagmål: hjemmelaget/bortelaget over 0,5 eller 1,5 mål når det finnes faktiske bookmakerodds med identifisert lag.
- Første omgang: over 0,5, over 1,5 og under 1,5 mål, **kun** når det finnes dokumenterte tidligere pauseresultater for begge lag og faktisk odds.
- Hjørnespark: støtte for over 8,5 og 9,5 er laget, men **deaktivert ved standardoppsett**. Den eksisterende gratis datakilden gir normalt ikke nødvendig fullstendig historikk med hjørnespark, og odds blir ikke bestilt før datatilgang er på plass. Legg ikke inn hjørnetips basert på antatte gjennomsnitt.

## Kvalitet og validering

- Hvert forslag krever bookmakerpriser, minst to bookmakere og gyldige historiske kamper.
- Større modellavvik mot implisert bookmakerpris underkjennes. Modellbaserte enkeltvinnere til odds over 4,00 blir ikke anbefalt av den enkle baseline-modellen. Dette fjerner for eksempel «11,18 på Slavia mot Arsenal» fra generatorens automatiske forslag.
- Motstridende utfall for samme kamp skal ikke vises som separate Safe og High Risk-forslag.
- Ved sluttresultat avregnes lagmål mot fulltid og 1.-omgangsmål mot faktisk `score.halfTime`. Manglende periode- eller hjørnestatistikk gir **Avventer**, aldri et påfunnet tap.

## Odds API og kvotekontroll

The Odds API har vanlige h2h-/totalsmarkeder og særskilte eventmarkeder. Tilleggsmarkedene krever én forespørsel per kamp og kan mangle i enkelte ligaer, bookmakerregioner og kontotyper. Vi ber om `btts,team_totals,totals_h1,alternate_totals` for et **lite antall** kvalifiserte kamper hver dag. Antallet begrenses av antatt kvoteforbruk (ca. 15 credits per dagsjobb); dette er en konservativ lokal øvre grense, **ikke** en garanti mot å nå kontokvoten. Restkvote under 35 stopper videre utvidelse i gjeldende kjøring.

Standard: opptil tre kamper for ekstramarkeder, men faktisk antall bestemmes av antall ligaer og budsjettet. Kilden for kampform er football-data.org; ekstra bookmakerodds kommer fra The Odds API.

Ønsker du hjørnespark senere: først koble til et lovlig, dekkende statistikk-API for tidligere hjørnespark; deretter kan `ODDS_CORNERS_ENABLED=1` brukes med et eksplisitt oppsett. Ikke aktiver uten historiske data.

Modellen er **ikke kalibrert eller backtestet**, og en estimert fordel er ingen garanti for overskudd. Et tomt utvalg er bedre enn tilfeldige spill.

## Installasjon

1. Last ned og pakk ut oppdaterings-ZIP.
2. Åpne GitHub Desktop, `Repository > Show in Finder`.
3. Kopier **de konkrete filene i pakken**, med samme undermappestruktur, til prosjektmappen og velg Erstatt ved spørsmål. Ikke slett `.git`, `state/active.json`, `state/history` eller `site/data/today.json`.
4. Commit «v1.2 utvidede statistiske spillmarkeder» og Push origin.
5. Push publiserer koden uten å starte en ny dagsanalyse. **Neste morgenanalyse** blir første kjøring av de nye markedene. Ekstramarkeder avhenger av reell API-dekning. Se GitHub Actions-logg `Built ...` og `COVERAGE ...`.

Verifikasjon lokalt: `python -m unittest discover -s tests -q` og `node --check site/app.js`.

**Utenfor scope:** Vitibet, Forebet og forumtips er ennå ikke integrert; denne endringen legger ikke til disse som kilder.
