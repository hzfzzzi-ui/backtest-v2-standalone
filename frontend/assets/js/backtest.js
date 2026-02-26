import { setActiveNav } from './ui.js';

function fmtNum(v, digits = 2) {
  const n = Number(v ?? 0);
  if (Number.isNaN(n)) return '-';
  return n.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function collectPayload() {
  const symbolsRaw = document.getElementById('symbols')?.value || '';
  const symbols = symbolsRaw.split(',').map((s) => s.trim()).filter(Boolean);
  return {
    strategy: document.getElementById('strategy')?.value || 'pipeline',
    start_date: document.getElementById('startDate')?.value || '2025-10-01',
    end_date: document.getElementById('endDate')?.value || '2026-02-01',
    index_code: document.getElementById('indexCode')?.value || 'sh000300',
    initial_capital: Number(document.getElementById('capital')?.value || 100000),
    max_positions: Number(document.getElementById('maxPositions')?.value || 6),
    symbols: symbols.length ? symbols : null,
  };
}

function renderSummary(resp) {
  const summary = resp.summary || {};
  const box = document.getElementById('summaryBody');
  const card = document.getElementById('summaryCard');
  if (!box || !card) return;
  card.style.display = 'block';
  box.innerHTML = `
    <div>交易日：${summary.trading_days ?? 0}</div>
    <div>交易次数：买 ${summary.buys_count ?? 0} / 卖 ${summary.sells_count ?? 0}</div>
    <div>总收益：${fmtNum(summary.total_return_pct ?? 0, 2)}%</div>
    <div>最大回撤：${fmtNum(summary.max_drawdown_pct ?? 0, 2)}%</div>
    <div>期末权益：¥${fmtNum(summary.final_equity ?? 0, 0)}</div>
  `;
}

function renderReport(resp) {
  const report = resp.report || {};
  const sections = report.sections || [];
  const box = document.getElementById('reportBody');
  const card = document.getElementById('reportCard');
  if (!box || !card) return;
  if (!sections.length) {
    card.style.display = 'none';
    return;
  }
  card.style.display = 'block';
  box.innerHTML = sections.map((s) => `<div><b>${s.title}</b><br>${s.content}</div>`).join('<hr style="border-color:rgba(110,118,129,.2)">');
}

function renderTrades(resp) {
  const trades = resp.trades || [];
  const card = document.getElementById('tradesCard');
  const tbody = document.getElementById('tradeRows');
  if (!card || !tbody) return;
  if (!trades.length) {
    card.style.display = 'none';
    return;
  }
  card.style.display = 'block';
  tbody.innerHTML = trades.slice(0, 100).map((t) => `
    <tr>
      <td class="mono">${t.date || ''}</td>
      <td>${t.action || ''}</td>
      <td>${t.symbol || t.name || ''}</td>
      <td class="num mono">${fmtNum(t.price, 3)}</td>
      <td class="num mono">${t.shares ?? ''}</td>
      <td class="num mono">¥${fmtNum(t.amount, 0)}</td>
    </tr>
  `).join('');
}

async function postJsonWithFallback(path, payload, timeoutMs = 300000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const primary = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
    if (primary.ok) return primary.json();
    const shouldFallback = (primary.status === 404 || primary.status === 405 || primary.status === 502 || primary.status === 503)
      && window.location.port === '8080';
    if (!shouldFallback) throw new Error(`${primary.status} ${primary.statusText}`);
  } finally {
    clearTimeout(timer);
  }

  const alt = `http://${window.location.hostname}:8090${path}`;
  const secondary = await fetch(alt, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!secondary.ok) throw new Error(`${secondary.status} ${secondary.statusText}`);
  return secondary.json();
}

async function runBacktest() {
  const btn = document.getElementById('btnRun');
  const status = document.getElementById('runStatus');
  if (!btn || !status) return;
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = '运行中...';
  status.style.display = 'block';
  status.innerHTML = '<div class="muted">正在执行回测，请稍候...</div>';

  try {
    const resp = await postJsonWithFallback('/api/backtest/run_unified', collectPayload(), 300000);
    status.style.display = 'none';
    renderSummary(resp);
    renderReport(resp);
    renderTrades(resp);
  } catch (e) {
    const msg = e && e.name === 'AbortError' ? 'Request timeout (300s)' : (e.message || e);
    status.style.display = 'block';
    status.innerHTML = `<div style="color:var(--bad)">回测失败: ${msg}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
}

function main() {
  setActiveNav();
  document.getElementById('btnRun')?.addEventListener('click', runBacktest);
}

main();
