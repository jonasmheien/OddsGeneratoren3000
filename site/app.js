'use strict';
const el=id=>document.getElementById(id);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dateFmt=new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',weekday:'long',day:'numeric',month:'long'});
const timeFmt=new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit'});
const stampFmt=new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit'});
const fmtOdds=x=>Number(x).toLocaleString('nb-NO',{minimumFractionDigits:2,maximumFractionDigits:2});
const pct=x=>Math.round(Number(x)*100)+' %';
const dayISO = date => {
  const part=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Oslo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date).filter(v=>v.type!=='literal').map(v=>[v.type,v.value]));
  return `${part.year}-${part.month}-${part.day}`;
};
function formText(s){
  if(!s) return '–';
  const xs=[...'WDL'].map(k=>[...String(s).toUpperCase()].filter(x=>x===k).length);
  return `${xs[0]}S · ${xs[1]}U · ${xs[2]}T`;
}
function demoSnapshot(){
  const now=new Date();
  const at=(h,m)=>{const d=new Date(now);d.setHours(h,m,0,0);return d.toISOString();};
  const pick=(id,home,away,league,h,m,label,price,category,prob,formHome,formAway,bookmakers)=>({
    matchId:id,home,away,league,kickoff:at(h,m),label,price,category,probability:prob,modelEdge:prob*price-1,formHome,formAway,bookmakers,
    oddsUpdatedAt:now.toISOString(),oddsSource:'Eksempeldata'
  });
  const recommendations=[
    pick('demo1','Nordby FK','Fjordvik','Eksempelliga',21,0,'Hjemmeseier',1.36,'safe',.70,'WWDWWW','LLDDWL',6),
    pick('demo2','Sørbyen','Vestland','Eksempelliga',21,30,'Over 2,5 mål',2.05,'high',.54,'WDWWLW','WWDLLD',5),
    pick('demo3','Lund Athletic','Havn FC','Eksempelcup',22,0,'Borteseier',2.64,'high',.43,'LLWDLD','WWDWWL',4),
    pick('demo4','Skogstad','Østvik','Eksempelliga',22,15,'Begge lag scorer',1.73,'standard',.61,'WDLLWW','LWWWDW',5),
    pick('demo5','Granheim','Vard','Eksempelliga',22,30,'Hjemmeseier',1.41,'safe',.69,'WWWDLW','LLLDLL',5)
  ];
  const safeBets=[recommendations[0],recommendations[4],pick('demo6','Kysten FK','Midtbyen','Eksempelcup',22,40,'Borteseier',1.45,'safe',.68,'DLDLWL','WWDWWD',5)];
  const highRisk=[recommendations[1],recommendations[2],pick('demo7','Dalen','Åsen','Eksempelliga',22,45,'Over 3,5 mål',3.28,'high',.35,'WWLDWD','LWDWDL',4)];
  for (const p of [...recommendations,...safeBets,...highRisk]) {p.formSample=[5,6];p.probabilitySource=p.category==='safe'?'market':'model';}
  return {version:3,localDate:dayISO(now),generatedAt:now.toISOString(),matches:Array.from({length:13},()=>({})),recommendations,safeBets,highRisk,coverage:{upcomingMatches:13,matchedOdds:11,withModel:9,externalPredictions:0},sources:[{name:'football-data.org',state:'connected'},{name:'The Odds API',state:'connected'}],dataStatus:{fixtures:'demo',odds:'demo'}};
}
function chip(p){return p.category==='safe'?'Safe Bet':p.category==='high'?'High Risk':'Dagens tips';}
function renderPick(p,i){
  const key=`stat-${i}`;
  const model=Number(p.probability);
  const breakEven=1/Number(p.price);
  const sourceLabel=p.probabilitySource==='market'?'Markedssjanse':'Modellsjanse';
  return `<article class="pick">
    <div class="pick-top"><span>${esc(p.league)}</span><span>${timeFmt.format(new Date(p.kickoff))}</span></div>
    <h3 class="fixture">${esc(p.home)} – ${esc(p.away)}</h3>
    <div class="market-row"><div><div class="market-label">Anbefalt spill</div><div class="market">${esc(p.label)}</div></div><div><div class="price">${fmtOdds(p.price)}</div><div class="price-caption">ODDS</div></div></div>
    <div class="key-stats"><div><div class="metric-name">${sourceLabel}</div><div class="metric-value prob">${pct(model)}</div></div><div><div class="metric-name">Krevd sannsynlighet</div><div class="metric-value">${pct(breakEven)}</div></div></div>
    <div class="card-actions"><span class="chip ${esc(p.category)}">${chip(p)}</span><button class="details-toggle" type="button" data-open="${key}" aria-expanded="false" aria-controls="${key}">Statistikk ＋</button></div>
    <div class="details" id="${key}"><div class="details-grid">
      <div><div class="detail-title">${esc(p.home)} · siste kamper</div><div class="detail-value">${esc(formText(p.formHome))}</div></div>
      <div><div class="detail-title">${esc(p.away)} · siste kamper</div><div class="detail-value">${esc(formText(p.formAway))}</div></div>
      <div><div class="detail-title">Modellavvik</div><div class="detail-value">${p.modelEdge!=null && Number.isFinite(Number(p.modelEdge))?((p.modelEdge>=0?'+':'')+(p.modelEdge*100).toFixed(1).replace('.',',')+' %'):'–'}</div></div>
      <div><div class="detail-title">Oddsgrunnlag</div><div class="detail-value">${esc(p.bookmakers||'–')} bookmakere</div></div>
      <div><div class="detail-title">Datagrunnlag</div><div class="detail-value">${Array.isArray(p.formSample)?p.formSample.map(x=>Number(x)).join(' / ')+' kamper':'–'}</div></div>
    </div></div>
  </article>`;
}
function renderRisk(items,id){
  el(id+'-count').textContent=String(items.length);
  el(id+'-list').innerHTML=items.length?items.map(p=>`<div class="risk-item"><div><div class="risk-title">${esc(p.home)} – ${esc(p.away)}</div><div class="risk-sub">${esc(p.label)} · ${timeFmt.format(new Date(p.kickoff))}</div><div class="risk-data"><span>${p.probabilitySource==='market'?'Marked':'Modell'} ${pct(p.probability)}</span><span>Form ${esc(formText(p.formHome))}</span></div></div><div class="risk-price">${fmtOdds(p.price)}</div></div>`).join(''):'<div class="empty">Ingen kvalifiserte tips i denne kategorien akkurat nå</div>';
}
function show(data,preview){
  const now=new Date(), generatedAt=Date.parse(data.generatedAt);
  const fresh=preview||(data.localDate===dayISO(now) && Number.isFinite(generatedAt) && generatedAt<=now.getTime()+3600000 && now.getTime()-generatedAt<=15*3600000);
  const validPick=p=>Boolean(p.kickoff&&p.oddsUpdatedAt&&Number(p.price)>1 && Number.isFinite(Number(p.probability)) && Date.parse(p.kickoff)>now.getTime()+600000 && Date.parse(p.oddsUpdatedAt)<now.getTime()+3600000 && now.getTime()-Date.parse(p.oddsUpdatedAt)<=12*3600000);
  const include=p=>preview||validPick(p);
  const picks=(fresh?data.recommendations||[]:[]).filter(include).slice(0,5);
  const safe=(fresh?data.safeBets||picks.filter(p=>p.category==='safe'):[]).filter(include).slice(0,5);
  const high=(fresh?data.highRisk||picks.filter(p=>p.category==='high'):[]).filter(include).slice(0,5);
  el('today-date').textContent=dateFmt.format(now).replace(/^./,x=>x.toUpperCase());
  el('last-updated').textContent=Number.isFinite(generatedAt)?'Oppdatert '+stampFmt.format(new Date(generatedAt)):'Ikke oppdatert';
  el('demo-marker').hidden=!preview;
  el('tips-count').textContent=`${picks.length} ${picks.length===1?'tips':'tips'}`;
  el('top-picks').innerHTML=picks.length?picks.map(renderPick).join(''):'<div class="empty">Ingen kvalifiserte tips tilgjengelig akkurat nå.</div>';
  renderRisk(safe,'safe');renderRisk(high,'high');
  const allMatches=Array.isArray(data.matches)?data.matches:[];
  const todays=allMatches.filter(p=>!p.kickoff||dayISO(new Date(p.kickoff))===dayISO(now));
  el('stats-matches').textContent=fresh?String(todays.length):'–';
  el('stats-count').textContent=String(picks.length);
  el('stats-average').textContent=picks.length?pct(picks.reduce((a,p)=>a+Number(p.probability),0)/picks.length):'–';
  const coverage=data.coverage||{};
  el('stats-priced').textContent=fresh?String(coverage.matchedOdds ?? allMatches.filter(m=>m.odds&&Object.keys(m.odds).length).length):'–';
  const sources=Array.isArray(data.sources)?data.sources:[];
  el('engine-status').textContent=preview?'Designforhåndsvisning':(data.dataStatus?.fixtures==='ok'&&data.dataStatus?.odds==='ok'?'Data oppdatert':'Datadekning begrenset');
  el('engine-coverage').textContent=Number.isFinite(coverage.matchedOdds)?`${coverage.matchedOdds}/${coverage.upcomingMatches} kamper med odds`:'–';
  const connected=sources.filter(x=>x.state==='connected');
  el('engine-sources').textContent=preview?'Illustrasjonsdata':`${connected.length} automatiske datakilder`;
  const manual=Number(coverage.manualPredictions||0);
  const independent=Number(coverage.apiPredictions||0);
  el('source-footnote').textContent=preview?'Illustrasjon, ikke ekte kampanbefalinger':`Automatisk: ${connected.map(x=>x.name).join(' + ') || 'ingen'} · API-prognoser: ${independent} · Manuelle vurderinger: ${manual}`;

  const notice=el('alert');notice.hidden=true;
  if(!preview&&!fresh){notice.hidden=false;notice.textContent='Dagens analyse er ennå ikke oppdatert.';}
  else if(!preview&&(data.dataStatus?.fixtures!=='ok'||data.dataStatus?.odds!=='ok')){notice.hidden=false;notice.textContent='Kampdata eller odds er ikke tilgjengelige.';}
  document.querySelectorAll('.details-toggle').forEach(b=>b.addEventListener('click',()=>{
    const content=el(b.dataset.open),open=content.classList.toggle('open');b.setAttribute('aria-expanded',String(open));b.textContent=open?'Skjul statistikk −':'Statistikk ＋';
  }));
}
async function loadLatest(){
  if(window.__ODDSGEN_DEMO__){show(demoSnapshot(),true);return;}
  try{
    const res=await fetch('data/today.json?v='+Date.now(),{cache:'no-store'});
    if(!res.ok)throw Error(`HTTP ${res.status}`);
    const data=await res.json();if(data.version!==3)throw Error('Ukjent dataformat');
    show(data,false);
  }catch(err){show({version:3,recommendations:[],generatedAt:null,localDate:null,dataStatus:{}},false);}
}
const refresh=el('refresh-data');
refresh.addEventListener('click',async()=>{refresh.disabled=true;try{await loadLatest()}finally{refresh.disabled=false}});
loadLatest();
