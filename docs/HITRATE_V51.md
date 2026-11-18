# Treffprosent og resultatoppfølging

`site/data/hitrate-v51.json` viser livslang statistikk per kategori. Datagrunnlaget er `state/hitrate-v51.json`, som fylles fra de eksisterende synlighetsjournalene i `state/tip-audit-v34/`.

Et tips må være arkivert før kampstart. Vi legger ikke til historiske kandidater som mangler slik dokumentasjon. Historikken starter ved første tilgjengelige synlighetsjournal, ikke nødvendigvis prosjektets første dag.

Identiteten består av lokal kampdato, begge lag i riktig rekkefølge og eksakt marked. Et tips som blir publisert flere ganger, skifter leverandør-ID eller flyttes mellom kategorier, telles én gang. Første publiserte kategori og odds beholdes. Endrede og fjernede tips forblir i statistikken. Forskjellige markeder som faktisk ble vist for samme kamp historisk, beholdes som forskjellige tips.

Treffprosent er `vunnet / (vunnet + tapt)`. Ventende, uavklarte, utsatte og annullerte tips er ikke med i nevneren. En kategori uten avgjorte tips viser «Ingen avgjorte». Interessante objekter følges separat som observasjoner.

Resultater kobles mot football-data.org, Sportmonks og UEFA. Leverandør-ID-er kan bare kobles via begge lagenes identitet, lokal dato og kampstart innen én time. Usikre koblinger eller motstridende sluttresultater avvises. UEFA-adapteren leser eksplisitt ordinær spilletid; totalscore etter ekstraomganger erstatter aldri 90-minuttersresultatet. Markeder uten nødvendig periode-/hendelsesstatistikk forblir uavklart. Resultatoppfølgingen bruker ingen odds-kreditter.

Tidligere utgaver kontrolleres også etter at en ny utgave er publisert. De siste sju dagene følges løpende. Eldre uavklarte tips kontrolleres i små dagsgrupper og høyst én gang per dag for å begrense API-belastning. Verifiserte utfall blir ikke slettet når en kilde midlertidig mangler data.

Oppdateringsjobben finnes bare i `.github/workflows/publish.yml`. To identiske kopier er deaktivert gjennom GitHub Actions. Workflow-filer lastes opp direkte av eieren og endres ikke av installerjobben. En bekreftet tom oddskatalog utsetter publiseringen, bevarer forrige utgave og lar neste automatiske forsøk fortsette. Manglende nøkler, mislykket kataloghenting og faktiske kildefeil godkjennes fortsatt ikke som en ny dagsutgave.

Validering: `python -m unittest discover -s tests -v`, frontendtestene i `tests/*.cjs`, samt mobil- og skrivebordsvisning av resultatkort, filtre og tipslogg.
