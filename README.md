# OddsGeneratoren3000 · v0.7

Et personlig dashboard for **Dagens tips til Jonnern**, med dagens prioriterte tips, Safe Bets, High Risk og kildebasert statistikk.

## Hva er live i dag?

- **football-data.org** for kamper, historikk og lagform (Actions secret `FOOTBALL_DATA_API_KEY`).
- **The Odds API** for bookmakerodds (Actions secret `ODDS_API_KEY`).
- Enkel, **ukalibrert** Poisson-baseline og separate kvalitetsregler for Safe Bets og High Risk.
- GitHub Actions bygger og publiserer siden automatisk hver dag klokken 09.17, Europe/Oslo. «Oppdater» på nettsiden leser **siste publiserte analyse**, det kjører ikke en ny modell.
- Valgfritt: **API-Football Predictions** med secret `API_FOOTBALL_KEY`; koden forsøker å hente opptil 10 uavhengige kamp-prognoser per dag. Krever registrering hos API-Football, tilgang for kampene på din plan og godkjent navne- og tidsmatching. Uten nøkkelen kjøres ingen kall.
- `data/manual_predictions.csv` støtter kildeangitte eksterne prognoser **når de føres inn manuelt**.

## Hva er IKKE koblet til ennå?

Vitibet, Forebet, menneskelige ekspertprognoser og diskusjonsforum har **ikke** et aktivt, automatisk datauttak i denne versjonen. Ikke anta at de er konsultert bare fordi navnet «Ekspert» brukes på nettsiden. For automatisk uttak må vi finne en støttet API/feed med tilgang og vilkår som tillater bruk, teste matching og logge kilder med publiseringstid. Foruminnlegg skal kun fungere som indikasjon på sentiment, aldri som kalibrert sannsynlighet.

## Mål og kvalitet

Mål: **3–5 Safe Bets og 3–5 High Risk** på dager med tilstrekkelig dokumenterte kandidater. Det er **ikke en kvote vi fyller ved å finne på råd eller slakke på kvalitetskrav**. Enkelte dager kan vise 0–2. Dette vises tydelig i dashboardets kilde- og dekningsstatistikk.

Safe Bets = favoritter støttet av ferske markedspriser, eller sterkere modellgrunnlag; ikke «sikre» utfall. High Risk = høyere odds, med tydeligere usikkerhet. Oddsene er bookmaker-medianer fra The Odds API, ikke liveodds fra Norsk Tipping. Det er ikke vist en dokumentert positiv forventningsverdi; modellen er ennå ikke historisk backtestet.

## Publisering

1. Kopier prosjektets filer og mapper til roten av den eksisterende `OddsGeneratoren3000`-mappen. **Ikke slett `.git`**. `site/index.html`, `site/styles.css`, `site/app.js` og alle filer i `tests` må være med.
2. I GitHub Desktop: Commit to main → Push origin.
3. Valgfritt: opprett gratis API-Football-konto og legg nøkkelen som secret `API_FOOTBALL_KEY` for en ekstra automatisk prognosekilde.
4. GitHub → Settings → Pages: velg **GitHub Actions**.
5. GitHub → Actions → **Oppdater OddsGeneratoren** → Run workflow (bruke API-kreditter). Kontroller at både build og deploy er grønne.
6. Åpne `https://jonasmheien.github.io/OddsGeneratoren3000/`.

Ingen nøkler må lagres i repoet. Bruk bare GitHub Actions Secrets for API-nøkler.

## Utvidelser når kildene er på plass

1. Kildeadapter for Vitibet/Forebet når vi har avklart dokumentert dataadgang og betingelser.
2. Strukturert ekspert-feed med publisert tidspunkt, kilde-URL og historisk treffsikkerhet.
3. Forumsignaler med kilde, tidspunkt og manuell eller lisensiert innsamling, tydelig at dette er meninger.
4. Dokumentert backtesting, sannsynlighetskalibrering og evaluering av prisforskjeller.
5. Bedre ligadekning, samt kontroll av hvor mange kamper som er priset og har formgrunnlag.

Kjør lokale tester: `python3 -m unittest discover -s tests -v`.
