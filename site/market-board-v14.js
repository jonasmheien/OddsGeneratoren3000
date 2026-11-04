'use strict';
/* Additional pre-match markets. Informational watch items are NEVER called tips. */
(() => {
  const esc = v => String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const odd = v => Number(v).toLocaleString('nb-NO', {minimumFractionDigits:2,maximumFractionDigits:2});
  const time = v => {const dt=new Date(v);return isNaN(dt.getTime())?'':new Intl.DateTimeFormat('nb-NO',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Oslo'}).format(dt);};
  let host;
  function ensure(){
    if(host)return host;
    const before=document.querySelector('#resultater');
    host=document.createElement('section');host.id='spesialmarkeder';host.className='extra-market-section';host.hidden=true;
    host.setAttribute('aria-labelledby','special-market-heading');
    host.innerHTML='<div class="extra-heading"><div><div class="extra-kicker">DAGLIG MARKEDSSJEKK</div><h2 id="special-market-heading">Flere spillmarkeder</h2></div></div><div class="extra-markets" id="extra-market-body"></div>';
    if(before)before.before(host);else document.querySelector('main')?.appendChild(host);
    return host;
  }
  function card(p, qualified){
    if(!p || !Number.isFinite(Number(p.price)) || !p.label)return '';
    const reasons=Array.isArray(p.rationale)?p.rationale.filter(v=>typeof v==='string').slice(0,5):[];
    const detail=reasons.length?`<ul>${reasons.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'';
    const klass=qualified?'market-good':'market-watch';
    return `<details class="extra-market-card ${klass}"><summary>
      <span class="extra-market-main"><span class="extra-market-league">${esc(p.league||'Fotball')} · ${esc(time(p.kickoff))}</span><span class="extra-market-match">${esc(p.home)} – ${esc(p.away)}</span><span class="extra-market-play">${esc(p.label)}</span></span>
      <span class="extra-market-right"><strong>${esc(odd(p.price))}</strong><span>${qualified?'ANALYSERT':'TIL VURDERING'}</span></span>
    </summary><div class="extra-market-analysis">${qualified?'<p>Analysegrunnlaget oppfyller markedskravene. Modellanslaget er usikkert og ikke en garantert verdi.</p>':'<p>Bookmakerpris er registrert, men grunnlaget er foreløpig ikke sterkt nok til å anbefale spillet.</p>'}${detail}<span class="extra-market-source">Kilde: ${esc(p.source||'The Odds API')} · odds ved analysen</span></div></details>`;
  }
  function render(snapshot){
    ensure();const data=snapshot?.additionalMarkets;
    if(!data || typeof data!=='object'){host.hidden=true;return;}
    const tips=Array.isArray(data.tips)?data.tips:[];
    const watch=Array.isArray(data.watchlist)?data.watchlist:[];
    const body=document.getElementById('extra-market-body');
    host.hidden=false;
    body.innerHTML=`<p class="extra-market-intro">Vi sjekker hjørnespark, kort og målscorere i tillegg til mål, lagmål og første omgang. Bare spill med reelle odds og tilstrekkelig datagrunnlag anbefales.</p>
    ${tips.length?`<div class="extra-market-subhead">Kvalifiserte spill <span>${tips.length}</span></div><div class="extra-market-grid">${tips.map(p=>card(p,true)).join('')}</div>`:''}
    ${watch.length?`<div class="extra-market-subhead">Mulige spill å undersøke <span>${watch.length}</span></div><div class="extra-market-grid">${watch.map(p=>card(p,false)).join('')}</div>`:''}
    ${!tips.length&&!watch.length?'<div class="extra-market-empty">Ingen ekstra markeder hadde tilstrekkelig dokumentert oddsdekning i dagens analyse. De ordinære tipsene påvirkes ikke.</div>':''}
    <p class="extra-market-footnote">Målscorerspill krever kontroll av lagoppstillingen. Kort og hjørnespark krever verifisert statistikk. Manglende data betyr ingen anbefaling.</p>`;
  }
  async function fetchBoard(){
    try{
      const response=await fetch(`data/today.json?market_v14=${Date.now()}`,{cache:'no-store'});
      if(!response.ok)return;
      render(await response.json());
    }catch(error){ /* do not block the primary dashboard */ }
  }
  document.addEventListener('DOMContentLoaded',()=>{
    ensure();fetchBoard();
    document.getElementById('refresh-data')?.addEventListener('click',fetchBoard);
    setInterval(()=>{if(document.visibilityState==='visible')fetchBoard();},60000);
  });
})();
