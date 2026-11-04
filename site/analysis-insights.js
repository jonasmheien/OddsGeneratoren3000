/* OddsGeneratoren v1.3 — verifiserbar, skriftlig kampvurdering.
 * Bruker utelukkende data som allerede finnes i den publiserte dagsutgaven.
 * Henter ikke inn ekspertmeninger og finner aldri på historiske resultater.
 */
(() => {
  'use strict';
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, chr => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[chr]));
  const number = value => {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const percent = value => `${Math.round(value * 100)} %`;
  const decimal = value => Number(value).toLocaleString('nb-NO', {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  });
  function formCounts(value) {
    if (typeof value !== 'string') return null;
    const sequence = value.toUpperCase().replace(/[^WDL]/g, '');
    if (!sequence.length) return null;
    return {
      played: sequence.length,
      won: (sequence.match(/W/g) || []).length,
      draw: (sequence.match(/D/g) || []).length,
      lost: (sequence.match(/L/g) || []).length
    };
  }
  function subject(p) {
    const home = String(p.home || 'hjemmelaget');
    const away = String(p.away || 'bortelaget');
    const code = String(p.market || '');
    if (code === 'H') return `hjemmeseier til ${home}`;
    if (code === 'B') return `borteseier til ${away}`;
    if (code === 'BTTS') return 'at begge lag scorer';
    if (code.startsWith('H1')) return 'antall mål i første omgang';
    if (code.startsWith('TH')) return `antall mål for ${home}`;
    if (code.startsWith('TA')) return `antall mål for ${away}`;
    if (/^(O|U)\d\d$/.test(code)) return 'antall mål i kampen';
    if (code.startsWith('CO')) return 'antall hjørnespark';
    return String(p.label || 'det valgte utfallet').toLowerCase();
  }
  function formSentence(p) {
    const home = formCounts(p.formHome);
    const away = formCounts(p.formAway);
    if (!home || !away) return 'Det finnes ikke nok registrert resultatdata til å sammenligne lagformen her.';
    const hName = String(p.home || 'Hjemmelaget');
    const aName = String(p.away || 'Bortelaget');
    const sample = `I de siste registrerte kampene har ${hName} ${home.won} seire på ${home.played} kamper, mens ${aName} har ${away.won} på ${away.played}.`;
    const code = String(p.market || '');
    if (code === 'H' && home.won < away.won) return `${sample} Den registrerte formen støtter derfor ikke en klar hjemmefavoritt.`;
    if (code === 'B' && away.won < home.won) return `${sample} Den registrerte formen støtter derfor ikke en klar bortefavoritt.`;
    if (code === 'H' && home.won > away.won) return `${sample} Resultatrekken gir noe støtte til hjemmelaget, men sier ikke alene nok om kampens utfall.`;
    if (code === 'B' && away.won > home.won) return `${sample} Resultatrekken gir noe støtte til bortelaget, men sier ikke alene nok om kampens utfall.`;
    return `${sample} Dette er formresultater, ikke en komplett målsjanse- eller prestasjonsanalyse.`;
  }
  function compose(p) {
    const odds = number(p.price);
    const modelProbability = number(p.probability);
    const bookmakers = Number.isInteger(Number(p.bookmakers)) && Number(p.bookmakers) > 0 ? Number(p.bookmakers) : null;
    const breakEven = odds !== null && odds > 1 ? 1 / odds : null;
    const isModel = p.probabilitySource !== 'market';
    const knownSources = [...new Set((Array.isArray(p.predictionSources) ? p.predictionSources : [])
      .filter(s => typeof s === 'string' && s.trim()).map(s => s.trim()))].slice(0, 3);
    const independent = Number.isInteger(Number(p.externalSupport)) && Number(p.externalSupport) > 0
      ? Number(p.externalSupport) : 0;
    const sample = Array.isArray(p.formSample) ? p.formSample.filter(v => Number.isInteger(v) && v >= 0) : [];
    const concerns = [];
    if (sample.length === 2 && Math.min(...sample) < 5) {
      concerns.push(`Formgrunnlaget er begrenset (${sample[0]} og ${sample[1]} registrerte kamper).`);
    }
    if (isModel && breakEven !== null && modelProbability !== null &&
      modelProbability >= 0 && modelProbability <= 1) {
      const diff = modelProbability - breakEven;
      if (diff > .20) concerns.push('Modellanslaget ligger svært langt over nivået oddsen krever. Dette kan skyldes forhold modellen ikke fanger opp.');
      else if (diff > .10) concerns.push('Modellen er mer optimistisk enn oddsprisen skulle tilsi. Det krever ekstra varsomhet.');
      else if (diff < -.05) concerns.push('Modellen er mindre optimistisk enn oddsprisen skulle tilsi.');
    }
    if (odds !== null && odds >= 3) concerns.push('Relativt høy odds innebærer betydelig risiko for at utfallet ikke inntreffer.');
    if (p.category === 'safe') concerns.push('«Safe Bet» er en kategori i generatoren, ikke et løfte om høy treffsikkerhet.');

    const primary = `Spillet gjelder ${subject(p)}. ${formSentence(p)}`;
    const sourcePart = bookmakers ? `basert på pris fra ${bookmakers} bookmakere` : 'uten oppgitt antall bookmakere';
    let market = odds !== null && odds > 1
      ? `Registrert odds er ${decimal(odds)}, ${sourcePart}. For å gå i null over mange tilsvarende spill må treffprosenten være minst omtrent ${percent(breakEven)} ved denne prisen.`
      : 'Ingen gyldig oddspris er oppgitt for dette utfallet.';
    if (modelProbability !== null && modelProbability >= 0 && modelProbability <= 1) {
      market += isModel
        ? ` Generatorens interne, ikke-kalibrerte modell anslår ${percent(modelProbability)}. Forskjellen er ikke dokumentasjon på positiv forventningsverdi.`
        : ` Det marginjusterte anslaget fra bookmakerprisene er ${percent(modelProbability)}, ikke et uavhengig modellfunn.`;
    }
    const external = knownSources.length
      ? `Registrert støtte fra: ${knownSources.join(', ')}. Disse prognosene er separate fra vår interne modell; kildegrunnlaget bør vurderes selvstendig.`
      : independent > 0
        ? `Dagsutgaven oppgir ${independent} støttende prognose(r), men navngir ingen etterprøvbar kilde for dette spillet.`
        : 'Ingen bekreftende ekstern prognose eller ekspertvurdering er registrert for dette spillet. Vi legger derfor ikke til påstander fra Vitibet, Forebet eller andre tjenester.';
    if (!concerns.length) concerns.push('Utvalget bygger på historiske data og odds som kan endre seg. Modellen er ikke dokumentert lønnsom.');
    return {primary, market, external, concerns: concerns.slice(0, 3)};
  }
  function render(p) {
    const d = compose(p || {});
    const para = (label, value) => `<p><strong>${escapeHtml(label)}</strong> ${escapeHtml(value)}</p>`;
    return `<section class="analysis-editorial" aria-label="Skriftlig vurdering av spillet">`
      + `<div class="analysis-editorial-title">Vurdering av spillet</div>`
      + para('Hva taler for eller imot?', d.primary)
      + para('Tallene bak tipset.', d.market)
      + para('Eksterne vurderinger.', d.external)
      + `<div class="analysis-caution"><strong>Usikkerhet</strong> ${escapeHtml(d.concerns.join(' '))}</div>`
      + `</section>`;
  }
  // app.js exposes the existing global analysis() function. Keep its factual
  // detail table; replace the repetitive rationale bullets with the prose.
  // The two deferred scripts load in order, before the first network response.
  if (typeof window.analysis === 'function') {
    const oldAnalysis = window.analysis;
    window.analysis = function (pick) {
      const markup = String(oldAnalysis(pick));
      const nonRepeating = markup.replace(/<ul class="detail-reasons">[\s\S]*?<\/ul>/, '');
      return render(pick) + nonRepeating;
    };
  }
  const style = document.createElement('style');
  style.textContent = `
    .analysis-editorial{margin-bottom:18px;padding-bottom:15px;border-bottom:1px solid rgba(171,195,177,.18)}
    .analysis-editorial-title{font-size:11px;letter-spacing:.09em;text-transform:uppercase;
      font-weight:800;color:#b9cebd;margin-bottom:10px}
    .analysis-editorial p{font-size:13px;line-height:1.65;color:#cbd7d1;margin:0 0 10px}
    .analysis-editorial p strong{color:#f0f4f0;font-weight:650}
    .analysis-caution{font-size:12px;line-height:1.6;color:#cfc7b1;background:rgba(154,133,74,.08);
      border-left:2px solid rgba(188,161,93,.6);padding:9px 11px;border-radius:2px}
    .analysis-caution strong{color:#e4d2a0}
  `;
  document.head.appendChild(style);
  // Test-only exports; does not alter dashboard behavior.
  if (typeof module !== 'undefined' && module.exports) module.exports = {compose, formCounts, render};
})();
