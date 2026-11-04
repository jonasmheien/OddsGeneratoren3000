'use strict';
/* v1.5. Source consensus is only formed from >=2 verified, distinct publishers. */
(() => {
  const $=id=>document.getElementById(id);
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=v=>{const d=new Date(v);return Number.isNaN(+d)?'':new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit'}).format(d);};
  const score=x=>Number.isInteger(x?.homeGoals)&&Number.isInteger(x?.awayGoals)?`${x.homeGoals}–${x.awayGoals}`:'–';
  const image=url=>{try{const u=new URL(url);return u.protocol==='https:'&&['crests.football-data.org','upload.wikimedia.org'].includes(u.hostname)?u.href:null;}catch{return null;}};
  const mono=name=>String(name||'?').split(/\s+/).filter(Boolean).slice(0,2).map(s=>s[0]).join('').toUpperCase()||'?';
  let root;
  function ensure(){
    if(root)return root;
    root=document.createElement('section');root.id='resultatprognoser';root.className='score-prediction-section';
    root.setAttribute('aria-labelledby','scores-heading');
    root.innerHTML='<div class="score-prediction-heading"><div class="score-prediction-kicker">RESULTATPROGNOSER</div><h2 id="scores-heading">Forventet resultat</h2></div><div id="score-predictions-list"></div>';
    const main=document.querySelector('main');const position=main?.querySelector('.categories')||main?.querySelector('#resultater');
    if(position)position.before(root);else main?.append(root);return root;
  }
  function teamMark(name,url,allowed){const src=allowed?image(url):null;return `<span class="score-team-mark" aria-hidden="true">${src?`<img src="${esc(src)}" loading="lazy" alt="">`:esc(mono(name))}</span>`;}
  function sourceLink(x){const url=String(x.sourceUrl||'');return /^https:\/\//.test(url)?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(x.source)}</a>`:esc(x.source);}
  function gameCard(g, fixture, allowed){
    if(!g||!g.home||!g.away)return '';
    const rows=(Array.isArray(g.sources)?g.sources:[]).filter(x=>Number.isInteger(x.homeGoals)&&Number.isInteger(x.awayGoals));
    const consensus=rows.length>=2?g.consensus:null;
    const own=g.ownModel&&Number.isInteger(g.ownModel.homeGoals)?g.ownModel:null;
    const display=consensus||own;
    const sub=consensus?`${rows.length} uavhengige kilder`:rows.length===1?'Én verifisert kilde':own?'OddsGeneratorens egen modell':'Ingen gyldig prognose';
    const notes=consensus?`Hvert nettsted teller én gang. Gjennomsnittet er ${esc(consensus.meanHome)}–${esc(consensus.meanAway)} mål, avrundet til nærmeste heltall.`:rows.length===1?'Det kreves minst to uavhengige kilder for å beregne et samlet resultattips.':'Ingen verifiserte eksterne resultatspådommer tilgjengelig for denne kampen.';
    const votes=consensus?.outcomeVotes;
    return `<details class="score-prediction-game"><summary>
      <span class="score-prediction-main"><span class="score-league">${esc(g.league||'Fotball')} · ${esc(fmt(g.kickoff))}</span>
        <span class="score-teams">${teamMark(g.home,fixture.homeCrest,allowed)} ${esc(g.home)} <span>–</span> ${teamMark(g.away,fixture.awayCrest,allowed)} ${esc(g.away)}</span>
        <span class="score-caption">${esc(sub)}</span></span>
      <span class="score-forecast"><strong>${score(display)}</strong><small>${consensus?'KILDESNITT':own?'EGEN MODELL':'INGEN DATA'}</small></span></summary>
      <div class="score-prediction-details"><p>${notes}</p>
        ${votes?`<p class="score-votes">Kildene: ${votes.H||0} hjemmeseier · ${votes.U||0} uavgjort · ${votes.B||0} borteseier</p>`:''}
        ${rows.length?`<div class="score-prediction-source-list">${rows.map(s=>`<div><span>${sourceLink(s)}${s.entry==='manual'?'<small class="score-source-note"> · manuelt registrert</small>':''}</span><strong>${score(s)}</strong></div>`).join('')}</div>`:''}
        ${own?`<div class="score-prediction-model">Egen Poisson-modell: <strong>${score(own)}</strong></div>`:''}
        <span class="score-disclaimer">Et forventet sluttresultat er ikke en anbefaling om å spille på eksakt resultat.</span>
      </div></details>`;
  }
  function render(snapshot){
    const holder=ensure().querySelector('#score-predictions-list');const dataset=snapshot?.scorePredictions;
    const games=Array.isArray(dataset?.games)?dataset.games:[];
    const fixtures=new Map((snapshot?.matches||[]).map(m=>[String(m.id),m]));
    const allowed=snapshot?.visualAssets?.licensedCrests===true;
    root.hidden=false;
    if(!dataset){holder.innerHTML='<p class="score-prediction-intro">Dagsutgaven er ennå ikke analysert med resultatprognosemodulen. En ny dagsanalyse må kjøres før denne delen kan vise kamper.</p>';return;}
    const sourceCount=Number(dataset.sourceForecasts||0),combined=Number(dataset.fixturesWithConsensus||0);
    const intro=`<p class="score-prediction-intro">${combined?`${combined} kamper har et samlet scoreanslag fra minst to ulike kilder.`:'Ingen kamper har ennå minst to dokumenterte eksterne scoreprognoser.'} ${sourceCount} eksterne resultattips registrert. Egen modell vises separat.</p>`;
    const visible=games.filter(g=>g.home&&g.away).slice(0,8);
    holder.innerHTML=intro+(visible.length?`<div class="score-prediction-grid">${visible.map(g=>gameCard(g,fixtures.get(String(g.matchId))||{},allowed)).join('')}</div>`:'<div class="score-prediction-empty">Ingen resultattips tilgjengelig i denne dagsutgaven.</div>')+
      '<p class="score-prediction-note">Forebet, Vitibet, PredictZ og WinDrawWin er ikke automatisk tilkoblet. Deres tips inngår bare når de er registrert med datostempel og kildelenke. API-Football kan brukes dersom abonnement og API-nøkkel er konfigurert. Ingen oppdiktede kilder.</p>';
    root.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{img.replaceWith(document.createTextNode('?'));},{once:true}));
  }
  async function read(){try{const response=await fetch(`data/today.json?score_v15=${Date.now()}`,{cache:'no-store'});if(response.ok)render(await response.json());}catch{}}
  document.addEventListener('DOMContentLoaded',()=>{ensure();read();$('refresh-data')?.addEventListener('click',read);setInterval(()=>{if(document.visibilityState==='visible')read();},60000);});
})();
