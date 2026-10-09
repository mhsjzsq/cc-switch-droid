(() => {
  const VERSION = '__ADDON_VERSION__';
  const prev = window.__droidAddon;
  if (prev && prev.version === VERSION) return;
  if (prev && typeof prev.destroy === 'function') {
    try { prev.destroy(); } catch (_) {}
  }

  const ICON_PATH = 'M321.997 150.712C321.401 150.568 320.844 150.299 320.363 149.925C319.883 149.551 319.491 149.08 319.215 148.544C318.938 148.008 318.783 147.42 318.76 146.821C318.738 146.22 318.848 145.624 319.084 145.07C327.226 125.716 330.819 110.23 325.021 103.747C309.666 86.5471 248.085 120.749 228.451 132.333C227.925 132.642 227.337 132.837 226.728 132.903C226.118 132.969 225.501 132.906 224.918 132.719C224.336 132.531 223.801 132.223 223.351 131.815C222.902 131.407 222.548 130.909 222.313 130.356C214.06 111.043 205.384 97.6094 196.589 97.0268C173.279 95.4688 154.491 162.187 148.991 183.932C148.844 184.515 148.57 185.06 148.188 185.528C147.805 185.998 147.323 186.381 146.775 186.651C146.227 186.921 145.626 187.072 145.012 187.094C144.399 187.116 143.788 187.009 143.221 186.778C123.406 178.825 107.545 175.316 100.914 180.98C83.305 195.978 118.315 256.126 130.175 275.304C130.492 275.816 130.692 276.391 130.76 276.987C130.829 277.582 130.765 278.186 130.573 278.755C130.381 279.325 130.065 279.847 129.647 280.286C129.228 280.725 128.718 281.07 128.15 281.298C108.384 289.359 94.6306 297.834 94.0272 306.424C92.439 329.192 160.74 347.544 183.01 352.916C183.605 353.061 184.16 353.33 184.64 353.704C185.118 354.077 185.509 354.548 185.785 355.083C186.061 355.618 186.215 356.205 186.237 356.803C186.26 357.402 186.151 357.998 185.916 358.551C177.773 377.905 174.181 393.398 179.979 399.874C195.334 417.074 256.921 382.877 276.556 371.293C277.081 370.984 277.67 370.789 278.28 370.722C278.889 370.655 279.507 370.717 280.09 370.905C280.673 371.093 281.207 371.402 281.657 371.81C282.106 372.219 282.46 372.717 282.694 373.271C290.947 392.578 299.616 406.012 308.417 406.601C331.728 408.153 350.516 341.44 356.009 319.688C356.157 319.106 356.432 318.562 356.816 318.094C357.2 317.625 357.682 317.243 358.231 316.974C358.779 316.705 359.381 316.554 359.995 316.533C360.608 316.511 361.219 316.619 361.786 316.85C381.601 324.803 397.455 328.304 404.093 322.648C421.702 307.65 386.684 247.495 374.825 228.317C374.51 227.804 374.312 227.229 374.245 226.634C374.177 226.039 374.242 225.436 374.434 224.868C374.626 224.299 374.941 223.777 375.358 223.338C375.775 222.899 376.284 222.552 376.85 222.323C396.623 214.261 410.376 205.786 410.973 197.196C412.568 174.428 344.26 156.078 321.997 150.712ZM295.254 128.885C299.734 136.73 276.646 189 259.474 225.561C259.186 226.172 258.715 226.682 258.121 227.024C257.528 227.365 256.842 227.521 256.155 227.47C255.468 227.419 254.814 227.164 254.28 226.739C253.746 226.314 253.358 225.739 253.169 225.093C246.234 201.322 238.306 173.392 229.824 149.683C229.491 148.752 229.508 147.736 229.871 146.817C230.235 145.897 230.921 145.133 231.808 144.662C252.989 133.363 289.234 118.358 295.254 128.885ZM193.746 135.355C202.589 137.807 224.103 190.714 238.424 228.426C238.664 229.056 238.699 229.742 238.527 230.393C238.354 231.044 237.983 231.627 237.461 232.065C236.939 232.503 236.292 232.775 235.608 232.844C234.923 232.913 234.234 232.775 233.632 232.45C211.501 220.453 185.694 206.159 162.529 195.253C161.622 194.823 160.901 194.093 160.493 193.192C160.085 192.292 160.018 191.279 160.303 190.335C167.12 167.736 181.865 132.069 193.746 135.355ZM126.652 210.04C134.676 205.664 188.197 228.216 225.621 244.989C226.248 245.269 226.771 245.73 227.12 246.31C227.47 246.889 227.629 247.56 227.577 248.23C227.524 248.901 227.264 249.54 226.828 250.062C226.393 250.582 225.805 250.962 225.143 251.147C200.813 257.921 172.211 265.664 147.937 273.949C146.985 274.272 145.946 274.255 145.007 273.9C144.067 273.545 143.286 272.876 142.805 272.011C131.257 251.322 115.867 215.92 126.652 210.04ZM133.275 309.188C135.779 300.551 189.952 279.537 228.562 265.548C229.207 265.315 229.91 265.28 230.576 265.448C231.243 265.617 231.84 265.98 232.288 266.49C232.736 266.999 233.015 267.631 233.085 268.299C233.155 268.968 233.015 269.641 232.682 270.23C220.392 291.846 205.758 317.053 194.592 339.672C194.156 340.561 193.409 341.269 192.486 341.668C191.563 342.068 190.525 342.134 189.557 341.853C166.42 335.235 129.905 320.792 133.275 309.188ZM209.739 374.722C205.252 366.884 228.347 314.608 245.519 278.054C245.806 277.442 246.279 276.931 246.872 276.59C247.465 276.249 248.151 276.093 248.838 276.144C249.525 276.194 250.179 276.45 250.713 276.875C251.247 277.3 251.634 277.874 251.824 278.521C258.759 302.285 266.686 330.222 275.169 353.932C275.499 354.862 275.481 355.877 275.117 356.795C274.752 357.713 274.064 358.475 273.178 358.945C252.004 370.223 215.752 385.256 209.76 374.722H209.739ZM311.247 368.252C302.397 365.807 280.883 312.894 266.562 275.182C266.322 274.55 266.285 273.862 266.458 273.21C266.63 272.559 267.003 271.974 267.526 271.536C268.049 271.097 268.697 270.826 269.382 270.758C270.068 270.69 270.759 270.83 271.361 271.157C293.485 283.154 319.299 297.455 342.457 308.362C343.366 308.789 344.089 309.519 344.497 310.42C344.905 311.321 344.971 312.335 344.683 313.28C337.872 335.912 323.128 371.544 311.247 368.252ZM378.341 293.566C370.31 297.949 316.795 275.391 279.365 258.618C278.738 258.338 278.215 257.877 277.866 257.297C277.516 256.718 277.357 256.047 277.409 255.377C277.461 254.706 277.722 254.067 278.158 253.546C278.593 253.025 279.181 252.646 279.843 252.461C304.18 245.687 332.775 237.943 357.049 229.658C358.003 229.335 359.043 229.353 359.984 229.709C360.925 230.065 361.706 230.737 362.188 231.603C373.729 252.285 389.119 287.693 378.341 293.566ZM371.718 194.419C369.207 203.063 315.041 224.077 276.431 238.066C275.784 238.3 275.08 238.335 274.413 238.167C273.746 237.999 273.148 237.635 272.698 237.124C272.249 236.613 271.972 235.98 271.903 235.31C271.833 234.641 271.975 233.966 272.311 233.377C284.594 211.768 299.228 186.554 310.394 163.935C310.833 163.048 311.58 162.343 312.502 161.945C313.425 161.546 314.462 161.481 315.429 161.76C338.566 168.413 375.081 182.815 371.718 194.419Z';
  const ICON = `<svg fill="currentColor" width="1em" height="1em" viewBox="93.5 92.814 318 318" xmlns="http://www.w3.org/2000/svg" style="flex:none;line-height:1"><path d="${ICON_PATH}"></path></svg>`;
  const REFRESH_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>';
  // Classes CC Switch puts on the selected sidebar entry (observed in v3.20).
  const ACTIVE_CLASSES = ['bg-selected', 'font-medium', 'hover:bg-selected'];
  const ATTR = 'data-droid-addon';

  const state = { data: null, active: false, refreshRequested: false, refreshing: false };
  let navBtn = null;
  let headerEl = null;
  let bodyEl = null;
  let styleEl = null;
  let observer = null;
  let suppressed = null;
  let scheduled = false;
  let timer = null;
  const listeners = [];

  const on = (target, type, fn, opts) => {
    target.addEventListener(type, fn, opts);
    listeners.push(() => target.removeEventListener(type, fn, opts));
  };

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const CSS = `
  .da-layer{position:absolute;z-index:40;background:var(--bg-app);color:var(--text-1);box-sizing:border-box}
  .da-head{top:0;left:0;display:flex;align-items:center;gap:10px;padding:0 16px 0 24px;border-bottom:1px solid hsl(var(--border))}
  .da-head .da-title{font-size:17px;font-weight:600;white-space:nowrap}
  .da-head .da-sub{font-size:12px;color:var(--text-3);white-space:nowrap}
  .da-head .da-spacer{flex:1}
  .da-btn{display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 12px;border:1px solid hsl(var(--border));border-radius:8px;background:var(--bg-card);color:var(--text-1);font-size:13px;cursor:pointer;white-space:nowrap}
  .da-btn:hover{background:var(--bg-subtle)}
  .da-btn[disabled]{opacity:.6;cursor:default}
  .da-body{left:0;right:0;bottom:0;overflow-y:auto;padding:8px 24px 24px}
  .da-card{border:1px solid hsl(var(--border));border-radius:12px;background:var(--bg-card);padding:14px 16px;margin-bottom:14px}
  .da-card-h{display:flex;align-items:center;gap:8px;margin-bottom:12px}
  .da-card-h .da-name{font-weight:600;font-size:14px}
  .da-pill{font-size:11px;padding:1px 8px;border-radius:999px;border:1px solid hsl(var(--border));color:var(--text-2)}
  .da-muted{color:var(--text-3);font-size:12px}
  .da-win{margin-top:12px}
  .da-win:first-of-type{margin-top:0}
  .da-row{display:flex;align-items:baseline;justify-content:space-between;gap:8px;font-size:13px}
  .da-row b{font-weight:600;font-variant-numeric:tabular-nums}
  .da-bar{height:6px;border-radius:999px;background:var(--bg-subtle);overflow:hidden;margin:6px 0 4px}
  .da-bar>i{display:block;height:100%;border-radius:999px;background:var(--chart-1)}
  .da-bar.warn>i{background:var(--warning)}
  .da-bar.low>i{background:var(--danger)}
  .da-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
  .da-metric{border:1px solid hsl(var(--border));border-radius:10px;padding:10px 12px}
  .da-metric .v{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums;margin-top:4px}
  .da-err{color:var(--danger-text);background:var(--danger-soft);border-radius:8px;padding:8px 10px;font-size:13px;margin-top:8px;word-break:break-all}
  .da-code{font-family:ui-monospace,Consolas,monospace;font-size:12px;background:var(--bg-subtle);padding:1px 5px;border-radius:4px;word-break:break-all;user-select:text}
  .da-foot{font-size:11px;color:var(--text-3);margin-top:4px}
  [data-da-on]>span[aria-hidden="true"]{opacity:0}
  body[data-da-busy] [data-radix-popper-content-wrapper]{opacity:0!important;pointer-events:none!important}
  #main-content{transition:opacity .12s ease-out}
  #main-content[data-da-loading]{opacity:0;transition:none}
  [data-da-on]>button[aria-pressed="true"]:not(.da-filter){font-weight:500;color:var(--text-2)}
  .da-filter[aria-pressed="true"]{background:var(--bg-card);box-shadow:var(--shadow-sm);color:var(--text-1)}
  .da-filter{color:var(--text-2)}
  .da-filter:hover{color:var(--text-1)}
  span[data-da-app]::before{content:"";flex:none;width:14px;height:14px;margin:0 1px;background-color:currentColor;-webkit-mask:var(--da-icon) center/contain no-repeat;mask:var(--da-icon) center/contain no-repeat}
  .da-toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:200;background:var(--inverse-bg);color:var(--inverse-fg);padding:8px 14px;border-radius:8px;font-size:13px;box-shadow:var(--shadow-md)}
  `;

  function nav() { return document.querySelector('nav'); }
  function mainArea() { return document.getElementById('content-area') || document.querySelector('main'); }

  function appsGroup() {
    const n = nav();
    if (!n) return null;
    const groups = [...n.querySelectorAll('[role="group"]')];
    // Only the app list qualifies; other sidebars (e.g. settings) must not get the entry.
    return groups.find((g) => {
      const names = [...g.children].filter((b) => b.tagName === 'BUTTON').map((b) => b.textContent);
      return names.some((t) => /Codex/.test(t)) && names.some((t) => /Claude/.test(t));
    }) || null;
  }

  function nativeButtons(group) {
    return [...group.children].filter((el) => el.tagName === 'BUTTON' && !el.hasAttribute(ATTR));
  }

  function baseClassName(template) {
    const cls = template.className.split(/\s+/).filter((c) => c && !ACTIVE_CLASSES.includes(c));
    if (!cls.includes('hover:bg-subtle')) cls.push('hover:bg-subtle');
    return cls.join(' ');
  }

  function buildNavButton(group) {
    const buttons = nativeButtons(group);
    const template = buttons[buttons.length - 1];
    if (!template) return null;
    const btn = template.cloneNode(true);
    btn.setAttribute(ATTR, '1');
    btn.removeAttribute('aria-current');
    btn.removeAttribute('id');
    btn.dataset.daBase = baseClassName(template);
    btn.className = btn.dataset.daBase;
    btn.title = 'Droid';
    const iconWrap = btn.querySelector('span[aria-hidden="true"]') || btn.firstElementChild;
    if (iconWrap) {
      iconWrap.innerHTML = `<span class="inline-flex items-center justify-center flex-shrink-0" style="width:16px;height:16px;font-size:16px;line-height:1;color:var(--text-1)">${ICON}</span>`;
    }
    const label = [...btn.querySelectorAll('span')].reverse().find((s) => !s.closest('span[aria-hidden="true"]') && s.children.length === 0);
    if (label) label.textContent = 'Droid';
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      activate();
    });
    return btn;
  }

  function ensureNavButton() {
    const group = appsGroup();
    if (!group) {
      if (navBtn) { navBtn.remove(); navBtn = null; }
      if (state.active) deactivate();
      return;
    }
    const buttons = nativeButtons(group);
    const last = buttons[buttons.length - 1];
    if (!last) return;
    const stale = navBtn && (navBtn.parentElement !== group || navBtn.dataset.daBase !== baseClassName(last));
    if (stale) { navBtn.remove(); navBtn = null; }
    if (!navBtn) {
      navBtn = buildNavButton(group);
      if (!navBtn) return;
    }
    if (navBtn.previousElementSibling !== last) last.after(navBtn);
    paintNavButton();
  }

  function paintNavButton() {
    if (!navBtn) return;
    const base = navBtn.dataset.daBase;
    navBtn.className = state.active ? `${base} ${ACTIVE_CLASSES.join(' ')}`.replace('hover:bg-subtle', '') : base;
    if (state.active) navBtn.setAttribute('aria-current', 'page');
    else navBtn.removeAttribute('aria-current');
  }

  function suppressNativeActive() {
    const n = nav();
    if (!n) return;
    const current = n.querySelector(`[aria-current="page"]:not([${ATTR}])`);
    if (suppressed && suppressed.el === current) return;
    restoreNativeActive();
    if (!current) return;
    suppressed = { el: current, bg: current.style.backgroundColor, fw: current.style.fontWeight };
    current.style.backgroundColor = 'transparent';
    current.style.fontWeight = '400';
  }

  function restoreNativeActive() {
    if (!suppressed) return;
    suppressed.el.style.backgroundColor = suppressed.bg;
    suppressed.el.style.fontWeight = suppressed.fw;
    suppressed = null;
  }

  function ensureLayers() {
    const main = mainArea();
    if (!main) return false;
    if (!headerEl || !main.contains(headerEl)) {
      headerEl = document.createElement('div');
      headerEl.className = 'da-layer da-head';
      headerEl.setAttribute(ATTR, 'head');
      main.appendChild(headerEl);
      headerEl.addEventListener('click', (e) => {
        if (e.target.closest('[data-da-refresh]')) requestRefresh();
      });
    }
    if (!bodyEl || !main.contains(bodyEl)) {
      bodyEl = document.createElement('div');
      bodyEl.className = 'da-layer da-body';
      bodyEl.setAttribute(ATTR, 'body');
      main.appendChild(bodyEl);
    }
    layout();
    return true;
  }

  function layout() {
    const main = mainArea();
    if (!main || !headerEl || !bodyEl) return;
    const mr = main.getBoundingClientRect();
    const header = main.querySelector('header');
    const hh = header ? Math.round(header.getBoundingClientRect().height) : 52;
    const minimize = main.querySelector('button[aria-label*="最小化"], button[aria-label*="inimize"]');
    const controls = minimize ? minimize.parentElement : null;
    const right = controls ? Math.max(0, Math.round(controls.getBoundingClientRect().left - mr.left) - 8) : mr.width - 120;
    Object.assign(headerEl.style, { height: `${hh}px`, width: `${right}px` });
    Object.assign(bodyEl.style, { top: `${hh}px` });
    const show = state.active ? '' : 'none';
    headerEl.style.display = show;
    bodyEl.style.display = show;
  }

  function activate() {
    state.active = true;
    ensureLayers();
    suppressNativeActive();
    paintNavButton();
    render();
  }

  function deactivate() {
    if (!state.active) return;
    state.active = false;
    restoreNativeActive();
    paintNavButton();
    layout();
  }

  function fmtNum(n) {
    n = Number(n) || 0;
    if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
    return String(n);
  }

  function fmtReset(ms) {
    if (!ms) return '';
    let s = Math.max(0, Math.round((ms - Date.now()) / 1000));
    const d = Math.floor(s / 86400); s -= d * 86400;
    const h = Math.floor(s / 3600); s -= h * 3600;
    const m = Math.floor(s / 60);
    if (d > 0) return `${d}天 ${h}小时后重置`;
    if (h > 0) return `${h}小时 ${m}分后重置`;
    return `${m}分后重置`;
  }

  function fmtTime(ms) {
    if (!ms) return '—';
    const d = new Date(ms);
    return d.toLocaleTimeString('zh-CN', { hour12: false });
  }

  function renderQuota(d) {
    const q = d.quota || {};
    if (!d.configured) {
      return `<div class="da-card"><div class="da-card-h"><span class="da-name">Factory 额度</span></div>
        <div class="da-muted">还没有配置 Factory API key。在下面的文件里填写 <span class="da-code">factoryApiKey</span>，保存后会自动生效：</div>
        <div style="margin-top:8px"><span class="da-code">${esc(d.configPath)}</span></div>
        <div class="da-muted" style="margin-top:8px">API key 可以在 <span class="da-code">https://app.factory.ai/settings/api-keys</span> 创建。</div></div>`;
    }
    const wins = (q.windows || []).map((w) => {
      const used = Math.max(0, Math.min(100, Number(w.usedPercent) || 0));
      const left = 100 - used;
      const cls = left <= 10 ? 'low' : left <= 30 ? 'warn' : '';
      return `<div class="da-win"><div class="da-row"><span>${esc(w.label)}</span><span><b>剩余 ${left.toFixed(left % 1 ? 1 : 0)}%</b></span></div>
        <div class="da-bar ${cls}"><i style="width:${left}%"></i></div>
        <div class="da-row da-muted"><span>已用 ${used.toFixed(used % 1 ? 1 : 0)}%</span><span data-da-reset="${w.resetsAt || ''}">${fmtReset(w.resetsAt)}</span></div></div>`;
    }).join('');
    const balance = q.balance != null ? `<div class="da-row" style="margin-top:12px"><span>额外用量余额</span><b>$${Number(q.balance).toFixed(2)}</b></div>` : '';
    const err = q.error ? `<div class="da-err">${esc(q.error)}</div>` : '';
    const empty = !wins && !q.error ? '<div class="da-muted">正在获取额度…</div>' : '';
    return `<div class="da-card"><div class="da-card-h"><span class="da-name">Factory 额度</span>${q.plan ? `<span class="da-pill">${esc(q.plan)}</span>` : ''}<span style="flex:1"></span>${q.account ? `<span class="da-muted">${esc(q.account)}</span>` : ''}</div>
      ${wins}${balance}${empty}${err}</div>`;
  }

  function renderToday(d) {
    const t = d.today || {};
    return `<div class="da-card"><div class="da-card-h"><span class="da-name">今日 Droid 用量</span><span style="flex:1"></span><span class="da-muted">本机会话日志</span></div>
      <div class="da-grid">
        <div class="da-metric"><div class="da-muted">Tokens</div><div class="v" title="${esc(t.tokens)}">${fmtNum(t.tokens)}</div></div>
        <div class="da-metric"><div class="da-muted">成本（按 API 价格）</div><div class="v">$${(Number(t.cost) || 0).toFixed(2)}</div></div>
        <div class="da-metric"><div class="da-muted">缓存命中</div><div class="v">${fmtNum(t.cacheRead)}</div></div>
      </div>
      <div class="da-foot" style="margin-top:10px">输入 ${fmtNum(t.input)} · 输出 ${fmtNum(t.output)} · 缓存写入 ${fmtNum(t.cacheCreation)} · 记录 ${Number(t.records) || 0} 条。详细记录在「用量统计」的「全部」里查看。</div></div>`;
  }

  function render() {
    if (!state.active || !headerEl || !bodyEl) return;
    const d = state.data || { configured: true, quota: {}, today: {} };
    const q = d.quota || {};
    headerEl.innerHTML = `<span data-tauri-drag-region style="display:inline-flex;font-size:20px;color:var(--text-1)">${ICON}</span>
      <span class="da-title" data-tauri-drag-region>Droid</span><span class="da-sub" data-tauri-drag-region>Factory 额度与用量</span>
      <span class="da-spacer" data-tauri-drag-region></span>
      <span class="da-sub" data-tauri-drag-region>额度更新于 ${fmtTime(q.updatedAt)}</span>
      <button type="button" class="da-btn" data-da-refresh ${state.refreshing ? 'disabled' : ''}>${REFRESH_ICON}${state.refreshing ? '刷新中…' : '立即刷新'}</button>`;
    headerEl.setAttribute('data-tauri-drag-region', '');
    bodyEl.innerHTML = renderQuota(d) + renderToday(d) +
      `<div class="da-foot">由 CC-Switch-Droid-Addon 注入，不是 CC Switch 自带的功能。</div>`;
  }

  function requestRefresh() {
    state.refreshRequested = true;
    state.refreshing = true;
    render();
  }

  function check() {
    scheduled = false;
    ensureNavButton();
    try { decorateUsage(); } catch (_) {}
    if (state.active) {
      const n = nav();
      const current = n && n.querySelector(`[aria-current="page"]:not([${ATTR}])`);
      if (suppressed && current !== suppressed.el) suppressNativeActive();
      if (!headerEl || !bodyEl || !mainArea() || !mainArea().contains(headerEl)) { ensureLayers(); render(); }
    }
  }

  // ---- 用量统计页：Droid 筛选按钮与名称显示 ----
  const DROID_PROVIDER = '_droid_session';
  const DROID_PROVIDER_LABEL = 'Droid · 会话日志';
  const ICON_MASK = `url("data:image/svg+xml,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' viewBox='93.5 92.814 318 318'><path d='${ICON_PATH}'/></svg>`)}")`;
  let filterBtn = null;
  let filterBusy = false;
  let filterPending = null;
  let toastEl = null;

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function waitFor(fn, timeout = 1500) {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      const v = fn();
      if (v) return v;
      await sleep(40);
    }
    return null;
  }

  // React keeps a single text node for these labels and updates it via
  // nodeValue, so editing it in place survives re-renders without conflicts.
  function setText(el, text) {
    if (!el) return;
    const n = el.firstChild;
    if (n && n.nodeType === 3 && el.childNodes.length === 1) {
      if (n.nodeValue !== text) n.nodeValue = text;
    }
  }
  function setTitle(el, text) {
    if (el && el.getAttribute('title') !== text) el.setAttribute('title', text);
  }

  function appFilterGroup() { return document.querySelector('[role="group"][aria-label="按应用筛选"]'); }
  function filterToolbar(group) { return group && group.parentElement; }
  function providerTrigger(group) {
    const bar = filterToolbar(group);
    return bar ? bar.querySelector('button[aria-haspopup="menu"]') : null;
  }
  function allAppsButton(group) {
    return [...group.querySelectorAll(':scope > button')].find((b) => !b.hasAttribute(ATTR) && !b.getAttribute('aria-label'));
  }
  function isDroidProviderSelected(group) {
    const t = providerTrigger(group);
    return !!t && (t.dataset.daDroid === '1' || t.getAttribute('title') === DROID_PROVIDER);
  }

  function decorateUsage() {
    // Request log rows
    document.querySelectorAll('tbody span[title="droid"], tbody span[data-da-app]').forEach((cell) => {
      cell.setAttribute('data-da-app', 'droid');
      setTitle(cell, 'Droid');
      cell.querySelectorAll(':scope > span').forEach((s) => setText(s, 'Droid'));
    });
    document.querySelectorAll(`tbody span[title="${DROID_PROVIDER}"], tbody span[data-da-prov]`).forEach((cell) => {
      cell.setAttribute('data-da-prov', '1');
      setTitle(cell, `${DROID_PROVIDER_LABEL}\n由 CC-Switch-Droid-Addon 从 Droid 会话日志导入`);
      setText(cell, '会话日志');
    });
    // Provider dropdown items and trigger
    document.querySelectorAll(`[role="menuitem"][title="${DROID_PROVIDER}"], [role="menuitem"][data-da-droid]`).forEach((item) => {
      item.dataset.daDroid = '1';
      setTitle(item, DROID_PROVIDER_LABEL);
      setText(item.querySelector('span.truncate') || item.querySelector('span'), DROID_PROVIDER_LABEL);
    });
    document.querySelectorAll('button[aria-haspopup="menu"]').forEach((b) => {
      const marked = b.dataset.daDroid === '1';
      const title = b.getAttribute('title');
      if (title === DROID_PROVIDER || (marked && title === DROID_PROVIDER_LABEL)) {
        b.dataset.daDroid = '1';
        setTitle(b, DROID_PROVIDER_LABEL);
        setText(b.querySelector('span.truncate') || b.querySelector('span'), DROID_PROVIDER_LABEL);
      } else if (marked) {
        delete b.dataset.daDroid;
      }
    });

    const group = appFilterGroup();
    if (!group) { filterBtn = null; return; }
    if (!filterBtn || filterBtn.parentElement !== group) {
      if (filterBtn) filterBtn.remove();
      filterBtn = buildFilterButton(group);
    }
    if (!filterBtn) return;
    const on = filterPending
      ? filterPending === 'on'
      : isDroidProviderSelected(group) && allAppsButton(group)?.getAttribute('aria-pressed') === 'true';
    if (on) group.setAttribute('data-da-on', '1');
    else group.removeAttribute('data-da-on');
    filterBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
  }

  function buildFilterButton(group) {
    const natives = [...group.querySelectorAll(':scope > button[aria-label]')].filter((b) => !b.hasAttribute(ATTR));
    const template = natives[natives.length - 1];
    if (!template) return null;
    const btn = template.cloneNode(true);
    btn.setAttribute(ATTR, 'filter');
    btn.setAttribute('aria-label', 'Droid');
    btn.setAttribute('aria-pressed', 'false');
    btn.removeAttribute('data-state');
    btn.removeAttribute('id');
    btn.title = 'Droid（按供应商筛选 Droid 会话日志）';
    btn.classList.add('da-filter');
    const icon = btn.querySelector('span[aria-hidden="true"]');
    if (icon) icon.innerHTML = `<span class="inline-flex items-center justify-center flex-shrink-0" style="width:16px;height:16px;font-size:16px;line-height:1">${ICON}</span>`;
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      toggleDroidFilter();
    });
    group.appendChild(btn);
    return btn;
  }

  function openMenu(trigger) {
    trigger.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, button: 0, pointerType: 'mouse' }));
  }
  function closeMenu() {
    const menu = document.querySelector('[role="menu"]');
    if (menu) menu.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  }

  function toast(msg) {
    if (toastEl) toastEl.remove();
    toastEl = document.createElement('div');
    toastEl.setAttribute(ATTR, 'toast');
    toastEl.className = 'da-toast';
    toastEl.textContent = msg;
    document.body.appendChild(toastEl);
    const el = toastEl;
    setTimeout(() => { el.remove(); if (toastEl === el) toastEl = null; }, 2500);
  }

  function usageContent() { return document.getElementById('main-content'); }

  // Rows render after the query returns; wait until the table reflects the
  // requested filter so the intermediate "全部" data is never shown.
  function filterSettled(wantOn) {
    const group = appFilterGroup();
    if (!group) return true;
    const trigger = providerTrigger(group);
    const droidSel = !!trigger && (trigger.dataset.daDroid === '1' || trigger.getAttribute('title') === DROID_PROVIDER);
    if (droidSel !== wantOn) return false;
    if (!wantOn) return true;
    const rows = [...document.querySelectorAll('tbody tr')].slice(0, 8);
    return rows.every((r) => r.querySelector('span[title="droid"], span[data-da-app]'));
  }

  async function toggleDroidFilter() {
    if (filterBusy) return;
    filterBusy = true;
    let group = appFilterGroup();
    const wasOn = !!group && group.getAttribute('data-da-on') === '1';
    filterPending = wasOn ? 'off' : 'on';
    document.body.setAttribute('data-da-busy', '1');
    const content = usageContent();
    if (content) content.setAttribute('data-da-loading', '1');
    decorateUsage();
    let selected = false;
    try {
      if (!group) return;
      if (!wasOn) {
        const all = allAppsButton(group);
        if (all && all.getAttribute('aria-pressed') !== 'true') {
          all.click();
          await waitFor(() => { const g = appFilterGroup(); return g && allAppsButton(g)?.getAttribute('aria-pressed') === 'true'; });
          await sleep(120);
          group = appFilterGroup();
        }
      }
      const trigger = providerTrigger(group);
      if (!trigger) return;
      openMenu(trigger);
      const item = await waitFor(() => {
        const items = [...document.querySelectorAll('[role="menu"] [role="menuitem"]')];
        if (!items.length) return null;
        if (wasOn) return items.find((i) => i.textContent.includes('全部供应商')) || items[0];
        return items.find((i) => i.dataset.daDroid === '1' || i.getAttribute('title') === DROID_PROVIDER) || 'none';
      });
      if (item && item !== 'none') {
        item.click();
        selected = true;
      } else {
        closeMenu();
        toast('当前时间范围内没有 Droid 记录');
      }
      if (selected) {
        await waitFor(() => filterSettled(!wasOn), 2500);
        await sleep(150);
      }
    } finally {
      filterPending = null;
      filterBusy = false;
      document.body.removeAttribute('data-da-busy');
      document.querySelectorAll('[data-da-loading]').forEach((el) => el.removeAttribute('data-da-loading'));
      decorateUsage();
      scheduleCheck();
    }
  }

  function scheduleCheck() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(check);
  }

  styleEl = document.createElement('style');
  styleEl.setAttribute(ATTR, 'style');
  styleEl.textContent = `${CSS}\n:root{--da-icon:${ICON_MASK}}`;
  document.head.appendChild(styleEl);

  on(document, 'click', (e) => {
    if (!state.active) return;
    const btn = e.target.closest && e.target.closest('nav button');
    if (btn && !btn.hasAttribute(ATTR)) deactivate();
  }, true);
  on(window, 'resize', () => { if (state.active) layout(); });
  // CC Switch's own "立即同步" only scans the tools it knows; also sync Droid.
  on(document, 'click', (e) => {
    const btn = e.target.closest && e.target.closest('header button');
    if (btn && btn.textContent.trim() === '立即同步') state.syncRequested = true;
  }, true);
  // "全部" is natively already pressed while the Droid filter is on, so CC Switch
  // ignores the click; treat it as "turn the Droid filter off".
  on(document, 'click', (e) => {
    const btn = e.target.closest && e.target.closest('[role="group"][aria-label="按应用筛选"] > button');
    if (!btn || btn.hasAttribute(ATTR) || filterPending) return;
    const group = btn.parentElement;
    if (group.getAttribute('data-da-on') !== '1' || btn !== allAppsButton(group)) return;
    e.preventDefault();
    e.stopPropagation();
    toggleDroidFilter();
  }, true);

  observer = new MutationObserver((records) => {
    for (const r of records) {
      const t = r.target && r.target.nodeType === 3 ? r.target.parentElement : r.target;
      if (t && t.closest && t.closest(`[${ATTR}]`)) continue;
      scheduleCheck();
      return;
    }
  });
  observer.observe(document.body, {
    childList: true, subtree: true, characterData: true,
    attributes: true, attributeFilter: ['aria-current', 'aria-pressed', 'class', 'title'],
  });

  timer = setInterval(() => {
    if (!state.active || !bodyEl) return;
    bodyEl.querySelectorAll('[data-da-reset]').forEach((el) => {
      const ms = Number(el.getAttribute('data-da-reset'));
      if (ms) el.textContent = fmtReset(ms);
    });
  }, 30000);

  window.__droidAddon = {
    version: VERSION,
    setData(data) {
      state.data = data;
      state.refreshing = !!(data && data.refreshing);
      render();
    },
    poll() {
      const r = state.refreshRequested;
      const s = state.syncRequested;
      state.refreshRequested = false;
      state.syncRequested = false;
      return { version: VERSION, refresh: r, syncNow: s, active: state.active };
    },
    destroy() {
      deactivate();
      observer && observer.disconnect();
      clearInterval(timer);
      listeners.forEach((off) => off());
      [navBtn, headerEl, bodyEl, styleEl, filterBtn, toastEl].forEach((el) => el && el.remove());
      const g = appFilterGroup();
      if (g) g.removeAttribute('data-da-on');
      delete window.__droidAddon;
    },
  };

  check();
})();
