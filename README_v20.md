# OddsGeneratoren v2.0 – første fungerende grunnlag

Denne pakken er en **målrettet oppdatering**, ikke et nytt komplett repository.

## Dette er implementert

- Ny kvalitetskontroll **etter** eksisterende kamp-/oddsinnhenting og spesialmarkedskontroll, **før** den aktive dagsutgaven lagres.
- Eliminerer den gamle «Safe Bet» snarveien der en favoritt kunne anbefales uten en modellbasert positiv verdi.
- Krav om ferske bookmakerpriser (maks. seks timer), relevante historiske resultater og positiv verdi **etter** en eksplisitt, pessimistisk justering av en ukalibrert modell.
- Alle støttede markeder konkurrerer om plass i én sortert anbefalingsliste. Fem første vises øverst, resten under «Flere kvalifiserte spill»; ingen kunstig maksgrense.
- Opptil to meningsfullt forskjellige tips per kamp. Motstridende/sterkt overlappende markeder filtreres ut.
- Safe Bet og High Risk er filtre i stedet for dupliserte hovedlister.
- Egne observasjoner, aldri forkledd som anbefalinger. Et marked uten statistisk signal blir ikke vist bare fordi oddsen finnes.
- Nye/eksisterende anbefalinger kan fortsatt avgjøres av eksisterende resultatrutine, fordi **alle** anbefalinger ligger i `recommendations`.
- Nytt skript `python scripts/backtest_v20.py` for en nøktern diagnostikk av historiske, avgjorte publiserte tips. Ingen nettverkskall.
- GitHub Actions kjører kontrollen **bare når en ny daglig analyse genereres**. En vanlig push republiserer fortsatt eksisterende dagsutgave.
- Den opprinnelige nettsiden fungerer fortsatt dersom v2-data ennå ikke finnes eller den nye visningen ikke kan lastes.

## Viktige forbehold

1. **Ingen dokumentert positiv forventet verdi ennå.** `conservativeEdge` er en *sensitivitetsberegning* med heuristisk justering mot marked og datamengde; det er **ikke** en validert sannsynlighet, statistisk konfidensgrense, påvist langsiktig fordel eller garanti.
2. **Ingen ny oddsleverandør er integrert.** Kildedekningen er fortsatt begrenset av eksisterende football-data.org og The Odds API. Gratisnivåene setter grenser for antall ligaer, kamper og spesialmarkeder. Manglende hjørnespark-/kortstatistikk skal fortsatt gi ingen anbefaling.
3. **Ikke live odds helt frem til kampstart ennå.** Resultatstatus kan oppdateres, men selve pre-match-analysen oppdateres ikke automatisk gjennom dagen. Dette krever ekstra, kuttede API-oppslag og versjonert anbefalingshistorikk som egen etappe.
4. **Automatiske kuponger er ikke aktivert.** Dagens leverandørdata inneholder bookmaker-medianer, men ikke bekreftede spillbare kombinasjonspriser fra én bookmaker. En kupongmotor uten dette ville vært misvisende.
5. **Ingen nye ekspertsider er automatisk koblet til**. Egen modell og tilgjengelige kilder holdes adskilt.
6. **Høyere krav kan gi færre eller ingen tips** sammenlignet med v1.6. Det er forventet når datagrunnlaget ikke tillater å underbygge verdi.
7. Små historiske utvalg kan ikke brukes som dokumentasjon for framtidig lønnsomhet. Diagnostikken merker utvalg under 100 avgjorte anbefalinger som utilstrekkelig.

## Installering uten å slette tidligere filer

1. Pakk ut ZIP-filen. **Ikke erstatt hele prosjekt-, `site`-, `scripts`-, `state`- eller `tests`-mapper.**
2. Åpne `OddsGeneratoren3000` via GitHub Desktop → `Repository` → `Show in Finder`.
3. Kopier **enkeltfilene** fra ZIP til nøyaktig disse stedene:

   - `.github/workflows/publish.yml` (erstatt denne enkeltfilen)
   - `scripts/quality_v20.py` (ny)
   - `scripts/qualify_v20.py` (ny)
   - `scripts/backtest_v20.py` (ny)
   - `site/quality-v20.js` (ny)
   - `site/quality-v20.css` (ny)
   - `site/index.html` (erstatt denne enkeltfilen)
   - `tests/test_quality_v20.py` (ny)
   - `README_v20.md` (ny, i prosjektets rotmappe)

   På Mac: `Cmd + Shift + .` viser skjulte `.github`-mapper.

4. Kontroller i GitHub Desktop at **ingen andre filer er markert som slettet**, spesielt ikke `scripts/build_data.py`, `scripts/lifecycle.py`, `site/app.js`, `site/data/today.json`, `site/data/history.json`, `site/assets/og-mark.svg` eller `state/active.json`.
5. `Commit to main` → `Push origin`. Under vanlig push vil workflow normalt **deploye eksisterende dagsutgave** og kjøre alle tester, men ikke konsumere nye bookmakerkreditter eller endre dagens tips.
6. Neste **daglige** analyse (09.17 Europe/Oslo) bruker v2-kvalitetskontrollen automatisk. Hvis du trenger ny dagsutgave samme dag, kan du selv åpne `Actions` → `Oppdater OddsGeneratoren` → `Run workflow` → `mode=daily`, `force_refresh=true`. Dette bruker API-kreditter og erstatter dagens aktive anbefalinger. Ikke kjør gjentatte ganger uten behov.

## Tester utført lokalt

- `python -m unittest discover -s tests -q`: 101 bestått i rekonstruert testmiljø inkludert 16 nye v2-tester. GitHub er endelig CI-fasit etter opplasting.
- `node --check site/quality-v20.js`: bestått.
- Test av YAML-parse og rekkefølgen i workflow: bestått.
- Lokal Chromium/Playwright: fem topptips, flere kvalifiserte, observasjoner, kategorifiltre, legacy-fallback og mobilbredde uten horisontal scrolling testet. Brukte **fiktive testdata**, ikke verifiserte live-odds.

## Videre utvikling av v2.0

1. Verifiser datatilgang/statistikk og kalibrer per marked med historiske tidsriktige data.
2. Implementer versjonerte anbefalinger og re-kvalifisering frem til kampstart innenfor faktisk gratis API-kvote.
3. Implementer spillbare doble og offensive kuponger først når bookmakeridentitet og tilbudte kombinasjonsodds kan verifiseres.
4. Utvid kampprogrammet utover ligaene som dagens football-data.org discovery dekker.

Pakken inneholder **ingen** `site/data/`, `state/`, API-nøkler, creds eller symlinker. Den oppdaterer ikke GitHub automatisk; du må selv publisere filene.
