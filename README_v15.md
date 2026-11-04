# OddsGeneratoren v1.5 | Oversikt over alle spillmarkeder

Dette er en **oppdateringspakke** for eksisterende v1.4, ikke et komplett nytt nettsted.

## Hva er nytt

- Tydelige filtre for **over/under mål**, **lagmål**, **begge lag scorer**, **første omgang**, **hjørnespark**, **kort** og **målscorer**. Markedene er synlige selv om dagens analyse mangler odds.
- Dagens kvalifiserte mål- og lagmålspill vises i den samme oversikten som de nye spesialmarkedene. «Til vurdering» er aldri merket som et anbefalt tips.
- Backend bevarer både over- og underobservasjoner og fordeler tilgjengelige utfall bedre mellom markedene, i stedet for at mange linjer fra én kamp fortrenger alt annet.
- «Forventet resultat» er synlig også når verifiserte eksterne spådommer mangler. Når minst to ulike kilder foreligger, vises et samlet resultat med én stemme per kilde og kildevisning. OddsGeneratorens egen Poisson-prognose vises **separat**.
- Lagene får mer distinkte, originale monogrammer når offisielle emblemer ikke kan vises. Støtten for ekte klubbemblemer i Football-data.orgs kampdata er fortsatt der, men krever avklart tillatelse.
- Samme minimalistiske, mørke utseende beholdes. Ingen eksisterende JSON-dagsutgaver eller historikk endres av pakken.

## Begrensninger du bør vite om

**Ingen av de nevnte prediksjonssidene er automatisk tilkoblet uten kildeavtale.** Forebet, Vitibet, PredictZ, WinDrawWin og FootballPredictions.net kan inngå i `data/score_predictions.csv` når et datostemplet, kildelenket eksakt resultat er registrert. API-Football er den automatiske kilden som støttes hvis `API_FOOTBALL_KEY` er konfigurert og abonnementet returnerer eksakte prognoser. Det er derfor ikke grunnlag for å kalle utfallet «snitt av alle prediksjonssidene» før flere kilder faktisk leverer data.

Kort/hjørnespark/målscorer kan undersøkes automatisk via The Odds API når leverandøren tilbyr pris på eventet og API-kvoten holder. Med dagens budsjett undersøkes bare et fåtall kamper daglig for slike ekstrafelt. Historisk spiller-, kort- og hjørnesparkstatistikk er ofte ikke tilgjengelig i dagens gratisdatakilder; i så fall blir det ingen anbefaling. Målscorere krever dessuten verifisert startoppstilling før et spill bør anses klart.

**Klubblogoer:** Football-data.org opplyser i sine vilkår at grafikken eies av rettighetshaverne. Visning av de ekte merkene krever rettighetene avklart. Når rettighetene er på plass, kan du angi GitHub Actions repository variable `SHOW_LICENSED_CRESTS=1` og kjøre en ny dagsanalyse for å aktivere eksisterende klubbemblemer. Uten dette brukes monogrammer. Det er ikke nødvendig å betale for egne monogrammer.

## Installering uten å miste filer

1. Pakk ut ZIP-filen.
2. GitHub Desktop → **Repository → Show in Finder**.
3. Kopier **filene**, og erstatt tilsvarende filer inne i `scripts/`, `site/`, `tests/` og `.github/workflows/`. **Ikke bytt ut hele mappene**. Ikke slett `state/` eller `site/data/`.
4. Kopier også **`.github/refresh-once-v15`** fra pakken inn i prosjektets `.github/`-mappe. På Mac viser du skjulte mapper med **Cmd + Shift + .** i Finder.
5. Commit to main → Push origin. **Denne ene opplastingen starter automatisk en ny analyse av dagens gjenstående kamper**, oppdaterer odds og publiserer nettsiden. Vanlige kodeoppdateringer senere vil ikke oppdatere dagens tips på nytt.

### Hva pakken endrer

- `scripts/market_scan_v14.py`
- `site/market-board-v14.js`, `site/market-board-v14.css`
- `site/score-consensus-v14.js`, `site/score-consensus-v14.css`
- `site/app.js`, `site/styles.css`, `site/index.html`
- `tests/test_dashboard_v15.py`
- `tests/test_reliability_v11.py`, `tests/test_same_day_refresh_v15.py`
- `.github/workflows/publish.yml`, `.github/refresh-once-v15`
- `README_v15.md`

**Den inneholder ingen datafil, hemmelige nøkler, lagrede resultater eller spillerådgivning som krever fremtidige API-kall for å få eksisterende tips til å fungere.**


## Viktig for dagens tips: v1.5 med engangsoppdatering

Denne pakken inkluderer `.github/workflows/publish.yml` og `.github/refresh-once-v15`. Når begge kopieres og du kjører **Commit to main → Push origin**, starter GitHub Actions **automatisk en ny dagsanalyse**, selv om dagens tidligere tips finnes. Ingen manuell `Run workflow` er nødvendig.

Analysejobben henter dagens gjenværende (ikke-startede) kamper og ferske odds, kjører ekstra markedssjekk og scoreprognoser, lagrer en ny dagsutgave og publiserer nettsiden. **Dette erstatter dagens tidligere tips og bruker API-kvoten.** Det er ikke en garanti for 3–5 spill i alle kategorier, eller for at alle spesialmarkeder har tilgjengelige odds.

Når analysen lykkes, fjerner GitHub Actions selv engangsfilen `.github/refresh-once-v15` fra repoet i samme commit som dagsutgaven. Senere kodeoppdateringer publiserer bare lagrede tips. Skulle API eller andre tester feile, blir jobben rød og forrige dagsutgave beholdes; engangsfilen blir liggende slik at du kan prøve igjen.

**Kontroll:** Åpne GitHub → Actions → siste kjøring. Den skal vise `Generer nytt dagsutvalg`, `Kontroller hjørnespark, kort og målscorere`, `Samle kildebaserte resultatprognoser` og `deploy` med grønt status. Åpne deretter nettsiden og trykk Oppdater.

**OBS:** Kopier bare enkeltfilene i ZIP-pakken inn i eksisterende mappehierarki, ikke erstatt mappene. Ingen lagrede JSON-filer er med i pakken.
