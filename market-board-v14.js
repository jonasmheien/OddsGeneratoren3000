'use strict';
/* v1.6: Show selections, never a catalogue of both outcomes or unqualified watch items.
   Archived watch candidates remain in JSON for audit, but are not betting tips. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const groups = [
    ['goals','Mål'],['team_goals','Lagmål'],['btts','Begge lag scorer'],
    ['first_half','1. omgang'],['corners','Hjørnespark'],['cards','Kort'],['goalscorer','Målscorer']
  ];
  const groupLabel = Object.fromEntries(groups);
  const fmtOdds = n => Number(n).toLocaleString('nb-NO',{minimumFractionDigits:2,maximumFractionDigits:2});
  const fmtTime = v => {const d=new Date(v);return Number.isNaN(+d)?'':new Intl.DateTimeFormat('nb-NO',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Oslo'}).format(d);};
  const image = url => {try{const u=new URL(url);return u.protocol==='https:'&&['crests.football-data.org','upload.wikimedia.org'].includes(u.hostname)?u.href:null;}catch{return null;}};
  const familyOf = code => {
    code=String(code||'');
    if(code.startsWith('CO'))return 'corners';
    if(code.startsWith('CA'))return 'cards';
    if(code.startsWith('GS:'))return 'goalscorer';
    if(code.startsWith('TH')||code.startsWith('TA'))return 'team_goals';
    if(code.startsWith('H1'))return 'first_half';
    if(code.startsWith('BTTS'))return 'btts';
    if(/^[OU](15|25|35)$/.test(code))return 'goals';
    return null;
  };
  function lineKey(code){
    code=String(code||'');
    if(/^CO[OU]\d+$/.test(code)||/^CA[OU]\d+$/.test(code))return code.slice(0,2)+':'+code.slice(3);
    if(/^H1[OU]\d+$/.test(code))return 'H1:'+code.slice(3);
    if(/^T[HA][OU]\d+$/.test(code))return code.slice(0,2)+':'+code.slice(3);
    if(/^[OU]\d+$/.test(code))return 'FT:'+code.slice(1);
    if(code==='BTTS'||code==='BTTSN')return 'BTTS';
    return code;
  }
  const keyOf = p => String(p.matchId)+'|'+String(p.market);
  const confidence = p => {
    const prob=Number(p.probability),price=Number(p.price),books=Number(p.bookmakers);
    const edge=Number.isFinite(prob)&&Number.isFinite(price)?prob*price-1:0;
    return (Number.isFinite(Number(p.score))?Number(p.score):0)+Math.min(Math.max(edge,-1),.25)*5+Math.min(books||0,10)*.05;
  };
  function selectRecommended(data){
    const otherSelections=new Set();
    for(const section of ['recommendations','safeBets','highRisk']){
      for(const p of (data?.[section]||[]))otherSelections.add(keyOf(p));
    }
    const matches=new Map((data?.matches||[]).map(m=>[String(m.id),m]));
    const grouped=new Map();
    for(const p of (data?.additionalMarkets?.tips||[])){
      if(!p || p.verified!==true || p.needsLineup===true || otherSelections.has(keyOf(p)))continue;
      const family=p.marketType||familyOf(p.market);
      const price=Number(p.price),prob=Number(p.probability),books=Number(p.bookmakers);
      if(!groupLabel[family] || !Number.isFinite(price) || price<=1 ||
         !Number.isFinite(prob) || prob<=0 || prob>=1 || books<2)continue;
      // Exactly one recommendation per match, family and line; the rejected
      // opposite can never become a second recommendation on screen.
      const key=String(p.matchId)+'|'+family+'|'+lineKey(p.market);
      const match=matches.get(String(p.matchId))||{};
      const enriched={...p,marketType:family,homeCrest:p.homeCrest||match.homeCrest,awayCrest:p.awayCrest||match.awayCrest};
      if(!grouped.has(key)||confidence(enriched)>confidence(grouped.get(key)))grouped.set(key,enriched);
    }
    // Avoid multiple different thresholds or overlapping special bets from
    // the same match and family. The top certified selection wins.
    const unique=new Map();
    for(const p of grouped.values()){
      const key=String(p.matchId)+'|'+p.marketType;
      if(!unique.has(key)||confidence(p)>confidence(unique.get(key)))unique.set(key,p);
    }
    return [...unique.values()].sort((a,b)=>confidence(b)-confidence(a)).slice(0,5);
  }
  let root,active='all',snapshot=null;
  function ensure(){
    if(root)return root;
    root=document.createElement('section');root.id='spesialmarkeder';root.className='extra-market-section';
    root.setAttribute('aria-labelledby','special-market-heading');
    root.innerHTML='<div class="extra-heading"><div><div class="extra-kicker">KVALIFISERTE SPILL</div><h2 id="special-market-heading">Andre spillmarkeder</h2></div></div><div class="market-filters" id="market-filters" role="group" aria-label="Filtrer anbefalte markeder"></div><div id="extra-market-body"></div>';
    const before=document.querySelector('#resultater');
    if(before)before.before(root);else document.querySelector('main')?.appendChild(root);
    root.querySelector('#market-filters').addEventListener('click',event=>{
      const button=event.target.closest('button[data-family]');if(!button)return;
      active=button.dataset.family;if(snapshot)render(snapshot);
    });
    return root;
  }
  function badge(name,url,allow){
    const initials=String(name||'?').split(/\s+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase()||'?';
    const src=allow?image(url):null;
    return `<span class="extra-team-mark" aria-hidden="true">${src?`<img src="${esc(src)}" loading="lazy" alt="">`:esc(initials)}</span>`;
  }
  function card(p,allowed){
    const reasons=(Array.isArray(p.rationale)?p.rationale:[]).filter(x=>typeof x==='string').slice(0,4);
    const prob=Number(p.probability);
    return `<details class="extra-market-card market-good"><summary>
      <span class="extra-market-main"><span class="extra-market-league">${esc(p.league||'Fotball')} · ${esc(fmtTime(p.kickoff))}</span>
      <span class="extra-market-match">${badge(p.home,p.homeCrest,allowed)} ${esc(p.home)} <span class="market-vs">–</span> ${badge(p.away,p.awayCrest,allowed)} ${esc(p.away)}</span>
      <span class="extra-market-play">${esc(p.label)}</span></span>
      <span class="extra-market-right"><strong>${esc(fmtOdds(p.price))}</strong><span>ANALYSERT</span></span>
      </summary><div class="extra-market-analysis"><p>Dette er den best rangerte, kvalifiserte linjen i markedet for denne kampen. Et modellanslag er ikke en garanti for verdi.</p>
      <span class="market-prob">Modellanslag: ${Math.round(prob*100)} %</span>
      ${reasons.length?`<ul>${reasons.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}
      <span class="extra-market-source">${esc(p.oddsSource||p.source||'The Odds API')} · odds ved analyse · ${esc(p.bookmakers)} bookmakere</span></div></details>`;
  }
  function render(data){
    snapshot=data;ensure();
    const all=selectRecommended(data);
    const body=$('extra-market-body');const filters=$('market-filters');
    const available=groups.filter(([key])=>all.some(p=>p.marketType===key));
    if(active!=='all'&&!available.some(([key])=>key===active))active='all';
    root.hidden=false;
    if(!all.length){
      filters.innerHTML='';
      body.innerHTML='<p class="extra-market-empty">Ingen ekstra markeder oppfyller kvalitetskravene i denne dagsutgaven. Kort, hjørnespark og målscorere vises ikke som tips bare fordi bookmakerne tilbyr odds.</p>';
      return;
    }
    filters.innerHTML=[['all','Alle',all.length],...available.map(([key,label])=>[key,label,all.filter(p=>p.marketType===key).length])]
      .map(([key,label,count])=>`<button type="button" data-family="${key}" aria-pressed="${String(active===key)}" class="market-filter${active===key?' selected':''}">${esc(label)} <span>${count}</span></button>`).join('');
    const shown=active==='all'?all:all.filter(p=>p.marketType===active);
    const approved=data?.visualAssets?.licensedCrests===true;
    body.innerHTML=`<p class="extra-market-intro">Kun godkjente analyser. Vi viser ikke begge sider av samme linje, duplikater fra Dagens tips eller rene oddsobservasjoner.</p><div class="extra-market-grid">${shown.map(p=>card(p,approved)).join('')}</div>`;
    root.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{img.replaceWith(document.createTextNode('?'));},{once:true}));
  }
  async function load(){
    try{const r=await fetch(`data/today.json?clean_v16=${Date.now()}`,{cache:'no-store'});if(r.ok)render(await r.json());}
    catch{/* Secondary UI must never prevent the main daily tips from rendering. */}
  }
  if(typeof module==='object'&&module.exports)module.exports={selectRecommended,lineKey,familyOf};
  if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',()=>{
    ensure();load();$('refresh-data')?.addEventListener('click',load);
    setInterval(()=>{if(document.visibilityState==='visible')load();},60000);
  });
})();
