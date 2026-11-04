'use strict';
/* Score consensus: never imply that an unconnected publisher submitted a forecast. */
(() => {
  const esc = x => String(x ?? '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
  const fmt = iso => {const d=new Date(iso); return isNaN(+d)?'':new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit'}).format(d);};
  const score = o => Number.isInteger(o?.homeGoals) && Number.isInteger(o?.awayGoals)?`${o.homeGoals}–${o.awayGoals}`:'–';
  let root;
  function ensure(){
    if(root)return root;
    root=document.createElement('section');root.id='resultatprognoser';root.className='score-prediction-section';root.hidden=true;
    root.setAttribute('aria-labelledby','scores-heading');
    root.innerHTML='<div class="score-prediction-heading"><div class="score-prediction-kicker">KILDEBASERTE RESULTATPROGNOSER</div><h2 id="scores-heading">Forventet resultat</h2></div><div id="score-predictions-list"></div>';
    const main=document.querySelector('main');
    const special=document.getElementById('spesialmarkeder');
    const position=main?.querySelector('.categories')||special||main?.querySelector('#resultater');
    if(position)position.before(root);else main?.append(root);
    return root;
  }
  function sourceLink(s){
    const url=String(s.sourceUrl||'');
    if(!/^https:\/\//i.test(url))return esc(s.source);
    return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(s.source)}</a>`;
  }
  function gameCard(g){
    if(!g || !g.home || !g.away)return '';
    const rows=(Array.isArray(g.sources)?g.sources:[]).filter(s=>Number.isInteger(s.homeGoals)&&Number.isInteger(s.awayGoals));
    const hasConsensus=!!g.consensus && rows.length>=2;
    const local=g.ownModel && Number.isInteger(g.ownModel.homeGoals)?g.ownModel:null;
    const display=hasConsensus?g.consensus:local;
    if(!display && !rows.length)return '';
    const title=hasConsensus?`Samlet fra ${rows.length} kilder`:rows.length?'Én ekstern kilde':'Kun OddsGeneratorens modell';
    const reason=hasConsensus?`Lik vekt per kilde. Gjennomsnittet er ${esc(String(g.consensus.meanHome))}–${esc(String(g.consensus.meanAway))} mål, avrundet til heltall.`:rows.length?'Foreløpig for få uavhengige prognoser til å beregne en samlet score.':'Ingen verifiserte eksterne scoreprognoser for denne kampen.';
    const votes=hasConsensus&&g.consensus.outcomeVotes?g.consensus.outcomeVotes:null;
    const voteText=votes?`<p class="score-votes">Kildenes utfall: hjemmeseier ${votes.H||0} · uavgjort ${votes.U||0} · borteseier ${votes.B||0}</p>`:'';
    return `<details class="score-prediction-game"><summary><span class="score-prediction-main"><span class="score-league">${esc(g.league||'Fotball')} · ${esc(fmt(g.kickoff))}</span><span class="score-teams">${esc(g.home)} – ${esc(g.away)}</span><span class="score-caption">${esc(title)}</span></span><span class="score-forecast"><strong>${score(display)}</strong><small>${hasConsensus?'KILDESNITT':local&&!rows.length?'EGEN MODELL':'FORELØPIG'}</small></span></summary><div class="score-prediction-details"><p>${reason}</p>${voteText}${rows.length?`<div class="score-prediction-source-list">${rows.map(s=>`<div><span>${sourceLink(s)}${s.entry==='manual'?'<small class="score-source-note"> · manuelt registrert</small>':''}</span><strong>${score(s)}</strong></div>`).join('')}</div>`:''}${local?`<div class="score-prediction-model">OddsGeneratorens egen modell: <strong>${score(local)}</strong></div>`:''}<span class="score-disclaimer">Resultatprognoser er scenarioer, ikke bekreftede sannsynligheter for eksakt score.</span></div></details>`;
  }
  function render(snapshot){
    const data=snapshot?.scorePredictions;if(!data || !Array.isArray(data.games)){if(root)root.hidden=true;return;}
    const body=ensure().querySelector('#score-predictions-list');
    const games=data.games.filter(g=>(g.sources||[]).length||g.ownModel).slice(0,8);
    if(!games.length){root.hidden=true;return;}
    root.hidden=false;
    const qualified=games.filter(g=>g.consensus).length;
    body.innerHTML=`<p class="score-prediction-intro">Samler kildeangitte resultatprognoser fra uavhengige kilder. ${qualified?`${qualified} kamper har et samlet kildesnitt.`:'Ingen kamp har foreløpig nok eksterne kilder til et samlet anslag.'} Vår egen modell vises separat.</p><div class="score-prediction-grid">${games.map(gameCard).join('')}</div><p class="score-prediction-note">Kilder må ha et datostemplet, identifiserbart resultattips. Manuelt registrerte kildeopplysninger er ikke kontrollert automatisk. Forventet resultat betyr ikke anbefaling om å spille på eksakt score.</p>`;
  }
  async function read(){
    try{const response=await fetch(`data/today.json?score_v14=${Date.now()}`,{cache:'no-store'});if(response.ok)render(await response.json());}catch{}
  }
  document.addEventListener('DOMContentLoaded',()=>{
    ensure();read();
    document.getElementById('refresh-data')?.addEventListener('click',read);
    setInterval(()=>{if(document.visibilityState==='visible')read();},60000);
  });
})();
