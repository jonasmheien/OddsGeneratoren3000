# Publisering og historikk v53

Vi viser tre kategorier: Safe Bets, High Risk og Interessante objekter. Hvert
oppgjør kan ha ett publisert spill, også på tvers av forhåndsanalyse,
morgenanalyse, leverandørbytter og senere oppdateringer.

Publiseringsgrensene i `lifecycle.create_edition` og `tomorrow.publish_preview`
leser tidligere registreringer før endelig valg. Et tidligere publisert marked
og kategori låses. Hvis dette spillet ikke lenger kvalifiserer med tilgjengelige
odds, utelates kampen. Et annet utfall eller marked kan ikke erstatte det.
Ledige plasser kan fylles med andre kamper som oppfyller kravene.

Treffprosenten bruker første registrering per reelle kamp, med opprinnelig odds
og kategori. Registreringer sorteres etter publiseringstid med stabil nøkkel
ved likt tidspunkt. Resultatet påvirker aldri hvilken registrering som teller.
Kun bekreftet vunnet og tapt inngår i nevneren. Manglende resultater gir ingen
antatt seier eller tap. Et tomt utvalg viser ingen prosent.

De opprinnelige revisjonene og samtlige tips i `state/hitrate-v51.json` beholdes.
Historiske alternativer fjernes bare fra den offentlige prosentberegningen og
resultatlisten. `publicationPolicy.excludedAlternatives` oppgir antallet.
Ved innføringen var det 176 registreringer fordelt på 131 kamper. Det betyr
45 senere alternativer utenfor beregningen. Ingen registrerte resultater er
endret som del av denne oppryddingen.

Eldre «kvalifiserte» tips knyttes til hovedkategorien der samme tips er registrert.
Hvis ingen slik kategori finnes, brukes de opprinnelige oddsgrensene: inntil
1,85 til Safe Bets, fra 2,25 til High Risk og øvrige til Interessante objekter.
Den opprinnelige kategorien bevares i den interne resultatloggen.

Grensesnittet laster kun den felles utvalgsvisningen, tipskortene og resultatloggen.
Markedsradar, ekstra toppvalg, søk, egen kvalifisert seksjon og driftsdiagnostikk
vises ikke. Kampanalysen ligger i en lukket detaljvisning.

Kontroll: hele Python-testpakken, felles JavaScript-utvalg og arkivering,
resultatfiltre, prosentberegning, HTML-escaping og nettleserkontroll på stor
skjerm og ved 390 piksler.
