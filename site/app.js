'use strict';
const $=id=>document.getElementById(id);
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dayFormat=new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',day:'numeric',month:'long',year:'numeric'});
const clockFormat=new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit'});
const fmtOdds=value=>Number(value).toLocaleString('nb-NO',{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtPct=value=>`${Math.round(Number(value)*100)} %`;
const dateISO=date=>{const p=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Oslo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date).filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));return `${p.year}-${p.month}-${p.day}`;};
const labelDate=day=>/^\d{4}-\d{2}-\d{2}$/.test(day||'')?dayFormat.format(new Date(`${day}T12:00:00Z`)):'Ingen dagsutgave';
const statusNames={scheduled:'Ikke startet',live:'LIVE',won:'Vunnet',lost:'Tapt',void:'Avlyst',postponed:'Utsatt',unverified:'Avventer'};
const resultOf=pick=>pick?.result||{status:'scheduled'};
const statusOf=pick=>resultOf(pick).status||'scheduled';
const validScore=score=>score&&Number.isInteger(score.home)&&Number.isInteger(score.away);
const scoreText=pick=>validScore(resultOf(pick).score)?`${resultOf(pick).score.home}–${resultOf(pick).score.away}`:null;
function statusText(pick){
  const r=resultOf(pick),s=statusOf(pick);
  if(s==='live'){
    if(r.phase==='Pause')return 'Pause';
    if(r.phase==='Ekstraomganger')return 'Ekstraomganger';
    if(r.phase==='Straffer')return 'Straffer';
    return Number.isInteger(r.minute)?`${r.minute}′ LIVE`:'LIVE';
  }
  if(s==='scheduled'&&Date.parse(pick.kickoff)<Date.now())return 'Avventer';
  return statusNames[s]||'Avventer';
}
function badge(pick){let s=statusOf(pick);if(s==='scheduled'&&Date.parse(pick.kickoff)<Date.now())s='unverified';return `<span class="result-badge ${escapeHtml(s)}">${escapeHtml(statusText(pick))}</span>`;}
function formText(s){if(!s)return '–';const a=[...'WDL'].map(x=>[...String(s).toUpperCase()].filter(v=>v===x).length);return `${a[0]}S · ${a[1]}U · ${a[2]}T`;}
function atTime(s){const dt=new Date(s);return Number.isFinite(dt.getTime())?clockFormat.format(dt):'–';}
function probabilityName(p){return p.probabilitySource==='market'?'Markedssjanse':'Modellanslag';}
function pickCard(p,i){
  const probability=Number(p.probability),niceProb=Number.isFinite(probability)?Math.max(0,Math.min(100,probability*100)):0;
  const id=`details-${i}`;
  const reasonList=(p.rationale||[]).slice(0,4).map(s=>`<li>${escapeHtml(s)}</li>`).join('');
  const stats=[
    ['Hjemmelag, siste kamper',formText(p.formHome)],
    ['Bortelag, siste kamper',formText(p.formAway)],
    ['Kamper i modellgrunnlaget',Array.isArray(p.formSample)?p.formSample.join(' / '):'–'],
    ['Odds fra',p.bookmakers?`${p.bookmakers} bookmakere`:'–']
  ];
  return `<article class="pick" data-match-id="${escapeHtml(p.matchId||'')}">
    <div class="pick-top"><span>${escapeHtml(p.league||'Fotball')}</span><div class="pick-top-right">${badge(p)}<span>${atTime(p.kickoff)}</span></div></div>
    <div class="fixture"><h3 class="team-names">${escapeHtml(p.home)}<span class="vs">–</span>${escapeHtml(p.away)}</h3>${scoreText(p)?`<strong class="fixture-score">${scoreText(p)}</strong>`:''}</div>
    <div class="play-row"><div><div class="play-label">ANBEFALT SPILL</div><div class="play-name">${escapeHtml(p.label)}</div></div><div><div class="price">${fmtOdds(p.price)}</div><span class="price-caption">ODDS VED ANALYSE</span></div></div>
    <div class="probline"><span class="prob-label">${escapeHtml(probabilityName(p))}</span><span class="prob-value">${fmtPct(probability)}</span></div><div class="prob-track" aria-hidden="true"><div class="prob-track-fill" style="width:${niceProb.toFixed(1)}%"></div></div>
    <div class="pick-foot"><span class="tag ${p.category==='high'?'high':''}">${escapeHtml(p.category==='safe'?'SAFE BET':p.category==='high'?'HIGH RISK':'DAGENS TIPS')}</span><button type="button" class="details-toggle" data-open="${id}" aria-controls="${id}" aria-expanded="false">Vis analyse +</button></div>
    <div class="details" id="${id}"><dl class="detail-grid">${stats.map(([k,v])=>`<div class="detail"><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`).join('')}</dl>${reasonList?`<ul class="detail-reasons">${reasonList}</ul>`:''}</div>
  </article>`;
}
function smallCard(p){const score=scoreText(p);return `<article class="mini"><div class="mini-main"><div class="mini-league">${escapeHtml(p.league||'Fotball')} · ${atTime(p.kickoff)}</div><div class="mini-names">${escapeHtml(p.home)} – ${escapeHtml(p.away)}</div><div class="mini-pick">${escapeHtml(p.label)}</div></div><div class="mini-right"><span class="mini-price">${fmtOdds(p.price)}</span>${score?`<span class="mini-score">${score}</span>`:''}${badge(p)}</div></article>`;}
function uniqueMatches(data){const map=new Map();for(const p of [...(data.recommendations||[]),...(data.safeBets||[]),...(data.highRisk||[])]){const id=String(p.matchId||`${p.home}-${p.away}-${p.kickoff}`);if(!map.has(id))map.set(id,p);else if(statusOf(p)==='live'&&statusOf(map.get(id))!=='live')map.set(id,p);}return [...map.values()];}
function liveCard(p){return `<article class="live-match"><div class="live-teams">${escapeHtml(p.home)} – ${escapeHtml(p.away)}</div><div class="score">${scoreText(p)||'– : –'}</div><div class="live-minute">${escapeHtml(statusText(p))}</div></article>`;}
function show(data,demo=false){
  const ed=data.editionDate||data.localDate;
  const picks=(data.recommendations||[]).slice(0,5);
  const safe=(data.safeBets||[]).slice(0,5),high=(data.highRisk||[]).slice(0,5);
  $('today-date').textContent=labelDate(ed);
  $('last-updated').textContent=data.generatedAt?`Analyse ${atTime(data.generatedAt)}`:'Ingen analyse';
  $('demo-marker').hidden=!demo;
  $('demo-note').hidden=!demo;
  $('tips-count').textContent=String(picks.length);$('safe-count').textContent=String(safe.length);$('high-count').textContent=String(high.length);
  $('top-picks').innerHTML=picks.length?picks.map(pickCard).join(''):'<div class="empty">Ingen utvalgte tips i denne dagsutgaven.</div>';
  $('safe-list').innerHTML=safe.length?safe.map(smallCard).join(''):'<div class="empty">Ingen kvalifiserte Safe Bets denne dagen.</div>';
  $('high-list').innerHTML=high.length?high.map(smallCard).join(''):'<div class="empty">Ingen kvalifiserte High Risk-spill denne dagen.</div>';
  const live=uniqueMatches(data).filter(p=>statusOf(p)==='live');
  $('live').hidden=!live.length;
  $('live-count').textContent=live.length?String(live.length):'';
  $('live-list').innerHTML=live.map(liveCard).join('');
  $('result-updated').textContent=data.resultUpdatedAt?`Sist oppdatert ${atTime(data.resultUpdatedAt)}`:'Oppdatering avventes';
  $('footer-status').textContent=data.resultUpdatedAt?`Resultater ${atTime(data.resultUpdatedAt)}`:'';
  const notice=$('alert');notice.hidden=true;
  if(!demo&&(!ed||!(data.dataStatus&&Array.isArray(data.recommendations)))){
    notice.textContent='Ingen dagsutgave er publisert ennå.';notice.hidden=false;
  }
  document.querySelectorAll('.details-toggle').forEach(btn=>btn.addEventListener('click',()=>{const d=$(btn.dataset.open),opened=d.classList.toggle('open');btn.setAttribute('aria-expanded',String(opened));btn.textContent=opened?'Skjul analyse −':'Vis analyse +';}));
}
function demoSnapshot(){
  const now=new Date(),today=dateISO(now);let i=0;
  const at=(h,m)=>{const x=new Date(now);x.setHours(h,m,0,0);return x.toISOString();};
  const make=(home,away,league,market,label,price,prob,category,result,clock,form=['WWDWLW','DLWDLW'])=>({matchId:'demo'+(++i),home,away,league,market,label,price,probability:prob,category,kickoff:at(clock,0),probabilitySource:category==='safe'?'market':'model',bookmakers:5,formHome:form[0],formAway:form[1],formSample:[6,5],modelEdge:prob*price-1,rationale:['Form siste seks kamper','Odds fra fem bookmakere'],result});
  const a=make('Northbridge','Westfield','Champions League','H','Hjemmeseier',1.43,.68,'safe',{status:'live',score:{home:2,away:0},minute:67,phase:'Live'},21);
  const b=make('Riverside','Linden','Championship','O25','Over 2,5 mål',2.18,.49,'high',{status:'live',score:{home:1,away:1},minute:72,phase:'Live'},21);
  const c=make('Fjordvik','Rosendale','Champions League','B','Borteseier',3.15,.39,'high',{status:'scheduled'},22);
  const d=make('Olympia','Harbour FC','Serie A','H','Hjemmeseier',1.56,.64,'safe',{status:'won',score:{home:2,away:0}},18);
  const e=make('Eastside','Arbor','La Liga','O35','Over 3,5 mål',2.76,.40,'high',{status:'lost',score:{home:1,away:1}},19);
  const f=make('Alpen','Valletta','Bundesliga','H','Hjemmeseier',1.51,.65,'safe',{status:'scheduled'},22);
  return {version:3,editionDate:today,localDate:today,generatedAt:at(9,17),resultUpdatedAt:now.toISOString(),recommendations:[a,b,c,d,e],safeBets:[a,d,f],highRisk:[b,c,e],dataStatus:{fixtures:'ok',odds:'ok'}};
}
async function loadLatest(){
  if(window.__ODDSGEN_DEMO__){show(demoSnapshot(),true);return;}
  try{
    const res=await fetch(`data/today.json?v=${Date.now()}`,{cache:'no-store'});
    if(!res.ok)throw Error(`Snapshot unavailable ${res.status}`);
    const data=await res.json();if(!Array.isArray(data.recommendations))throw Error('Unexpected snapshot');show(data,false);
  }catch(e){show({recommendations:[],safeBets:[],highRisk:[],dataStatus:{}},false);}
}
const refresh=$('refresh-data');refresh.addEventListener('click',async()=>{refresh.disabled=true;try{await loadLatest();}finally{refresh.disabled=false;}});
// Refreshes the already-published GitHub Pages snapshot; no secrets or bookmaker calls in browser.
// GitHub Actions publishes changes periodically, not as a true second-by-second live feed.
setInterval(()=>{if(document.visibilityState==='visible'&&!window.__ODDSGEN_DEMO__)loadLatest();},60*1000);
loadLatest();
