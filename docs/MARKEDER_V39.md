# OddsGeneratoren v39 — Flere spillmarkeder

Oppdatert 6. november 2026. Dette er en isolert frontend-/kategoritilpasning. Ingen API-nøkler eller nye eksterne datakilder.

## Hva v39 gjør

1. Utvider den eksisterende *markedsbaserte kandidatlisten* for Safe Bets fra hjemme-/borteseier til også over/under 2,5 og 3,5 mål. Eksisterende krav til odds 1,14–1,70, markedsanslag minst 58 %, korrekt motstående bookmakerlinje, antall bookmakere, fersk pris og modellmotstrid beholdes. Dette er fortsatt markedsbaserte **kandidater**, ikke beviste verdispill.
2. Beholder eksisterende High Risk-kandidater (1X2 og over/under 2,5/3,5) og backendkvalifisering urørt.
3. Legger til en egen **Markedsradar** under de eksisterende tipskategoriene. Kategorier med priser blir dynamiske: mål, begge lag scorer, mål i første omgang, lagmål, hjørnespark, kort og målscorere. Kategorier uten tilgjengelige priser vises ikke som falske aktive filtre.
4. Bruker kun publisert `today.json` / `tomorrow.json`, spesielt `additionalMarkets.watchlist`, `additionalMarkets.tips`, `observations`, `recommendations` og `matches[].odds`. Ingen ny innhenting fra oddsleverandør i nettleseren.
5. Bruker sannsynlighetsanslag kun hvis de eksisterer i backend. Oddspriser alene blir ikke markedsført som anbefalinger. **Kun `recommendations` som allerede har bestått konservativ verdikontroll kan merkes kvalifisert**. Ekstra `tips` som ikke ble godkjent av den strenge kvalifiseringen merkes «Ikke kvalifisert».
6. Skjuler kamper som har startet og feil dagsutgave; krever pris >1,01, minst én bookmaker, og max 12 timer gammel quote (6 timer for strengt kvalifiserte). Kravene for backend er uendret.
7. Viser ikke falske spillbar-knapper; registrert bookmakerodds merkes som slik, ikke livepris. For målscorer vises behovet for startoppstillingskontroll.
8. Integrerer med v37s søk og mobile/desktop-nav, i tillegg til automatisk lasting hvert 60. sekund og oppdateringsknappen.
9. Dersom samme kamp finnes med flere kjente navnevarianter i samme starttime, dedupliseres identiske markeder. Ukjente lagnavn merges ikke automatisk. Max 28 radarobjekter, distribuert over markedstypene for å unngå at målmarkeder dominerer alle treff.
10. Den aktive tre-kategori-pickeren og v34-arkivet bruker samme Safe-utvelgelse, derfor vil arkivering fremdeles beskrive nøyaktig det som vises. Den nye radaren er ikke inkludert i v34s arkiv over **tipsgenererte kategorier**, fordi de fleste radarobjekter kun er priser og observasjoner.

## Berørte filer

Oppdateres:
- `site/three-fields-v26.js`: målmarkedene inn i Safe-markedskandidater og eksplisitt markering av dagens JSON-utgave for radaren.
- `site/index.html`: innlasting av radarens JS/CSS.
- `.github/workflows/publish.yml`: kjør v39-kontroll i eksisterende frontendtestfase.

Legges til:
- `site/market-radar-v39.js`
- `site/market-radar-v39.css`
- `tests/test_market_radar_v39.cjs`
- `docs/MARKEDER_V39.md`

## Avgrensninger

Det er **ikke** opprettet nye statistiske kort-, hjørnespark- eller målscorermodeller. Disse markedene blir ikke fremhevet som kvalifiserte spill uten at den eksisterende backend faktisk kvalifiserer dem. Ingen kategoriterskler senkes. Målmarkedene O25/U25/O35/U35 vises i Safe-kategoriene som markedsbaserte kandidater med samme regelverk som eksisterende favoritter. Hovedmodellen er fortsatt ikke historisk kalibrert.

## Test og drift

Kjør `node tests/test_market_radar_v39.cjs` for syntetiske tester og `python3 -m unittest discover -s tests -q` for øvrige regresjonstester. Installasjonspakken kjører dette lokalt før commit. GitHub Actions kjører den nye Node-testen ved etterfølgende push. Push gir normalt en deploy av lagret JSON uten nye API-kall. Neste ordinære dagsanalyse oppdaterer datagrunnlaget.
