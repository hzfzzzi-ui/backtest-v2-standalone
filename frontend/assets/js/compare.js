/* compare.js: experiment compare overlay */
/* Globals: state, byId, esc, pct, num, fmtInt, addLog, apiRequestJson */

let _wbCompareChart = null;

function _cmpColor(i) {
  const palette = ['#58a6ff', '#22c55e', '#f59e0b', '#ef4444', '#14b8a6', '#a78bfa', '#f97316', '#06b6d4'];
  return palette[i % palette.length];
}

function _normNav(navRows) {
  const arr = Array.isArray(navRows) ? navRows : [];
  const out = [];
  for (const r of arr) {
    const d = String(r?.date || '').slice(0, 10);
    const v = Number(r?.nav);
    if (!d || !Number.isFinite(v) || v <= 0) continue;
    out.push({ date: d, nav: v });
  }
  out.sort((a, b) => (a.date < b.date ? -1 : 1));
  return out;
}

function _renderCompareKpi(items) {
  const rows = (items || []).map((x) => {
    const perf = x?.perf || {};
    return {
      exp_id: String(x?.exp_id || ''),
      label: String(x?.label || x?.exp_id || ''),
      cagr: Number(perf?.cagr),
      sharpe: Number(perf?.sharpe),
      max_drawdown: Number(perf?.max_drawdown),
      total_return: Number(perf?.total_return),
      trades: Number(perf?.trades),
    };
  });
  const best = {
    cagr: Math.max(...rows.map((r) => (Number.isFinite(r.cagr) ? r.cagr : -Infinity))),
    sharpe: Math.max(...rows.map((r) => (Number.isFinite(r.sharpe) ? r.sharpe : -Infinity))),
    total_return: Math.max(...rows.map((r) => (Number.isFinite(r.total_return) ? r.total_return : -Infinity))),
    max_drawdown: Math.max(...rows.map((r) => (Number.isFinite(r.max_drawdown) ? r.max_drawdown : -Infinity))),
  };
  return `
    <table class="wb-table" style="margin-bottom:10px">
      <thead>
        <tr><th>实验</th><th>总收益</th><th>年化</th><th>夏普</th><th>最大回撤</th><th>交易数</th></tr>
      </thead>
      <tbody>
        ${rows.map((r) => `
          <tr>
            <td title="${esc(r.exp_id)}">${esc(r.label)}</td>
            <td class="num ${r.total_return === best.total_return ? 'wb-green-text' : ''}">${pct(r.total_return)}</td>
            <td class="num ${r.cagr === best.cagr ? 'wb-green-text' : ''}">${pct(r.cagr)}</td>
            <td class="num ${r.sharpe === best.sharpe ? 'wb-green-text' : ''}">${num(r.sharpe, 2)}</td>
            <td class="num ${r.max_drawdown === best.max_drawdown ? 'wb-green-text' : ''}">${pct(r.max_drawdown)}</td>
            <td class="num">${fmtInt(r.trades)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function _renderCompareChart(items) {
  const container = byId('wbCompareChart');
  if (!container) return;
  if (_wbCompareChart) {
    _wbCompareChart.remove();
    _wbCompareChart = null;
  }
  const LWC = window.LightweightCharts;
  if (!LWC) {
    container.innerHTML = '<div class="wb-empty"><span>lightweight-charts 加载失败</span></div>';
    return;
  }
  const chart = LWC.createChart(container, {
    width: container.clientWidth || 900,
    height: 300,
    layout: {
      background: { type: LWC.ColorType ? LWC.ColorType.Solid : 'solid', color: 'transparent' },
      textColor: '#94a3b8',
      fontSize: 11,
    },
    grid: {
      vertLines: { color: 'rgba(51,65,85,0.4)' },
      horzLines: { color: 'rgba(51,65,85,0.4)' },
    },
    timeScale: { borderColor: '#334155', rightOffset: 4 },
    rightPriceScale: { borderColor: '#334155' },
  });
  _wbCompareChart = chart;

  items.forEach((it, idx) => {
    const nav = _normNav(it?.nav || []);
    if (!nav.length) return;
    const base = nav[0].nav;
    const data = nav.map((p) => ({ time: p.date, value: p.nav / base }));
    const color = _cmpColor(idx);
    const s = typeof chart.addLineSeries === 'function'
      ? chart.addLineSeries({ color, lineWidth: 2, priceLineVisible: false })
      : chart.addSeries(LWC.LineSeries, { color, lineWidth: 2, priceLineVisible: false });
    s.setData(data);
  });

  chart.timeScale().fitContent();
  const ro = new ResizeObserver(() => {
    if (_wbCompareChart === chart) {
      chart.applyOptions({ width: container.clientWidth || 900, height: 300 });
    }
  });
  ro.observe(container);
}

function closeExperimentCompare() {
  const overlay = byId('wbCompareOverlay');
  if (overlay) overlay.hidden = true;
}

async function openExperimentCompare() {
  const selected = Array.isArray(state.compare_selected_ids) ? state.compare_selected_ids : [];
  if (selected.length < 2) {
    addLog('至少勾选 2 个实验再对比');
    return;
  }
  const payload = await apiRequestJson('experiments_compare', '/api/backtest_v2/experiments/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ exp_ids: selected }),
  });
  const items = Array.isArray(payload?.items) ? payload.items : [];
  if (items.length < 2) {
    addLog('可对比实验不足');
    return;
  }

  const overlay = byId('wbCompareOverlay');
  const body = byId('wbCompareBody');
  if (!overlay || !body) return;
  body.innerHTML = `${_renderCompareKpi(items)}<div id="wbCompareChart" style="height:300px"></div>`;
  overlay.hidden = false;
  _renderCompareChart(items);
}
