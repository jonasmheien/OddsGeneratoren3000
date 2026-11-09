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
