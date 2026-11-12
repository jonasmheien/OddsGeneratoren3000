# OddsGeneratoren3000 v43 – landskamper

## Hva endres

* Landskamper oppdages automatisk med The Odds API v4 sine `/sports` og `/sports/{sport}/events`-endepunkter **før** betalte oddsforespørsler. Begge disse endepunktene bruker **0 odds-kreditter** ifølge leverandørens v4-dokumentasjon (kontroller vilkårene hvis de endres).
* Kun turneringer med reelle, fremtidige kamper på **den aktuelle Oslo-datoen** prioriteres. UEFA Nations League velges først når den har kamper den dagen. Høyest to landslagsturneringer brukes i samme kjøring. De resterende plassene brukes til klubbligaer, innenfor eksisterende `ODDS_SPORTS_PER_RUN` og kvotereserve.
* V43 registrerer Nations League, VM-kvalifisering Europa og Sør-Amerika, EM-kvalifisering, VM og EM. Turneringer er bare aktive når bookmakerleverandørens katalog og faktiske kamplister støtter dem. Vennskapskamper legges ikke inn før en dokumentert datakilde finnes.
* Odds fra eksisterende The Odds API-konto brukes uten ny API-nøkkel. Den eksisterende konservative utvelgelsen, konfliktkontrollen og publiseringsplanen videreføres.
* Nye diagnostikkfelter i `dataStatus`: `internationalDiscovery` (aktiv katalog, antall arrangementer og begrensninger) samt `internationalSportsSelected`. Aldri API-nøkler i diagnostikk.

## Kvalitetsgrenser

En kamp fra The Odds API er kun et ekte oddsnotert arrangement. Det lages **ikke** historiske landslagsresultater, fiktive ekspertprognoser eller en sannsynlighetsmodell fra lagets navn. Med manglende formdata kan modellen bare behandle faktiske bookmakerpriser etter de eksisterende kravene, uten å hevde at markedsestimerte sannsynligheter dokumenterer positiv verdi.

VIKTIG: For kamper som bare har `odds:`-kamp-ID, støtter ikke dagens automatiske resultatavstemming nødvendigvis sluttresultat. Disse spillene kan derfor bli stående med `unverified/scheduled` til en verifisert resultatkilde er integrert. Dette endres ikke i v43 og skal løses i en egen oppdatering, med kontroll på API-kvoter.

## Testing og publisering

`python3 -m unittest discover -s tests -q` kjører alle eksisterende og nye Python-tester. JavaScript-testene kjøres også av installasjonsprogrammet. Testene bruker syntetiske sports-/arrangementssvar og **ingen** ekte API-kreditter. Programmet tilbakestiller alle endrede filer om en test mislykkes. V43 endrer ikke GitHub Actions-tidsplan, hemmeligheter eller dagens publiserte datagrunnlag ved installasjon; nye kamper dukker opp først etter neste vellykkede analyse.

Offisielle kilder: <https://the-odds-api.com/liveapi/guides/v4/> og <https://the-odds-api.com/sports-odds-data/sports-apis.html>.

## Landslagsform og kvalifisering fra v48

Dagsanalysen og forhåndsanalysen henter én offentlig [resultatfil](https://github.com/martj42/international_results) når det er landskamper i utvalget. Filen publiseres av Mart Jürisoo, som oppgir CC0 for datasettet. UEFA-lag kobles med forbundskoder og eksplisitte navnevarianter. Resultater fra de fem siste verifiserte kampene vises per lag. Kilde og siste tilgjengelige resultatdato står i analysens diagnostikk.

Landslagsmodellen bruker inntil 548 dagers historikk. En kamps vekt halveres etter 270 dager, og treningskamper får 70 prosent av vekten til en tellende kamp av samme alder. Vektene brukes både i målanslag og i kvalitetskontrollens utvalgsstørrelse. CSV-filen inneholder sluttresultat med eventuelle ekstraomganger, så inntaket avgrenser turneringene til kjente liga- og gruppespill. Dato uten avsparkstid behandles som dato; resultater fra analysedagen brukes ikke. Ved feil i CSV-kilden fortsetter analysen med tilgjengelig form fra de andre kildene.

I en datoordnet prøve ga 548 dager noe bedre treffsikkerhet på kampresultat enn 365 dager ved samme vekting, både på 70 felles VM-gruppekamper og på 104 Nations League-kamper. Dette var en kontroll av sannsynlighetsanslag mot faktiske resultater. Historiske odds manglet for den sammenligningen.

Kvalifiserte spill rangeres på beregnet verdi i det konservative scenarioet, med ett spill per kamp. De fem øverste vises først. Begge lag scorer og lagmål kan kvalifiseres når modellen har grunnlag og relevante, ferske priser finnes i den ordinære oddshentingen.

Kjør **Oppdater OddsGeneratoren** på **main** med **daily** og **force_refresh** for å beregne dagens utgave på nytt etter installasjon. Bruk **tomorrow** for en separat forhåndsanalyse.

### Motstanderjustert landslagsmodell i v49

Landslagsanalysen estimerer nå hvert lags angrep og forsvar samlet på tvers av motstanderne i de 548 dagene med historikk. Den bruker de samme vektene for alder og treningskamper som før. Modellen estimerer hjemmefordel fra kampene og tar hensyn til kjent nøytral bane. Sannsynlighetene for kampresultat og mål bygger på hvor mange mål modellen forventer per lag.

I den datoordnede kontrollen av 104 Nations League-kamper falt Brier-feilen på kampresultat fra 0,606 til 0,545. I en ny kjøring med de 54 lagrede prisene for 12. november 2026 passerte ingen spill det eksisterende verdifilteret. Sammenligningen på historiske kamper målte prognosefeil mot utfall.
