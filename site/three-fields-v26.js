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
  // Identity is per real match, not per provider-specific numeric/odds ID.
  // Only narrow, known team-name aliases are used. Never guess unrelated teams.
  const gameToken = p => {
    const canon = name => {
      const n=String(name||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
        .toLowerCase().replace(/[^a-z0-9]/g,'');
      const aliases={boltonwanderers:'bolton',silkeborgif:'silkeborg',
        fczwolle:'zwolle',peczwolle:'zwolle'};
      return aliases[n]||n;
    };
    const h=canon(p.home),a=canon(p.away),k=new Date(p.kickoff);
    return h&&a&&Number.isFinite(+k)?`game:${h}|${a}|${osloDate(k)}`:null;
  };
  const alreadyUsed = (seen,p) => seen.has(String(p.matchId??p.id)) ||
    (gameToken(p)!==null && seen.has(gameToken(p)));
  const markUsed = (seen,p) => {
    seen.add(String(p.matchId??p.id));
    const k=gameToken(p);if(k)seen.add(k);
  };
  const unique = picks => {
    const used=new Set();return picks.filter(p=>{if(!p || !p.home || !p.away || !futureKickoff(p,new Date()))return false;
      const k=key(p);if(used.has(k))return false;used.add(k);return true;});
  };
  // Additional opportunities are candidates, NEVER substitutes for the strict
  // uncalibrated value gate. Every listed price must exist in this edition.
  const numberIn = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)) ? Number(value) : null;
  const labels = {H:'Hjemmeseier',B:'Borteseier',U:'Uavgjort',O25:'Over 2,5 mål',U25:'Under 2,5 mål',O35:'Over 3,5 mål',U35:'Under 3,5 mål',BTTS:'Begge lag scorer'};
  const isOnDay = (p,edition,now) => futureKickoff(p,now) && osloDate(new Date(p.kickoff))===dayOf(edition);
  function freshBookmaker(q, now){
    const odds=numberIn(q?.price), books=numberIn(q?.books ?? q?.bookmakers);
    const stamped=+new Date(q?.lastUpdated ?? q?.oddsUpdatedAt);
    const age=+now-stamped;
    return odds!==null && odds>=1.05 && odds<=25 && books!==null && books>=3 && Number.isFinite(stamped) &&
      age>=-120000 && age<=18*3600000;
  }
  function fairMarket(m,code,now){
    const quotes=m.odds||{};
    let pair;
    if(['H','U','B'].includes(code))pair=['H','U','B'];
    else if(code==='O25'||code==='U25')pair=['O25','U25'];
    else if(code==='O35'||code==='U35')pair=['O35','U35'];
    else return null;
    if(!pair.every(k=>freshBookmaker(quotes[k],now)))return null;
    const overround=pair.reduce((sum,k)=>sum+1/Number(quotes[k].price),0);
    if(overround<.98||overround>1.27)return null;
    return (1/Number(quotes[code].price))/overround;
  }
  // v40: betting candidates are generated by scripts/final_selection_v40.py.
  // The browser must never calculate, re-rank or backfill tips.
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
    const match=(Array.isArray(edition?.matches)?edition.matches:[])
      .find(m=>m && String(m.id)===String(p.matchId));
    const model=match?.model || null;
    const quote=match?.odds?.[p.market] || null;
    const formHome=String(match?.formHome || p.formHome || '').trim();
    const formAway=String(match?.formAway || p.formAway || '').trim();

    // The data provider stores results newest first. Show at most five real
    // results, never pad missing history with invented outcomes.
    const recentForm=(team,sequence,records,role)=>{
      const raw=Array.isArray(records)?records:[];
      const verdict={'W':'S','D':'U','L':'T'};
      const valid=r=>{
        if(!r||r.verified!==true||r.status!=='FINISHED'||!['W','D','L'].includes(r.resultForAnalyzedTeam))return false;
        if(!Number.isInteger(r.homeGoals)||r.homeGoals<0||!Number.isInteger(r.awayGoals)||r.awayGoals<0)return false;
        if(!r.homeTeam?.name||!r.awayTeam?.name||!['home','away'].includes(r.analyzedTeamSide))return false;
        if(!Number.isFinite(+new Date(r.kickoffUtc)))return false;
        const goals=r.analyzedTeamSide==='home'?[r.homeGoals,r.awayGoals]:[r.awayGoals,r.homeGoals];
        const expected=goals[0]>goals[1]?'W':goals[0]<goals[1]?'L':'D';
        return expected===r.resultForAnalyzedTeam;
      };
      const rows=raw.filter(valid).slice(0,5);
      const heading=`<div class="tf-form-side"><strong>${esc(team)}</strong><span>${esc(role)}</span></div>`;
      const label='<div class="tf-form-scope">Siste 5 kamper, alle arenaer</div>';
      if(rows.length){
        const content=rows.map(r=>{
          const dt=new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(r.kickoffUtc));
          const outcome=r.resultForAnalyzedTeam;
          const venue=r.analyzedTeamSide==='home'?'Hjemme':'Borte';
          const source=r.source?` · ${esc(r.source)}`:'';
          return `<div class="tf-form-match"><div class="tf-form-match-info">${esc(dt)} · ${venue}${source}</div>`+
            `<div class="tf-form-match-result"><span>${esc(r.homeTeam.name)} <b>${r.homeGoals}–${r.awayGoals}</b> ${esc(r.awayTeam.name)}</span>`+
            `<span class="tf-form-badge tf-form-${outcome}" title="${outcome==='W'?'Seier':outcome==='D'?'Uavgjort':'Tap'}">${verdict[outcome]}</span></div></div>`;
        }).join('');
        const caveat=rows.length<5?`<p class="tf-form-limited">${rows.length} verifiserbare kamper er tilgjengelige i denne utgaven.</p>`:'';
        return `<div class="tf-form-report">${heading}${label}<div class="tf-form-results">${content}</div>${caveat}</div>`;
      }
      // New-format records without complete metadata must never fall back to
      // unverified score badges. Only historical snapshots can show legacy WDL.
      if(Array.isArray(records)){
        return `<div class="tf-form-report">${heading}${label}<p class="tf-form-limited">Ingen verifiserbare kampdetaljer tilgjengelig for dette laget i dagens datagrunnlag.</p></div>`;
      }
      // Older published editions contain only W/D/L strings, no actual match
      // details. Label the legacy sequence honestly instead of inventing them.
      const legacy=/^[WDL]{1,20}$/.test(sequence)?sequence.slice(0,5).split(''):[];
      if(legacy.length){
        const badges=legacy.map(v=>`<span class="tf-form-badge tf-form-${v}" title="${v==='W'?'Seier':v==='D'?'Uavgjort':'Tap'}">${verdict[v]}</span>`).join('');
        return `<div class="tf-form-report">${heading}${label}<div class="tf-form-badges">${badges}</div>`+
          '<p class="tf-form-limited">Eldre utgave: kampdetaljer kan ikke verifiseres. Kun registrert formrekkefølge.</p></div>';
      }
      return `<div class="tf-form-report">${heading}${label}<p class="tf-form-limited">Ingen registrert kampform med verifiserbare kampdetaljer.</p></div>`;
    };

    // Do not misrepresent bookmaker-implied percentages as independent models.
    const modelChance=finiteNumber(model?.probabilities?.[p.market]);
    const recordedChance=finiteNumber(p.probability);
    const conservativeChance=finiteNumber(p.conservativeProbability);
    let chance=null, method='';
    if(recommended && !p._candidateType && conservativeChance!==null){
      chance=conservativeChance;method='Konservativt modellscenario, ikke kalibrert';
    }else if(p._candidateType==='market'){
      chance=recordedChance;
      if(chance===null && match)chance=fairMarket(match,p.market,new Date());
      method='Anslått fra bookmakerodds uten margin';
    }else if(modelChance!==null){
      chance=modelChance;method='Formmodell, ikke historisk kalibrert';
    }else if(recordedChance!==null && p._candidateType==='model'){
      chance=recordedChance;method='Foreløpig modellanslag, ikke kalibrert';
    }else if(match){
      chance=fairMarket(match,p.market,new Date());
      method='Anslått fra bookmakerodds uten margin';
    }
    const chanceText=chance!==null && chance>=0 && chance<=1 ? fraction(chance) : null;

    // An expert quote must have attribution. Provider numeric forecasts alone
    // do not constitute an expert's written explanation.
    const verifiedExpert=(typeof p.expertReason==='string' && p.expertReason.trim() &&
      typeof p.expertSource==='string' && p.expertSource.trim())?
      {reason:p.expertReason.trim(),source:p.expertSource.trim()}:
      (Array.isArray(match?.predictions)?match.predictions:[])
        .filter(x=>x && typeof x.reason==='string' && x.reason.trim() &&
          typeof x.source==='string' && x.source.trim())[0];
    let heading='Vurdering';
    let reason='';
    if(verifiedExpert){
      heading='Ekspertens begrunnelse';
      reason=`${esc(verifiedExpert.reason)} <span class="tf-attribution">${esc(verifiedExpert.source)}</span>`;
    }else if(p._candidateType==='market'){
      reason='Spillet er valgt ut fra registrerte bookmakerodds. Det er en markedsbasert kandidat, ikke et dokumentert verdiobjekt.';
    }else if(p._candidateType==='model'){
      reason='Spillet er valgt som modellkandidat ut fra registrert lagform og bookmakerpriser. Modellens treffsikkerhet er ikke dokumentert.';
    }else if(recommended){
      reason='Spillet har passert modellens verdifilter. Beregningen er foreløpig og er ikke historisk kalibrert.';
    }else{
      reason=esc(p.reason || p._why || 'Kampen er under vurdering, men datagrunnlaget er foreløpig utilstrekkelig.');
    }

    const analysisKey=`${dayOf(edition)}|${String(p.matchId??'')}|${String(p.market??'')}`;
    return `<details class="tf-analysis" data-analysis-key="${esc(analysisKey)}">
      <summary><span class="tf-show">Vis analysen</span><span class="tf-hide">Skjul analysen</span></summary>
      <div class="tf-analysis-body tf-analysis-compact">
        <section class="tf-compact-block"><h3>${heading}</h3><p>${reason}</p></section>
        <section class="tf-compact-block"><h3>Siste fem kamper <span class="tf-form-order">nyeste først · alle arenaer</span></h3>
          ${recentForm(p.home,formHome,match?.formMatchesHome,'HJEMMELAG')}
          ${recentForm(p.away,formAway,match?.formMatchesAway,'BORTELAG')}
        </section>
        <section class="tf-compact-block"><h3>Sannsynlighet for spillet</h3>
          <div class="tf-probability">${chanceText===null?'Ikke beregnet':esc(chanceText)}</div>
          ${chanceText===null?'':`<p class="tf-probability-source">${esc(method)}</p>`}
        </section>
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
      ${recommended?`<div class="tf-note">${p._candidateType==='market'?(p.category==='high'?'Markedsbasert High Risk · ingen modellbekreftet verdi':'Markedsbasert Safe Bet · ikke modellbekreftet'):p._candidateType==='model'?'Modellkandidat · ikke kvalifisert verdiobjekt':'Kvalifisert i modellens konservative scenario'} · Sjekk oppdatert bookmakerodds.</div>`:''}
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
      const now=new Date();
      const chosen=window.OddsVisibleV40?.selectEdition(today,preview,now)||null;
      const useTomorrow=Boolean(chosen?.useTomorrow);
      const edition=chosen?.edition||null;
      const editionDay=dayOf(edition);
      // Share the actual edition selected by the existing picker with the
      // supplementary market radar. No new odds or tips are calculated here.
      const marketRoot=$('tf-root');
      if(marketRoot?.dataset){
        marketRoot.dataset.ogEditionDate=editionDay;
        marketRoot.dataset.ogEditionFile=edition===preview?'tomorrow':'today';
      }
      const expired=Boolean(chosen?.expired);
      const safe=chosen?.groups.safe||[];
      const high=chosen?.groups.high||[];
      const watch=chosen?.groups.watch||[];
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
            id==='safe'?'Ingen Safe Bets oppfyller dagens krav. Ingen udokumenterte tips legges til.':'Ingen dokumenterte kandidater fra dagens datagrunnlag.'}</p>`;
        for(const details of list.querySelectorAll('details.tf-analysis')){
          if(expanded.has(details.getAttribute('data-analysis-key')))details.open=true;
        }
      }
      const lack=Object.entries({safe:'Safe Bets',high:'High Risk',watch:'Interessante objekter'})
        .filter(([key])=>(chosen?.groups[key]||[]).length<3)
        .map(([key,name])=>`${name}: færre enn tre konfliktfrie kandidater med gyldig datagrunnlag.`).join(' ');
      $('tf-status').textContent=expired?'Dagens kamper har startet. Neste utvalg publiseres automatisk når analysen er klar.':
        !chosen?.authoritative?'Dagsutgaven mangler sentral konfliktkontroll. Ingen gamle frontendforslag vises.':
        'Alle tips er valgt i backend og kontrollert for kampkonflikter. Odds er ikke sanntidspriser. '+lack;
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
