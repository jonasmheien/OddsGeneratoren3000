# OddsGeneratoren v1.4: flere markeder og forventet resultat

**Patch til v1.3.** Beholder originalt minimalt grensesnitt. `market_scan_v14.py` er en valgfri markedsanalyse; `score_consensus_v14.py` beregner et samlet resultat fra dokumenterte, uavhengige scoreprediksjoner, uten å blande dette med generatorens egen modell.

## Kildetilgang

| Del | Status |
| --- | --- |
| The Odds API: kort, hjørnespark og målscorerodds | Hentes hvis markedet tilbys og budsjettet tillater det |
| Football-data.org: historiske lagstatistikker | Benyttes bare hvis API-et faktisk gir relevante verdier |
| Mål, første omgang, lagmål, begge scorer | Videreføres fra v1.2, med ekstra bookmakerlinjer for blant annet lagmål under og begge scorer: nei |
| API-Football Predictions: eksakt resultat | Automatisk **kun** med tilkoblet `API_FOOTBALL_KEY`, og kun hvis API-et returnerer eksakte mål for begge lag |
| Forebet, Vitibet, PredictZ, WinDrawWin, FootballPredictions.net | **Ikke automatisk integrert.** Kan bidra med verifiserte resultattips i `data/score_predictions.csv` |

Et samlet resultattips vises bare ved minst to uavhengige, eksakte prognoser for den identifiserte kampen, med én stemme per kilde. Et separat resultat fra OddsGeneratorens Poisson-modell kan vises når eksterne kilder mangler. Det betyr ikke at resultatet er sannsynlig eller et anbefalt spill på eksakt score.

## Installering

Pakk ut ZIP og kopier **de enkelte filene** inn i eksisterende repo, ikke erstatt hele mapper. Ingen eksisterende `site/data/`- eller `state/`-filer skal endres. Push til GitHub for vanlig deploy. Dagens låste dagsutgave bygges ikke på nytt ved vanlig push. For umiddelbar analyse: GitHub Actions → `Run workflow` → `mode=daily` → `force_refresh=true`; ellers oppdateres innholdet ved neste automatiske dagsanalyse.

Se `LES_MEG_v14.txt` for detaljert oppsett og CSV-format.
