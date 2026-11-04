# OddsGeneratoren v2.1 – modell- og forklaringsrettelse

Dette er **en målrettet reparasjon** på et allerede oppdatert v2.0-repo. Den er ikke et nytt komplett repository.

## Slik installeres den (Mac / GitHub Desktop)

1. Pakk ut ZIP-filen. Dobbeltklikk **`KJOR_OPPDATERING.command`**. Programmet forsøker å finne OddsGeneratoren3000 i den vanlige GitHub Desktop-mappen. Dersom det ikke finner prosjektet, kan du dra prosjektmappen fra Finder inn i Terminal-vinduet.
2. Når du får **KLART: Alle tester bestått**, åpne GitHub Desktop, kontroller at **ingen prosjektfiler er slettet**, velg **Commit to main** og **Push origin**.
3. Den neste pushen ber automatisk om **én ny analyse av samme dag**. Det er fordi installereren lager `.github/refresh-once-v15`, som workflowen allerede kjenner. Hvis dagens API-kvote er tom, kan kjøringen feile uten å hente nye tips.

**Alternativ:** Hvis macOS blokkerer `.command`-filen, kan du høyreklikke og velge Åpne. Eller kopier pakkens enkeltfiler inn i prosjektet (ikke hele mapper), åpne Terminal i prosjektmappen og kjør `python3 install_v21.py`.

**Viktig:** Hvis installasjonen rapporterer feil, **ikke push**. `site/data/today.json` og `site/data/history.json` er ikke inkludert og skal ikke endres manuelt.

## Hva som faktisk endres

- Mer historikk: opptil 16 kamper per lag, hentet fra et vindu på opptil 180 dager der API-et støtter det.
- En forsiktig motstanderjustering basert på observerte, fullførte kamper. Uten tilstrekkelig data beholdes opprinnelige kampresultater ujustert.
- En **effektiv utvalgsstørrelse** som diskonterer gamle kamper, slik at 16 gamle resultater ikke automatisk gir høy tillit.
- Separate og forståelige avvisningsårsaker i `qualityAudit.rejections`.
- Observasjoner med svært store, urealistiske modell/marked-avvik skjules.
- Nettsiden viser hvorfor det kan være null kvalifiserte spill.
- Ingen flere API-kall per kamp, men historikk-kall henter lengre tidsrom. De samme API-kvotene gjelder.

## Dette er ikke dokumentert enda

Sannsynlighetsmodellen er fortsatt ikke kalibrert eller validert med nok historiske resultater. Ingen garanti for flere anbefalinger, positiv forventet verdi eller gevinst. Modellen har ikke full spiller-/lagoppstillingsdata, ikke dokumentert tilgang til alle kort-/hjørnesparkmarkeder, og bookmaker-median er ikke i seg selv en spillbar odds.

## Filer i pakken

- `scripts/form_v21.py` – ny historikk- og motstanderjustering
- `scripts/quality_v20.py` – respekterer effektivt historikkutvalg; kategoriserer avslag
- `scripts/qualify_v20.py` – forklarer avslag og avviser urealistiske observasjoner
- `site/quality-v20.js` – viser forklaringer ved null tips
- `tests/test_form_v21.py` – regresjonstester
- `install_v21.py` – retter en begrenset del av eksisterende `scripts/build_data.py`
- `KJOR_OPPDATERING.command` – enkel macOS-starter

Skriptet nekter å endre byggemotoren hvis GitHub-koden ikke stemmer med forventet utgave. En sikkerhetskopi av `build_data.py` lagres under `~/.odds_generatoren_backups` utenfor repoet.
