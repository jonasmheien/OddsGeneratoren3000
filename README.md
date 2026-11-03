# OddsGeneratoren3000 v1.1 · Pålitelig morgenanalyse

Denne oppgraderingen prioriterer **daglig generering av kildebaserte oddsforslag**. Designet og alle eksisterende funksjoner fra v1.0 er beholdt.

## Hva som er rettet

- Kandidat-analysen bygges i en egen, midlertidig `state/.candidate.json` før den publiseres. Den kan ikke overskrive de lagrede tipsene hvis API-kall eller validering feiler.
- En utgave med kommende kamper, men **null matchede bookmakerodds**, blir avvist. GitHub-jobben blir rød med en tydelig feilmelding, i stedet for å publisere «0 tips» som om analysen fungerte.
- Ekte data og gyldige odds kan fortsatt resultere i **0 kvalifiserte tips**. Det er et screeningsresultat, ikke en feil, og vi fyller ikke på med oppdiktede spill.
- Planlagt morgenanalyse kl. 09.17 norsk tid, og reserveforsøk kl. 10.17 og 11.17 bare hvis dagens utgave mangler. GitHub Actions kan starte sent.
- Dagsutgaven låses. Nye kjøringer samme dag beholder de opprinnelige oddsene og valgene (med mindre eksplisitt `FORCE_REPLACE_EDITION=1` konfigureres, noe som normalt ikke skal brukes).
- Hvis `state/active.json` forsvinner, gjenopprettes den fra en tidligere *gyldig og låst* `site/data/today.json`. Uferdige eksempeldata behandles aldri som en ekte analyse.
- Resultat-/historikkfiler tas med i GitHub-commiten slik at historikken blir varig.
- Loggene viser kampdekning, oddsdekning og hvor mange forslag som ble funnet.

## Oppdatering fra v1.0

1. Pakk ut ZIP-pakken og kopier **innholdet** inn i repo-mappen via GitHub Desktop. Velg Erstatt for eksisterende kodefiler.
2. **Ikke slett** `.git`, `state/active.json`, `state/history/`, `site/data/today.json` eller `site/data/history.json`. Denne oppdateringspakken inneholder **ikke** disse produksjonsdatafilene.
3. Commit og Push i GitHub Desktop.
4. En `push` oppdaterer kun nettsiden. Neste dagskjøring gir en ny analyse. Dersom du vil kjøre en morgenanalyse manuelt, velg `daily` i Actions → Oppdater OddsGeneratoren, mens det fortsatt er kommende kamper den dagen.

## Kildebegrensninger

Football-data.org gir kamp- og formdata. The Odds API gir odds. Eventuell API-Football Predictions krever egen nøkkel. Vitibet, Forebet og forumkilder er **ikke** automatisk integrert. Ingen del av koden dokumenterer positiv forventningsverdi eller garanterer 3–5 forslag per kategori. For det kreves mer komplett datadekning og historisk evaluering.

## Validering

`python -m unittest discover -s tests -v` kjører offline-testsuiten, inkludert feilbehandling og datasikkerhet. **Reelle API-nøkler kan ikke testes lokalt av ChatGPT** fordi de er lagret i GitHub Secrets. Den neste daglige Actions-kjøringen er nødvendig for å bekrefte virkelig datadekning.
