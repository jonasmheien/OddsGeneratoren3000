'use strict';
/* v39: UI for existing, source-backed non-1X2 prices. No new recommendations. */
(() => {
  const FAMILIES={
    goals:'Mål',btts:'Begge lag scorer',first_half:'1. omgang',
    team_goals:'Lagmål',corners:'Hjørnespark',cards:'Kort',goalscorer:'Målscorer'
  };
  const ORDER=['btts','first_half','team_goals','corners','cards','goalscorer','goals'];
  const CORE={O15:'Over 1,5 mål',U15:'Under 1,5 mål',O25:'Over 2,5 mål',U25:'Under 2,5 mål',
    O35:'Over 3,5 mål',U35:'Under 3,5 mål',BTTS:'Begge lag scorer: Ja',BTTSN:'Begge lag scorer: Nei'};
  const HOUR=3600000;
  const norm=v=>String(v||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const familyFor=(code,type)=>{
    if(Object.prototype.hasOwnProperty.call(FAMILIES,type))return type;
    const c=String(code||'');
    if(/^GS:/.test(c))return 'goalscorer';
    if(/^CO(?:O|U|\d)/.test(c))return 'corners';
    if(/^CA(?:O|U|\d)/.test(c))return 'cards';
    if(/^H1/.test(c))return 'first_half';
    if(/^T[HA]/.test(c))return 'team_goals';
    if(/^BTTS/.test(c))return 'btts';
    if(/^[OU]\d\d$/.test(c))return 'goals';
    return null;
  };
  const osloDay=value=>{
    const d=new Date(value);
    if(!Number.isFinite(+d))return '';
    const items=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Oslo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);
    const kv=Object.fromEntries(items.map(x=>[x.type,x.value]));
    return `${kv.year}-${kv.month}-${kv.day}`;
  };
  const valuePrice=q=>Number(q?.price);
  function quoteIsFresh(q,now,maxAge=12){
    if(!q||typeof q!=='object'||q.price===null||q.price===undefined||q.price==='')return false;
    const price=valuePrice(q),books=Number(q.bookmakers??q.books),at=new Date(q.oddsUpdatedAt??q.lastUpdated);
    const age=+now-+at;
    return Number.isFinite(price)&&price>1.01&&price<100&&Number.isFinite(books)&&books>=1&&
      Number.isFinite(+at)&&age>=-5*60000&&age<=maxAge*HOUR;
  }
  const marketKey=e=>`${String(e.matchId)}|${String(e.market)}`;
  const teamKey=name=>{
    const s=norm(name).replace(/[^a-z0-9]+/g,'');
    return ({boltonwanderers:'bolton',silkeborgif:'silkeborg',sevillafc:'sevilla',
      peczwolle:'zwolle',fczwolle:'zwolle',
      hsv:'hamburgersv',hamburgsv:'hamburgersv',
      mgladbach:'monchengladbach',borussiamgladbach:'monchengladbach',
      borussiamonchengladbach:'monchengladbach',
      blackburnrovers:'blackburn',westhamunited:'westham',
      vfbstuttgart:'stuttgart',werderbremen:'bremen',
      prestonnorthend:'prestonne',fsvmainz05:'mainz',bayernmunich:'bayern',
      norwichcity:'norwich',stokecity:'stoke',wrexhamafc:'wrexham',
      wolverhamptonwanderers:'wolverhampton',birminghamcity:'birmingham',
      cardiffcity:'cardiff',charltonathletic:'charlton',
      sheffieldunited:'sheffieldutd',queensparkrangers:'qpr',
      westbromwichalbion:'westbrom',nottinghamforest:'nottingham',
      manchestercity:'mancity',tottenhamhotspur:'tottenham'})[s]||s;
  };
  // Only explicit, narrow aliases. Uncertain club identities are not merged.
  const sameFixture=(a,b)=>Number.isFinite(+new Date(a.kickoff))&&Number.isFinite(+new Date(b.kickoff))&&
    Math.abs(+new Date(a.kickoff)-+new Date(b.kickoff))<=HOUR&&
    teamKey(a.home)===teamKey(b.home)&&teamKey(a.away)===teamKey(b.away);
  const labelFor=(entry,market)=>{
    if(CORE[market])return CORE[market];
    const rule=/^H1([OU])(\d{2,3})$/.exec(market);
    if(rule)return `1. omgang ${rule[1]==='O'?'over':'under'} ${(Number(rule[2])/10).toLocaleString('nb-NO',{minimumFractionDigits:1})} mål`;
    const t=/^T([HA])([OU])(\d{2,3})$/.exec(market);
    if(t)return `${t[1]==='H'?'Hjemmelaget':'Bortelaget'} ${t[2]==='O'?'over':'under'} ${(Number(t[3])/10).toLocaleString('nb-NO',{minimumFractionDigits:1})} mål`;
    const c=/^C([OA])([OU])(\d{2,3})$/.exec(market);
    if(c)return `${c[2]==='O'?'Over':'Under'} ${(Number(c[3])/10).toLocaleString('nb-NO',{minimumFractionDigits:1})} ${c[1]==='O'?'hjørnespark':'kort'}`;
    const label=String(entry.label||'').trim();
    return label&&label!==market?label.slice(0,120):null;
  };
  function extractMarketItems(edition,now=new Date(),maxItems=28){
    const day=String(edition?.editionDate||edition?.localDate||'');
    if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||day<osloDay(now))return [];
    const matches=(edition?.matches||[]).filter(m=>m&&m.home&&m.away&&
      osloDay(m.kickoff)===day&&+new Date(m.kickoff)>+now);
    const matchById=new Map(matches.map(m=>[String(m.id),m]));
    const choices=[];
    function add(entry,tier,from){
      if(!entry||!entry.market||!entry.matchId)return;
      const family=familyFor(entry.market,entry.marketType);
      if(!family||!quoteIsFresh(entry,now,tier==='qualified'?6:12))return;
      const match=matchById.get(String(entry.matchId));
      if(!match)return; // Never display a quote unlinked to a known current fixture.
      if(entry.home && teamKey(entry.home)!==teamKey(match.home))return;
      if(entry.away && teamKey(entry.away)!==teamKey(match.away))return;
      const label=labelFor(entry,String(entry.market));
      if(!label)return; // An undecodable market code is never shown as a wager.
      const prob=Number(entry.probability);
      const chance=entry.probability!==null&&entry.probability!==undefined&&Number.isFinite(prob)&&prob>=0&&prob<=1?prob:null;
      choices.push({matchId:String(match.id),home:match.home,away:match.away,league:match.league||'Fotball',
        kickoff:match.kickoff,market:String(entry.market),label,family,
        price:valuePrice(entry),books:Number(entry.bookmakers??entry.books),updated:String(entry.oddsUpdatedAt??entry.lastUpdated),
        source:String(entry.source||entry.oddsSource||'The Odds API').slice(0,90),tier,
        probability:chance,needsLineup:entry.needsLineup===true,
        reason:Array.isArray(entry.rationale)?String(entry.rationale.find(x=>typeof x==='string')||''):
          String(entry.reason||''),from});
    }
    for(const p of edition?.recommendations||[]){
      if(p&&p.conservativeEdge!==null&&p.conservativeEdge!==undefined&&Number(p.conservativeEdge)>=.02)
        add(p,'qualified','recommendation');
    }
    for(const p of edition?.observations||[])add(p,'observation','observation');
    for(const p of edition?.additionalMarkets?.tips||[])add(p,'review','extra_tip');
    for(const p of edition?.additionalMarkets?.watchlist||[])add(p,'watch','watchlist');
    // Supplement the dedicated market scan with real quoted goal totals.
    // Unlike recommendations, these are ONLY registered prices, not predictions.
    for(const m of matches){
      for(const [code,q] of Object.entries(m.odds||{})){
        if(!familyFor(code))continue;
        add({matchId:m.id,market:code,label:CORE[code]||code,price:q.price,bookmakers:q.books,
          oddsUpdatedAt:q.lastUpdated,source:q.source},'watch','core_quote');
      }
    }
    const priority={qualified:0,observation:1,review:2,watch:3};
    choices.sort((a,b)=>priority[a.tier]-priority[b.tier]||b.books-a.books||+new Date(a.kickoff)-+new Date(b.kickoff)||a.market.localeCompare(b.market));
    const unique=[];
    for(const c of choices){
      if(unique.some(x=>sameFixture(x,c)))continue;
      unique.push(c);
    }
    // Fair distribution. A large number of goal quotes must not obscure BTTS,
    // cards, corners or scorers. All quote-only objects remain non-recommendations.
    const grouped=Object.fromEntries(ORDER.map(f=>[f,unique.filter(x=>x.family===f)]));
    const selected=[];
    while(selected.length<maxItems&&ORDER.some(f=>grouped[f].length)){
      for(const f of ORDER){
        if(selected.length>=maxItems)break;
        const next=grouped[f].shift();if(next)selected.push(next);
      }
    }
    return selected;
  }
  const fmtOdds=n=>Number(n).toLocaleString('nb-NO',{minimumFractionDigits:2,maximumFractionDigits:2});
  const fmtKickoff=v=>new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit'}).format(new Date(v));
  const fmtUpdated=v=>new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit'}).format(new Date(v));
  const create=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
  let root,filters,grid,count,empty,activeFamily='all',currentItems=[],fetching=false,reloadQueued=false,lastEdition=null;
  function applyFilters(){
    const query=norm(document.getElementById('og-search')?.value||'').trim();
    let visible=0;
    for(const card of grid.querySelectorAll('.mr-card')){
      const passFamily=activeFamily==='all'||card.dataset.family===activeFamily;
      const text=norm(card.textContent);
      const passQuery=!query||query.split(/\s+/).every(t=>text.includes(t));
      card.hidden=!(passFamily&&passQuery);if(!card.hidden)visible++;
    }
    empty.hidden=visible!==0;
    if(!visible)empty.textContent=query?'Ingen markeder samsvarer med søket.':
      'Ingen registrerte, ferske priser i denne markedsgruppen.';
    if(count)count.textContent=String(visible);
    const summary=document.getElementById('og-search-summary');
    if(query && summary){
      const original=Array.from(document.querySelectorAll('.og-category .tf-card')).filter(c=>!c.hidden).length;
      summary.textContent=`${original+visible} treff på «${document.getElementById('og-search')?.value.trim()||''}»`;
    }
  }
  function renderCard(p){
    const card=create('article','mr-card');card.dataset.family=p.family;
    const meta=create('div','mr-meta');
    meta.append(create('span','',p.league),create('time','',fmtKickoff(p.kickoff)));
    const teams=create('h3','mr-teams',`${p.home} – ${p.away}`);
    const market=create('div','mr-market');market.append(create('span','mr-market-name',p.label));
    const quote=create('span','mr-quote',fmtOdds(p.price));quote.title='Registrert bookmakerodds, ingen spillknapp';market.append(quote);
    const tierText={qualified:'Kvalifisert av modellen',observation:'Statistisk observasjon',
      review:'Ikke kvalifisert',watch:'Bookmakerpris · ikke tips'};
    const tier=create('span',`mr-tier mr-tier-${p.tier}`,tierText[p.tier]);
    const more=create('details','mr-details');const summary=create('summary','','Datagrunnlag');more.append(summary);
    const body=create('div','mr-info');
    body.append(create('p','',`${p.books} bookmaker${p.books===1?'':'e'} · sist registrert ${fmtUpdated(p.updated)} · ${p.source}`));
    if(p.tier==='qualified')body.append(create('p','',
      'Passerte backendens kvalitetskontroll. Modellens sannsynlighet er ikke historisk kalibrert.'));
    else body.append(create('p','',p.reason||'Registrerte odds uten dokumentert positiv spillverdi.'));
    if(p.needsLineup)body.append(create('p','mr-warning','Startoppstilling er ikke bekreftet.'));
    if(p.probability!==null&&p.tier!=='watch')body.append(create('p','',
      `Foreløpig modellanslag: ${(p.probability*100).toLocaleString('nb-NO',{maximumFractionDigits:1})} %`));
    body.append(create('p','mr-muted','Odds er ikke oppdatert i sanntid og kan være endret.'));
    more.append(body);card.append(meta,teams,market,tier,more);return card;
  }
  function draw(items){
    currentItems=items;const available=ORDER.filter(f=>items.some(x=>x.family===f));
    if(activeFamily!=='all'&&!available.includes(activeFamily))activeFamily='all';
    filters.replaceChildren();
    const options=[['all','Alle'],...available.map(f=>[f,FAMILIES[f]])];
    for(const [key,label] of options){
      const n=items.filter(x=>key==='all'||x.family===key).length;
      const b=create('button','mr-filter',`${label} · ${n}`);b.type='button';
      b.setAttribute('aria-pressed',String(key===activeFamily));
      b.addEventListener('click',()=>{activeFamily=key;filters.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));applyFilters();});
      filters.append(b);
    }
    grid.replaceChildren(...items.map(renderCard));
    root.querySelector('.mr-description').textContent=items.length?
      `${items.filter(x=>x.tier==='qualified').length} kvalifiserte · ${items.length} registrerte markeder. Øvrige er kun til vurdering.`:
      'Ingen tilgjengelige markedspriser for gjeldende dagsutgave.';
    applyFilters();
  }
  async function refresh(){
    if(fetching){reloadQueued=true;return;}
    fetching=true;
    try{
      const source=document.getElementById('tf-root')?.dataset.ogEditionFile||'today';
      const day=document.getElementById('tf-root')?.dataset.ogEditionDate||osloDay(new Date());
      const response=await fetch(`data/${source==='tomorrow'?'tomorrow':'today'}.json?market39=${Date.now()}`,{cache:'no-store'});
      if(!response.ok)throw new Error('not published');
      const edition=await response.json();
      const editionDay=String(edition.editionDate||edition.localDate||'');
      lastEdition=edition;
      draw(editionDay===day?extractMarketItems(edition,new Date()):[]);
    }catch{
      const selected=document.getElementById('tf-root')?.dataset.ogEditionDate||osloDay(new Date());
      if(lastEdition && String(lastEdition.editionDate||lastEdition.localDate||'')===selected)
        draw(extractMarketItems(lastEdition,new Date()));
      else root.querySelector('.mr-description').textContent='Kunne ikke hente publiserte markedsdata.';
    }
    finally{fetching=false;if(reloadQueued){reloadQueued=false;setTimeout(refresh,0);}}
  }
  function navLink(parent,kind){
    if(!parent)return;
    const link=create('a',kind==='dock'?'og-dock-link':'og-shortcut');
    link.href='#og-markets';link.dataset.ogTarget='og-markets';
    const glyph=create('span','mr-nav-icon','◉');glyph.setAttribute('aria-hidden','true');
    link.append(glyph,create('span','','Markeder'));
    link.addEventListener('click',e=>{
      e.preventDefault();root.scrollIntoView({behavior:'smooth',block:'start'});
      document.querySelectorAll('[data-og-target]').forEach(el=>{
        const active=el.dataset.ogTarget==='og-markets';
        el.classList.toggle('og-current',active);
        if(active)el.setAttribute('aria-current','location');else el.removeAttribute('aria-current');
      });
    });
    parent.append(link);
  }
  function start(){
    const source=document.getElementById('tf-root'),main=document.querySelector('main');
    if(!source||!main||document.getElementById('og-markets'))return;
    root=create('section','mr-root');root.id='og-markets';root.setAttribute('aria-labelledby','mr-title');
    const header=create('div','mr-header');
    const text=create('div');text.append(create('div','mr-eyebrow','FLERE SPILLMARKEDER'));
    const title=create('h2','', 'Markedsradar');title.id='mr-title';text.append(title);
    text.append(create('p','mr-description','Henter registrerte markedspriser …'));
    header.append(text,create('span','mr-header-symbol','◉'));root.append(header);
    filters=create('div','mr-filters');filters.setAttribute('role','group');filters.setAttribute('aria-label','Filtrer markeder');
    grid=create('div','mr-grid');empty=create('p','mr-empty');empty.hidden=true;
    count=create('output','mr-count');count.hidden=true;
    root.append(filters,grid,empty,count);source.after(root);
    navLink(document.querySelector('.og-shortcuts'),'shortcuts');navLink(document.getElementById('og-dock'),'dock');
    const search=document.getElementById('og-search');
    search?.addEventListener('input',applyFilters);
    document.querySelector('.og-search-clear')?.addEventListener('click',()=>setTimeout(applyFilters,0));
    const observer=new MutationObserver(records=>{
      if(records.some(r=>r.attributeName==='data-og-edition-date'||r.attributeName==='data-og-edition-file'))refresh();
    });
    observer.observe(source,{attributes:true,attributeFilter:['data-og-edition-date','data-og-edition-file']});
    document.getElementById('refresh-data')?.addEventListener('click',()=>setTimeout(refresh,300));
    setInterval(()=>{if(document.visibilityState==='visible')refresh();},60000);
    refresh();
  }
  if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',start);
  if(typeof module==='object'&&module.exports)module.exports={familyFor,quoteIsFresh,extractMarketItems,osloDay,sameFixture};
})();
