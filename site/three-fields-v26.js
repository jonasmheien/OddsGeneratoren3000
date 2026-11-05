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
  // Data displayed here comes exclusively from the published match snapshot.
  // An odds quote alone is not a model forecast or a recommended bet.
  const finiteNumber = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)) ? Number(value) : null;
  const fraction = value => {
    const n=finiteNumber(value);
    return n!==null && n>=0 && n<=1 ? `${(n*100).toLocaleString('nb-NO',{maximumFractionDigits:1})} %` : null;
  };
  const decimal = value => {
    const n=finiteNumber(value);
    return n!==null && n>=0 && n<100 ? n.toLocaleString('nb-NO',{maximumFractionDigits:2}) : null;
  };
  const recordedAt = value => {
    if(!value || !Number.isFinite(+new Date(value)))return null;
    return new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}).format(new Date(value));
  };
  function analysisDetails(p,recommended,edition){
    const match=(Array.isArray(edition?.matches)?edition.matches:[]).find(m=>m && String(m.id)===String(p.matchId));
    const model=match?.model || null;
    const quote=match?.odds?.[p.market] || null;
    const rawProbability=finiteNumber(p.probability ?? model?.probabilities?.[p.market]);
    const conservativeProbability=finiteNumber(p.conservativeProbability);
    const estimatedGoals=Array.isArray(model?.expectedGoals)?model.expectedGoals:[];
    const sample=Array.isArray(model?.sample)?model.sample:Array.isArray(p.formSample)?p.formSample:[];
    const homeSample=Number.isInteger(Number(sample[0])) && Number(sample[0])>0 ? Number(sample[0]) : null;
    const awaySample=Number.isInteger(Number(sample[1])) && Number(sample[1])>0 ? Number(sample[1]) : null;
    const rows=[];
    const row=(label,value)=>{if(value!==null && value!==undefined && value!=='')rows.push(`<div class="tf-fact"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`);};
    row('Bookmakerodds',Number(p.price)>1 ? price(p.price) : null);
    const books=finiteNumber(p.bookmakers ?? quote?.books);
    row('Antall bookmakere',books!==null && Number.isInteger(books) && books>0?books:null);
    row('Odds registrert',recordedAt(p.oddsUpdatedAt ?? quote?.lastUpdated));
    if(homeSample!==null && awaySample!==null)row('Kamper i formutvalget',`${homeSample} hjemmelag / ${awaySample} bortelag`);
    const formHome=String(match?.formHome || p.formHome || '').trim();
    const formAway=String(match?.formAway || p.formAway || '').trim();
    if(/^[WDL]{3,20}$/.test(formHome))row(`${p.home} · resultatrekke`,formHome.replaceAll('W','S').replaceAll('D','U').replaceAll('L','T'));
    if(/^[WDL]{3,20}$/.test(formAway))row(`${p.away} · resultatrekke`,formAway.replaceAll('W','S').replaceAll('D','U').replaceAll('L','T'));
    if(estimatedGoals.length===2 && decimal(estimatedGoals[0])!==null && decimal(estimatedGoals[1])!==null){
      row('Forventede mål · modell',`${decimal(estimatedGoals[0])} / ${decimal(estimatedGoals[1])}`);
    }
    if(rawProbability!==null)row('Modellestimat for utfallet',fraction(rawProbability));
    if(recommended && conservativeProbability!==null)row('Usikkerhetsjustert estimat',fraction(conservativeProbability));
    if(recommended && finiteNumber(p.conservativeEdge)!==null){
      const edge=finiteNumber(p.conservativeEdge);
      row('Beregnet verdi i scenario',`${edge>=0?'+':''}${(edge*100).toLocaleString('nb-NO',{maximumFractionDigits:1})} %`);
    }
    const sourcePredictions=Array.isArray(match?.predictions)?match.predictions:[];
    const predictions=sourcePredictions.filter(x=>x && typeof x.source==='string' && x.source.length && fraction(x.probabilities?.[p.market])!==null).slice(0,2);
    for(const prediction of predictions){
      row(`${prediction.source} · anslag`,`${fraction(prediction.probabilities[p.market])} (ekstern prognose)`);
    }
    const statements=(Array.isArray(p.rationale)?p.rationale:[]).filter(s=>typeof s==='string' && s.trim()).slice(0,6);
    const reason= !recommended ? (p.reason || p._why || 'Ikke tilstrekkelig grunnlag for anbefaling.') :
      (statements[0] || 'Spillet har passert kvalitetskontrollen for denne utgaven.');
    const why=statements.length?`<ul class="tf-analysis-list">${statements.map(s=>`<li>${esc(s)}</li>`).join('')}</ul>`:
      `<p>${esc(reason)}</p>`;
    const warning= !recommended ?
      (!model ? 'Ingen verifisert, komplett formmodell for begge lag i denne kampen. Registrert odds er ikke et spilltips.' :
       'En modellberegning finnes, men spillet oppfylte ikke kravene til anbefaling. Modellen er ikke historisk kalibrert.') :
      'Estimater er usikre og ikke historisk kalibrert. Oppgitt odds er en bookmaker-median, ikke en garantert spillbar pris.';
    const sources=[];
    if(model)sources.push('Lagform: registrerte kampresultater fra tilknyttede datakilder.');
    if(Number(p.price)>1)sources.push('Odds: The Odds API, oppgitt som indikativ bookmaker-median.');
    if(predictions.length)sources.push('Eksterne anslag vises separat og er ikke dokumentert som treffsikre.');
    if(!sources.length)sources.push('Uavhengig datagrunnlag er ikke tilgjengelig for dette utfallet.');
    const formLegend=/^[WDL]{3,20}$/.test(formHome) || /^[WDL]{3,20}$/.test(formAway) ? '<p class="tf-legend">S = seier · U = uavgjort · T = tap</p>' : '';
    const facts=rows.length?`<dl class="tf-facts">${rows.join('')}</dl>${formLegend}`:
      '<p>Ingen verifiserbare nøkkeltall tilgjengelige for denne kampen.</p>';
    const analysisKey=`${dayOf(edition)}|${String(p.matchId??'')}|${String(p.market??'')}`;
    return `<details class="tf-analysis" data-analysis-key="${esc(analysisKey)}">
      <summary><span class="tf-show">Vis analysen</span><span class="tf-hide">Skjul analysen</span></summary>
      <div class="tf-analysis-body">
        <h3>Datagrunnlag</h3>${facts}
        <h3>${recommended?'Hvorfor dette spillet?':'Hvorfor ikke anbefalt?'}</h3>${why}
        <p class="tf-analysis-warning">${esc(warning)}</p>
        <p class="tf-analysis-sources">${sources.map(esc).join(' ')}</p>
      </div>
    </details>`;
  }
  function card(p,recommended,edition){
    const validPrice=Number.isFinite(Number(p.price))&&Number(p.price)>1;
    const rationale=Array.isArray(p.rationale)?p.rationale.find(s=>typeof s==='string'):null;
    return `<article class="tf-card">
      <div class="tf-meta">${esc(p.league||'Fotball')} <span>· ${esc(kickoff(p.kickoff))}</span></div>
      <div class="tf-teams">${esc(p.home)} <span>–</span> ${esc(p.away)}</div>
      <div class="tf-market"><span>${esc(p.label||'Marked under vurdering')}</span>${validPrice?`<strong>${esc(price(p.price))}</strong>`:''}</div>
      <div class="tf-reason">${esc(recommended?(rationale||'Kvalifisert av analysemodellen.'):(p._why||p.reason||'Ikke anbefalt.'))}</div>
      ${recommended?'<div class="tf-note">Indikativ bookmaker-median, kontroller tilgjengelig odds før spill.</div>':''}
      ${analysisDetails(p,recommended,edition)}
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
        const list=$('tf-'+id+'-list');
        // Keep expanded analyses open across automatic data refreshes.
        const expanded=new Set(Array.from(list.querySelectorAll('details.tf-analysis[open]'),el=>el.getAttribute('data-analysis-key')));
        list.innerHTML=entries.length?entries.map(p=>card(p,id!=='watch',edition)).join(''):
          `<p class="tf-empty">${id==='watch'?'Ingen aktuelle objekter under vurdering.':
            'Ingen kvalifiserte forslag akkurat nå.'}</p>`;
        for(const details of list.querySelectorAll('details.tf-analysis')){
          if(expanded.has(details.getAttribute('data-analysis-key')))details.open=true;
        }
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
