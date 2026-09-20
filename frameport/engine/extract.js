() => {
  const warnings = [];
  let count = 0;
  const ignored = new Set(['SCRIPT','STYLE','NOSCRIPT','TEMPLATE','LINK','META','BASE','OBJECT','EMBED']);
  const unsafeSVG = new Set(['foreignObject','animate','animateMotion','animateTransform','set']);
  const base = document.baseURI;
  const urlAttrs = new Set(['href','src','poster','xlink:href']);
  function walk(node, depth = 0) {
    if (depth > 80 || ++count > 7000) throw new Error('Page exceeds the 7,000-node or 80-level conversion limit.');
    const id = `n${count}`;
    if (node.nodeType === Node.TEXT_NODE) return {id, text: node.textContent || ''};
    if (node.nodeType !== Node.ELEMENT_NODE || ignored.has(node.tagName) || unsafeSVG.has(node.localName)) return null;
    if (node.tagName === 'IFRAME' || node.tagName === 'CANVAS') {
      warnings.push({code: node.tagName.toLowerCase(), message: `${node.tagName.toLowerCase()} content needs a manual replacement.`, severity: 'warning'});
      return {id, tag:'div', attrs:{'data-frameport-placeholder':node.tagName.toLowerCase(), style:`width:${node.clientWidth}px;min-height:${node.clientHeight}px;`}, children:[{id:`${id}-text`,text:`[${node.tagName.toLowerCase()} requires reconnection]`}]};
    }
    const attrs = {};
    for (const attr of Array.from(node.attributes)) {
      const name = attr.name.toLowerCase();
      if (name.startsWith('on') || ['srcdoc','nonce','integrity','crossorigin','ping','action','formaction','autofocus','is','srcset'].includes(name)) continue;
      if (['value','checked','selected'].includes(name) && ['INPUT','OPTION','TEXTAREA'].includes(node.tagName)) continue;
      let value = attr.value;
      if (urlAttrs.has(name) && value && !value.startsWith('#')) {
        try { value = new URL(value, base).href; } catch { continue; }
      }
      attrs[name] = value;
    }
    if (node.tagName === 'IMG') {
      attrs.src = node.currentSrc || node.src;
      attrs.loading = 'eager';
    }
    if (node.tagName === 'SOURCE') return null;
    if (node.tagName === 'INPUT') attrs.autocomplete = 'off';
    if (node.tagName === 'FORM') warnings.push({code:'form',message:'Form presentation is exported. Submission is disabled until you connect a backend.',severity:'warning'});
    if (node.tagName === 'BUTTON' && !node.hasAttribute('aria-controls') && !node.closest('form')) warnings.push({code:'custom-control',message:'A JavaScript-driven button has no portable interaction contract. Reconnect and test it.',severity:'warning'});
    if (node.shadowRoot) warnings.push({code:'shadow-dom',message:'Shadow DOM styling is not reconstructed.',severity:'warning'});
    if (node.tagName === 'VIDEO' || node.tagName === 'AUDIO') {
      warnings.push({code:'media',message:'Media playback and large streaming resources need review.',severity:'warning'});
      attrs.controls = '';
      delete attrs.autoplay;
    }
    const children = node.tagName === 'TEXTAREA' ? [] : Array.from(node.childNodes).map(n => walk(n, depth+1)).filter(Boolean);
    return {id, tag:node.localName, attrs, children};
  }
  const styles = [];
  const seen = new Set();
  for (const sheet of Array.from(document.styleSheets)) {
    if (sheet.ownerNode?.dataset?.frameportFreeze) continue;
    try {
      const css = Array.from(sheet.cssRules).map(r => r.cssText).join('\n');
      const key = `${sheet.href || ''}\n${css}`;
      if (!seen.has(key)) {styles.push({css, base:sheet.href || base}); seen.add(key);}
    } catch { if (sheet.href) styles.push({url:sheet.href,base:sheet.href}); }
  }
  for (const sheet of Array.from(document.adoptedStyleSheets || [])) {
    try {styles.push({css:Array.from(sheet.cssRules).map(r=>r.cssText).join('\n'),base});} catch {}
  }
  const tree = walk(document.body);
  const links = Array.from(document.querySelectorAll('a[href]')).map(a=>a.href).filter(h=>h.startsWith('http'));
  return {url:location.href,title:document.title || location.hostname,description:document.querySelector('meta[name="description"]')?.content || '',lang:document.documentElement.lang || 'en',htmlAttrs:{class:document.documentElement.className,style:document.documentElement.getAttribute('style') || ''},tree,styles,links,warnings,nodes:count,height:document.documentElement.scrollHeight,framer:!!document.querySelector('[data-framer-name],meta[name="generator"][content*="Framer"]')};
}
