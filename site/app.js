'use strict';
const $ = id => document.getElementById(id);
const esc = x => String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nbDate = new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',weekday:'long',day:'numeric',month:'long'});
const nbTime = new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit'});
const fmtOdds = x => Number(x).toLocaleString('nb-NO',{minimumFractionDigits:2,maximumFractionDigits:2});
const pct = x => `${Math.round(Number(x)*100)} %`;
const dateISO = date => {let p=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Oslo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date).filter(v=>v.type!=='literal').map(v=>[v.type,v.value]));return `${p.year}-${p.month}-${p.day}`;};
const formatEdition = s => {if(!/^\d{4}-\d\d-\d\d$/.test(s||''))return 'Ingen dagsutgave';const d=new Date(`${s}T12:00:00Z`);return nbDate.format(d).replace(/^./,x=>x.toUpperCase());};
const formText = s => {if(!s) return '–';const vals=[...'WDL'].map(k=>[...String(s).toUpperCase()].filter(x=>x===k).length);return `${vals[0]}S · ${vals[1]}U · ${vals[2]}T`;};
const states={scheduled:'Ikke startet',live:'Pågår',won:'Vunnet',lost:'Tapt',void:'Avlyst',postponed:'Utsatt',unverified:'Avventer'};
function state(p){return p?.result?.status || 'scheduled';}
function displayState(p){const v=state(p);if(v==='scheduled'&&Date.parse(p.kickoff)<Date.now())return 'Avventer resultat';return states[v]||'Avventer';}
function statusChip(p,small=false){const v=state(p);return `<span class="${small?'risk-status':'result-badge'} ${esc(v)}">${esc(displayState(p))}</span>`;}
const label=p=>p.category==='safe'?'SAFE BET':p.category==='high'?'HIGH RISK':'DAGENS TIPS';
function fixtureScore(p){const s=p.result?.score;return s && Number.isInteger(s.home)&&Number.isInteger(s.away)?`<span class="fixture-score">${s.home}–${s.away}</span>`:'';}
function pickCard(p,i){const key=`p-${i}`,prob=Number(p.probability),breakEven=1/Number(p.price),src=p.probabilitySource==='market'?'Markedssjanse':'Modellsjanse';return `<article class="pick">
  <div class="pick-top"><span>${esc(p.league||'Fotball')}</span><span class="top-right">${fixtureScore(p)} ${statusChip(p)}<span>${nbTime.format(new Date(p.kickoff))}</span></span></div>
  <h3 class="fixture">${esc(p.home)} <span aria-hidden="true" style="color:#895c6f">–</span> ${esc(p.away)}</h3>
  <div class="play-row"><div><div class="play-label">ANBEFALT SPILL</div><div class="play-name">${esc(p.label)}</div></div><div><div class="price">${fmtOdds(p.price)}</div><span class="price-caption">ODDS VED ANALYSE</span></div></div>
  <div class="prob-row"><div><small>${esc(src)}</small><b class="prob-color">${pct(prob)}</b></div><div><small>Nullpunkt i odds</small><b>${pct(breakEven)}</b></div></div>
  <div class="pick-foot"><span class="chip ${esc(p.category)}">${label(p)}</span><button type="button" class="details-toggle" data-open="${key}" aria-controls="${key}" aria-expanded="false">Statistikk +</button></div>
  <div id="${key}" class="details"><div class="details-grid">
    <div><div class="detail-title">${esc(p.home)} · siste kamper</div><div class="detail-value">${esc(formText(p.formHome))}</div></div>
    <div><div class="detail-title">${esc(p.away)} · siste kamper</div><div class="detail-value">${esc(formText(p.formAway))}</div></div>
    <div><div class="detail-title">Modellavvik</div><div class="detail-value">${Number.isFinite(Number(p.modelEdge)) && p.modelEdge!=null ? (Number(p.modelEdge)*100).toFixed(1).replace('.',',')+' %':'–'}</div></div>
    <div><div class="detail-title">Oddsgrunnlag</div><div class="detail-value">${esc(p.bookmakers||'–')} bookmakere</div></div>
    <div><div class="detail-title">Formgrunnlag</div><div class="detail-value">${Array.isArray(p.formSample)?esc(p.formSample.join(' / '))+' kamper':'–'}</div></div>
    <div><div class="detail-title">Resultatstatus</div><div class="detail-value">${esc(displayState(p))}</div></div>
  </div></div></article>`;}
function riskCard(p){return `<div class="risk-item"><div><div class="risk-title">${esc(p.home)} – ${esc(p.away)}</div><div class="risk-sub">${esc(p.label)} · ${nbTime.format(new Date(p.kickoff))} ${fixtureScore(p)}</div><div class="risk-data">${p.probabilitySource==='market'?'Marked':'Modell'} ${pct(p.probability)} · ${esc(formText(p.formHome))}</div></div><div class="risk-right"><div class="risk-odds">${fmtOdds(p.price)}</div>${statusChip(p,true)}</div></div>`;}
function uniqPicks(data){const seen=new Map();for(const p of [...(data.recommendations||[]),...(data.safeBets||[]),...(data.highRisk||[])]){const k=`${p.matchId}:${p.market||p.label}`;if(!seen.has(k))seen.set(k,p);}return [...seen.values()];}
function show(data,preview=false){
  const edition=data.editionDate||data.localDate;
  const picks=(data.recommendations||[]).slice(0,5),safe=(data.safeBets||[]).slice(0,5),high=(data.highRisk||[]).slice(0,5);
  const all=uniqPicks(data),counts={won:0,lost:0,live:0};for(const p of all){const s=state(p);if(s in counts)counts[s]++;}
  $('today-date').textContent=formatEdition(edition);
  $('last-updated').textContent=data.generatedAt?'Analyse '+nbTime.format(new Date(data.generatedAt)):'Ingen analyse';
  $('demo-marker').hidden=!preview;
  $('engine-status').textContent=preview?'Designforhåndsvisning':(data.dataStatus?.fixtures==='ok'&&data.dataStatus?.odds==='ok'?'Kilder oppdatert':'Dekning begrenset');
  $('metric-picks').textContent=String(all.length);$('metric-won').textContent=counts.won;$('metric-lost').textContent=counts.lost;$('metric-live').textContent=counts.live;
  $('tips-count').textContent=picks.length+' tips';$('safe-count').textContent=String(safe.length);$('high-count').textContent=String(high.length);
  $('top-picks').innerHTML=picks.length?picks.map(pickCard).join(''):'<div class="empty">Ingen utvalgte tips i denne utgaven.</div>';
  $('safe-list').innerHTML=safe.length?safe.map(riskCard).join(''):'<div class="empty">Ingen kvalifiserte Safe Bets denne dagen.</div>';
  $('high-list').innerHTML=high.length?high.map(riskCard).join(''):'<div class="empty">Ingen kvalifiserte High Risk-spill denne dagen.</div>';
  const coverage=data.coverage||{};
  $('engine-coverage').textContent=`${coverage.matchedOdds ?? 0}/${coverage.upcomingMatches ?? 0} kamper med odds`;
  const sources=(data.sources||[]).filter(x=>x.state==='connected');
  $('engine-sources').textContent=preview?'Design / demo':`${sources.length} aktive kilder`;
  $('stats-matches').textContent=String(coverage.upcomingMatches ?? (data.matches||[]).length);
  $('stats-priced').textContent=String(coverage.matchedOdds ?? 0);
  $('stats-count').textContent=String(all.length);
  $('stats-average').textContent=all.length?pct(all.reduce((a,p)=>a+Number(p.probability||0),0)/all.length):'–';
  $('source-footnote').textContent=preview?'Fiktive data for designvisning':`Automatisk: ${sources.map(x=>x.name).join(' + ')||'ingen'} · Uavhengige prognoser: ${coverage.apiPredictions||0}`;
  $('result-updated').textContent=data.resultUpdatedAt?'Resultatkontroll '+nbTime.format(new Date(data.resultUpdatedAt)):'Resultater oppdateres automatisk';
  const warning=$('alert');warning.hidden=true;
  if(!preview&&edition&&edition!==dateISO(new Date())){warning.hidden=false;warning.textContent='Forrige dagsutgave vises frem til neste vellykkede morgenanalyse.';}
  if(!preview&&data.dataStatus?.fixtures!=='ok'){warning.hidden=false;warning.textContent='Kun lagret analyse er tilgjengelig. Siste datainnhenting er ikke bekreftet.';}
  document.querySelectorAll('.details-toggle').forEach(b=>b.addEventListener('click',()=>{const e=$(b.dataset.open),open=e.classList.toggle('open');b.setAttribute('aria-expanded',String(open));b.textContent=open?'Skjul statistikk −':'Statistikk +';}));
}
function demoSnapshot(){const now=new Date(),today=dateISO(now);const at=(hour,min)=>{const t=new Date(now);t.setHours(hour,min,0,0);return t.toISOString();};let i=0;
  const pick=(home,away,league,market,label,price,prob,category,result,hour=21)=>({matchId:'demo'+(++i),home,away,league,market,label,price,probability:prob,category,kickoff:at(hour,0),probabilitySource:category==='safe'?'market':'model',bookmakers:5,formHome:'WWDWLW',formAway:'DWLWLW',formSample:[6,6],modelEdge:prob*price-1,result:result||{status:'scheduled'}});
  const a=pick('Nordhavn','Solstrand','Champions League','H','Hjemmeseier',1.43,.67,'safe',{status:'won',score:{home:2,away:0}});
  const b=pick('Riverside','Vestby','Championship','O25','Over 2,5 mål',2.08,.52,'high',{status:'lost',score:{home:1,away:1}});
  const c=pick('Olympia','Kystbyen','Champions League','B','Borteseier',3.15,.39,'high',{status:'live',score:{home:0,away:1}});
  const d=pick('Rosenvik','Linden','Serie A','H','Hjemmeseier',1.57,.64,'safe',{status:'scheduled'});
  const e=pick('Eastbridge','Lago','La Liga','O35','Over 3,5 mål',2.74,.40,'high',{status:'scheduled'});
  const f=pick('Alpen FC','LASKbyen','Bundesliga','B','Borteseier',1.51,.64,'safe',{status:'scheduled'});
  return {editionDate:today,localDate:today,generatedAt:now.toISOString(),resultUpdatedAt:now.toISOString(),
    recommendations:[a,b,c,d,e],safeBets:[a,d,f],highRisk:[b,c,e],coverage:{upcomingMatches:24,matchedOdds:19,withModel:16},
    sources:[{name:'football-data.org',state:'connected'},{name:'The Odds API',state:'connected'}],dataStatus:{fixtures:'ok',odds:'ok'}};}
async function loadLatest(){if(window.__ODDSGEN_DEMO__){show(demoSnapshot(),true);return;}try{const res=await fetch('data/today.json?v='+Date.now(),{cache:'no-store'});if(!res.ok)throw Error('Snapshot not found');const data=await res.json();if(!Array.isArray(data.recommendations))throw Error('Malformed snapshot');show(data);}catch(err){show({recommendations:[],safeBets:[],highRisk:[],coverage:{},sources:[],dataStatus:{}},false);const warning=$('alert');warning.hidden=false;warning.textContent='Ingen publisert dagsutgave er tilgjengelig ennå.';}}
$('refresh-data').addEventListener('click',async()=>{const b=$('refresh-data');b.disabled=true;try{await loadLatest();}finally{b.disabled=false;}});
loadLatest();
