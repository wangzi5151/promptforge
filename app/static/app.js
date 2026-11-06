/* PromptForge 2.0 — frontend runtime (vanilla, no build step) */

/* ============================== utils ============================== */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtNum = n => n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + 'k' : String(n ?? 0);
const fmtTime = t => { const d = new Date(t * 1000); const diff = Math.max(0, (Date.now() - d) / 1000); if (diff < 60) return '刚刚'; if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前'; if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前'; if (diff < 604800) return Math.floor(diff / 86400) + ' 天前'; return d.toLocaleDateString('zh-CN'); };

async function api(path, opt = {}) {
  const res = await fetch('/api' + path, { headers: { 'Content-Type': 'application/json' }, ...opt });
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail || j.message || msg; } catch { }
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return res.status === 204 ? null : res.json();
}

function toast(msg, type = 'ok') {
  const icons = {
    ok: '<path d="M20 6L9 17l-5-5" stroke="currentColor" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    err: '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" fill="none"/><path d="M12 7v6M12 16.5v.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    info: '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" fill="none"/><path d="M12 11v6M12 7.5v.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
  };
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.innerHTML = `<svg class="ti" viewBox="0 0 24 24" fill="none">${icons[type] || icons.info}</svg><span>${esc(msg)}</span>`;
  $('#toasts').appendChild(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 280); }, 3000);
}

/* minimal markdown (safe: escapes first) */
function md(src) {
  let s = esc(src || '');
  const blocks = [];
  s = s.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => { blocks.push(`<pre><code>${code}</code></pre>`); return `\u0000${blocks.length - 1}\u0000`; });
  s = s.replace(/^### (.*)$/gm, '<h3>$1</h3>')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>')
    .replace(/^# (.*)$/gm, '<h1>$1</h1>')
    .replace(/^> (.*)$/gm, '<blockquote>$1</blockquote>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
  // tables
  s = s.replace(/^\|(.+)\|\n\|[\s:|-]+\|\n((?:\|.+\|\n?)+)/gm, (m, head, body) => {
    const th = head.split('|').map(c => c.trim()).filter(Boolean).map(c => `<th>${c}</th>`).join('');
    const trs = body.trim().split('\n').map(r => '<tr>' + r.split('|').map(c => c.trim()).filter((c, i, a) => !(i === 0 && c === '') && !(i === a.length - 1 && c === '')).map(c => `<td>${c}</td>`).join('') + '</tr>').join('');
    return `<table><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table>`;
  });
  // lists
  s = s.replace(/(?:^[-*] .+$\n?)+/gm, m => '<ul>' + m.trim().split('\n').map(l => `<li>${l.replace(/^[-*] /, '')}</li>`).join('') + '</ul>');
  s = s.replace(/(?:^\d+\. .+$\n?)+/gm, m => '<ol>' + m.trim().split('\n').map(l => `<li>${l.replace(/^\d+\. /, '')}</li>`).join('') + '</ol>');
  s = s.split('\n\n').map(p => /^<(h\d|ul|ol|pre|table|blockquote)/.test(p.trim()) ? p : p.trim() ? `<p>${p.replace(/\n/g, '<br>')}</p>` : '').join('');
  s = s.replace(/\u0000(\d+)\u0000/g, (_, i) => blocks[+i]);
  return s;
}

/* ============================== icons ============================== */
const I = {
  dash: '<path d="M3 13h5v8H3zM10 3h4v18h-4zM16 9h5v12h-5z" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linejoin="round"/>',
  lib: '<path d="M4 5h16M4 12h16M4 19h10" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>',
  play: '<path d="M7 4.5l12 7.5-12 7.5z" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linejoin="round"/>',
  chart: '<path d="M4 19V9M10 19V5M16 19v-7M22 19H2" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>',
  cog: '<circle cx="12" cy="12" r="3.2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M12 2.5v3M12 18.5v3M21.5 12h-3M5.5 12h-3M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1M18.7 18.7l-2.1-2.1M7.4 7.4L5.3 5.3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  key: '<circle cx="8" cy="15" r="4" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M11 12l9-9M17 6l2 2M14 9l2 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  plus: '<path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
  search: '<circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.9" fill="none"/><path d="M16 16l4 4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>',
  star: '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linejoin="round"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  save: '<path d="M5 4h11l3 3v13H5z" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linejoin="round"/><path d="M8 4v6h7V4M8 20v-6h8v6" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linejoin="round"/>',
  close: '<path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  clock: '<circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M12 7.5V12l3.2 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2" stroke="currentColor" stroke-width="1.8" fill="none"/><path d="M15 5H6a1 1 0 00-1 1v9" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/>',
  refresh: '<path d="M20 11a8 8 0 10-2.3 6.3M20 4v7h-7" stroke="currentColor" stroke-width="1.9" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  bolt: '<path d="M13 2L4.5 13.5H11L10 22l8.5-11.5H12z" fill="currentColor"/>',
  cmp: '<path d="M12 3v18M7 8L3 12l4 4M17 8l4 4-4 4" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  down: '<path d="M12 4v12M6 12l6 6 6-6M4 20h16" stroke="currentColor" stroke-width="1.9" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  up: '<path d="M12 20V8M6 12l6-6 6 6M4 4h16" stroke="currentColor" stroke-width="1.9" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
};
const svg = (k, cls = '') => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" width="16" height="16">${I[k]}</svg>`;

/* ============================== state ============================== */
const S = {
  page: 'dashboard',
  prompts: [],
  category: '',
  favoriteOnly: false,
  query: '',
  editing: null,   // prompt object
  dirty: false,
  llmReady: false,
  providers: []
};

/* ============================== router ============================== */
const PAGES = ['dashboard', 'library', 'insights', 'settings', 'keys'];

$$('.nav-item').forEach(n => n.addEventListener('click', () => go(n.dataset.page)));

function go(page) {
  if (!PAGES.includes(page)) page = 'dashboard';
  S.page = page;
  $$('.page').forEach(p => p.classList.toggle('show', p.id === 'page-' + page));
  $$('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.page === page));
  location.hash = page;
  if (page === 'dashboard') loadDashboard();
  if (page === 'library') loadLibrary();
  if (page === 'insights') loadInsights();
  if (page === 'settings') loadSettings();
  if (page === 'keys') loadKeys();
}

/* ============================== dashboard ============================== */
async function loadDashboard() {
  try {
    const [a] = await Promise.all([api('/analytics'), checkHealth()]);
    renderTrend('#dashTrend', a.trend);
    renderTopPrompts('#dashTop', a.top_prompts);
    renderCatBars('#dashCats', a.by_category);
    $('#kPrompts').textContent = a.total_prompts;
    $('#kRuns').textContent = fmtNum(a.total_runs);
    $('#kScore').textContent = a.avg_score ? a.avg_score.toFixed(1) : '—';
    $('#kScoreFoot').textContent = a.scored_runs ? `${a.scored_runs} 次评分` : '尚无评分';
    $('#kTokens').textContent = fmtNum(a.total_tokens);
    $('#kLatency').textContent = a.avg_latency_ms ? a.avg_latency_ms + 'ms' : '—';
    $('#recentList').innerHTML = await renderRecent();
  } catch (e) { toast(e.message, 'err'); }
}

async function renderRecent() {
  try {
    const runs = await api('/runs?limit=6');
    if (!runs.length) return '<div class="empty" style="padding:28px"><p>还没有运行记录</p></div>';
    return runs.map(r => `
      <div class="ver-row" style="cursor:pointer" onclick="openPlayground('${r.prompt_id}')">
        <span class="ver-badge">${r.variant || 'A'}</span>
        <span class="ver-note">${esc((r.output || r.rendered || '').slice(0, 60).replace(/\n/g, ' '))}</span>
        <span class="ver-time">${fmtTime(r.created_at)}</span>
      </div>`).join('');
  } catch { return ''; }
}

function renderTrend(sel, trend) {
  const el = $(sel); if (!el) return;
  const days = [...Array(14)].map((_, i) => {
    const d = new Date(Date.now() - (13 - i) * 864e5);
    const k = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return { k, label: `${d.getMonth() + 1}/${d.getDate()}`, v: trend[k] || 0 };
  });
  const max = Math.max(1, ...days.map(d => d.v));
  el.innerHTML = days.map(d => `
    <div class="col">
      <div class="tip">${d.v} 次运行</div>
      <div class="fill${d.v ? '' : ' zero'}" style="height:${Math.max(3, (d.v / max) * 100)}%"></div>
      <div class="x">${d.label}</div>
    </div>`).join('');
}

function renderTopPrompts(sel, top) {
  const el = $(sel); if (!el) return;
  if (!top || !top.length) { el.innerHTML = '<div class="empty" style="padding:20px"><p>暂无数据</p></div>'; return; }
  el.innerHTML = top.map((t, i) => `
    <div class="ver-row">
      <span class="mono muted" style="width:14px;font-size:11px">${i + 1}</span>
      <span class="ver-note" style="cursor:pointer" onclick="openPlayground('${t.id}')">${esc(t.title)}</span>
      <span class="ver-time">${t.runs} 次</span>
      ${t.avg_score ? `<span class="tag amber">★ ${t.avg_score}</span>` : ''}
    </div>`).join('');
}

function renderCatBars(sel, cats) {
  const el = $(sel); if (!el) return;
  const entries = Object.entries(cats || {});
  if (!entries.length) { el.innerHTML = '<div class="empty" style="padding:20px"><p>暂无分类</p></div>'; return; }
  const max = Math.max(...entries.map(([, v]) => v));
  el.innerHTML = entries.map(([k, v]) => `
    <div class="bar-row">
      <div class="br-top"><span class="n">${esc(k)}</span><span class="v">${v}</span></div>
      <div class="bar-track"><i style="width:${(v / max) * 100}%"></i></div>
    </div>`).join('');
}

/* ============================== library ============================== */
let searchTimer;
function onSearch(v) { S.query = v; clearTimeout(searchTimer); searchTimer = setTimeout(loadLibrary, 200); }

async function loadLibrary() {
  try {
    const params = new URLSearchParams({ q: S.query, favoriteOnly: '' });
    let list = await api(`/prompts?q=${encodeURIComponent(S.query)}`);
    if (S.favoriteOnly) list = list.filter(p => p.favorite);
    S.prompts = list;
    const cats = await api('/categories');
    const counts = {}; list.forEach(p => counts[p.category] = (counts[p.category] || 0) + 1);
    $('#catChips').innerHTML =
      `<button class="chip ${!S.category ? 'active' : ''}" onclick="setCat('')">全部<span class="cnt">${list.length}</span></button>` +
      cats.map(c => `<button class="chip ${S.category === c ? 'active' : ''}" onclick="setCat('${esc(c)}')">${esc(c)}<span class="cnt">${counts[c] || 0}</span></button>`).join('');
    renderCards();
  } catch (e) { toast(e.message, 'err'); }
}

function setCat(c) { S.category = c; renderCards(); loadLibrary(); }

function renderCards() {
  const list = S.category ? S.prompts.filter(p => p.category === S.category) : S.prompts;
  const box = $('#cards');
  if (!list.length) {
    box.innerHTML = `<div class="empty" style="grid-column:1/-1">
      <div style="font-size:32px;opacity:.5">🗂</div>
      <h3>没有找到提示词</h3><p>换个关键词，或创建一条新的。</p>
      <button class="btn primary" style="margin-top:14px" onclick="openEditor()">${svg('plus')}新建提示词</button></div>`;
    return;
  }
  box.innerHTML = list.map(p => `
    <article class="pcard" onclick="openEditor('${p.id}')">
      <div class="pc-top">
        <div class="pc-title">${esc(p.title)}</div>
        <span class="star ${p.favorite ? 'on' : ''}" title="收藏" onclick="event.stopPropagation();toggleStar('${p.id}')">${svg('star')}</span>
      </div>
      <div class="pc-desc">${esc(p.description || '—')}</div>
      <pre>${esc(p.body.replace(/[#*`>]/g, '').replace(/\n{2,}/g, '\n').slice(0, 170))}</pre>
      <div class="pc-foot">
        <span class="tag brand">${esc(p.category)}</span>
        ${p.variables.length ? `<span class="tag">${p.variables.length} 变量</span>` : ''}
        <span class="tag">v${p.version}</span>
        ${p.model_hint && p.model_hint !== 'any' ? `<span class="tag mint">${esc(p.model_hint)}</span>` : ''}
        <span class="grow"></span>
        <span class="mono muted" style="font-size:10.5px">${fmtTime(p.updated_at)}</span>
      </div>
    </article>`).join('');
}

async function toggleStar(id) {
  try { await api(`/prompts/${id}/favorite`, { method: 'POST' }); await loadLibrary(); } catch (e) { toast(e.message, 'err'); }
}

/* ============================== editor ============================== */
function openEditor(id) {
  S.editing = id ? S.prompts.find(p => p.id === id) : null;
  if (id && !S.editing) { api('/prompts/' + id).then(p => { S.editing = p; renderEditor(); }); return; }
  renderEditor();
}

async function renderEditor() {
  const p = S.editing;
  const isNew = !p;
  $('#editorTitle').textContent = isNew ? '新建提示词' : '编辑提示词';
  $('#editorSub').textContent = isNew ? '支持 {{变量}} 占位符' : `v${p.version} · 更新于 ${fmtTime(p.updated_at)}`;
  $('#fId').value = p?.id || '';
  $('#fTitle').value = p?.title || '';
  $('#fCategory').value = p?.category || 'general';
  $('#fDesc').value = p?.description || '';
  $('#fModel').value = p?.model_hint || '';
  $('#fBody').value = p?.body || '';
  $('#editorDelete').classList.toggle('hidden', isNew);
  $('#btnVersions').classList.toggle('hidden', isNew);
  $('#btnCompare').classList.toggle('hidden', isNew);
  $('#outputBox').innerHTML = '<span class="muted">点击「运行」查看模型输出</span>';
  $('#runMeta').innerHTML = '';
  switchTab('editor');
  updateVarFields();
  if (!isNew) loadVersions(p.id);
  showScrim('editorScrim');
  setTimeout(() => $('#fTitle').focus(), 60);
}

function updateVarFields() {
  const body = $('#fBody').value;
  const vars = [...new Set([...body.matchAll(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g)].map(m => m[1]))];
  $('#varCount').textContent = vars.length ? `${vars.length} 个变量` : '暂无变量';
  $('#varFields').innerHTML = vars.length ? vars.map(v => `
    <div class="field" style="margin-bottom:9px">
      <label><span class="var-token">&#123;&#123;${esc(v)}&#125;&#125;</span></label>
      <input data-var="${esc(v)}" placeholder="填入 ${esc(v)}…">
    </div>`).join('') : '<div class="muted" style="font-size:12px">在正文中使用 <code class="mono">{{name}}</code> 声明变量</div>';
}

function switchTab(t) {
  $$('.tab', $('#editorTabs')).forEach(x => x.classList.toggle('active', x.dataset.tab === t));
  $$('.tab-pane', $('#editorBody')).forEach(x => x.classList.toggle('hidden', x.id !== 'tab-' + t));
  if (t === 'versions' && S.editing) loadVersions(S.editing.id);
}

async function loadVersions(pid) {
  try {
    const vs = await api(`/prompts/${pid}/versions`);
    $('#verList').innerHTML = vs.map((v, i) => `
      <div class="ver-row">
        <span class="ver-badge">v${v.version}</span>
        <span class="ver-note">${esc(v.note || '—')}</span>
        <span class="ver-time">${fmtTime(v.created_at)}</span>
        <button class="btn sm ghost" onclick="viewDiff('${pid}',${v.version})">diff</button>
        ${i === 0 ? '<span class="tag mint">当前</span>' : `<button class="btn sm" onclick="restoreVer('${pid}',${v.version})">恢复</button>`}
      </div>`).join('');
  } catch { }
}

async function viewDiff(pid, ver) {
  try {
    const r = await api(`/prompts/${pid}/versions/${ver}/diff`);
    const html = esc(r.diff || '（无差异）').split('\n').map(l =>
      l.startsWith('+++') || l.startsWith('---') ? `<span class="hunk">${l}</span>` :
        l.startsWith('+') ? `<span class="add">${l}</span>` :
          l.startsWith('-') ? `<span class="del">${l}</span>` : `<span class="ctx">${l}</span>`).join('');
    $('#diffBox').innerHTML = `<div class="diff-view">${html}</div>`;
    $('#diffModal').classList.add('show');
  } catch (e) { toast(e.message, 'err'); }
}

async function restoreVer(pid, ver) {
  if (!confirm(`恢复到 v${ver}？将生成一个新版本。`)) return;
  try {
    const p = await api(`/prompts/${pid}/versions/${ver}/restore`, { method: 'POST' });
    S.editing = p; await renderEditor(); await loadLibrary();
    toast(`已恢复到 v${ver}`);
  } catch (e) { toast(e.message, 'err'); }
}

async function savePrompt() {
  const body = {
    title: $('#fTitle').value.trim(),
    body: $('#fBody').value.trim(),
    category: $('#fCategory').value.trim() || 'general',
    description: $('#fDesc').value.trim(),
    model_hint: $('#fModel').value.trim()
  };
  if (!body.title || !body.body) return toast('标题和正文不能为空', 'err');
  try {
    if (S.editing) {
      const p = await api('/prompts/' + S.editing.id, { method: 'PATCH', body: JSON.stringify(body) });
      S.editing = p; toast(p.version > (S.editing.version || 1) ? `已保存，新版本 v${p.version}` : '已保存');
    } else {
      const p = await api('/prompts', { method: 'POST', body: JSON.stringify(body) });
      S.editing = p; toast('创建成功');
    }
    $('#editorSub').textContent = `v${S.editing.version} · 刚刚保存`;
    hideScrim('editorScrim');
    await loadLibrary();
  } catch (e) { toast(e.message, 'err'); }
}

async function deletePrompt() {
  if (!S.editing || !confirm('删除该提示词？其全部版本与运行记录都会一并删除。')) return;
  try { await api('/prompts/' + S.editing.id, { method: 'DELETE' }); toast('已删除'); hideScrim('editorScrim'); await loadLibrary(); }
  catch (e) { toast(e.message, 'err'); }
}

/* ============================== playground ============================== */
async function openPlayground(pid) {
  let p = S.prompts.find(x => x.id === pid);
  if (!p) p = await api('/prompts/' + pid);
  S.editing = p;
  $('#pgTitle').textContent = p.title;
  $('#pgPrompt').value = p.body;
  $('#pgOut').innerHTML = '<span class="muted">选择变量后点击「流式运行」</span>';
  updatePgVars();
  showScrim('pgScrim');
}

function updatePgVars() {
  const body = $('#pgPrompt').value;
  const vars = [...new Set([...body.matchAll(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g)].map(m => m[1]))];
  $('#pgVars').innerHTML = vars.length ? vars.map(v => `
    <div class="field" style="margin-bottom:9px">
      <label><span class="var-token">&#123;&#123;${esc(v)}&#125;&#125;</span></label>
      <textarea data-pgvar="${esc(v)}" rows="2" placeholder="${esc(v)}…" style="min-height:52px"></textarea>
    </div>`).join('') : '<div class="muted" style="font-size:12px">该提示词没有变量</div>';
}

async function runStream() {
  if (!S.editing) return;
  const vars = {};
  $$('[data-pgvar]').forEach(i => { if (i.value.trim()) vars[i.dataset.pgvar] = i.value; });
  $('#pgOut').innerHTML = '';
  const meta = $('#pgMeta'); meta.innerHTML = '<span class="muted">连接中…</span>';
  const t0 = performance.now();
  let acc = '';
  try {
    const res = await fetch(`/api/prompts/${S.editing.id}/stream`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ variables: vars, prompt_body: $('#pgPrompt').value })
    });
    if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.detail || res.statusText); }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split('\n\n'); buf = parts.pop();
      for (const part of parts) {
        const line = part.split('\n').find(l => l.startsWith('data: '));
        if (!line) continue;
        const ev = JSON.parse(line.slice(6));
        if (ev.event === 'delta') { acc += ev.text; $('#pgOut').innerHTML = md(acc); }
        if (ev.event === 'error') throw new Error(ev.message);
      }
    }
    const ms = Math.round(performance.now() - t0);
    meta.innerHTML = `<span class="muted">耗时 <b>${ms}ms</b> · 输出 <b>${acc.length}</b> 字符</span>`;
  } catch (e) {
    $('#pgOut').innerHTML = `<div style="color:var(--rose)">${esc(e.message)}</div>`;
    meta.innerHTML = '';
  }
}

async function runOnce() {
  if (!S.editing) return;
  const vars = {};
  $$('[data-var]').forEach(i => { if (i.value.trim()) vars[i.dataset.var] = i.value; });
  const btn = $('#btnRun'); btn.disabled = true;
  $('#outputBox').innerHTML = '<span class="muted">生成中…</span>';
  try {
    const r = await api(`/prompts/${S.editing.id}/run`, {
      method: 'POST',
      body: JSON.stringify({ variables: vars, prompt_body: $('#fBody').value, call_llm: true })
    });
    $('#outputBox').innerHTML = md(r.output || r.rendered);
    $('#runMeta').innerHTML = `<span>模型 <b>${esc(r.model || '—')}</b></span><span>耗时 <b>${r.latency_ms || 0}ms</b></span><span>tokens <b>${(r.tokens_in || 0)}+${(r.tokens_out || 0)}</b></span>${r.mocked ? '<span class="tag amber">演示模式</span>' : ''}`;
    switchTab('output');
    if (r.id) {
      $('#scoreRow').classList.remove('hidden');
      $('#scoreRow').dataset.runId = r.id;
    }
  } catch (e) {
    $('#outputBox').innerHTML = `<div style="color:var(--rose)">${esc(e.message)}</div>`;
    toast(e.message, 'err');
  } finally { btn.disabled = false; }
}

async function scoreRun(n) {
  const rid = $('#scoreRow').dataset.runId;
  if (!rid) return;
  try {
    await api(`/runs/${rid}/score`, { method: 'POST', body: JSON.stringify({ score: n }) });
    $('#scoreRow').innerHTML = `<span class="muted" style="font-size:12px">已评分 ${'★'.repeat(n)}</span>`;
    toast('评分已记录');
  } catch (e) { toast(e.message, 'err'); }
}

/* ============================== compare ============================== */
function openCompare() {
  if (!S.editing) return;
  $('#cmpA').value = $('#fBody').value;
  $('#cmpB').value = $('#fBody').value;
  $('#cmpResult').innerHTML = '';
  updateCmpVars();
  $('#cmpScrim').classList.add('show');
}
function updateCmpVars() {
  const body = $('#cmpA').value;
  const vars = [...new Set([...body.matchAll(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g)].map(m => m[1]))];
  $('#cmpVars').innerHTML = vars.length ? `<div class="row" style="flex-wrap:wrap;gap:8px">` + vars.map(v =>
    `<div class="field" style="gap:4px"><label><span class="var-token">&#123;&#123;${esc(v)}&#125;&#125;</span></label>
     <input data-cmpvar="${esc(v)}" placeholder="${esc(v)}" style="width:150px;height:31px;font-size:12px"></div>`).join('') + '</div>'
    : '<span class="muted" style="font-size:12px">无变量</span>';
}
async function runCompare() {
  if (!S.editing) return;
  const vars = {};
  $$('[data-cmpvar]').forEach(i => { if (i.value.trim()) vars[i.dataset.cmpvar] = i.value; });
  $('#cmpResult').innerHTML = '<div class="muted" style="padding:20px;text-align:center">并行调用中…</div>';
  try {
    const r = await api(`/prompts/${S.editing.id}/compare`, {
      method: 'POST', body: JSON.stringify({ variables: vars, body_a: $('#cmpA').value, body_b: $('#cmpB').value })
    });
    $('#cmpResult').innerHTML = `<div class="cmp-grid">` + r.results.map(x => `
      <div class="cmp-col ${x.variant.toLowerCase()}">
        <div class="cmp-h"><span class="letter">${x.variant}</span>
          <span class="muted" style="font-size:11.5px">${x.latency_ms ? x.latency_ms + 'ms · ' + x.tokens_out + ' tokens' : ''}</span></div>
        <div class="output-box md" style="min-height:160px;max-height:300px">${x.error ? `<span style="color:var(--rose)">${esc(x.error)}</span>` : md(x.output)}</div>
      </div>`).join('') + `</div>`;
  } catch (e) { $('#cmpResult').innerHTML = `<div style="color:var(--rose)">${esc(e.message)}</div>`; }
}

/* ============================== insights ============================== */
async function loadInsights() {
  try {
    const a = await api('/analytics');
    renderTrend('#insTrend', a.trend);
    renderTopPrompts('#insTop', a.top_prompts);
    renderCatBars('#insCats', a.by_category);
    $('#insAvgScore').textContent = a.avg_score || '—';
    $('#insLatency').textContent = a.avg_latency_ms ? a.avg_latency_ms + ' ms' : '—';
    $('#insTokens').textContent = fmtNum(a.total_tokens);
    $('#insRuns').textContent = fmtNum(a.total_runs);
    const runs = await api('/runs?limit=12');
    $('#insRunsTable').innerHTML = runs.length ? runs.map(r => `
      <div class="ver-row">
        <span class="ver-badge">${r.variant || 'A'}</span>
        <span class="ver-note mono" style="font-size:11.5px">${esc((r.output || '(未调用)').slice(0, 50).replace(/\n/g, ' '))}</span>
        <span class="ver-time">${r.latency_ms ? r.latency_ms + 'ms' : '—'}</span>
        <span class="ver-time">${fmtTime(r.created_at)}</span>
      </div>`).join('') : '<div class="empty" style="padding:24px"><p>暂无运行记录</p></div>';
  } catch (e) { toast(e.message, 'err'); }
}

/* ============================== settings ============================== */
async function checkHealth() {
  try {
    const h = await api('/health');
    S.llmReady = h.llm_ready;
    $('#llmDot').className = 'dot ' + (h.llm_ready ? 'on' : 'off');
    $('#llmText').textContent = h.llm_ready ? (h.provider || '已连接') : '演示模式';
    return h;
  } catch { return {}; }
}

async function loadSettings() {
  try {
    S.providers = await api('/providers');
    $('#provList').innerHTML = S.providers.map(p => `
      <div class="prov-row ${p.is_active ? 'active' : ''}">
        <div class="p-main">
          <div class="p-name">${esc(p.name)} ${p.is_active ? '<span class="tag mint">使用中</span>' : ''} ${p.has_key ? '' : '<span class="tag amber">无 Key</span>'}</div>
          <div class="p-url">${esc(p.base_url)} · ${esc(p.model)}</div>
        </div>
        <button class="btn sm" onclick="pingProvider('${p.id}',this)">测速</button>
        <button class="btn sm" onclick="editProvider('${p.id}')">编辑</button>
        ${p.is_active ? '' : `<button class="btn sm primary" onclick="activateProvider('${p.id}')">启用</button>`}
        <button class="btn sm ghost" onclick="deleteProvider('${p.id}')">${svg('trash')}</button>
      </div>`).join('') || '<div class="empty" style="padding:24px"><p>还没有配置模型服务</p></div>';
    await checkHealth();
  } catch (e) { toast(e.message, 'err'); }
}

function editProvider(id) {
  const p = S.providers.find(x => x.id === id) || {};
  $('#pvId').value = p.id || '';
  $('#pvName').value = p.name || '';
  $('#pvUrl').value = p.base_url || 'https://api.openai.com/v1';
  $('#pvModel').value = p.model || '';
  $('#pvKey').value = '';
  $('#pvKey').placeholder = p.has_key ? '已保存，留空则不修改' : 'sk-...';
  $('#pvTemp').value = p.temperature ?? 0.7;
  $('#pvMax').value = p.max_tokens ?? 1024;
  $('#provForm').classList.remove('hidden');
  $('#provFormTitle').textContent = p.id ? '编辑 ' + p.name : '新增模型服务';
}

async function saveProvider() {
  const body = {
    name: $('#pvName').value.trim(),
    base_url: $('#pvUrl').value.trim(),
    model: $('#pvModel').value.trim(),
    temperature: parseFloat($('#pvTemp').value) || 0.7,
    max_tokens: parseInt($('#pvMax').value) || 1024
  };
  const id = $('#pvId').value;
  if (id) body.id = id;
  const key = $('#pvKey').value.trim();
  if (key) body.api_key = key;
  if (!body.name || !body.base_url || !body.model) return toast('名称、地址、模型都必填', 'err');
  try {
    await api('/providers', { method: 'POST', body: JSON.stringify(body) });
    toast('已保存'); $('#provForm').classList.add('hidden'); await loadSettings();
  } catch (e) { toast(e.message, 'err'); }
}

async function activateProvider(id) {
  try { await api(`/providers/${id}/activate`, { method: 'POST' }); await loadSettings(); toast('已切换'); }
  catch (e) { toast(e.message, 'err'); }
}
async function deleteProvider(id) {
  if (!confirm('删除该模型服务？')) return;
  try { await api(`/providers/${id}`, { method: 'DELETE' }); await loadSettings(); } catch (e) { toast(e.message, 'err'); }
}
async function pingProvider(id, btn) {
  btn.disabled = true; btn.textContent = '…';
  try {
    const r = await api(`/providers/${id}/ping`, { method: 'POST' });
    toast(r.mocked ? '演示模式（未配置 Key）' : `连通 ✓ ${r.latency_ms}ms`, r.mocked ? 'info' : 'ok');
  } catch (e) { toast(e.message, 'err'); }
  finally { btn.disabled = false; btn.textContent = '测速'; }
}

/* ============================== keys ============================== */
async function loadKeys() {
  try {
    const keys = await api('/api-keys');
    $('#keyList').innerHTML = keys.length ? keys.map(k => `
      <div class="ver-row">
        <code class="mono" style="font-size:11.5px;color:#a8baff;background:rgba(109,139,255,.1);padding:2px 7px;border-radius:5px">${esc(k.key)}</code>
        <span class="ver-note">${esc(k.label || '未命名')}</span>
        <span class="ver-time">${k.last_used ? '上次 ' + fmtTime(k.last_used) : '从未使用'}</span>
        <button class="btn sm ghost" onclick="copyText('${esc(k.key)}')">${svg('copy')}</button>
        <button class="btn sm ghost" onclick="delKey('${esc(k.key)}')">${svg('trash')}</button>
      </div>`).join('') : '<div class="empty" style="padding:24px"><p>还没有密钥</p></div>';
  } catch (e) { toast(e.message, 'err'); }
}
async function createKey() {
  const label = prompt('密钥备注：', 'automation');
  if (label === null) return;
  try { await api('/api-keys', { method: 'POST', body: JSON.stringify({ label }) }); await loadKeys(); toast('已生成'); }
  catch (e) { toast(e.message, 'err'); }
}
async function delKey(k) {
  if (!confirm('删除该密钥？')) return;
  try { await api('/api-keys/' + k, { method: 'DELETE' }); await loadKeys(); } catch (e) { toast(e.message, 'err'); }
}

function copyText(t) { navigator.clipboard?.writeText(t).then(() => toast('已复制')); }

/* ============================== io ============================== */
function exportData() { location.href = '/api/export'; }
async function importData() {
  $('#importFile').click();
}
async function onImportFile(e) {
  const f = e.target.files[0]; if (!f) return;
  try {
    const text = await f.text();
    const data = JSON.parse(text);
    const prompts = Array.isArray(data) ? data : data.prompts || [];
    const r = await api('/import', { method: 'POST', body: JSON.stringify({ prompts }) });
    toast(`导入 ${r.imported} 条`); await loadLibrary();
  } catch (err) { toast('导入失败：' + err.message, 'err'); }
  e.target.value = '';
}

/* ============================== scrim ============================== */
function showScrim(id) { $('#' + id).classList.add('show'); }
function hideScrim(id) { $('#' + id).classList.remove('show'); }
document.addEventListener('click', e => {
  if (e.target.classList.contains('scrim')) e.target.classList.remove('show');
});

/* ============================== keyboard ============================== */
document.addEventListener('keydown', e => {
  const inField = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
  if (e.key === 'Escape') { $$('.scrim.show').forEach(s => s.classList.remove('show')); return; }
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); go('library'); $('#libSearch').focus(); return; }
  if ((e.metaKey || e.ctrlKey) && e.key === 'n') { e.preventDefault(); openEditor(); return; }
  if ((e.metaKey || e.ctrlKey) && e.key === 's' && $('#editorScrim').classList.contains('show')) {
    e.preventDefault(); savePrompt(); return;
  }
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && $('#editorScrim').classList.contains('show')) {
    e.preventDefault(); runOnce(); return;
  }
  if (!inField && /^[1-5]$/.test(e.key)) go(PAGES[+e.key - 1]);
});

/* ============================== boot ============================== */
(async function boot() {
  const page = (location.hash || '#dashboard').slice(1);
  go(PAGES.includes(page) ? page : 'dashboard');
  await checkHealth();
  window.addEventListener('hashchange', () => {
    const p = (location.hash || '#dashboard').slice(1);
    if (PAGES.includes(p) && p !== S.page) go(p);
  });
})();
