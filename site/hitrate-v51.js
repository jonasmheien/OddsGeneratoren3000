'use strict';
/* Display recorded outcomes only. No tips, prices or results are created here. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root?.document)api.mount(root);
})(typeof globalThis==='object'?globalThis:null,function(){
  const groups={safe:'Safe Bets',high:'High Risk',watch:'Interessante objekter',qualified:'Kvalifiserte spill'};
  const statuses={won:'Vunnet',lost:'Tapt',void:'Annullert',unverified:'Uavklart',scheduled:'Venter',live:'Pågår',postponed:'Utsatt'};
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>Number.isFinite(Number(v))?Number(v):0;
  const percent=v=>v===null||v===undefined?'Ingen avgjorte':`${Number(v).toLocaleString('nb-NO',{maximumFractionDigits:1})} %`;
  const date=v=>{
    const value=new Date(v);
    return Number.isFinite(+value)?new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',day:'numeric',month:'short',year:'numeric'}).format(value):'';
  };
  function cards(report){
    return Object.entries(groups).map(([key,label])=>{
      const stats=report.categories?.[key]||{};
      const rate=stats.hitRatePct, decided=num(stats.settled);
      const width=rate===null||rate===undefined?0:Math.max(0,Math.min(100,num(rate)));
      return `<article class="hr51-card"><h3>${label}</h3>`+
        `<strong class="hr51-rate${decided?'':' hr51-no-rate'}">${esc(percent(rate))}</strong>`+
        `<p class="hr51-denominator">${num(stats.wins)} av ${decided} avgjorte tips</p>`+
        `<div class="hr51-bar" aria-hidden="true"><span style="width:${width}%"></span></div>`+
        `<dl class="hr51-outcomes"><div><dt>Vunnet</dt><dd class="hr51-won">${num(stats.wins)}</dd></div>`+
        `<div><dt>Tapt</dt><dd class="hr51-lost">${num(stats.losses)}</dd></div></dl>`+
        `<p class="hr51-pending">${num(stats.pending)} venter · ${num(stats.unverified)} uavklart · ${num(stats.voids)} annullert</p></article>`;
    }).join('');
  }
  function filtered(tips,category='all',outcome='all'){
    return (Array.isArray(tips)?tips:[]).filter(p=>(category==='all'||p.category===category)&&
      (outcome==='all'||p.result?.status===outcome||outcome==='pending'&&['scheduled','live','postponed'].includes(p.result?.status)));
  }
  function rows(tips){
    return tips.length?tips.map(p=>{
      const state=p.result?.status||'unverified';
      const score=p.result?.score;
      const result=score&&Number.isInteger(score.home)&&Number.isInteger(score.away)?`<small>${score.home} : ${score.away}</small>`:'';
      return `<tr><td class="hr51-fixture"><span>${esc(p.home)} mot ${esc(p.away)}</span><small>${esc(date(p.kickoff))}</small></td>`+
        `<td>${esc(groups[p.category]||'')}</td><td>${esc(p.label||p.market)}</td>`+
        `<td class="hr51-result ${['won','lost'].includes(state)?'hr51-'+state:''}">${esc(statuses[state]||'Uavklart')}${result}</td></tr>`;
    }).join(''):'<tr><td colspan="4" class="hr51-empty">Ingen tips med dette filteret.</td></tr>';
  }
  function markup(report){
    const summary=report.overall||{};
    return `<header class="hr51-heading"><div><p class="hr51-kicker">RESULTATLOGG</p><h2 id="hr51-title">Treffprosent</h2></div>`+
      `<span class="hr51-since">${report.trackedFrom?'Fra '+esc(date(report.trackedFrom)):'Ingen arkiverte tips ennå'}</span></header>`+
      `<p class="hr51-intro">${num(summary.total)} publiserte tips. Vunnet delt på vunnet og tapt. Hvert tips telles én gang, i kategorien det først ble vist i.</p>`+
      `<div class="hr51-cards">${cards(report)}</div>`+
      '<p class="hr51-note">Ventende, uavklarte og annullerte tips er utenfor treffprosenten. Interessante objekter er observasjoner.</p>'+
      '<details class="hr51-log"><summary>Vis tips og resultater</summary><div class="hr51-filters">'+
      '<label>Kategori<select id="hr51-category"><option value="all">Alle kategorier</option>'+
      Object.entries(groups).map(([key,label])=>`<option value="${key}">${label}</option>`).join('')+
      '</select></label><label>Resultat<select id="hr51-outcome"><option value="all">Alle resultater</option>'+ 
      [['won','Vunnet'],['lost','Tapt'],['pending','Venter / pågår'],['unverified','Uavklart'],['void','Annullert']]
        .map(([key,label])=>`<option value="${key}">${label}</option>`).join('')+
      '</select></label></div><div class="hr51-table-wrap"><table><caption class="hr51-sr">Arkiverte tips og bekreftede resultater</caption>'+
      '<thead><tr><th scope="col">Kamp</th><th scope="col">Kategori</th><th scope="col">Tips</th><th scope="col">Resultat</th></tr></thead>'+
      `<tbody id="hr51-rows">${rows((report.tips||[]).slice(0,30))}</tbody></table></div>`+
      `<button id="hr51-more" class="hr51-more" type="button"${(report.tips||[]).length<=30?' hidden':''}>Vis flere tips</button></details>`;
  }
  function mount(window){
    const document=window.document;
    let section, current, busy=false, limit=30;
    function drawLog(){
      const tips=filtered(current?.tips,section.querySelector('#hr51-category')?.value,
        section.querySelector('#hr51-outcome')?.value);
      section.querySelector('#hr51-rows').innerHTML=rows(tips.slice(0,limit));
      section.querySelector('#hr51-more').hidden=tips.length<=limit;
    }
    async function load(){
      if(busy)return;busy=true;
      try{
        const response=await window.fetch(`data/hitrate-v51.json?v=${Date.now()}`,{cache:'no-store'});
        if(!response.ok)throw new Error('Statistics unavailable');
        const report=await response.json();
        if(report.schemaVersion!==51||!report.categories)throw new Error('Unknown statistics');
        const previous=section.querySelector('.hr51-log');
        const open=Boolean(previous?.open);
        const category=section.querySelector('#hr51-category')?.value||'all';
        const outcome=section.querySelector('#hr51-outcome')?.value||'all';
        current=report;section.innerHTML=markup(report);
        section.querySelector('.hr51-log').open=open;
        section.querySelector('#hr51-category').value=category;
        section.querySelector('#hr51-outcome').value=outcome;
        drawLog();
      }catch{
        if(!current)section.innerHTML='<h2 id="hr51-title">Treffprosent</h2><p class="hr51-note">Statistikken er ikke tilgjengelig akkurat nå.</p>';
      }finally{busy=false;}
    }
    document.addEventListener('DOMContentLoaded',()=>{
      const parent=document.getElementById('tf-root');if(!parent)return;
      section=document.createElement('section');section.id='hitrate';section.className='hr51';
      section.setAttribute('aria-labelledby','hr51-title');
      section.innerHTML='<h2 id="hr51-title">Treffprosent</h2><p class="hr51-note">Henter resultatlogg ...</p>';
      parent.append(section);
      section.addEventListener('change',()=>{limit=30;drawLog();});
      section.addEventListener('click',event=>{if(event.target.closest('#hr51-more')){limit+=30;drawLog();}});
      document.getElementById('refresh-data')?.addEventListener('click',load);
      window.setInterval(()=>{if(document.visibilityState==='visible')load();},60000);
      load();
    });
  }
  return {cards,rows,filtered,markup,mount};
});
