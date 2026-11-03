# OddsGeneratoren3000 v1.0 · Pro interface

**Dagens tips til Jonnern** – komplett statisk nettside med daglig låst analyse, live-resultatoppfølging og historikk.

## Nytt i v1.0

- Egen, original **OG-logo** som lokalt SVG-ikon og favicon (`site/assets/og-mark.svg`). Ingen tredjeparts logo ble kopiert.
- Ny designprofil: mørk grafitt, Krypton-inspirert grønt og Swedish Gold-inspirert gull. Premium kampkort med tydelig odds og responsive mobilkort.
- **Klubb-badges** laget av initialer som fungerer for alle lag. Fotball-API-et leverer også `crest`/`emblem`-adresser; de lagres som metadata og kan vises *hvis brukstillatelse er ordnet* (se under).
- **Kampdetaljer** kan åpnes både på Dagens tips og i Safe Bets / High Risk, med sannsynlighetskilde, bookmakergrunnlag, lagform og reelle kildeangitte prognoser der de finnes.
- **Live nå** er kun synlig når minst én anbefalt kamp faktisk har live-status. Viser klubber, løpende resultat, kampminutt hvis levert, og alle anbefalte spill på kampen. Ved overmål/BTTS vises progresjon – aldri forhåndsavregning som Vunnet.
- **Resultater** vises bare når minst ett tips er avregnet. En kompakt oversikt leser de siste arkiverte utgavene, uten å telle samme kamp/spill flere ganger fra ulike kategorier.
- Ingen generiske dekningsvarsler eller meningsløst statistikkpanel på forsiden.

## Slik oppdaterer du GitHub Pages

1. Pakk ut ZIP-filen.
2. GitHub Desktop → **Repository → Show in Finder**.
3. Kopier **innholdet** fra ZIP-mappen inn i eksisterende `OddsGeneratoren3000`-mappe. Velg **Erstatt** for eksisterende filer. **Ikke slett `.git`, `state/active.json` eller `state/history/`**, som inneholder ekte dagsutgaver og historikk. `.github` er skjult i Finder, vis med `Cmd + Shift + .`.
4. GitHub Desktop → **Summary:** `Upgrade OddsGeneratoren to v1.0 Pro` → **Commit to main** → **Push origin**.
5. Se etter grønne `build` og `deploy` på [GitHub Actions](https://github.com/jonasmheien/OddsGeneratoren3000/actions). Åpne [nettsiden](https://jonasmheien.github.io/OddsGeneratoren3000/) og gjør en hard refresh ved behov.

En **push** distribuerer designet og gjenoppretter gjeldende lagrede dagsutgave; den kjører **ikke ny oddsberegning**. Den nye dagsanalysen skjer ved neste vellykkede planlagte kjøring kl. 09.17 (Europe/Oslo), eventuelt ved manuelt `Run workflow` → `daily`. Starter du `daily` sent etter kampstart, kan dagen bli stående uten kvalifiserte tips.

## Live- og resultatlogikk

- GitHub Actions henter kampstatus fra **football-data.org** omtrent hvert 10. minutt 16.00–23.59 og hvert 20. minutt 00.00–02.59 norsk tid. Planlagte jobber kan bli forsinket.
- Når HTML-siden er åpen, sjekker nettleseren den **publiserte** JSON-filen hvert minutt. Den har aldri tilgang til API-nøklene, og dette er **ikke et push-basert sanntidssignal**.
- Vunnet/tapt krever offisiell `FINISHED` og tilstrekkelig grunnlag. Kampresultat i ekstraomganger avregnes med `regularTime` når kildefeltet finnes, ellers står markedet som uavklart.
- Den lagrede dagsutgaven er fast frem til neste vellykkede dagsanalyse. Odds og tips blir ikke erstattet av en resultatoppdatering.
- Ved nytt døgn arkiveres forrige utgave i `state/history/`. `site/data/history.json` genereres fra avregnede kamper, med deduplisering av samme spill.

## Klubblogoer og rettigheter

**Viktig:** Football-data.org API v4 leverer `homeTeam.crest`, `awayTeam.crest` og `competition.emblem`, men leverandørens vilkår, punkt 9.2, sier at disse grafikkene er opphavsrettslig beskyttet og at brukstillatelse må innhentes fra de respektive rettighetshaverne. En GitHub Pages-side er offentlig, selv om den er ment til personlig bruk.

Derfor er **ekte klubblogoer av som standard**. Den gjennomførte fallback-visningen bruker klubbinitialer. Når du har nødvendig tillatelse, kan du opprette en GitHub Actions *repository variable* `SHOW_LICENSED_CRESTS=1` under Settings → Secrets and variables → Actions → Variables. Deretter vil *neste dagsanalyse* merke nye anbefalinger med godkjente eksterne logo-URL-er og frontend vil vise dem, bare fra kildedomener `crests.football-data.org` og `upload.wikimedia.org`. Ikke sett denne variabelen uten å ha avklart rettighetene.

## Datakilder

| Kilde | Status |
| --- | --- |
| football-data.org | Tilkoblet hvis `FOOTBALL_DATA_API_KEY` finnes, for kamper, historikk og score |
| The Odds API | Tilkoblet hvis `ODDS_API_KEY` finnes, for bookmakerpriser |
| API-Football Predictions | Valgfri med `API_FOOTBALL_KEY`, tilgang avhenger av abonnement |
| Vitibet / Forebet / Reddit / ekspertfora | **Ikke automatisk integrert**. Krever tillatt tilkobling og pålitelige data |

Modellen er ikke ferdig backtestet eller kalibrert. Ingen antall Safe Bets/High Risk kan garanteres uten å dikte opp kandidater. Designendringen gjør ikke analysen mer treffsikker i seg selv.

## Test og forhåndsvisning

```bash
python3 -m unittest discover -s tests -q
node --check site/app.js
```

- `forhandsvisning.html` i ZIP-filen er en **fungerende offline-demo** med oppdiktede kamper/utfall; den bruker ingen API-forespørsler.
- `site/` er den faktiske nettsiden, med relative filer for GitHub Pages.
- Illustrasjonsskjermbilder følger separat, ikke som faktiske kampanbefalinger.
