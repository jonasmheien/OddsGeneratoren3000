# OddsGeneratoren3000 – v41, 7. november 2026

## Hva var faktisk galt?

- Hovedutgaven i `state/active.json` / `site/data/today.json` var fortsatt datert 6. november etter 09:17 norsk tid 7. november. GitHub hadde ennå ikke registrert morgenjobben. GitHub Actions dokumenterer at planlagte jobber kan bli forsinket eller droppet. Dette er ikke en garanti om presis kjøretid.
- Forhåndsanalysen 7. november hadde eksempelvis to Stuttgart–Bremen, to Preston NE–Southampton og to Blackburn–West Ham. Feilen kom av ulike lagnavn/fixture-ID-er fra forskjellige leverandører.
- Frontend `visible-selection-v40.js` stolte på backendens allerede låste utvalg og filtrerte ikke eldre duplikate forhåndsutgaver. Markedsradaren manglet de samme sikre navnealiasene.
- `tomorrow-v24.js` viste en egen forhåndsvisning også på dagen som forhåndsutgaven gjaldt. Dette kan duplisere visningen, og er fjernet.

## Oppdateringens innhold

- `scripts/final_selection_v40.py`: eksplisitte, verifiserte leverandøraliaser. Kun ett aktivt valg per faktisk kamp, selv om kampene har ulike API-ID-er. Ingen fuzzy matching eller oppdiktede odds.
- `site/visible-selection-v40.js`: en **defensiv** duplikatsperre i visningen for eldre forhåndsdata; fortsatt *ingen* separat analyse eller nye tips i nettleseren.
- `site/market-radar-v39.js`: samme lagaliaser for å hindre doble markedsrader for samme kamp.
- `site/tomorrow-v24.js`: egen forhåndsseksjon vises ikke igjen på selve kampdagen.
- `.github/workflows/publish.yml`: tidligere morgenforsøk 09:07, fallback 09:17 / 09:37 / 10:17 / 11:17. Nye odds analyser kl. 13:17, 16:17 og 19:17 i tillegg. Lunsj- og kveldskjøringene bruker begrenset dekning på to sportsgrupper for å redusere API-bruk; morgenen og 16:17 bruker fire sportsgrupper. Resultatkontrollene hvert 10.–20. minutt er beholdt. Alle tidene er **Europe/Oslo** og GitHub kan forsinke kjøringer. `concurrency.queue: max` hindrer at hyppige statusjobber erstatter en ventende morgenanalyse.
- `.github/refresh-once-v15`: innført av installasjonen for å be om **én** ny dagsanalyse i første push etter installasjonen. Flagget er bygget inn i eksisterende workflow og skal fjernes av workflow når den behandles. Ved feil i datakilde kan en utgave fortsatt utebli, så kontroller workflow-status og dato i `site/data/today.json`.

## Viktig driftsbegrensning

Dette **garanterer ikke** oppdatering nøyaktig 09:17: GitHub Actions er en købasert tjeneste uten slik tids-SLA. Flere forsøk reduserer sjansen for en uteblitt analyse. For garanterte tidspunkter kreves en ekstern scheduler/trigger.

Flere oddsoppdateringer bruker mer kvote. Hvis ODDS_API_KEY-kvoten er lav, kan datautvalget bli mindre eller utebli. Det er derfor begrenset antall sportsgrupper på ekstra kjøringer, og vi har ikke lagt opp til kostbare oddsforespørsler hvert 10. minutt. Det kan dessuten være null kvalifiserte spill; ingen minimum fylles med svake kandidater.

## Installasjon

1. I GitHub Desktop: Fetch origin og Pull origin (synkroniser snapshots fra GitHub).
2. Pakk ut v41 ZIP i Nedlastinger.
3. I GitHub Desktop: Repository → Open in Terminal.
4. Kjør `python3 ~/Downloads/OddsGeneratoren3000_v41/INSTALLER_v41.py`.
5. Kontroller **`V41 PATCH INSTALLED AND TESTED`**. Installasjonen ruller tilbake på testfeil, slik at du ikke skal pushe en feilretting som ikke består lokaltestene.
6. Commit to main → Push origin. GitHub Actions vil kjøre full Python- og JS-test, deretter be om én ny analyse gjennom refresh-flagget.
7. Kontroller siste Actions-run og at `site/data/today.json` har riktig dato og ny `generatedAt`.

## Regresjonstester

- `tests/test_fixture_identity_v41.py`: 6 leverandøralias-par, bortfiltrering og avvisning av injisert duplikat.
- `tests/test_visible_selection_v41.cjs`: duplikatsperre for gamle publiserte forhåndsdata, ingen genererte odds.
- `tests/test_market_radar_v41.cjs`: leverandøraliaser i markedsradaren.
- `tests/test_morning_schedule_v41.py`: 09:07 erstatter dagens utgave, 09:17/10:17 gjentar ikke dataforespørsel, og workflow-skjemaet inneholder angitte tidspunkter.
- Gamle tester som antok *duplikat* kamper med fem forskjellige match-ID-er eller feil cache-versjon er oppdatert, uten å redusere testdekningen.


## Korrigering 7. november 2026

En eldre v35-test krever ni ligaer ved engangsoppdatering og normaldekning på fire ligaer. Den første v41-installasjonen overskrev denne funksjonen i stedet for å legge til `low_volume` for ekstrakjøringer. Korrigert versjon bevarer tidligere modus og lar 13:17/19:17 kjøre med to ligaer.
