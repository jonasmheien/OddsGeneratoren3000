'use strict';
/* OddsGeneratoren v2 foundation: one qualified list + clearly separate observations.
   Never relabel unqualified candidates as recommended bets. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clock = value => {
    if(!value)return '–';
    const d = new Date(value);
    return Number.isNaN(+d)?'–':new Intl.DateTimeFormat('nb-NO',{
      timeZone:'Europe/Oslo',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'
    }).format(d);
  };
  const odds = value => Number(value).toLocaleString('nb-NO',{minimumFractionDigits:2,maximumFractionDigits:2});
  let edition, active = 'all';
  function view(p){
    const category = p.category === 'safe'?'Safe Bet':p.category==='high'?'High Risk':'Dagens tips';
    const rationale = (Array.isArray(p.rationale)?p.rationale:[]).filter(x=>typeof x==='string').slice(0,7);
    const result = p.result?.status;
    const state = ({won:'Vunnet',lost:'Tapt',live:'Pågår',void:'Annullert',postponed:'Utsatt'})[result] || '';
    return `<article class="q20-card">
      <div class="q20-top"><span>${esc(p.league||'Fotball')} · ${esc(clock(p.kickoff))}</span><span>${esc(category)}${state?' · '+esc(state):''}</span></div>
      <div class="q20-match">${esc(p.home)} <span>–</span> ${esc(p.away)}</div>
      <div class="q20-bet"><strong>${esc(p.label)}</strong><strong class="q20-odds">${esc(odds(p.price))}</strong></div>
      <p class="q20-explain">${esc(rationale[0]||'Kvalifisert i konservativt scenario, men ikke historisk validert.')}</p>
      <details class="q20-details"><summary>Vis full analyse</summary>
        <div class="q20-detail-body"><ul>${rationale.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
        <p>Prisobservasjon: ${esc(clock(p.oddsUpdatedAt))}. Beregningen er et usikkerhetsjustert scenario, ikke dokumentert avkastning.</p>
        <p>Oppgitt odds er en bookmaker-median. Faktisk spillbar pris må kontrolleres hos bookmakeren.</p></div>
      </details></article>`;
  }
  function observation(p){
    return `<article class="q20-observation">
      <div class="q20-top"><span>${esc(p.league||'Fotball')} · ${esc(clock(p.kickoff))}</span><span>Ikke anbefalt</span></div>
      <div class="q20-match">${esc(p.home)} – ${esc(p.away)}</div>
      <div class="q20-bet"><strong>${esc(p.label)}</strong><strong>${esc(odds(p.price))}</strong></div>
      <p>${esc(p.reason||'Ikke tilstrekkelig analysegrunnlag.')}</p></article>`;
  }
  function display(){
    const picks = (edition?.recommendations||[]).filter(p=>Number.isFinite(Number(p.price)) &&
      Number.isFinite(Number(p.conservativeEdge)) && Number(p.conservativeEdge) >= .02);
    const shown=active==='all'?picks:picks.filter(p=>p.category===active);
    $('q20-counter').textContent = `${picks.length} kvalifiserte · ${edition.observations?.length||0} observasjoner`;
    $('q20-filters').innerHTML = [['all','Alle'],['safe','Safe Bets'],['high','High Risk'],['standard','Andre']]
      .filter(([key])=>key==='all'||picks.some(p=>p.category===key))
      .map(([key,name])=>`<button type="button" data-filter="${key}" class="q20-filter ${active===key?'is-active':''}" aria-pressed="${active===key}">${name}</button>`).join('');
    const limit=5;
    $('q20-top').innerHTML = shown.length?shown.slice(0,limit).map(view).join(''):
      '<p class="q20-empty">Ingen kvalifiserte anbefalinger i denne kategorien. Vi fyller ikke opp listen med svakere spill.</p>';
    const remaining=shown.slice(limit);
    $('q20-more-wrap').hidden=!remaining.length;
    $('q20-more-title').textContent=`Flere kvalifiserte spill (${remaining.length})`;
    $('q20-more').innerHTML=remaining.map(view).join('');
    const obs = Array.isArray(edition.observations)?edition.observations:[];
    $('q20-observations').innerHTML=obs.length?obs.map(observation).join(''):
      '<p class="q20-empty">Ingen dokumenterte observasjoner i denne dagsutgaven.</p>';
  }
  async function load(){
    try{
      const response=await fetch(`data/today.json?v20=${Date.now()}`,{cache:'no-store'});
      if(!response.ok)return;
      const data=await response.json();
      if(data.modelVersion!=='2.0-foundation' || !Array.isArray(data.recommendations))return;
      edition=data;
      if(!$('q20-root')){
        const root=document.createElement('section');root.id='q20-root';root.className='q20-root';
        root.innerHTML='<div class="q20-heading"><div><span class="q20-kicker">DATASTØTTET UTVALG · V2.0</span><h2>Dagens 5 beste</h2><p>Alle markeder vurderes etter samme konservative kvalitetskrav.</p></div><span id="q20-counter"></span></div>'+
          '<div class="q20-filters" id="q20-filters" role="group" aria-label="Filtrer kvalifiserte tips"></div>'+
          '<div class="q20-grid" id="q20-top"></div>'+
          '<section id="q20-more-wrap"><h3 id="q20-more-title">Flere kvalifiserte spill</h3><div class="q20-grid" id="q20-more"></div></section>'+
          '<section class="q20-watch"><h3>Under observasjon</h3><p class="q20-sub">Konkrete statistiske signaler som ikke oppfyller kravene til anbefaling.</p><div class="q20-grid" id="q20-observations"></div></section>'+
          '<p class="q20-footnote">Modellen er ennå ikke kalibrert mot tilstrekkelig historisk utvalg. «Positiv verdi» viser et konservativt beregningsscenario, ikke påvist avkastning.</p>';
        const old=$('dagens');if(!old)return;old.before(root);
        root.addEventListener('click', event=>{
          const button=event.target.closest('button[data-filter]');if(!button)return;
          active=button.dataset.filter;display();
        });
      }
      document.body.classList.add('v20-active');
      display();
    }catch{/* If v2 data unavailable, retain the previous working interface. */}
  }
  document.addEventListener('DOMContentLoaded',()=>{
    load();$('refresh-data')?.addEventListener('click',load);
    setInterval(()=>{if(document.visibilityState==='visible')load();},60000);
  });
})();
