/* WealthOS 前端（零构建 vanilla JS）— v2：可视化晨报 + Roadmap + SVG 图表 */
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const LABEL_CN = { fact: "事实", expectation: "市场预期", analysis: "分析",
                   opinion: "观点", signal: "信号", infer: "AI 推断" };
const PALETTE = ["#1d5c4d", "#2563eb", "#d97706", "#7c3aed", "#059669",
                 "#dc2626", "#0891b2", "#65a30d", "#be185d", "#475569"];
let STATUS = null;

async function api(path, opts) {
  const r = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts));
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error
    || (await r.json().catch(() => ({}))).detail || r.status);
  return r.json();
}
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
const fmt = (v) => v == null ? "" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
const pctCls = (p) => p > 0 ? "pos" : (p < 0 ? "neg" : "");

/* ── SVG 图表（手写，零依赖）──────────────────────── */
function donutSVG(items, size = 150) {
  const total = items.reduce((a, b) => a + (b.pct || 0), 0) || 1;
  let acc = 0, r = size / 2 - 6, cx = size / 2, cy = size / 2;
  const arcs = items.slice(0, 8).map((it, i) => {
    const frac = (it.pct || 0) / total;
    const a0 = acc * 2 * Math.PI - Math.PI / 2, a1 = (acc + frac) * 2 * Math.PI - Math.PI / 2;
    acc += frac;
    if (frac <= 0.002) return "";
    const large = frac > 0.5 ? 1 : 0;
    const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    return `<path d="M ${cx} ${cy} L ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)} Z"
      fill="${PALETTE[i % PALETTE.length]}" opacity="0.9"><title>${esc(it.key)}: ${it.pct}%</title></path>`;
  }).join("");
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img">${arcs}
    <circle cx="${cx}" cy="${cy}" r="${r * 0.58}" fill="var(--panel)"/></svg>`;
}

function legendHTML(items) {
  return `<div class="legend">${items.slice(0, 8).map((it, i) =>
    `<span><i style="background:${PALETTE[i % PALETTE.length]}"></i>${esc(it.key)} ${it.pct}%</span>`).join("")}</div>`;
}

function lineSVG(series, w = 460, h = 160) {
  if (!series || series.length < 2) return "";
  const vals = series.map(s => s.total ?? s.total_base);
  const min = Math.min(...vals) * 0.998, max = Math.max(...vals) * 1.002;
  const pad = 26;
  const x = (i) => pad + i * (w - pad * 2) / (series.length - 1);
  const y = (v) => h - pad - (v - min) / (max - min || 1) * (h - pad * 2);
  const pts = vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `M ${x(0)},${h - pad} L ${pts.replace(/ /g, " L ")} L ${x(series.length - 1)},${h - pad} Z`;
  const last = vals[vals.length - 1];
  return `<svg width="100%" viewBox="0 0 ${w} ${h}" role="img" class="linechart">
    <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1d5c4d" stop-opacity="0.25"/><stop offset="100%" stop-color="#1d5c4d" stop-opacity="0"/>
    </linearGradient></defs>
    <path d="${area}" fill="url(#g)"/>
    <polyline points="${pts}" fill="none" stroke="#1d5c4d" stroke-width="2.2" stroke-linejoin="round"/>
    ${vals.map((v, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="3" fill="#1d5c4d"><title>${series[i].as_of}: ${fmt(v)}</title></circle>`).join("")}
    <text x="${pad}" y="14" class="axis">${fmt(min)}</text>
    <text x="${w - pad}" y="14" text-anchor="end" class="axis">${fmt(max)}</text>
    <text x="${pad}" y="${h - 6}" class="axis">${series[0].as_of}</text>
    <text x="${w - pad}" y="${h - 6}" text-anchor="end" class="axis">${series[series.length - 1].as_of}</text>
  </svg>`;
}

/* ── 状态 / 横幅 / 引导 ────────────────────────────── */
function applyStatus(s) {
  STATUS = s;
  const zero = s.accounts === 0;
  $("#onboarding").style.display = zero ? "block" : "none";
  $("main").style.display = zero ? "none" : "block";
  $("#fab-run").style.display = zero ? "none" : "block";
  $("#fab-brief").style.display = zero ? "none" : "block";
  $("#demo-banner").style.display = (!zero && s.demo_mode) ? "block" : "none";
  $("#freshness").textContent = zero ? "" :
    `持仓 ${s.holdings_as_of || "—"} · 汇率 ${s.fx_as_of || "—"} · 新闻 ${s.items} 条`;
}
async function refreshStatus() {
  try { applyStatus(await api("/api/status")); } catch { $("#freshness").textContent = ""; }
}

$$("nav button[data-tab]").forEach((b) =>
  b.addEventListener("click", () => {
    $$("nav button").forEach((x) => x.classList.remove("active"));
    $$(".tab").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    $(`#tab-${b.dataset.tab}`).classList.add("active");
    loadTab(b.dataset.tab);
  }));

async function loadTab(tab) {
  try {
    if (tab === "today") await loadBrief();
    if (tab === "roadmap") await loadRoadmap();
    if (tab === "portfolio") await loadPortfolio();
    if (tab === "research") await loadResearch();
    if (tab === "feed") await loadFeed();
    if (tab === "learn") await loadLesson();
    if (tab === "setup") await loadSetup();
  } catch (e) { console.error(e); }
}

/* ── Research：研报手把手精读 ──────────────────────── */
async function loadResearch() {
  const r = await api("/api/research");
  $("#research-list").innerHTML = `
    <h2>📚 明星公司研报精读</h2>
    <p class="muted">每周一自动用 <b>SEC EDGAR 官方数据</b>更新观察名单研报。
    每篇 8 节，每节 = 真实数字（可溯源）+ 怎么读 + 知识点高亮；读完登记进你的知识图谱。</p>
    <div class="watch-grid">${(r.watchlist || []).map(c => `
      <div class="watch-card ${c.held ? "held" : ""}" data-symbol="${esc(c.symbol)}">
        <b>${esc(c.name)} <span class="muted">${esc(c.symbol)}</span>
          ${c.held ? '<span class="tag fact">已持有</span>' : ""}</b>
        <p class="muted">${esc(c.why)}</p>
      </div>`).join("")}</div>
    ${(r.briefs || []).length ? `<p class="tiny">最近精读：${r.briefs.map(b =>
      `${esc(b.name)}(${b.sections}节)`).join(" · ")}</p>` : ""}
    <button id="btn-run-research" class="ghost">⟳ 生成/更新全部研报（EDGAR 实时拉取）</button>`;
  $("#btn-run-research").addEventListener("click", async (e) => {
    e.target.textContent = "拉取中（约 20 秒）…";
    try {
      const res = await api("/api/run/research", { method: "POST" });
      e.target.textContent = `✓ 完成 ${res.done.length} 家` + (res.failed.length ? ` ⚠ ${res.failed.length} 失败` : "");
      loadResearch();
    } catch (err) { e.target.textContent = "失败: " + err.message; }
  });
  $$(".watch-card").forEach(card =>
    card.addEventListener("click", () => openResearch(card.dataset.symbol)));
}

async function openResearch(symbol) {
  let b;
  try { b = await api(`/api/research/${encodeURIComponent(symbol)}`); }
  catch (e) { alert("生成失败: " + e.message); return; }
  const secHTML = (b.sections || []).map((s, i) => `
    <details class="rs-section" ${i === 0 ? "open" : ""}>
      <summary><span class="rs-no">${i + 1}</span>${esc(s.title)}</summary>
      <div class="rs-body">
        ${s.data && s.data.length ? `<table class="rs-data">${s.data.map(d =>
          `<tr><td>${esc(d.label)}</td><td><b>${esc(d.value)}</b></td>
           <td class="src">${esc(d.source)}</td></tr>`).join("")}</table>` : ""}
        <div class="rs-teach">${esc(s.teach)}</div>
        ${s.highlight ? `<div class="rs-highlight">💡 ${esc(s.highlight)}</div>` : ""}
        ${s.concept ? `<span class="chip">知识点：${esc(s.concept)}</span>` : ""}
      </div>
    </details>`).join("");
  $("#research-reader").innerHTML = `
    <div class="card rs-head">
      <h2>${esc(b.name)} <span class="muted">${esc(b.symbol)}</span>
        ${b.held ? `<span class="tag fact">我持有 ${b.held_qty}</span>` : ""}</h2>
      <p class="muted">${esc(b.why_star)}</p>
      <div class="chip-row">
        <span class="chip">数据源：${esc(b.data_source)}</span>
        <span class="chip">生成于 ${esc(b.generated_at)}</span>
        <a class="chip" href="${esc(b.ir_url)}" target="_blank" rel="noopener">公司 IR ↗</a>
      </div>
    </div>
    ${secHTML}
    ${b.quiz ? `<div class="card rs-quiz"><b>🎯 毕业小测：${esc(b.quiz.q)}</b>
      ${b.quiz.options.map((o, i) => `<button class="quiz-opt" data-i="${i}"
        data-answer="${b.quiz.answer}" data-explain="${esc(b.quiz.explain)}">${esc(o)}</button>`).join("")}
    </div>` : ""}`;
  $("#research-reader").scrollIntoView({ behavior: "smooth" });
  $$(".quiz-opt").forEach(btn => btn.addEventListener("click", () => {
    const ok = btn.dataset.i === btn.dataset.answer;
    alert(`${ok ? "✓ 正确" : "✗ 再想想"}\n\n${btn.dataset.explain}`);
  }));
}

/* ── Onboarding ────────────────────────────────────── */
$("#ob-cash button").addEventListener("click", () => openAccountDialog());
$("#ob-demo button").addEventListener("click", async (e) => {
  e.target.disabled = true; e.target.textContent = "载入中…（含真实行情与新闻，约 1 分钟）";
  try {
    await api("/api/demo/load", { method: "POST" });
    await api("/api/run/fetch", { method: "POST" }).catch(() => {});
    await api("/api/run/brief", { method: "POST" }).catch(() => {});
  } catch (err) { alert("载入失败: " + err.message); }
  location.reload();
});
$("#ob-learn button").addEventListener("click", () => {
  $$("nav button").forEach((x) => x.classList.remove("active"));
  $$(".tab").forEach((x) => x.classList.remove("active"));
  document.querySelector('[data-tab="learn"]').classList.add("active");
  $("#tab-learn").classList.add("active");
  $("main").style.display = "block";
  $("#onboarding").style.display = "none";
  loadLesson();
});
$("#btn-demo-clear").addEventListener("click", async () => {
  if (!confirm("确认清除全部示例数据？（你的真实账户不受影响）")) return;
  await api("/api/demo/clear", { method: "POST" });
  await refreshStatus();
  loadTab("today");
});

/* ── Today：可视化晨报 ─────────────────────────────── */
async function loadBrief() {
  let b;
  try { b = await api("/api/brief/latest"); }
  catch (e) {
    $("#brief-visual").innerHTML = `<div class="card"><p class="muted">尚无简报（${esc(e.message)}）——点击右下角「✦ 生成简报」。</p></div>`;
    return;
  }
  $("#brief").textContent = b.content;
  const j = b.content_json, nw = j.net_worth || {};
  const delta = nw.delta;
  // by_asset_class 是 {类别: 金额}，转成图表需要的 [{key, pct}]
  const classEntries = Object.entries(nw.by_asset_class || {});
  const classTotal = classEntries.reduce((a, [k, v]) => a + v, 0) || 1;
  const donutItems = classEntries.map(([k, v]) => ({ key: k, value_base: v, pct: +(v / classTotal * 100).toFixed(1) }));

  const hero = nw.empty ? `<div class="hero-stats empty">暂无数据</div>` : `
    <div class="hero-stats">
      <div class="hs-main"><span class="hs-label">总净值 · ${esc(nw.base)}</span>
        <span class="hs-num">${fmt(nw.total)}</span>
        ${delta ? `<span class="hs-delta ${pctCls(delta.pct)}">${fmt(delta.abs)} (${delta.pct}%) vs ${delta.prev_as_of}</span>` : ""}
      </div>
      <div class="hs-donut">${donutSVG(donutItems)}${legendHTML(donutItems)}</div>
    </div>
    <div class="hs-meta">数据截至 ${esc(nw.as_of || "—")}${(nw.missing_fx || []).length ? ` · <span class="warn">缺汇率：${nw.missing_fx.map(m => esc(m.currency)).join("、")}</span>` : ""}</div>`;

  const news = (j.news || []).map((n, i) => `
    <div class="news-card">
      <div class="news-head">
        <span class="tag ${n.oneliner_label === "AI 推断" ? "infer" : (n.reliability === "Primary" || n.reliability === "High" ? "fact" : "opinion")}">
          ${esc(n.oneliner_label || (n.reliability === "Primary" || n.reliability === "High" ? "事实" : "观点"))}</span>
        ${n.relevance >= 0.05 ? `<span class="rel">与我相关 ${(n.relevance * 100).toFixed(0)}%</span>` : ""}
      </div>
      <div class="news-title"><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.oneliner || n.title)}</a></div>
      <div class="news-meta">${esc(n.src_name)} · ${esc(n.reliability)} · ${(n.published_at || "").slice(0, 10)}</div>
    </div>`).join("") || `<p class="muted">暂无新闻——「⟳ 拉数据」。</p>`;

  const mine = j.personal_story ? `
    <div class="story-card">
      <div class="tag analysis">分析</div>
      <h3>${esc(j.personal_story.title)}</h3>
      <div class="path-chips">${(j.personal_story.path || "").split(" → ").map(p =>
        `<span class="chip">${esc(p.replace(/^\w+:/, ""))}</span>`).join('<span class="arrow">→</span>')}</div>
      <div class="story-grid">
        <div><b>你的敞口</b><br>${esc(j.personal_story.exposure_dim)} ≈ ${esc(j.personal_story.exposure_pct)} <span class="src">[计算]</span></div>
        <div><b>为什么重要</b><br>${esc((j.personal_story.why_it_matters || "").slice(0, 160))}</div>
      </div>
      <div class="news-meta">证据：${esc(j.personal_story.source)}（${esc(j.personal_story.reliability)}）· 未确定部分：影响取决于事件细节，以上是传导框架而非预测</div>
    </div>` : `<p class="muted">今日没有相关性达标的事件——你的组合今天不忙。</p>`;

  const opps = (j.opportunities || []).map(c => `
    <div class="opp-card">
      <div class="tag analysis">分析</div>
      <b>${esc(c.title)}</b>
      <p class="muted">${esc(c.why)}</p>
      <div class="chip-row">${(c.options || []).map(o => `<span class="chip">${esc(o)}</span>`).join("")}</div>
      <p class="tiny">${esc(c.note)}</p>
    </div>`).join("") || `<p class="muted">当前敞口未触发任何研究提示。</p>`;

  const ls = j.lesson ? `
    <div class="lesson-mini">
      <h3>📖 ${esc(j.lesson.title)} · 约 3 分钟</h3>
      <p>${esc((j.lesson.body || "").slice(0, 120))}…</p>
      <p class="rel-note">${esc(j.lesson.relation || "")}</p>
      <button class="ghost" id="go-learn">去答题 →</button>
    </div>` : "";

  $("#brief-visual").innerHTML = `
    <div class="card hero-card">
      <div class="hero-date">GOOD MORNING · ${esc(j.date)}</div>
      ${hero}
    </div>
    <h3 class="sec">今天值得你知道的事</h3><div class="news-grid">${news}</div>
    <h3 class="sec">🎯 与你有关的一件事</h3>${mine}
    <h3 class="sec">💡 值得研究的机会</h3><div class="opp-grid">${opps}</div>
    ${ls ? `<h3 class="sec">今日金融课</h3>` : ""}${ls}
    <p class="tiny center">${j.llm_enhanced ? "AI 增强已开启" : "确定性模式：所有数字来自本地计算，可点开原始文本核对"} · 免责：信息整理与研究辅助，不构成投资建议。</p>`;
  const go = $("#go-learn");
  if (go) go.addEventListener("click", () =>
    document.querySelector('[data-tab="learn"]').click());
}

/* ── Roadmap ───────────────────────────────────────── */
async function loadRoadmap() {
  const rm = await api("/api/roadmap");
  const ctx = rm.context || {};
  $("#roadmap-intro").innerHTML = `
    <h2>🗺️ 从 0 开始的财富路线图</h2>
    <p class="muted">每一步都告诉你<b>做什么、为什么、依据是什么</b>。带 ✓ 的步骤会随你的真实数据自动判定；
    其余可以手动勾选完成。<b>这不是投资建议</b>——是把通行的理财实践翻译成小白能执行的动作清单。</p>
    <div class="ctx-chips">
      <span class="chip">真实账户 ${ctx.real_accounts} 个</span>
      <span class="chip">已记录现金 ${fmt(ctx.cash_total_base)} ${esc(ctx.base || "")}</span>
      <span class="chip">已学课程 ${ctx.lessons_learned} 节</span>
    </div>`;

  $("#roadmap-list").innerHTML = rm.stages.map((st, idx) => {
    const cls = st.done ? "done" : "";
    const check = st.auto_done ? '<span class="st-auto">✓ 自动</span>'
      : `<label class="st-check"><input type="checkbox" ${st.manual_done ? "checked" : ""}
           data-stage="${st.id}"> 我完成了这步</label>`;
    const cards = (st.cards || []).map(c => {
      const rows = [
        ["为什么", c.why], ["怎么做 / 选项", c.how], ["前提", c.prereq], ["成本", c.cost],
        ["风险", c.risk], ["适合", c.fits], "not_fits" in c ? ["不适合", c.not_fits] : null,
        "alternatives" in c ? ["替代方案", c.alternatives] : null, ["📌 依据", c.evidence],
      ].filter(r => r && r[1]);
      return `<details class="rm-card"><summary>${esc(c.title)}</summary>
        ${rows.map(([k, v]) => `<div class="rm-row"><b>${k}</b><div>${esc(v)}</div></div>`).join("")}
      </details>`;
    }).join("");
    return `<div class="rm-stage ${cls}">
      <div class="rm-head">
        <span class="rm-dot">${st.done ? "✓" : idx + 1}</span>
        <div><b>${esc(st.title)}</b><p class="muted">${esc(st.goal)}</p>
          ${st.prereq_note ? `<p class="prereq">${esc(st.prereq_note)}</p>` : ""}</div>
        <span class="rm-status">${st.done ? "已完成" : "进行中"}</span>${check}
      </div>
      ${cards}</div>`;
  }).join("");
  $$(".st-check input").forEach(cb =>
    cb.addEventListener("change", async () => {
      await api("/api/roadmap/toggle", { method: "POST",
        body: JSON.stringify({ stage_id: cb.dataset.stage }) });
      loadRoadmap();
    }));
}

/* ── Portfolio ─────────────────────────────────────── */
function bars(rows) {
  const max = Math.max(...rows.map((r) => r.pct || 0), 1);
  return rows.slice(0, 8).map((r, i) => `
    <div class="bar-row"><span class="k">${esc(r.key)}</span>
      <span class="track"><span class="fill" style="width:${((r.pct || 0) / max) * 100}%;background:${PALETTE[i % PALETTE.length]}"></span></span>
      <span class="v">${r.pct}% · ${fmt(r.value_base)}</span></div>`).join("");
}

async function loadPortfolio() {
  const p = await api("/api/portfolio");
  const nw = p.net_worth;
  $("#nw").innerHTML = nw.empty
    ? "<h3>Net Worth</h3><p class='muted'>还没有任何资产记录——点下方「＋ 记录资产/持仓」写下第一笔。</p>"
    : `<h3>Net Worth（${esc(nw.base)}）</h3>
       <div class="big-num">${fmt(nw.total)}</div>
       ${nw.delta ? `<div class="hs-delta ${pctCls(nw.delta.pct)}">${fmt(nw.delta.abs)} (${nw.delta.pct}%) vs ${nw.delta.prev_as_of}</div>` : ""}
       ${(nw.missing_fx || []).length ? `<div class="warn">⚠ 缺汇率: ${nw.missing_fx.map((m) => esc(m.currency)).join("、")}</div>` : ""}`;
  $("#nw-chart").innerHTML = (nw.series && nw.series.length >= 2)
    ? `<h3>净值走势</h3>${lineSVG(nw.series)}` : "";
  const e = p.exposures;
  $("#exposures").innerHTML = (e && !e.empty)
    ? [["currency", "币种"], ["country", "国家/地区"], ["asset_class", "资产类别"],
       ["sector", "行业"], ["institution", "机构"]]
      .map(([k, t]) => `<div class="card"><h3>${t}</h3>${bars(e[k] || [])}</div>`).join("")
    : "";
  $("#accounts").innerHTML = `<h3>Accounts</h3><table><tr><th>账户</th><th>机构</th><th>币种</th><th>市值</th></tr>${
    (p.accounts || []).map((a) => `<tr class="${a.is_demo ? "demo-row" : ""}">
      <td>${esc(a.name)}${a.is_demo ? ' <span class="tag opinion">示例</span>' : ""}</td>
      <td>${esc(a.institution)}</td><td>${a.currency}</td>
      <td>${fmt(a.market_value)} ${a.market_value != null ? a.currency : ""}</td></tr>`).join("")}</table>`;
  fillAccountSelect(p.accounts || []);
}

function fillAccountSelect(accounts) {
  $("#hold-account-select").innerHTML = accounts
    .map((a) => `<option value="${esc(a.name)}">${esc(a.name)}（${a.currency}）</option>`).join("");
}

/* ── Feed ──────────────────────────────────────────── */
async function loadFeed() {
  const only = $("#only-relevant").checked ? 0.05 : 0;
  const f = await api(`/api/feed?limit=60&min_relevance=${only}`);
  $("#feed-list").innerHTML = f.items.length ? f.items.map((i) => `
    <div class="item">
      <div><span class="tag ${i.label}">${LABEL_CN[i.label] || i.label}</span>
        ${i.relevance >= 0.05 ? `<span class="rel">与我相关 ${(i.relevance * 100).toFixed(0)}%</span>` : ""}
      </div>
      <div style="margin:8px 0"><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a></div>
      ${i.summary ? `<div class="muted" style="font-size:13px">${esc(i.summary.slice(0, 180))}…</div>` : ""}
      <div class="meta"><span>${esc(i.src_name)}</span><span>${i.reliability}</span>
        <span>${(i.published_at || "").slice(0, 10)}</span>
        ${(i.entities || []).slice(0, 4).map((x) => `<span class="tag analysis">${esc(x.split(":").slice(-1)[0])}</span>`).join("")}</div>
    </div>`).join("") : "<p class='muted'>暂无新闻——点击右下角「⟳ 拉数据」。</p>";
}
$("#only-relevant").addEventListener("change", () => loadFeed());

/* ── Learn ─────────────────────────────────────────── */
const DOMAIN_CN = { basics: "基础", instruments: "工具", portfolio: "组合",
  fixed_income: "债券", macro: "宏观·汇率", legal_tax: "合规与税务",
  micro_economics: "微观经济", macro_economics: "宏观经济", research: "研报概念" };

async function loadLesson() {
  const l = await api("/api/lessons/today");
  const prog = await api("/api/lessons/progress").catch(() => null);
  if (l.done) { $("#lesson").innerHTML = "<h2>课程库已学完一轮 🎉</h2><p class='muted'>复习队列与月度测验即将上线。</p>"; return; }
  const hard = l.quiz_level === "hard";
  $("#lesson").innerHTML = `
    <h2>📖 ${esc(l.title)} ${hard ? '<span class="lvl-badge hard">⭐ 进阶</span>' : '<span class="lvl-badge">简单</span>'}</h2>
    <p class="tiny">${esc(DOMAIN_CN[l.domain] || l.domain || "")} · 当前掌握度将随答题累积（0.8 即掌握）</p>
    <p style="white-space:pre-wrap">${esc(l.body)}</p>
    <div class="rel-note"><b>和我的资产的关系：</b>${esc(l.relation)}</div>
    ${l.quiz ? `<div class="quiz"><b>${hard ? "⭐ 场景应用题" : "小问题"}：${esc(l.quiz.q)}</b>${
      l.quiz.options.map((o, idx) => `<button data-correct="${idx === l.quiz.answer}" data-concept="${esc(l.concept)}" data-level="${l.quiz_level}">${esc(o)}</button>`).join("")
    }</div>` : ""}`;
  $$(".quiz button").forEach((b) =>
    b.addEventListener("click", async () => {
      const correct = b.dataset.correct === "true";
      const r = await api("/api/lessons/answer", {
        method: "POST", body: JSON.stringify({ concept: b.dataset.concept, correct,
                                               level: b.dataset.level }) });
      alert(`${correct ? "✓ 正确" : "✗ 再想想"} · 掌握度 ${Math.round(r.mastery * 100)}%`
            + (r.known ? " 🎉 已掌握！进入复习队列" : `（${correct ? "继续强化" : "稳住"}，答到 80% 即掌握）`));
      loadLesson();
    }));
  renderProgress(prog);
}

function renderProgress(prog) {
  const box = $("#progress-card");
  if (!prog || !box) return;
  const doms = {};
  prog.nodes.forEach(n => (doms[n.domain] = doms[n.domain] || []).push(n));
  box.innerHTML = `
    <h3>🧠 知识图谱进度 · 已掌握 ${prog.known}/${prog.total} · 平均 ${Math.round(prog.avg_mastery * 100)}%</h3>
    ${Object.entries(doms).map(([d, nodes]) => `
      <div class="prog-domain"><b>${esc(DOMAIN_CN[d] || d)}</b>
        ${nodes.map(n => `
          <div class="prog-row ${n.status}">
            <span class="prog-k">${esc(n.concept)}</span>
            <span class="prog-track"><span class="prog-fill ${n.status}"
              style="width:${Math.round((n.mastery_score || 0) * 100)}%"></span></span>
            <span class="prog-v">${n.status === "known" ? "✅" : n.status === "weak" ? "薄弱" : Math.round((n.mastery_score || 0) * 100) + "%"}</span>
          </div>`).join("")}
      </div>`).join("")}`;
}

/* ── Setup：接口打通中心（保姆级）─────────────────── */
const ENV_PATH = "~/.wealthos/env";

const KEY_GUIDES = [
  {
    id: "llm", icon: "🧠", title: "LLM 大脑（AI 模式）",
    benefit: "晨报新闻变成人话摘要、对话升级为深度分析。不配也完全可用（确定性模式）。",
    cost: "方案 A 免费（本机跑，慢一点）· 方案 B/C 按量计费（日常一个月约 ¥5–30）",
    paths: [
      {
        name: "方案 A · Ollama 本地（免费·零门槛·数据不出电脑·国内直连）",
        steps: [
          "打开 https://ollama.com 点「Download」下载 macOS 版，双击安装（像装微信一样）。",
          "装好后打开「终端」App（聚焦搜索输入 terminal 回车），粘贴运行：<code>ollama pull qwen2.5:7b</code>（约 4.7GB，等进度条走完；电脑内存 8G 以下就改用 qwen2.5:3b）。",
          "把右边三行写进配置文件（见下方「怎么写配置文件」），模型名填 qwen2.5:7b。",
          "验证：回到 ZCode 说「重启 WealthOS」，然后点「✦ 生成简报」，末尾会显示「AI 增强已开启」。",
        ],
        env: ["WEALTHOS_LLM_PROVIDER=ollama", "WEALTHOS_LLM_MODEL=qwen2.5:7b"],
      },
      {
        name: "方案 B · 智谱 GLM（国内直连·人民币付款·兼容 OpenAI 协议·有免费模型）",
        steps: [
          "打开 https://open.bigmodel.cn 用手机号注册登录。",
          "点右上角「API Keys」→「新建 API Key」，复制那串 Key（只显示一次，先存好）。",
          "在「财务中心」充值（免费模型 glm-4-flash 不用充也能用；想更快可充 ¥10）。",
          "把右边四行写进配置文件，BASE_URL 必须原样照抄。",
        ],
        env: ["WEALTHOS_LLM_PROVIDER=openai",
              "WEALTHOS_LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4",
              "WEALTHOS_LLM_API_KEY=你的Key粘贴到这里",
              "WEALTHOS_LLM_MODEL=glm-4-flash"],
      },
      {
        name: "方案 C · OpenAI / Anthropic（效果上限高·需海外支付方式与网络环境）",
        steps: [
          "OpenAI：https://platform.openai.com 注册 → 左侧「API keys」→ Create new secret key 复制 sk-…（只显示一次）→ 「Billing」充 $5+。",
          "或 Anthropic：https://console.anthropic.com 注册 → API Keys → 充值 $5+。",
          "把对应几行写进配置文件（OpenAI 填前 3 行；Anthropic 把 PROVIDER 换成 anthropic、MODEL 换成 claude-sonnet-4-5）。",
          "注意：两家在国内通常需要自备网络环境与外币卡，不方便就用方案 A/B。",
        ],
        env: ["WEALTHOS_LLM_PROVIDER=openai",
              "WEALTHOS_LLM_API_KEY=sk-你的key",
              "WEALTHOS_LLM_MODEL=gpt-4o-mini"],
      },
    ],
  },
  {
    id: "telegram", icon: "📲", title: "Telegram 推送（晨报/研报送到手机）",
    benefit: "每天早上简报自动出现在手机上，不用主动打开网页。", cost: "免费",
    paths: [
      {
        name: "全程约 10 分钟",
        steps: [
          "手机安装 Telegram（App Store / Google Play，或桌面版 telegram.org）。⚠️ 在中国大陆需要自备可用的网络环境；不方便的话跳过此项，网页版功能完整。",
          "在 Telegram 顶部搜索框输入 <code>BotFather</code>（认准蓝色认证勾），点 START，发送：<code>/newbot</code>。",
          "它问你两个问题：① 机器人显示名（随便起，如 My WealthOS）；② 用户名（必须以 bot 结尾，如 my_wealthos_01_bot）。",
          "成功后 BotFather 回一条长消息，中间有一行类似 <code>7123456789:AAH9x…</code> ——点它复制，这就是 <b>Token</b>。谁都不许给（泄露了回 BotFather 发 /revoke 换新的）。",
          "现在去搜索你刚起的机器人用户名，点 START 并随便发一句「hi」——<b>必须先发一条</b>，否则它没权限给你发消息。",
          "获取 Chat ID：用浏览器打开这个网址（把「你的Token」替换成第 4 步那串）：<code>https://api.telegram.org/bot你的Token/getUpdates</code>，在满屏 JSON 里找 <code>\"chat\":{\"id\":数字</code>，那个<b>数字</b>就是你的 Chat ID（个人号是正数）。",
          "把右边两行写进配置文件，回到 ZCode 说「运行 wealthos doctor」——它会真发一条测试消息到你的 Telegram。",
        ],
        env: ["WEALTHOS_TELEGRAM_TOKEN=7123456789:AAH9x…粘贴这里",
              "WEALTHOS_TELEGRAM_CHAT_ID=你的ChatID数字"],
      },
    ],
  },
  {
    id: "fred", icon: "🏦", title: "FRED 利率数据（美联储官方）",
    benefit: "利率/国债收益率数据更稳更快。不配也有无 key 备源，属于锦上添花。", cost: "免费",
    paths: [
      {
        name: "全程约 3 分钟",
        steps: [
          "打开 https://fred.stlouisfed.org 点右上角「Register」，用一个邮箱注册（免费，秒过）。",
          "登录后点右上角你的用户名 → 「API Keys」——系统已经自动帮你生成了一个 32 位 Key。",
          "点「Copy」复制，把右边一行写进配置文件即可（重启后生效）。",
        ],
        env: ["WEALTHOS_FRED_KEY=32位key粘贴到这里"],
      },
    ],
  },
  {
    id: "xueqiu", icon: "🏮", title: "雪球行情（中文市场兜底 · 可选）",
    benefit: "A 股/港美股中文行情兜底 + 热门内容。不配则行情走 Yahoo/Stooq，无影响。",
    cost: "免费（需要你雪球账号的登录态授权）",
    paths: [
      {
        name: "全程约 5 分钟（合规路径：只用你自己的 Cookie）",
        steps: [
          "电脑 Chrome 打开 https://xueqiu.com 并登录你的账号（没有就手机号注册一个）。",
          "按 F12 打开开发者工具 → 顶部选「Network（网络）」→ 刷新页面 → 点列表里任意一个 xueqiu.com 请求。",
          "在右侧「Headers」里找到 <code>Cookie:</code> 一行，复制其中 <code>xq_a_token=…</code> 冒号后的值（只要这一段，到分号为止）。",
          "把右边一行写进配置文件（值就是刚复制的整段 xq_a_token=xxxx）。它只存本机、只用于读行情。",
          "验证：运行 <code>wealthos doctor</code>，雪球一栏变 ✅。",
        ],
        env: ["WEALTHOS_XUEQIU_COOKIE=xq_a_token=粘贴这里"],
      },
    ],
  },
  {
    id: "exa", icon: "🔎", title: "Exa 语义搜索（深度研究 · 可选）",
    benefit: "Chat 里问深度问题时自动联网搜索高质量来源（引用带原文段落）。",
    cost: "免费额度（注册即送，日常问答够用）",
    paths: [
      {
        name: "全程约 4 分钟",
        steps: [
          "打开 https://dashboard.exa.ai 用邮箱/Google 注册。",
          "左侧「API Keys」→ 复制 Key。",
          "把右边一行写进配置文件，重启后生效。",
        ],
        env: ["WEALTHOS_EXA_API_KEY=粘贴key"],
      },
    ],
  },
  {
    id: "broker", icon: "🏛️", title: "券商 API（持仓自动同步）",
    benefit: "以后你开户买了第一只股票，持仓可以自动同步，不再手动记录。", cost: "免费（需先开户）",
    paths: [
      {
        name: "等你走到 Roadmap 第 4 步再回来做",
        steps: [
          "长桥（最轻）：开户后打开 https://open.longbridge.com → 开发者中心完成认证 → 拿到 App Key/Secret/Access Token。",
          "IBKR（最全）：Client Portal → Performance & Reports → Flex Queries：新建一个包含 Positions/Balances 的查询拿 Query ID，再 Settings→Account Settings→Flex Report Access 生成 Token——天生只读、免网关，最适合自用。",
          "这两项的系统端对接已在架构里预留（调研报告 research-notes/F），到时候回 ZCode 说「接入长桥/IBKR」即可。",
        ],
        env: ["# （开户后再配，键名届时由接入代码指定）"],
      },
    ],
  },
  {
    id: "x", icon: "🐦", title: "X 情报信号（可选·付费）",
    benefit: "追踪金融 KOL 观点信号（只作为信号，永远要经过验证层才进简报）。", cost: "按量：约 $0.005/条，$5–30/月",
    paths: [
      {
        name: "开发中，接口已预留",
        steps: [
          "https://developer.x.com 注册开发者账号 → 绑卡（送 $20 额度，按用量付费无月费）。",
          "创建 Project & App → 拿 Bearer Token。",
          "本系统的 X 情报层按合规设计（List 轮询 + 24h 去重计费 + 消费熔断），代码尚未实装——配好 Key 后回 ZCode 说「启用 X 层」。",
        ],
        env: ["WEALTHOS_X_BEARER_TOKEN=你的token"],
      },
    ],
  },
];

async function loadSetup() {
  const st = await api("/api/config-status");
  $("#setup-intro").innerHTML = `
    <h2>⚙️ 接口打通中心（保姆级）</h2>
    <p class="muted">每配置一个，系统就长出一块新能力。<b>全部不配也完全可用</b>——先跑起来，按需点亮。
    当前状态实时检测：${badge(st.llm.configured, "LLM")} ${badge(st.telegram.configured, "Telegram")}
    ${badge(st.fred.configured, "FRED")} ${badge(st.x.configured, "X")}</p>
    <div class="card env-how">
      <b>📍 怎么写配置文件（所有 key 都写进同一个文件）</b>
      <p class="muted" style="margin:8px 0">打开「终端」App，逐条粘贴运行下面的命令（把「…」换成你自己的值）。
      文件位置：<code>${ENV_PATH}</code>，每行一条 <code>KEY=值</code>，改完回来刷新本页即可看到状态变化。</p>
      <div class="codebox">mkdir -p ~/.wealthos && cat >> ~/.wealthos/env << 'EOF'
WEALTHOS_XXX_KEY=…（要写的行）
EOF</div>
      <p class="tiny">写错/想删某行：用 <code>open -e ~/.wealthos/env</code> 直接编辑文本。
      环境变量优先于文件。Key 只存在本机，系统不上传任何服务器。</p>
    </div>`;
  $("#setup-list").innerHTML = KEY_GUIDES.map(g => {
    const s = st[g.id] || { configured: false };
    return `<div class="card setup-card ${s.configured ? "on" : ""}">
      <div class="setup-head">${g.icon} <b>${g.title}</b> ${badge(s.configured, s.configured ? "已打通" : "未打通")}
        ${s.configured && s.key ? `<span class="tiny">${esc(s.key)}</span>` : ""}</div>
      <p class="muted" style="margin:6px 0">🎯 ${g.benefit}<br>💰 ${g.cost}</p>
      ${g.paths.map(p => `<details class="setup-path"><summary>${esc(p.name)}</summary>
        <ol>${p.steps.map(t => `<li>${t}</li>`).join("")}</ol>
        <div class="codebox">${p.env.map(l => esc(l)).join("\n")}</div>
        <button class="ghost copy-btn">📋 一键复制以上配置行</button>
      </details>`).join("")}
    </div>`;
  }).join("");
  $$(".copy-btn").forEach(btn => btn.addEventListener("click", (e) => {
    const text = e.target.closest(".setup-path").querySelector(".codebox").textContent;
    navigator.clipboard.writeText(text).then(() => {
      e.target.textContent = "✅ 已复制，去终端粘贴";
      setTimeout(() => (e.target.textContent = "📋 一键复制以上配置行"), 2500);
    });
  }));
}

function badge(on, label) {
  return `<span class="st-badge ${on ? "ok" : "off"}">${on ? "✅" : "⚪"} ${label}</span>`;
}

/* ── 弹窗表单 ──────────────────────────────────────── */
function openAccountDialog() { $("#dlg-account").showModal(); }
$("#btn-add-account").addEventListener("click", openAccountDialog);
$("#btn-add-holding").addEventListener("click", async () => {
  if (!STATUS || STATUS.accounts === 0) { alert("请先添加一个账户"); openAccountDialog(); return; }
  const p = await api("/api/portfolio").catch(() => null);
  if (p) fillAccountSelect(p.accounts || []);
  $("#dlg-holding").showModal();
});
$$("dialog [data-close]").forEach((b) => b.addEventListener("click", (e) =>
  e.target.closest("dialog").close()));
$$("dialog").forEach((d) => d.addEventListener("click", (e) => { if (e.target === d) d.close(); }));
$("#btn-guide").addEventListener("click", () => $("#dlg-guide").showModal());

$("#form-account").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api("/api/accounts", { method: "POST", body: JSON.stringify({
      name: f.get("name"), institution: f.get("institution"),
      currency: f.get("currency"), account_type: f.get("account_type") }) });
    e.target.reset(); $("#dlg-account").close();
    await refreshStatus(); loadTab("portfolio");
  } catch (err) { alert("创建失败: " + err.message); }
});

$("#form-holding").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const symbol = String(f.get("symbol") || "").trim();
  const isCash = symbol.toUpperCase().startsWith("CASH:");
  try {
    await api("/api/holdings", { method: "POST", body: JSON.stringify({
      account: f.get("account"), symbol,
      quantity: Number(f.get("quantity")),
      currency: String(f.get("currency")).toUpperCase(),
      price: f.get("price") ? Number(f.get("price")) : (isCash ? 1 : null),
      as_of: f.get("as_of") || null }) });
    e.target.reset(); $("#dlg-holding").close();
    await api("/api/run/fetch", { method: "POST" }).catch(() => {});
    await refreshStatus(); loadTab("portfolio");
  } catch (err) { alert("保存失败: " + err.message); }
});

/* ── FABs ──────────────────────────────────────────── */
$("#fab-run").addEventListener("click", async (e) => {
  e.target.textContent = "拉取中…";
  try { await api("/api/run/fetch", { method: "POST" }); } catch (err) { alert("拉取失败: " + err.message); }
  e.target.textContent = "⟳ 拉数据";
  refreshStatus(); loadTab(document.querySelector("nav button.active").dataset.tab);
});
$("#fab-brief").addEventListener("click", async (e) => {
  e.target.textContent = "生成中…";
  try {
    const r = await api("/api/run/brief", { method: "POST" });
    if (r.audit_failures && r.audit_failures.length)
      alert("审计警告: " + JSON.stringify(r.audit_failures));
  } catch (err) { alert("生成失败: " + err.message); }
  e.target.textContent = "✦ 生成简报";
  loadBrief(); refreshStatus();
});

/* ── Chat ──────────────────────────────────────────── */
$("#chat-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = $("#chat-input").value.trim();
  if (!q) return;
  $("#chat-input").value = "";
  const log = $("#chat-log");
  log.insertAdjacentHTML("beforeend", `<div class="msg user">你：${esc(q)}</div>`);
  log.scrollTop = log.scrollHeight;
  try {
    const r = await api("/api/chat", { method: "POST", body: JSON.stringify({ question: q }) });
    log.insertAdjacentHTML("beforeend", `<div class="msg">WealthOS：${esc(r.answer)}</div>`);
  } catch (e) {
    log.insertAdjacentHTML("beforeend", `<div class="msg warn">出错: ${esc(e.message)}</div>`);
  }
  log.scrollTop = log.scrollHeight;
});

/* ── 启动 ──────────────────────────────────────────── */
(async () => {
  await refreshStatus();
  if (STATUS && STATUS.accounts !== 0) loadTab("today");
})();
