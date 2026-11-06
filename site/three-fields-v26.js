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
  function safeMarketCandidates(edition, now){
    const choices=[];
    for(const m of (edition?.matches||[])){
      if(!m||!isOnDay(m,edition,now))continue;
      for(const code of ['H','B','O25','U25','O35','U35']){
        const q=m.odds?.[code];
        if(!freshBookmaker(q,now)||Number(q.price)<1.14||Number(q.price)>1.70)continue;
        const fair=fairMarket(m,code,now);
        if(fair===null||fair<.58)continue;
        const modelChance=numberIn(m.model?.probabilities?.[code]);
        // Never promote a market favourite when our available form model
        // strongly contradicts that favourite.
        if(modelChance!==null && modelChance<fair-.16)continue;
        const bookCount=Number(q.books??q.bookmakers);
        const reasons=[
          `Markedsbasert kandidat: ${Math.round(fair*100)} % anslått fra bookmakerodds uten margin. Dette er ikke dokumentert spillverdi.`,
          `Basert på prisene fra ${bookCount} bookmakere. Ikke et uavhengig modellbekreftet tips.`,
        ];
        if(modelChance!==null)reasons.push(`Formmodell: ${Math.round(modelChance*100)} %. Modellen er ikke kalibrert.`);
        choices.push({matchId:m.id,home:m.home,away:m.away,league:m.league,kickoff:m.kickoff,
          market:code,label:labels[code],price:Number(q.price),bookmakers:bookCount,
          oddsUpdatedAt:q.lastUpdated,oddsSource:q.source||'The Odds API',
          probability:fair,category:'safe',_candidateType:'market',rationale:reasons,
          _rank:fair+.001*bookCount+(modelChance!==null?.02:0)});
      }
    }
    return choices.sort((a,b)=>b._rank-a._rank||a.price-b.price);
  }
  function highModelCandidates(edition, now){
    const choices=[];
    for(const m of (edition?.matches||[])){
      if(!m||!isOnDay(m,edition,now)||!m.model)continue;
      const sample=m.model.sample;
      if(!Array.isArray(sample)||sample.length!==2||!sample.every(x=>Number.isInteger(x)&&x>=5))continue;
      const effective=m.model.effectiveSample;
      if(Array.isArray(effective)&&effective.length===2 && Math.min(...effective.map(Number))<4)continue;
      for(const code of ['H','B','U','O25','U25','O35','U35']){
        const q=m.odds?.[code], modelChance=numberIn(m.model.probabilities?.[code]);
        if(!freshBookmaker(q,now)||Number(q.price)<2.20||Number(q.price)>8||modelChance===null||modelChance<.20||modelChance>.75)continue;
        const fair=fairMarket(m,code,now);
        if(fair===null || Math.abs(modelChance-fair)>.20 || modelChance<fair+.015)continue;
        const comparisons=(m.predictions||[]).map(src=>numberIn(src?.probabilities?.[code])).filter(x=>x!==null);
        if(comparisons.some(x=>x<modelChance-.22))continue;
        const books=Number(q.books??q.bookmakers);
        const reasons=[
          `Modellkandidat: ${Math.round(modelChance*100)} % fra lagform mot ${Math.round(fair*100)} % anslått fra bookmakerodds uten margin.`,
          `Formgrunnlag: ${sample[0]} og ${sample[1]} kamper. Odds fra ${books} bookmakere.`,
          'Foreløpig modellanslag. Spillet bestod ikke den strenge verdikontrollen og er ikke historisk validert.'
        ];
        choices.push({matchId:m.id,home:m.home,away:m.away,league:m.league,kickoff:m.kickoff,
          market:code,label:labels[code],price:Number(q.price),bookmakers:books,
          oddsUpdatedAt:q.lastUpdated,oddsSource:q.source||'The Odds API',
          probability:modelChance,formSample:sample,category:'high',
          _candidateType:'model',rationale:reasons,
          _rank:(modelChance-fair)+.001*books+.001*Math.min(...sample)});
      }
    }
    return choices.sort((a,b)=>b._rank-a._rank||a.price-b.price);
  }

// Supplement the high-risk list with sourced bookmaker outcomes only when
// the form model cannot produce five viable candidates.  This is an
// explicit MARKET-BASED longshot, never a purported statistical edge.
function highMarketCandidates(edition,now){
  const choices=[];
  for(const m of (edition?.matches||[])){
    if(!m||!isOnDay(m,edition,now))continue;
    for(const code of ['H','B','O25','U25','O35','U35']){
      const q=m.odds?.[code];
      if(!freshBookmaker(q,now)||Number(q.price)<2.2||Number(q.price)>5.5)continue;
      const fair=fairMarket(m,code,now);
      if(fair===null||fair<.18||fair>.47)continue;
      const actualModel=numberIn(m.model?.probabilities?.[code]);
      // If a real form model exists and disagrees materially with the
      // bookmaker's implied chance, do not promote the candidate.
      if(actualModel!==null&&actualModel<fair-.12)continue;
      const books=Number(q.books??q.bookmakers);
      if(books<5)continue;
      const why=[
        `Bookmakerbasert risikokandidat: omtrent ${Math.round(fair*100)} % markedsanslag uten margin. Ingen dokumentert positiv spillverdi.`,
        `Pris fra ${books} bookmakere. Ikke kvalifisert gjennom den strenge modellkontrollen.`,
      ];
      if(actualModel!==null)why.push(`Formmodell: ${Math.round(actualModel*100)} % (ikke kalibrert).`);
      else why.push('Fullstendig verifisert formstatistikk mangler for minst ett lag.');
      choices.push({matchId:m.id,home:m.home,away:m.away,league:m.league,kickoff:m.kickoff,
        market:code,label:labels[code],price:Number(q.price),bookmakers:books,
        oddsUpdatedAt:q.lastUpdated,oddsSource:q.source||'The Odds API',probability:fair,
        category:'high',_candidateType:'market',rationale:why,
        _rank:fair+.002*Math.min(books,20)+(actualModel!==null?.03:0)});
    }
  }
  return choices.sort((a,b)=>b._rank-a._rank||a.price-b.price);
}
  function featured(edition,category,now,usedMatches=new Set()){
    const strict=unique((edition?.recommendations||[]).filter(p=>p?.category===category))
      .filter(p=>isOnDay(p,edition,now)&&Number(p.price)>1 &&
        numberIn(p.conservativeEdge)!==null && Number(p.conservativeEdge)>=.02 &&
        freshBookmaker({price:p.price,books:p.bookmakers,lastUpdated:p.oddsUpdatedAt},now));
    const out=[], seen=new Set(usedMatches);
    for(const p of strict){
      if(alreadyUsed(seen,p))continue;
      out.push(p);markUsed(seen,p);
      if(out.length>=5)return out;
    }
    const candidates=category==='safe'?safeMarketCandidates(edition,now):
      [...highModelCandidates(edition,now),...highMarketCandidates(edition,now)];
    for(const p of candidates){
      if(alreadyUsed(seen,p))continue;
      out.push(p);markUsed(seen,p);
      if(out.length>=5)break;
    }
    return out;
  }
  function interesting(edition, now, usedMatches=new Set()){

    const chosen=new Set((edition?.recommendations||[]).map(key));
    const seen=new Set(usedMatches);
    const observations=unique(edition?.observations||[]).filter(p=>futureKickoff(p,now)&&osloDate(new Date(p.kickoff))===dayOf(edition)&&!chosen.has(key(p))&&!alreadyUsed(seen,p)&&freshBookmaker({price:p.price,books:p.bookmakers,lastUpdated:p.oddsUpdatedAt},now))
      .filter(p=>{if(alreadyUsed(seen,p))return false;markUsed(seen,p);return true;})
      .map(p=>({...p,_why:p.reason||'Interessant signal, men ikke kvalifisert som anbefaling.'}));
    const quotes=(edition?.matches||[]).filter(m=>m?.home&&m?.away&&futureKickoff(m,now)&&osloDate(new Date(m.kickoff))===dayOf(edition)&&Object.keys(m.odds||{}).length)
      .filter(m=>!alreadyUsed(seen,m))
      .map(m=>{
        const prices=Object.entries(m.odds||{}).filter(([code,q])=>['H','B','U','O25','U25'].includes(code)&&freshBookmaker(q,now));
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
    for(const p of quotes){if(merged.length>=5)break;if(alreadyUsed(seen,p))continue;merged.push(p);markUsed(seen,p);}
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
      const now=new Date();const useTomorrow=shouldShowTomorrow(today,preview,now);
      let edition=useTomorrow?preview:today;
      if(!edition && preview && dayOf(preview)>=osloDate(now)){edition=preview;}
      const editionDay=dayOf(edition);
      // Share the actual edition selected by the existing picker with the
      // supplementary market radar. No new odds or tips are calculated here.
      const marketRoot=$('tf-root');
      if(marketRoot?.dataset){
        marketRoot.dataset.ogEditionDate=editionDay;
        marketRoot.dataset.ogEditionFile=edition===preview?'tomorrow':'today';
      }
      const todayExpired=edition && editionDay<osloDate(now);
      const starts=shownKickoffs(edition,now);
      const expired=!!(todayExpired || (edition&&!useTomorrow&&starts.length&&starts.every(t=>t<=+now)));
      // Give eligible low-odds candidates their own slot before high-risk
      // selections consume the same fixture. Quality gates are unchanged.
      const safe=edition&&!expired?featured(edition,'safe',now):[];
      const occupied=new Set();for(const p of safe)markUsed(occupied,p);
      const high=edition&&!expired?featured(edition,'high',now,occupied):[];
      for(const p of high)markUsed(occupied,p);
      const watch=edition&&!expired?interesting(edition,now,occupied):[];
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
      $('tf-status').textContent=expired?'Dagens kamper har startet. Neste utvalg publiseres automatisk når analysen er klar.':
        'Kvalifiserte spill, modellkandidater og markedsbaserte kandidater er tydelig merket. Odds er fra siste registrerte analyse, ikke sanntidspriser.';
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
