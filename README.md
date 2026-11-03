# OddsGeneratoren3000 · v0.8

**Dagens tips til Jonnern** – mobilvennlig personlig analyse-dashboard.

## Hva denne versjonen gjør

1. Klokken **09.17 Europe/Oslo** hver dag forsøker GitHub Actions å produsere en ny dagsutgave fra football-data.org, The Odds API og eventuelt API-Football Predictions (hvis nøkkel er lagt inn). GitHub-planlagte jobber kan starte senere enn klokkeslettet.
2. Den publiserte **dagsutgaven lagres i `state/active.json` på main-grenen** og blir stående til neste vellykkede dagsanalyse. Det å åpne siden, trykke «Oppdater» eller gjøre en vanlig kodeendring skal ikke slette anbefalingene. Selv etter avspark, midnatt og utløpt pre-match-odds vises de opprinnelige tipsene og den opprinnelige oddsen.
3. Hver halvtime mellom 15.07 og 03.37 (norsk tid) forsøker en lett GitHub Actions-jobb å hente *offisielle kampresultater* fra football-data.org. **Den kaller ikke The Odds API**, så dette bruker ikke bookmakerkvoten. Når status eller sluttresultat endres, lagres en ny JSON og siden publiseres automatisk. Vunnet / tapt avregnes først ved FINISHED. Ved ekstraomganger brukes `regularTime` (90 minutter), og uavklart resultat forblir uavklart.
4. Ved neste vellykkede dagsanalyse oppdateres gårsdagens siste resultat én gang til og den forrige utgaven arkiveres i `state/history/YYYY-MM-DD.json`. Publisering av dagens nye tips er avhengig av at kampdata og odds ikke har en kritisk feil.
5. **Safe Bets** er markedsfavoritter eller modellkandidater, mens **High Risk** er høyere odds; kategoriene kan inneholde inntil fem hver. Det finnes **ingen kunstig minstefylling** eller oppdiktede odds.
6. Det nye designet er mørk burgunder med funksjonelle resultatchips, odds/kampkort og en kompakt statistikkoversikt. Ingen slagord eller lange disclaimere vises i toppområdet.

## Oppdater fra v0.7

1. På Mac: åpne GitHub Desktop → **Repository → Show in Finder**.
2. Kopier **innholdet** fra v0.8 ZIP-en inn i eksisterende `OddsGeneratoren3000`-mappe. Velg **Erstatt** for filer med samme navn. **Behold `.git`**. Husk at `.github` er skjult; `Cmd + Shift + .` i Finder viser den.
3. I GitHub Desktop: **Commit to main** og **Push origin**.
4. Ved push deployes **den lagrede dagsutgaven**, uten å gjøre en ny automatisk dagsanalyse. Før den første nye v0.8-utgaven finnes ennå ikke lagret `state/active.json`; nettstedet viser da det siste medfølgende datasettet fram til første dagskjøring. For å lage en ny utgave i morgen klokken 09.17, gjør du ingenting.
5. Du kan manuelt starte `Actions → Oppdater OddsGeneratoren → Run workflow` med valget `daily` for **ny utgave**, `results` for **oppdatere resultater**, eller `deploy` for **re-publisere eksisterende utgave**. Som sikker standard er `deploy` valgt. Ikke velg `daily` om kvelden når de fleste kampene allerede har startet.
6. Den første daglige jobben må få **Contents: write** (satt i workflowfilen) slik at den kan opprette `state/active.json`. Hvis repositoriets Actions-innstillinger overstyrer dette og jobben blir rød ved `git push`, gå til `Settings → Actions → General → Workflow permissions` og kontroller innstillingene, eller send feilloggen til ChatGPT. Ikke lim inn hemmelige API-nøkler i chatten eller filer.

GitHub Pages: `https://jonasmheien.github.io/OddsGeneratoren3000/`

## De faktiske kildene (ikke overdriv kildegrunnlaget)

| Kilde | Status | Bruk |
|---|---|---|
| football-data.org | Tilkoblet når `FOOTBALL_DATA_API_KEY` er lagt inn | Kamper, form, sluttresultat |
| The Odds API | Tilkoblet når `ODDS_API_KEY` er lagt inn | Bookmakerpriser og marked |
| API-Football Predictions | Valgfri, krever `API_FOOTBALL_KEY` | Uavhengig modell for enkelte tilgjengelige kamper |
| Vitibet | **IKKE tilkoblet** | Krever bekreftet tillatt programmatisk tilgang |
| Forebet | **IKKE tilkoblet** | Innhold er lisensiert; tillatelse trengs før automatisert kopiering/bruk |
| Forumsignaler, inkludert Reddit | **IKKE tilkoblet** | Reddit API har separat godkjenning / vilkår; skal ikke utgis for ekspertprognoser |

CSV-format for **manuelle, kildeangitte sannsynligheter** finnes i `data/manual_predictions.csv`. Det er ikke en automatisk Vitibet- eller Forebet-integrasjon. Manuelle kilder kan bare vises som faktiske kilder når de er lagt inn og validert. En mer komplett kildeplattform krever autorisert feed, kildefelter, kildeferskhet, prioritering og backtesting.

## Hva som fortsatt mangler for en dokumentert solid tipser

- Historisk backtesting, kalibrerte sannsynligheter, dokumentert yield/ROI og treffrate *per marked og kilde*.
- Flere datadekkede ligaer, bedre klubbmatching og en mer fullstendig markedsdekning (målspill, begge lag scorer, dobbel sjanse) med faktiske priser.
- Skader, forventede oppstillinger, hjem/borte-kontekst og relevant fersk laginformasjon.
- Lovlig lisensiert automatisk tilgang til Vitibet, Forebet og uavhengige ekspert-/forumsignaler.
- Resultathistorikk med aggregerte nøkkeltall på tvers av datoer. v0.8 arkiverer resultater, men presenterer ennå ikke en langtidsgraf på nettsiden.

## Tekniske merknader

- Snapshot er en **førkamp-vurdering**, ikke live odds. Visningens odds oppdateres ikke etter kampstart.
- Et *published* resultat for `FINISHED` kommer fra football-data.org. Forsinkede kildedata og ekstraordinære avregningsregler kan kreve manuell kontroll.
- `state/active.json` og `site/data/today.json` er offentlige fotballtips. API-nøkler ligger bare i GitHub Secrets.
- GitHub Actions `schedule` med `timezone: Europe/Oslo` støttes, men kjøringen kan forsinkes og er ikke en sanntids-server.
- `python3 -m unittest discover -s tests -v` kjører offline-testene. Ingen API-forespørsler gjøres fra testene.
