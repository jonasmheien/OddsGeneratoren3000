'use strict';
/* Exactly three sections: High Risk, Safe Bets, Interesting but not recommended.
   Never promote an unqualified bookmaker quote to a recommended wager. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const osloDate = date => {
    const parts = new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Oslo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date);
    const vals = Object.fromEntries(parts.map(p => [p.type,p.value]));
    return `${vals.year}-${vals.month}-${vals.day}`;
  };
  const dateText = date => {
    if(!/^\d{4}-\d{2}-\d{2}$/.test(String(date||''))) return 'Ukjent dato';
    return new Intl.DateTimeFormat('nb-NO',{timeZone:'UTC',weekday:'long',day:'numeric',month:'long'})
      .format(new Date(date+'T12:00:00Z'));
  };
  const kickoff = value => {
    const date = new Date(value);
    if(!Number.isFinite(+date))return 'Ukjent start';
    return new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit'}).format(date);
  };
  const price = value => Number(value).toLocaleString('nb-NO',{minimumFractionDigits:2,maximumFractionDigits:2});
  const key = pick => String(pick.matchId??pick.id??'')+'|'+String(pick.market??'');
  const dayOf = edition => String(edition?.editionDate||edition?.localDate||'');
  const futureKickoff = (p, now) => Number.isFinite(+new Date(p?.kickoff)) && +new Date(p.kickoff) > +now;
  const shownKickoffs = (edition, now) => {
    let picks = ['recommendations','safeBets','highRisk','observations']
      .flatMap(k => Array.isArray(edition?.[k])?edition[k]:[])
      .map(p => +new Date(p?.kickoff)).filter(n => Number.isFinite(n) && n > 0 && osloDate(new Date(n))===dayOf(edition));
    if(!picks.length) picks=(edition?.matches||[]).filter(m=>m && m.odds && Object.keys(m.odds).length)
      .map(m=>+new Date(m.kickoff)).filter(n=>Number.isFinite(n)&&n>0&&osloDate(new Date(n))===dayOf(edition));
    return picks;
  };
  function shouldShowTomorrow(today, preview, now){
    if(!preview || preview.previewEdition!==true || !/^\d{4}-\d{2}-\d{2}$/.test(dayOf(preview)))return false;
    const local=osloDate(now);
    if(dayOf(preview)<local)return false;
    if(today && dayOf(today)>=dayOf(preview))return false;
    if(!today || dayOf(today)<local)return true;
    const starts=shownKickoffs(today,now);
    // No recommendations and no quoted fixtures: don't hold a blank day forever.
    if(!starts.length)return Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Oslo',hour:'2-digit',hourCycle:'h23'}).format(now))>=18;
    return starts.every(t=>t<=+now);
  }
  const unique = picks => {
    const used=new Set();return picks.filter(p=>{if(!p || !p.home || !p.away || !futureKickoff(p,new Date()))return false;
      const k=key(p);if(used.has(k))return false;used.add(k);return true;});
  };
  function qualified(edition,category,now){
    const main=(edition?.recommendations||[]).filter(p=>p?.category===category);
    return unique(main).filter(p=>futureKickoff(p,now) && osloDate(new Date(p.kickoff))===dayOf(edition) && Number(p.price)>1 &&
      p.conservativeEdge!=null && Number.isFinite(Number(p.conservativeEdge)) && Number(p.conservativeEdge)>=.02
    ).slice(0,5);
  }
  function interesting(edition, now){
    const chosen=new Set((edition?.recommendations||[]).map(key));
    const observations=unique(edition?.observations||[]).filter(p=>futureKickoff(p,now)&&osloDate(new Date(p.kickoff))===dayOf(edition)&&!chosen.has(key(p)))
      .map(p=>({...p,_why:p.reason||'Interessant signal, men ikke kvalifisert som anbefaling.'}));
    const seen=new Set(observations.map(p=>String(p.matchId)));
    const quotes=(edition?.matches||[]).filter(m=>m?.home&&m?.away&&futureKickoff(m,now)&&osloDate(new Date(m.kickoff))===dayOf(edition)&&Object.keys(m.odds||{}).length)
      .filter(m=>!seen.has(String(m.id)))
      .map(m=>{
        const prices=Object.entries(m.odds||{}).filter(([code,q])=>['H','B','U','O25','U25'].includes(code)&&Number(q?.price)>1);
        const opt=prices.find(([code])=>code==='H')||prices[0];
        if(!opt)return null;
        const [code,q]=opt;
        const labels={H:'Hjemmeseier',B:'Borteseier',U:'Uavgjort',O25:'Over 2,5 mål',U25:'Under 2,5 mål'};
        return {matchId:m.id,home:m.home,away:m.away,league:m.league,kickoff:m.kickoff,
          market:code,label:labels[code],price:q.price,bookmakers:q.books,
          _priority:(m.predictions||[]).length?100:0,_books:Number(q.books)||0,
          _why:(m.predictions||[]).length?'Ekstern prognose finnes, men kampens statistikk er ikke tilstrekkelig for en anbefaling.':
            'Bookmakerodds finnes, men datagrunnlaget er ikke godt nok for en anbefaling.'};
      }).filter(Boolean)
      .sort((a,b)=>b._priority-a._priority||b._books-a._books||String(a.kickoff).localeCompare(String(b.kickoff)));
    const merged=observations.slice();
    for(const p of quotes){if(merged.length>=5)break;if(merged.some(x=>String(x.matchId)===String(p.matchId)))continue;merged.push(p);}
    return merged.slice(0,5);
  }
  function card(p,recommended){
    const validPrice=Number.isFinite(Number(p.price))&&Number(p.price)>1;
    const rationale=Array.isArray(p.rationale)?p.rationale.find(s=>typeof s==='string'):null;
    return `<article class="tf-card">
      <div class="tf-meta">${esc(p.league||'Fotball')} <span>· ${esc(kickoff(p.kickoff))}</span></div>
      <div class="tf-teams">${esc(p.home)} <span>–</span> ${esc(p.away)}</div>
      <div class="tf-market"><span>${esc(p.label||'Marked under vurdering')}</span>${validPrice?`<strong>${esc(price(p.price))}</strong>`:''}</div>
      <div class="tf-reason">${esc(recommended?(rationale||'Kvalifisert av analysemodellen.'):(p._why||p.reason||'Ikke anbefalt.'))}</div>
      ${recommended?'<div class="tf-note">Indikativ bookmaker-median, kontroller tilgjengelig odds før spill.</div>':''}
    </article>`;
  }
  let parent;
  let loading=false;
  async function get(path){
    try{const response=await fetch(`data/${path}.json?t=${Date.now()}`,{cache:'no-store'});
      return response.ok?await response.json():null;}catch{return null;}
  }
  async function load(){
    if(loading)return;
    loading=true;
    try{
      const [today,preview]=await Promise.all([get('today'),get('tomorrow')]);
      const now=new Date();const useTomorrow=shouldShowTomorrow(today,preview,now);
      let edition=useTomorrow?preview:today;
      if(!edition && preview && dayOf(preview)>=osloDate(now)){edition=preview;}
      const editionDay=dayOf(edition);
      const todayExpired=edition && editionDay<osloDate(now);
      const starts=shownKickoffs(edition,now);
      const expired=!!(todayExpired || (edition&&!useTomorrow&&starts.length&&starts.every(t=>t<=+now)));
      const high=edition&&!expired?qualified(edition,'high',now):[];
      const safe=edition&&!expired?qualified(edition,'safe',now):[];
      const watch=edition&&!expired?interesting(edition,now):[];
      const selectedDay=!expired?editionDay:'';
      $('tf-date').textContent=selectedDay?`Forslag for ${dateText(selectedDay)}${useTomorrow?' · forhåndsanalyse':''}`:
        'Venter på neste dags utvalg';
      const heroDate=$('today-date');if(heroDate)heroDate.textContent=selectedDay?dateText(selectedDay):'Neste dags utvalg kommer';
      const editionIndicator=$('edition-indicator');if(editionIndicator)editionIndicator.textContent=useTomorrow?'MORGENDAGENS UTGAVE':'DAGENS UTGAVE';
      const lastUpdated=$('last-updated');if(lastUpdated)lastUpdated.textContent=edition?.generatedAt?`Analyse ${kickoff(edition.generatedAt)}`:'Oppdatering ikke klar';
      const sections=[['high',high],['safe',safe],['watch',watch]];
      for(const [id,entries] of sections){
        $('tf-'+id+'-count').textContent=String(entries.length);
        $('tf-'+id+'-list').innerHTML=entries.length?entries.map(p=>card(p,id!=='watch')).join(''):
          `<p class="tf-empty">${id==='watch'?'Ingen aktuelle objekter under vurdering.':
            'Ingen kvalifiserte forslag akkurat nå.'}</p>`;
      }
      $('tf-status').textContent=expired?'Dagens kamper har startet. Neste utvalg publiseres automatisk når analysen er klar.':
        'Forslag og odds kontrolleres automatisk. Ingen spill legges til for å fylle opp listene.';
    }finally{loading=false;}
  }
  document.addEventListener('DOMContentLoaded',()=>{
    parent=document.createElement('section');parent.className='tf-root';parent.id='tf-root';
    parent.innerHTML='<div class="tf-date" id="tf-date">Henter siste utvalg …</div>'+
    '<div class="tf-columns">'+
    '<section class="tf-section" aria-labelledby="tf-high-title"><header><h2 id="tf-high-title">High Risk</h2><span id="tf-high-count">0</span></header><div id="tf-high-list" class="tf-list"></div></section>'+
    '<section class="tf-section" aria-labelledby="tf-safe-title"><header><h2 id="tf-safe-title">Safe Bets</h2><span id="tf-safe-count">0</span></header><div id="tf-safe-list" class="tf-list"></div></section>'+
    '<section class="tf-section" aria-labelledby="tf-watch-title"><header><h2 id="tf-watch-title">Interessante objekter</h2><span id="tf-watch-count">0</span></header><p class="tf-subtitle">Til vurdering, ikke anbefalt</p><div id="tf-watch-list" class="tf-list"></div></section>'+
    '</div><p class="tf-status" id="tf-status" role="status"></p>';
    const main=document.querySelector('main');if(!main)return;const hero=main.querySelector('.hero');
    if(hero && typeof hero.after==='function')hero.after(parent);else main.prepend(parent);
    document.body.classList.add('three-v26');
    load();$('refresh-data')?.addEventListener('click',load);
    setInterval(()=>{if(document.visibilityState==='visible')load();},60000);
  });
})();
