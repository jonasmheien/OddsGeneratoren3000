'use strict';
/* OddsGeneratoren v37 — presentation-only enhancement of the existing three-fields UI.
   Does not decide tips, calculate probabilities, or contact third-party services. */
(() => {
  const $ = id => document.getElementById(id);
  const ICONS = {
    home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    zap: '<path d="m13 2-9 12h7l-1 8 10-12h-7l0-8z"/>',
    eye: '<path d="M2 12s3.7-7 10-7 10 7 10 7-3.7 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    search: '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/>',
    arrow: '<path d="m5 12 14 0m-6-6 6 6-6 6"/>',
    close: '<path d="M5 5 19 19M19 5 5 19"/>',
    spark: '<path d="m12 2 1.9 6.1L20 10l-6.1 1.9L12 18l-1.9-6.1L4 10l6.1-1.9L12 2ZM19 17l.7 2.3L22 20l-2.3.7L19 23l-.7-2.3L16 20l2.3-.7L19 17Z"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/>',
    history: '<path d="M3 12a9 9 0 1 0 2-5.6L3 8"/><path d="M3 3v5h5M12 7v5l4 2"/>'
  };
  const icon = name => `<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`;
  const norm = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const config = [
    {key:'safe', target:'og-safe', title:'Safe Bets', desc:'Høyere estimert sannsynlighet', icon:'shield'},
    {key:'high', target:'og-high', title:'High Risk', desc:'Høyere odds og risiko', icon:'zap'},
    {key:'watch', target:'og-watch', title:'Interessante objekter', desc:'Kamper og markeder til vurdering', icon:'eye'}
  ];
  const tokens = Object.freeze({qualified:'Kvalifisert',model:'Modellkandidat',market:'Markedskandidat',observation:'Observasjon'});
  const trustFromCard = (card, key) => {
    if (key === 'watch') return 'observation';
    const note = norm(card.querySelector('.tf-note')?.textContent);
    if (note.includes('markedsbasert')) return 'market';
    if (note.includes('modellkandidat')) return 'model';
    if (note.includes('kvalifisert i modellens konservative')) return 'qualified';
    return null; // Do not invent an evidence tier.
  };
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className=cls;
    if (text !== undefined) node.textContent=text;
    return node;
  };
  let tools, featured, search, searchSummary, dock, observed;
  let query = '';
  let updating = false;
  const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  function heading(container, eyebrow, title, description) {
    const h=el('div','og-section-heading');
    const copy=el('div');copy.append(el('div','og-eyebrow',eyebrow),el('h2','',title));
    if(description)copy.append(el('p','og-section-description',description));
    container.append(h);h.append(copy);
    return h;
  }
  function jump(target) {
    const section=$(target);
    if(!section) return;
    section.scrollIntoView({behavior:reducedMotion()?'auto':'smooth',block:'start'});
    document.querySelectorAll('[data-og-target]').forEach(node=>{
      const active=node.dataset.ogTarget===target;
      node.classList.toggle('og-current',active);
      if(active)node.setAttribute('aria-current','location');else node.removeAttribute('aria-current');
    });
  }
  function link(label, key, target, cls) {
    const anchor=el('a',cls);
    anchor.href=`#${target}`;
    anchor.dataset.ogTarget=target;
    anchor.innerHTML=icon(key); // Inline icon is fixed project-authored markup.
    anchor.append(el('span','',label));
    anchor.addEventListener('click',event=>{
      if(!$(target))return;
      event.preventDefault();jump(target);
    });
    return anchor;
  }
  function buildTools(main, hero) {
    tools=el('section','og-tools');tools.id='og-tools';tools.setAttribute('aria-label','Søk og hurtignavigasjon');
    const form=el('div','og-search-wrap');
    const lead=el('span','og-search-icon');lead.innerHTML=icon('search');
    search=el('input','og-search');search.type='search';search.id='og-search';
    search.placeholder='Søk etter lag, kamp eller liga';search.setAttribute('aria-label',search.placeholder);
    search.autocomplete='off';search.spellcheck=false;
    const clear=el('button','og-search-clear');clear.type='button';clear.setAttribute('aria-label','Tøm søket');
    clear.innerHTML=icon('close');clear.hidden=true;
    clear.addEventListener('click',()=>{search.value='';query='';clear.hidden=true;update();search.focus();});
    search.addEventListener('input',()=>{query=norm(search.value.trim());clear.hidden=!query;update();});
    form.append(lead,search,clear);
    searchSummary=el('p','og-search-summary');searchSummary.setAttribute('role','status');searchSummary.setAttribute('aria-live','polite');searchSummary.hidden=true;
    const shortcuts=el('nav','og-shortcuts');shortcuts.setAttribute('aria-label','Kategorier');
    shortcuts.append(link('Dagens','home','toppen','og-shortcut og-current'));
    for(const c of config)shortcuts.append(link(c.title,c.icon,c.target,'og-shortcut'));
    tools.append(form,searchSummary,shortcuts);
    hero.after(tools);
  }
  function buildFeatured() {
    featured=el('section','og-featured');featured.id='og-featured';featured.setAttribute('aria-label','Dagens toppvalg');
    heading(featured,'DAGENS UTVALG','Toppvalg','Et utvalg av tips som allerede vises nedenfor.');
    const cards=el('div','og-featured-list');cards.id='og-featured-list';featured.append(cards);
    tools.after(featured);
  }
  function setupSections() {
    const root=$('tf-root');if(!root)return null;
    root.classList.add('og-upgraded');
    for(const c of config){
      const section=$(`tf-${c.key}-title`)?.closest('.tf-section');
      if(!section)continue;
      section.id=c.target;section.classList.add('og-category',`og-category-${c.key}`);
      const h=section.querySelector('header');
      if(h&&!h.querySelector('.og-section-icon')){
        const logo=el('span','og-section-icon');logo.innerHTML=icon(c.icon);
        h.prepend(logo);
        const title=h.querySelector('h2');if(title)title.insertAdjacentElement('afterend',el('p','og-category-subtitle',c.desc));
      }
    }
    return root;
  }
  function buildDock() {
    dock=el('nav','og-dock');dock.id='og-dock';dock.setAttribute('aria-label','Mobilnavigasjon');
    dock.append(link('Hjem','home','toppen','og-dock-link og-current'));
    for(const c of config)dock.append(link(c.key==='watch'?'Objekter':c.title,c.icon,c.target,'og-dock-link'));
    document.body.append(dock);
  }
  function decorateCards() {
    let total=0;
    for(const c of config){
      const section=$(c.target);if(!section)continue;
      for(const card of section.querySelectorAll('.tf-card')){
        total++;
        // The legacy renderer has two text nodes around an en dash. Wrap the
        // names so the mobile layout can show each club on its own line.
        const teams=card.querySelector('.tf-teams');
        if(teams && !teams.querySelector('.og-team-name')){
          const divider=Array.from(teams.children).find(n=>n.tagName==='SPAN');
          if(divider){
            const nodes=Array.from(teams.childNodes), at=nodes.indexOf(divider);
            const home=nodes.slice(0,at).map(n=>n.textContent).join('').trim();
            const away=nodes.slice(at+1).map(n=>n.textContent).join('').trim();
            if(home&&away)teams.replaceChildren(el('span','og-team-name',home),el('span','og-team-name',away));
          }
        }
        const tier=trustFromCard(card,c.key);
        if(tier && !card.querySelector('.og-tier')) {
          const span=el('span',`og-tier og-tier-${tier}`,tokens[tier]);
          const placement=card.querySelector('.tf-note')||card.querySelector('.tf-analysis');
          if(placement)placement.before(span);else card.append(span);
        }
        const odd=card.querySelector('.tf-market strong');
        if(odd&&!odd.classList.contains('og-odd-box')){
          odd.classList.add('og-odd-box');odd.setAttribute('title','Registrert bookmaker-median, ikke en spillknapp');
        }
        if(!card.hasAttribute('tabindex'))card.setAttribute('tabindex','-1');
      }
    }
    return total;
  }
  function allCards() {
    return config.flatMap(c=>Array.from($(c.target)?.querySelectorAll('.tf-card')||[]).map(card=>({card,category:c.key})));
  }
  function applySearch() {
    let found=0;
    for(const {card} of allCards()){
      const text=norm(card.textContent);
      const matches=!query||query.split(/\s+/).every(part=>text.includes(part));
      card.hidden=!matches;if(matches)found++;
    }
    for(const c of config){
      const section=$(c.target);if(!section)continue;
      const list=section.querySelector('.tf-list');
      if(!list)continue;
      let empty=list.querySelector('.og-filter-empty');
      const orig=list.querySelector('.tf-empty');
      if(orig)orig.hidden=!!query;
      const cards=Array.from(list.querySelectorAll('.tf-card'));
      const visibleCount=cards.filter(card=>!card.hidden).length;
      const counter=section.querySelector('header > span:not(.og-section-icon)');
      if(counter)counter.textContent=String(query?visibleCount:cards.length);
      if(query && visibleCount===0){
        if(!empty){empty=el('p','og-filter-empty','Ingen treff i denne kategorien.');list.append(empty);}
        empty.hidden=false;
      }else if(empty)empty.hidden=true;
    }
    searchSummary.hidden=!query;
    if(query)searchSummary.textContent=`${found} treff på «${search.value.trim()}»`;
    return found;
  }
  function featuredSummary(card,category,index) {
    const source=card;
    const item=el('article','og-spotlight');
    const categoryLabel=category==='safe'?'SAFE BETS':'HIGH RISK';
    const top=el('div','og-spotlight-top');
    top.append(el('span','og-eyebrow',index===0?'UTVALGT OBJEKT':`TOPPVALG ${index+1}`),el('span','og-spotlight-category',categoryLabel));
    const clubNames=Array.from(source.querySelectorAll('.tf-teams .og-team-name')).map(n=>n.textContent.trim());
    const teams=el('h3','og-spotlight-teams',clubNames.length===2?clubNames.join(' – '):(source.querySelector('.tf-teams')?.textContent.trim()||'Kamp'));
    const market=el('div','og-spotlight-market',source.querySelector('.tf-market > span')?.textContent.trim()||'Marked');
    const odds=el('span','og-spotlight-odds',source.querySelector('.tf-market > strong')?.textContent.trim()||'');
    const bottom=el('div','og-spotlight-bottom');bottom.append(market,odds);
    const info=el('div','og-spotlight-info');
    info.append(el('span','',source.querySelector('.tf-meta')?.textContent.trim()||''));
    const action=el('button','og-spotlight-open');action.type='button';
    action.append(document.createTextNode('Vis analysen '));action.insertAdjacentHTML('beforeend',icon('arrow'));
    action.addEventListener('click',()=>{
      // Never duplicate bets or fabricate an analysis: open the existing card.
      const target=source.querySelector('details.tf-analysis');
      if(target)target.open=true;
      source.scrollIntoView({behavior:reducedMotion()?'auto':'smooth',block:'center'});
      source.focus({preventScroll:true});
    });
    const tier=source.querySelector('.og-tier');
    if(tier)info.append(el('span','og-spotlight-tier',tier.textContent));
    item.append(top,teams,bottom,info,action);
    return item;
  }
  function updateFeatured() {
    const list=$('og-featured-list');if(!list)return;
    const choices=[...Array.from($('og-safe')?.querySelectorAll('.tf-card')||[]).map(card=>({card,category:'safe'})),
      ...Array.from($('og-high')?.querySelectorAll('.tf-card')||[]).map(card=>({card,category:'high'}))];
    list.replaceChildren();
    if(!choices.length){featured.hidden=true;return;}
    featured.hidden=false;
    choices.slice(0,3).forEach(({card,category},i)=>list.append(featuredSummary(card,category,i)));
  }
  function update() {
    if(updating)return;
    updating=true;
    try {decorateCards();applySearch();updateFeatured();}
    finally {updating=false;}
  }
  function startup() {
    const main=document.querySelector('main'),hero=main?.querySelector('.hero');
    if(!main||!hero||!setupSections())return;
    document.body.classList.add('og-v37');
    const brand=document.querySelector('.identity-word');
    if(brand)brand.innerHTML='ODDSGENERATOREN <span class="identity-3000">3000</span>';
    buildTools(main,hero);buildFeatured();buildDock();
    const root=$('tf-root');
    // Main renderer rewrites the three .tf-list elements every minute. Observer
    // reacts only to childList changes, not to our search/appearance attributes.
    observed=new MutationObserver(changes=>{
      if(changes.some(change=>change.type==='childList'&&(
        change.target.classList?.contains('tf-list')||
        change.target.closest?.('.tf-list'))))update();
    });
    observed.observe(root,{subtree:true,childList:true});
    update();
    window.addEventListener('hashchange',()=>{
      const target=window.location.hash.slice(1);
      document.querySelectorAll('[data-og-target]').forEach(node=>node.classList.toggle('og-current',node.dataset.ogTarget===target));
    });
  }
  if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',startup);
  if(typeof module==='object'&&module.exports)module.exports={norm,trustFromCard,config,tokens};
})();
