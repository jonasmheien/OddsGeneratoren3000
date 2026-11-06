# V38: Sporbar kampform i «Vis analysen»

## Grunnlag og begrensning

Før v38 hadde `site/data/today.json` bare `formHome` / `formAway` som W/D/L-tekster. Motstander, hjemmelag/bortelag, score, dato og kildereferanse var ikke bevart i det publiserte snapshotet. Historiske bokstaver kan derfor ikke etterprøves fra gamle JSON-filer. Ingen historiske resultater er gjettet eller reparert retroaktivt.

## Datakjede

`football-data.org` / `API-Football` / `football-data.co.uk` → eksisterende datainnhenting og ID-kobling i `scripts/build_data.py`, `form_bridge_v27.py`, `form_bridge_v30.py`, `expanded_sources_v23.py` → `scripts/form_history_v38.py` → `matches[].formMatchesHome/Away`, `matches[].formHome/Away`, `matches[].model` i `today.json` → `site/three-fields-v26.js` → «Vis analysen».

Ny normalisering skjer etter innhenting, uten nye API-kall. Bare kildemerkede `FINISHED`-kamper med gyldig regulært sluttresultat og eksakt, leverandøravgrenset lag-ID tas med. Kildenavn, kamp-ID, dato, hjemme/bortenavn og sluttresultat lagres i hver historikkpost. W/D/L og modellen bruker den samme dedupliserte historikken.

Ved `EXTRA_TIME` og `PENALTY_SHOOTOUT` kreves eksplisitt `score.regularTime`. `score.fullTime` brukes ikke som erstatning når 90-minuttersresultatet mangler. Kamper over 180 dager gamle, fremtidige, uten score eller med tvilsom score utelates. Kjente kolliderende kampoppføringer avvises med `score_conflict`. Eksakte duplikater slås sammen med `duplicate_merged`. Ukjente linker til bookmakeroppdagede lag aksepteres ikke uten bekreftet navn fra lagets historiske poster (`team_match_uncertain`).

Nye felter i `matches[]`:

- `formMatchesHome` / `formMatchesAway`: inntil fem visbare historiske kamper for det aktuelle laget; full hjemme-/borterekkefølge med tall fra kilden.
- `formHistoryDiagnostics`: antall verifiserte, antall visbare, maskinlesbare problemkoder per side.
- `formHome` / `formAway`: eksisterende historiske formstrenger opprettholdes for bakoverkompatibilitet.
- `model`: eksisterende Poissonmodell med uendrede kvalitetsgrenser; beregningsgrunnlaget er de korrigerte, dedupliserte faktiske kampene.

Visning: «Siste fem kamper · alle arenaer». `HJEMMELAG` og `BORTELAG` angir det laget som evalueres i *dagens kamp*, mens `Hjemme` og `Borte` på historiske rader angir spillestedet for den konkrete historiske kampen. Score vises alltid i faktisk hjemme-/borterekkefølge. S/U/T beregnes fra laget under analyse. Ingen fiktive rader.

Gamle dagsutgaver som mangler `formMatchesHome/Away` beholder den gamle formstrengen, men merkes tydelig med at kampdetaljene ikke kan verifiseres. Dersom en ny-format utgave ikke har fullstendige historiske lagnavn, viser UI mangel på verifiserbare kampdetaljer i stedet for å finne på navn.

## Driftsfrekvens

Normal dagskjøring produserer nye `formMatches` automatisk når kildene leverer oppdaterte fullførte kamper. Hovedkildens ligahistorikk hentes ved daglig analyse. Football-data.co.uk har fortsatt konservativ 96-timers cache av hensyn til kildevilkår. Dette kan forsinke ny form fra denne supplerende CSV-kilden, men pakken endrer ikke kvote eller API-forbruk. Dagens allerede publiserte JSON får ikke nye formfelter før en **ny dagsanalyse** etter kodepublisering; en ren Pages-deploy kan ikke fylle dem.

## Sikkerhet og avgrensning

- Ingen API-nøkler, nye integrasjoner, SQL eller betalte tjenester.
- Ingen modifikasjoner av Safe/High/Interessante-grenser.
- Ingen overskriving av `state/`, `site/data/today.json` eller historikk.
- Kildene er ikke uavhengig kontrollert mot live API-responser i denne kildekodebaserte gjennomgangen; de faktiske nye radene må kontrolleres etter en ny dagskjøring.
- Det er ikke etablert en fullverdig universell kryssreferanse mellom klubb-ID-er hos alle leverandørene. Usikre koblinger avvises heller enn å bli vist.

## Test og publisering

Installasjonsskriptet krever ren arbeidskopi, kjører eksisterende Python- og JavaScript-tester før og etter endringen, i tillegg til v38-testene. Ved feil rulles alle modifiserte filer tilbake. Publisering skjer først etter lokal `Commit to main` og `Push origin`, og deretter vellykket GitHub Actions/Pages. Det kan være nødvendig med en manuell `daily`-kjøring for å få formdetaljer umiddelbart; dette vil bruke ordinær API-kvote.
