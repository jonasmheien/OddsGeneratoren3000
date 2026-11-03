# OddsGeneratoren3000 v0.9 · Clean Tech / Live Tracker

**Dagens tips til Jonnern**. Et privat analyse-dashboard med tydelige tips, separate Safe Bets og High Risk, og kampstatus. Ingen brukernøkkel lagres i nettsiden.

## Hva er nytt fra v0.8?

- **Renere grensesnitt:** Fjernet «Dekning begrenset», hele «Data og statistikk»-panelet og den store tellerraden på toppen. Kun Dagens tips, Safe Bets, High Risk og en *betinget* LIVE-visning.
- **Ny visuell retning:** mørk grafitt med Krypton-inspirerte grønne aksenter og Swedish Gold-inspirerte gulltoner. Fargene er skjermtilpassede tilnærminger, ikke offisielle fabrikklakk-koder.
- **Live for utvalgte kamper:** en kompakt LIVE-strip vises **bare når minst ett lagret tips har `live`-status**. Stilling, kampminutt og pause vises når den autoriserte kampdatakilden leverer feltene. Ingen minutter eller resultater blir gjettet.
- **Oppdatert kampstatus:** GitHub Actions spør football-data.org omtrent hver 10. minutt fra 16.00 til 23.59 og omtrent hvert 20. minutt fra 00.00 til 02.59 norsk tid. Planlagte GitHub-jobber kan starte forsinket. Dette er en **periodisk oppdatert scoretracker, ikke en sanntidsfeed på sekundnivå**.
- **Oppdater-knappen og automatisk nettleserrefresh:** siden henter sist publiserte JSON ved klikk og hvert minutt mens fanen er aktiv. Disse hentene bruker ikke API-nøkler og genererer ingen nye spill.
- **Bedre resultathenting:** bytter ut udokumentert `ids=`-filter på `/matches` med dokumentert `dateFrom/dateTo` og filtrering på lagrede kamp-ID-er lokalt. Sluttstatus blir ikke overstyrt av et forsinket «Pågår»-svar.
- **Fast dagsutgave:** v0.8-funksjonen er beholdt. Tips og opprinnelig odds blir stående til neste vellykkede dagsanalyse. Kun kampresultater og status endres i mellomtiden.

## Installasjon i eksisterende GitHub-repository

1. Last ned ZIP, pakk den ut på Mac.
2. GitHub Desktop → **Repository → Show in Finder**.
3. Kopier **innholdet** fra den utpakkede mappen inn i eksisterende `OddsGeneratoren3000`. Velg *Erstatt* ved filkonflikter. **Ikke slett `.git`, `state/active.json` eller hele repositorymappen**. Husk at `.github` er skjult. `Cmd + Shift + .` viser skjulte filer på Mac.
4. GitHub Desktop → **Summary:** `v0.9 clean tech and live scores` → **Commit to main** → **Push origin**.
5. Åpne [Actions](https://github.com/jonasmheien/OddsGeneratoren3000/actions) og kontroller grønne `build`/`deploy`.
6. Åpne [OddsGeneratoren](https://jonasmheien.github.io/OddsGeneratoren3000/). En kodeendring publiserer den **eksisterende lagrede dagsutgaven**. Den lager ikke nye tips. `daily` må kun startes eksplisitt eller fra neste morgenplan.

## Automatisering

| Oppgave | Tidspunkt | Kilde | Endrer tips? |
|---|---|---|---|
| Dagsanalyse | 09.17 Europe/Oslo | football-data.org, The Odds API, evt. API-Football | **Ja**, ny dagsutgave |
| Score- og resultatkontroll | Ca. hvert 10. minutt 16–23 og hvert 20. minutt 00–02 | football-data.org | **Nei**, kun resultater/status |
| Nettleser / Oppdater | Hvert minutt mens fanen er synlig / ved klikk | publisert GitHub Pages JSON | **Nei** |

Ingen oppdatering er garantert til nøyaktig minutt. Kampminutt avhenger av dekning på football-data.org sitt abonnement. Ved `FINISHED` avregnes 1X2 og målspill etter regulær tid slik kildefeltene tillater. Kamper med manglende avregningsgrunnlag blir stående som «Avventer».

## Datakilder og avgrensninger

**Aktive ved oppgitt nøkkel:** football-data.org og The Odds API. **Valgfritt:** API-Football Predictions med `API_FOOTBALL_KEY`.

**Ikke integrert:** Vitibet, Forebet, Reddit- og andre ekspert-/forumsignaler. Disse kan ikke omtales som aktive eller automatisk inkludert før korrekt og tillatt datatilgang er ordnet.

Dette er fortsatt en **ikke-kalibrert modell** og er ikke dokumentert å slå markedet. Safe Bets betyr relativt tydeligere markedsfavoritter, ikke sikker gevinst. Kategorien får maks fem faktiske kandidater når data tilsier det; ingen syntetiske tips blir fylt inn.

## Testing

```bash
python3 -m unittest discover -s tests -v
node --check site/app.js
```

`forhandsvisning.html` er en **selvstendig design-demo** med oppdiktede lag og utfall. Den bruker ikke API-er og er ikke reelle tipseanbefalinger. Nettsiden i `site/` henter `site/data/today.json` fra GitHub Pages.
