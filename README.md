# OddsGeneratoren – gratis, automatisk start (v0.5)

**Ett sted for dagens fotballkamper.** Maks fem kuraterte spill, separat oversikt for «Safe Bets» og «High Risk». Ingen kupongbygger, ingen oppdiktede odds. Mobil og desktop.

## Nåværende status

Dette er en **fungerende kodebase for automatisering**, men ikke en aktiv livefeed før du selv har:
1. Opprettet to gratis API-nøkler.
2. Lagt nøkler i *GitHub Actions Secrets* i ditt GitHub-repository.
3. Aktivert *GitHub Pages*.

**Ingen API-kall med ekte nøkler er utført her.** Uten nøkler publiserer den en tom oversikt, ikke falske spill. Kodet og testet med syntetiske responsdata.

## 1. Opprett datanøkler (0 kr)

| Kilde | Formål | Direkte lenke |
|---|---|---|
| football-data.org | Kamper, historikk, lagform | https://www.football-data.org/ |
| The Odds API | Ekte odds fra tilgjengelige internasjonale bookmakere | https://the-odds-api.com/ |

**Viktig forveksling:** Bruk `the-odds-api.com` (bindestrek), **ikke** `theoddsapi.com`. Dette er to ulike tjenester. Gratisnivået hos sistnevnte dekker ikke fotball, mens **The Odds API med bindestrek** oppgir gratis 500 kreditter/måned på tvers av idretter. Dokumentasjon: https://the-odds-api.com/liveapi/guides/v4/. Denne koden er skrevet for `https://api.the-odds-api.com/v4`.

### Gratis-kvote

Én planlagt kjøring per dag (09:17 `Europe/Oslo`) med maks tre relevante ligaer og to markeder (`h2h` og `totals`) er dimensjonert for om lag **186 kreditter i en måned på 31 dager**, forutsatt leverandørens normale beregningsregel: 1 kreditt per marked × region per liga og kjøring. Kvoter og API-vilkår kan endres, så følg forbruket på leverandørens konto. Ingen automatiske ekstrakjøringer av odds bør brukes uten å vurdere kvoten. En manuell `workflow_dispatch` trekker også kvote.

football-data.org gratis: inntil 12 utvalgte konkurranser, 10 kall/minutt. **Ikke full dekning av Eliteserien, Allsvenskan og dansk Superliga**, og cupkamper og skader er heller ikke nødvendigvis med. Dette legges senere inn gjennom autoriserte leverandører.

## 2. Publiser med GitHub

1. Repository `jonasmheien/OddsGeneratoren3000` er opprettet, men prosjektfilene må lastes opp fra denne ZIP-pakken.
2. Åpne **Settings → Secrets and variables → Actions → New repository secret**. Lag nøyaktig disse to:
   - `FOOTBALL_DATA_API_KEY` = nøkkelen fra football-data.org
   - `ODDS_API_KEY` = nøkkelen fra **the-odds-api.com**
3. Åpne **Settings → Pages → Build and deployment**, velg **Source: GitHub Actions**.
4. Åpne **Actions → Oppdater OddsGeneratoren → Run workflow**. Kjør én gang og undersøk loggen.
5. Når jobben er grønn, finn adressen under **Settings → Pages**. Den vil vanligvis ligne `https://jonasmheien.github.io/OddsGeneratoren3000/`.

**Nøkler skal aldri** limes inn i `site`-filer, JavaScript, issues eller commits. De blir kun lest på GitHub-serveren under den planlagte kjøringen.

## 3. Hva skjer automatisk?

- 09.17 norsk lokal tid (også riktig ved sommertid) starter GitHub Actions. Jobbene kan bli forsinket av GitHub.
- Henter dagens kamper og inntil 75 dagers historikk for de opptil tre valgte ligaene fra football-data.org. Når CL-lag mangler formgrunnlag, forsøker den inntil 16 lagspesifikke oppslag på tvers av ligaer, hastighetsbegrenset for gratiskontoen.
- Velger inntil tre konkurranser med kommende kamper, henter markedsodds fra The Odds API.
- Matcher hjemmelag, bortelag og avspark (avviser usikre matcher).
- Beregner en **foreløpig, ikke-kalibrert** Poisson-modell basert på inntil seks registrerte siste resultater per lag.
- Viser Safe Bets ved minst 5 tidligere kamper per lag, vanlige tips ved minst 4, og High Risk ved minst 3. Krever fremdeles minst to oddsleverandører, odds yngre enn tolv timer og en foreløpig beregnet fordel. For CL forsøker modellen nå også å hente lagenes hjemlige ligakamper.
- Bygger en statisk `site/data/today.json` uten nøkkelopplysninger og publiserer den på GitHub Pages.
- Fjerner automatisk utdaterte kampvalg fra nettleseren når dagens dato eller odds blir gamle.

**Safe Bets** = normalt odds ≤1,50 med minst 5 registrerte kamper per lag; betyr ikke sikkert spill. **High Risk** = normalt odds ≥1,85, med minst 3 tidligere kamper per lag og et markert begrenset datagrunnlag dersom det er under 5. Kun H/U/B og over/under 2,5/over 3,5 er tilgjengelig når leverandøren har markedet. `Begge lag scorer` kan modelleres, men er **ikke** automatisk oddsdekket av gratis `h2h,totals` og blir derfor ikke foreslått i denne versjonen.

### Datakvalitet

- Det finnes ingen automatisk Vitibet-, Forebet- eller Norsk Tipping-integrasjon. Ingen åpne, autoriserte grensesnitt er verifisert. Filen `data/manual_predictions.csv` kan fylles ut manuelt med kildeangitte prognoser, når du har lov å bruke dem.
- Oddsene er **medianer av bookmakerpriser** fra internasjonale bookmakere, aldri kalt «Norsk Tipping». Mediansammenligninger garanterer ikke at en bookmaker tilbyr den viste prisen.
- Modellen er **ikke** validert med historisk backtesting eller skade-/lagoppstillingsdata. En foreslått modellfordel er ikke dokumentert spillverdi. Ingen tips er et legitimt dagsresultat.
- GitHub Pages er offentlig selv om du kun bruker portalen selv. Nøkler publiseres ikke, men tipssidens URL er ingen sikker privat tilgangskontroll.

## 4. Lokal test uten API-nøkler

Fra prosjektmappen:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_data.py
cd site
python3 -m http.server 8000
```

Åpne http://localhost:8000. Du får en korrekt tomtilstand uten nøkler. For å teste designet med **tydelig merket fiksjon**, bruk den separate HTML-forhåndsvisningen som følger leveransen.

## Prosjektstruktur

```
.github/workflows/publish.yml    # Kjører og publiserer én gang per dag
scripts/build_data.py           # Leverandørkall, kilde- og tidskontroll, kampmatching
scripts/recommend.py            # Kvalitetssil og topp fem
site/                           # Mobilvennlig nettportal
site/data/today.json           # Maskinlesbart snapshot, ingen nøkler
data/manual_predictions.csv    # Valgfritt kildeangitt manuelt bidrag
tests/                         # Enhetstester
```

## Andre versjon etter gratis oppstart

Utvid med godkjente kampdata for norsk/svensk/dansk liga, flere uavhengige prognosekilder, dokumentert backtesting og eventuell godkjent Norsk Tipping-oddsfeed. Ikke bruk uautorisert scraping som avhengighet.

## Daglig bruk

Åpne GitHub Pages-adressen og trykk **Oppdater**. Knappen henter det siste publiserte datasettet, og kjører **ikke** nye API-kall. GitHub oppdaterer analysen automatisk ca. 09.17 norsk tid; planlagte kjøringer kan være forsinket. Du kan også manuelt velge Actions → Oppdater OddsGeneratoren → Run workflow når du vil tvinge en ny analyse, men dette bruker API-kvoten.

**Viktig:** Inntil du har opprettet begge API-nøklene og slått på Pages, finnes ingen fungerende liveoppdatering. Kvalitetskravene kan gi 0 tips noen dager.

## Nettsidens utseende

Nettsiden viser kun «Dagens tips til Jonnern», «Dagens tips», «Safe Bets», «High Risk» og «Data og statistikk». Statistikk på hvert kort kan åpnes ved behov. Metode, API-dokumentasjon og forbehold hører hjemme i denne README-filen og vises ikke som lange tekstblokker på selve siden. Demo viser oppdiktede lag og priser og er tydelig markert «Eksempeldata».
