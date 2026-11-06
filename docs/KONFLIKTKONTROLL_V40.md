# OddsGeneratoren3000 v40: sentral konfliktkontroll

## Funnet i aktiv `main` 6. november 2026

`build_data.py` produserer foreløpige `recommendations`, `safeBets` og `highRisk`. Det har en hardkodet `incompatible`-kontroll mot utvalgte Over/Under-koder på *samme matchId*. `market_scan_v14.py` legger til spesialmarkedspriser og observasjoner. `score_consensus_v14.py` legger til kildebaserte prognoser. `qualify_v20.py` vurderer sannsynligheter og usikkerhetsjustert verdi, begrenser enkelte familiekombinasjoner etter samme match-ID og **nullstiller `safeBets`/`highRisk`**. Deretter velger `site/three-fields-v26.js` sine egne markedsbaserte Safe og High Risk-objekter. `capture_visible_v34.cjs` evaluerer deler av den samme frontendkoden for å rekonstruere historikk. Dette er ikke én autoritativ beslutning.

Den publiserte utgaven for 6. november hadde 46 kamper, 26 med bookmakerodds og null kvalifiserte `recommendations`. Frontenden viste likevel 2 Safe og 3 High Risk, der HSV–M'gladbach ble valgt som Safe to ganger med ulike kamp-ID-er. Markedsradaren viste også flere linjer for denne kampen. Dette er observerte feil, ikke en hypotese om andre kamper.

## Ny produksjonsflyt

```
football-data / Odds API / API-Football
 -> scripts/build_data.py (rå og modellbaserte kampkandidater)
 -> scripts/market_scan_v14.py (kildeprisede ekstra markeder)
 -> scripts/score_consensus_v14.py (kildeprognoser)
 -> scripts/qualify_v20.py (konservativ kvalifisering)
 -> scripts/final_selection_v40.py (ENDELGYLDIG valg, identitet, konfliktkontroll)
 -> scripts/lifecycle.py (kontroll og publisering)
 -> site/data/today.json (safeBets, highRisk, interestingObjects)
 -> site/visible-selection-v40.js (dato/avspark/formateringskontroll, INGEN sportslig nyvurdering)
    -> site/three-fields-v26.js (visning)
    -> scripts/capture_visible_v34.cjs (arkivering av akkurat det synlige utvalget)
```

`recommendations` beholdes for bakoverkompatibilitet og resultatsettling, men inneholder bare de kvalifiserte elementene som faktisk ble valgt i `safeBets`/`highRisk`. `observations` beholdes som analysegrunnlag. Ny `interestingObjects` er autoritativ liste for visning.

## Identitet og konflikt

`fixtureKey` baseres på Oslo-lokal kampdato og ordnede lagidentiteter, med kun forhåndsdefinerte, sikre navnealiaser for kjente forskjeller. Det brukes ikke bred fuzzy matching. `marketIdentity` inneholder familie, periode, linje, subjekt og utfall for 1X2, BTTS, ordinære totalmål, første omgang, lagmål, kort, hjørnespark og navngitte målscorere. Ukjente koder kan ikke kvalifiseres som aktive tips.

Den operative sikkerhetspolitikken er bevisst streng: **maksimalt ett aktivt objekt per kamp**, på tvers av alle kategorier. Dette forhindrer både direkte motstrid og usikker korrelasjon mellom ulike markeder uten å gi feilaktige inntrykk av statistisk uavhengighet. Også markedskandidater uten positivt kalibrert edge beskrives eksplisitt som kandidater og rangeres under backend-kvalifiserte objekter.

## Kategorier og sporbarhet

1. Backend-kvalifiserte med `conservativeEdge >= 0.02`, fersk bokmakerpris og kategori `safe` eller `high` går først.
2. Modellkandidater kan fylle High Risk uten å fremstilles som kvalifiserte verdispill.
3. Markedsbaserte favoritter/longshots kan fylle Safe/High når reelle, friske bookmakertilbud og ekstra kontroller finnes.
4. Interessante objekter kommer bare fra dokumenterte statistiske observasjoner og får aldri anbefalingsstatus av frontend.
5. Maks fem per kategori, ingen kunstig minimumsfylling. Ved færre enn tre vises forklaring i brukergrensesnittet.

`selectionId` er stabil hash av kamp- og markedsidentitet. `finalSelection.trace` dokumenterer valgte og undertrykte kandidater. Resultatet valideres før publisering. Et gammelt snapshot oppgraderes bare hvis det fortsatt er dagens utgave, uten API-kall. Eldre arkiverte utgaver endres ikke.

## Begrensninger og restrisiko

Kampaliaser er konservativt forhåndsdefinerte; andre leverandørnavn kan fortsatt gi duplikater fram til identiteten er kartlagt. Modeller og sannsynligheter er ikke dokumentert lønnsomme eller kalibrerte. To ulike fotballkamper mellom de samme lagene samme dag ville bli behandlet som én, bevisst konservativt; dette krever en entydig leverandørkobling hvis det skulle forekomme. Arkivposter fra før v40 endres ikke retroaktivt. `Markedsradar` viser bookmakerobservasjoner som eget, **ikke-anbefalt** materiale, nå høyst ett objekt per faktisk kamp for å unngå repetitive kort.

## Testing, publisering og rollback

`python3 -m unittest discover -s tests -q`, `node tests/test_visible_selection_v40.cjs`, `node tests/test_tip_audit_v34.cjs`, `node tests/test_market_radar_v39.cjs`. Installasjonsskriptet stopper og ruller tilbake på feil. Etter en godkjent installasjon: commit/push i GitHub Desktop og eventuelt `Actions -> Oppdater OddsGeneratoren -> Run workflow -> daily`, med `force_refresh=true` for ny analyse. Dette bruker eksisterende API-kvoter. Behold `.git`. Ingen endringer i API-nøkler eller secrets.
