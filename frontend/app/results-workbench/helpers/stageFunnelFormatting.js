function fmtInt(value) {
  const num = Number(value);
  return Number.isFinite(num) ? Math.round(num).toLocaleString('en-US') : '-';
}

function fmtPct(value) {
  const num = Number(value);
  return Number.isFinite(num) ? `${(num * 100).toFixed(2)}%` : '-';
}

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const EXIT_REASON_CODES = new Set([
  'TAKE_PROFIT',
  'FIXED_STOP_LOSS',
  'STOP_LOSS',
  'SIGNAL_REVERSE',
  'TREND_REVERSE',
  'RISK_OFF_EXIT',
]);

const REASON_LABELS = {
  ATR_STOP_LOSS: 'ATR止损',
  ATR_TRAIL_EXIT: 'ATR跟踪退出',
  TAKE_PROFIT: '止盈',
  FIXED_STOP_LOSS: '固定止损',
  STOP_LOSS: '止损',
  SIGNAL_REVERSE: '信号反转',
  TREND_REVERSE: '趋势反转',
  RISK_OFF_EXIT: '风险关闭退出',
};

function sumDailyInt(rows, key) {
  return (Array.isArray(rows) ? rows : []).reduce((sum, row) => {
    const value = Number(row?.[key]);
    return sum + (Number.isFinite(value) ? value : 0);
  }, 0);
}

function stageClass(stageKey) {
  const key = String(stageKey || '').toLowerCase();
  if (key === 's1') return 'wb-funnel-stage-pool';
  if (key === 's8') return 'wb-funnel-stage-s8';
  if (key === 's9') return 'wb-funnel-stage-exit';
  return 'wb-funnel-stage-buy';
}

function renderStageCountPills(items, emptyText = '暂无额外原始计数') {
  const normalized = (items || []).filter((item) => {
    const label = String(item?.label || '').trim();
    const value = Number(item?.value);
    return !!label && Number.isFinite(value);
  });
  if (!normalized.length) {
    return `<div class="wb-funnel-row-stats"><span>${esc(emptyText)}</span></div>`;
  }
  return `<div class="wb-funnel-row-stats">${normalized.map((item) => (
    `<span>${esc(String(item.label))}=${fmtInt(item.value)}</span>`
  )).join('')}</div>`;
}

function renderStageTrackCard(title, items, emptyText) {
  return `<div class="wb-stage-track-card"><div class="wb-stage-track-title">${esc(title)}</div>${renderStageCountPills(items, emptyText)}</div>`;
}

export function reasonCodeOf(row) {
  return String(row?.code || row?.reason_code || '').toUpperCase();
}

export function reasonZh(code) {
  const normalized = String(code || '').toUpperCase();
  return REASON_LABELS[normalized] || normalized || '-';
}

export function reasonByPrefix(rows) {
  return (Array.isArray(rows) ? rows : []).reduce((acc, row) => {
    const code = reasonCodeOf(row);
    if (!code) return acc;
    if (code.includes('EXIT') || code.includes('ATR_') || EXIT_REASON_CODES.has(code)) {
      acc.exit.push(row);
    } else if (code.includes('RISK') || code.includes('DD_')) {
      acc.risk.push(row);
    } else if (code.includes('ENTRY') || code.includes('BREAKOUT')) {
      acc.entry.push(row);
    } else {
      acc.other.push(row);
    }
    return acc;
  }, { exit: [], risk: [], entry: [], other: [] });
}

export function buildStageRows(artifacts, counters) {
  const buyStageRows = Array.isArray(artifacts?.funnelRows) && artifacts.funnelRows.length
    ? artifacts.funnelRows
    : (Array.isArray(counters?.buy_stage_funnel) ? counters.buy_stage_funnel : []);
  const dailyRows = Array.isArray(artifacts?.dailyRows) ? artifacts.dailyRows : [];
  const rawSignals = sumDailyInt(dailyRows, 'raw_buy_signal_count');
  const buyCandidates = sumDailyInt(dailyRows, 'buy_candidate_count');
  const buyOrders = Number(counters?.buy_orders_count ?? 0);
  const minHoldBlockCount = Number(counters?.min_hold_block_count ?? 0);
  const cooldownBlockCount = Number(counters?.cooldown_block_count ?? 0);
  const heldDupBlockCount = Math.max(rawSignals - buyCandidates - minHoldBlockCount - cooldownBlockCount, 0);
  const mfRankAppliedDays = Number(counters?.mf_rank_applied_days ?? 0);
  const mfTopkRejectCount = Number(counters?.mf_topk_reject_count ?? 0);
  const rankActuallyApplied = mfRankAppliedDays > 0 || mfTopkRejectCount > 0;

  return buyStageRows.map((rowDef) => {
    const key = String(rowDef?.stage_key || '').toLowerCase();
    if (key === 's4') {
      const inputCount = Number(rowDef?.input_count ?? 0);
      const outputCount = buyCandidates > 0 ? buyCandidates : Number(rowDef?.output_count ?? 0);
      const noRawSignalCount = Math.max(inputCount - rawSignals, 0);
      return {
        ...rowDef,
        input_count: inputCount,
        output_count: outputCount,
        filtered_count: Math.max(inputCount - outputCount, 0),
        note: `全回测期可交易 stock-day 事件压缩为候选买入；未触发原始买点=${fmtInt(noRawSignalCount)}，持仓去重/再入场阻塞=${fmtInt(heldDupBlockCount + minHoldBlockCount + cooldownBlockCount)}`,
        raw_items: [
          { label: 'INPUT_CNT', value: inputCount },
          { label: 'KEEP_CNT', value: outputCount },
          { label: 'FILTERED_CNT', value: Math.max(inputCount - outputCount, 0) },
          { label: 'RAW_SIGNAL_CNT', value: rawSignals },
          { label: 'NO_RAW_SIGNAL', value: noRawSignalCount },
          { label: 'HELD_DUP_BLOCK', value: heldDupBlockCount },
          { label: 'MIN_HOLD_BLOCK', value: minHoldBlockCount },
          { label: 'COOLDOWN_BLOCK', value: cooldownBlockCount },
        ],
      };
    }
    if (key === 's5') {
      const inputCount = buyCandidates > 0 ? buyCandidates : Number(rowDef?.input_count ?? 0);
      const outputCount = rankActuallyApplied ? Math.max(inputCount - mfTopkRejectCount, 0) : inputCount;
      return {
        ...rowDef,
        input_count: inputCount,
        output_count: outputCount,
        filtered_count: Math.max(inputCount - outputCount, 0),
        note: rankActuallyApplied
          ? `排序层实际生效；TopK/多因子截断过滤=${fmtInt(mfTopkRejectCount)}`
          : '当前基线未启用独立排序截断，排序层按实际显示为 0 过滤。',
        raw_items: [
          { label: 'INPUT_CNT', value: inputCount },
          { label: 'KEEP_CNT', value: outputCount },
          { label: 'FILTERED_CNT', value: Math.max(inputCount - outputCount, 0) },
          { label: 'MF_RANK_APPLIED_DAYS', value: mfRankAppliedDays },
          { label: 'MF_TOPK_REJECT_CNT', value: mfTopkRejectCount },
        ],
      };
    }
    if (key === 's6') {
      const inputCount = rankActuallyApplied
        ? Math.max((buyCandidates > 0 ? buyCandidates : Number(rowDef?.input_count ?? 0)) - mfTopkRejectCount, 0)
        : (buyCandidates > 0 ? buyCandidates : Number(rowDef?.input_count ?? 0));
      return {
        ...rowDef,
        input_count: inputCount,
        output_count: buyOrders,
        filtered_count: Math.max(inputCount - buyOrders, 0),
        note: '入场信号在本层收口为最终实际开仓次数。',
        raw_items: [
          { label: 'INPUT_CNT', value: inputCount },
          { label: 'KEEP_CNT', value: buyOrders },
          { label: 'FILTERED_CNT', value: Math.max(inputCount - buyOrders, 0) },
          { label: 'BUY_ORDER_CNT', value: buyOrders },
          { label: 'ABOVE_SLOW_MA_BLOCK', value: Number(counters?.entry_above_slow_ma_block_count ?? 0) },
          { label: 'SLOPE_BLOCK', value: Number(counters?.entry_slope_block_count ?? 0) },
        ],
      };
    }
    if (key === 's7') {
      return {
        ...rowDef,
        stage_label: 'S7 仓位控制',
        input_count: buyOrders,
        output_count: buyOrders,
        filtered_count: 0,
        note: '仓位控制层；当前基线未输出独立 slot 收缩计数，沿用最终开仓数展示。',
        raw_items: [
          { label: 'INPUT_CNT', value: buyOrders },
          { label: 'KEEP_CNT', value: buyOrders },
          { label: 'FILTERED_CNT', value: 0 },
          { label: 'BUY_ORDER_CNT', value: buyOrders },
          { label: 'AVG_POSITIONS', value: Number(counters?.avg_positions ?? 0) },
          { label: 'MAX_POSITIONS', value: Number(counters?.max_positions ?? 0) },
        ],
      };
    }
    return {
      ...rowDef,
      raw_items: [
        { label: 'INPUT_CNT', value: Number(rowDef?.input_count ?? 0) },
        { label: 'KEEP_CNT', value: Number(rowDef?.output_count ?? 0) },
        { label: 'FILTERED_CNT', value: Number(rowDef?.filtered_count ?? 0) },
      ],
    };
  });
}

export function renderUnifiedStageFunnel(stageRows, counters, exitRows) {
  const rows = Array.isArray(stageRows) ? stageRows.map((row) => ({ ...row })) : [];
  if (!rows.length) {
    return '<div class="wb-mini">当前结果尚未提供 stage counters，无法生成统一 9-stage 漏斗。</div>';
  }

  const maxValue = Math.max(1, ...rows.map((row) => Number(row.output_count ?? row.input_count ?? row.filtered_count ?? 0) || 0));
  const ratioText = (numerator, denominator) => {
    const n = Number(numerator);
    const d = Number(denominator);
    return Number.isFinite(n) && Number.isFinite(d) && d > 0 ? fmtPct(n / d) : '-';
  };

  const body = rows.map((row) => {
    const key = String(row.stage_key || '').toLowerCase();
    let available = row.available !== false;
    let note = String(row.note || (available ? '已接入后端真实计数。' : '当前无独立计数。'));
    let inputCount = Number(row.input_count);
    let outputCount = Number(row.output_count);
    let filteredCount = Number(row.filtered_count);
    let extraHtml = '';
    let rawItems = Array.isArray(row.raw_items) ? row.raw_items : [];

    if (key === 's8') {
      available = true;
      note = '唯一同时涉及买入和卖出的阶段；左侧看建仓约束，右侧看风险侧卖出统计。';
      inputCount = Number.NaN;
      outputCount = Number.NaN;
      filteredCount = Number.NaN;
      rawItems = [];
      extraHtml = `<div class="wb-stage-track-grid">${renderStageTrackCard('S8 买入侧', [
        { label: 'CASH_SKIP', value: Number(counters?.cash_skip_count ?? 0) },
        { label: 'LOT_SKIP', value: Number(counters?.lot_skip_count ?? 0) },
        { label: 'SINGLE_CAP', value: Number(counters?.cap_hit_single ?? 0) },
        { label: 'INDUSTRY_CAP', value: Number(counters?.cap_hit_industry ?? 0) },
      ], '当前无独立买入约束计数')}${renderStageTrackCard('S8 卖出侧', [
        { label: 'DD_REDUCED', value: Number(counters?.dd_reduced_count ?? 0) },
        { label: 'DD_SCALE_08', value: Number(counters?.dd_scale_08_count ?? 0) },
        { label: 'DD_SCALE_06', value: Number(counters?.dd_scale_06_count ?? 0) },
        { label: 'DD_FIXED_03', value: Number(counters?.dd_fixed_03_count ?? 0) },
        { label: 'DD_STOP', value: Number(counters?.dd_stop_count ?? 0) },
      ], '当前无独立卖出风险计数')}</div>`;
    } else if (key === 's9') {
      available = true;
      note = '退出阶段只看卖出链路；按退出原因展示原始计数与占比。';
      inputCount = Number.NaN;
      outputCount = Number.NaN;
      filteredCount = Number.NaN;
      rawItems = [
        { label: 'SELL_ORDER_CNT', value: Number(counters?.sell_orders_count ?? 0) },
        { label: 'CLOSED_TRADE_CNT', value: Number(counters?.closed_trades ?? 0) },
      ];
      const normalizedExitRows = (Array.isArray(exitRows) ? exitRows : [])
        .map((row) => ({
          code: reasonCodeOf(row),
          value: Number(row?.count ?? 0),
        }))
        .filter((row) => row.code && row.value > 0)
        .sort((a, b) => b.value - a.value);
      const exitTotal = normalizedExitRows.reduce((sum, row) => sum + row.value, 0);
      extraHtml = normalizedExitRows.length
        ? `<div class="wb-stage-exit-stack"><div class="wb-stage-exit-head">S9 退出原因分布 | 总退出=${fmtInt(exitTotal)}</div>${normalizedExitRows.map((row) => {
            const ratio = exitTotal > 0 ? row.value / exitTotal : 0;
            return `<div class="wb-stage-exit-row"><div class="wb-stage-exit-meta"><span class="wb-stage-exit-name">${esc(reasonZh(row.code))} <span class="wb-stage-exit-code">${esc(row.code)}</span></span><span class="wb-stage-exit-count">${fmtInt(row.value)} | ${fmtPct(ratio)}</span></div><div class="wb-stage-exit-bar"><span style="width:${Math.max(6, ratio * 100)}%"></span></div></div>`;
          }).join('')}</div>`
        : '';
    }

    const inputText = Number.isFinite(inputCount) ? fmtInt(inputCount) : '-';
    const outputText = Number.isFinite(outputCount) ? fmtInt(outputCount) : '-';
    const filteredText = Number.isFinite(filteredCount) ? fmtInt(filteredCount) : '-';
    const width = Number.isFinite(outputCount) ? Math.max(6, (outputCount / maxValue) * 100) : 0;

    return `<div class="wb-funnel-row ${stageClass(key)}${available ? '' : ' wb-funnel-unavailable'}"><div class="wb-funnel-row-head"><div class="wb-funnel-row-title">${esc(row.stage_label || row.title || row.stage_key || '阶段')}</div><div class="wb-funnel-row-note">${esc(note)}</div></div><div class="wb-bar"><span style="width:${width}%"></span></div><div class="wb-funnel-row-meta"><div><span>输入</span><strong>${inputText}</strong></div><div><span>保留</span><strong>${outputText}</strong></div><div><span>过滤</span><strong>${filteredText}</strong></div></div>${renderStageCountPills(rawItems, available ? '暂无额外原始计数' : '当前无独立原始计数')}${Number.isFinite(inputCount) ? `<div class="wb-funnel-row-stats"><span>保留率=${ratioText(outputCount, inputCount)}</span><span>过滤率=${ratioText(filteredCount, inputCount)}</span></div>` : ''}${extraHtml}</div>`;
  }).join('');

  const totals = rows.reduce((acc, row) => {
    acc.input += Number(row.input_count || 0);
    acc.output += Number(row.output_count || 0);
    acc.filtered += Number(row.filtered_count || 0);
    return acc;
  }, { input: 0, output: 0, filtered: 0 });

  return `<div class="wb-funnel-scroll wb-scrollbox"><div class="wb-funnel-stack">${body}</div><div class="wb-funnel-summary"><span>stage_cnt=${fmtInt(rows.length)}</span><span>input_sum=${fmtInt(totals.input)}</span><span>keep_sum=${fmtInt(totals.output)}</span><span>filtered_sum=${fmtInt(totals.filtered)}</span><span>buy_order_cnt=${fmtInt(counters?.buy_orders_count ?? 0)}</span><span>sell_order_cnt=${fmtInt(counters?.sell_orders_count ?? 0)}</span></div></div>`;
}

export function buildUnifiedStageFunnelFromSnapshot(snapshot) {
  const artifacts = snapshot?.artifacts || {};
  const counters = artifacts?.run_meta?.counters || {};
  const stageRows = buildStageRows(artifacts, counters);
  const exitRows = reasonByPrefix(artifacts.reasonRows || []).exit || [];
  return {
    html: renderUnifiedStageFunnel(stageRows, counters, exitRows),
    meta: `买入 ${fmtInt(counters?.buy_orders_count ?? 0)} 笔 | 卖出 ${fmtInt(counters?.sell_orders_count ?? 0)} 笔 | stage=${fmtInt(stageRows.length)}`,
    stageRows,
    exitRows,
  };
}
function normalizeMetricItems(items = [], formatter = fmtInt) {
  return (Array.isArray(items) ? items : [])
    .map((item) => {
      const label = String(item?.label || '').trim();
      const value = Number(item?.value);
      if (!label || !Number.isFinite(value)) return null;
      return {
        label,
        value,
        text: formatter(value),
      };
    })
    .filter(Boolean);
}

function stageStatus(row) {
  const key = String(row?.stage_key || '').toLowerCase();
  if (key === 's1') return { label: '汇总口径', tone: 'derived' };
  if (row?.available === false) return { label: '未单独计数', tone: 'missing' };
  return { label: '真实计数', tone: 'ok' };
}

function stageMetrics(row, counters) {
  const key = String(row?.stage_key || '').toLowerCase();
  const items = [];
  const inputCount = Number(row?.input_count);
  const outputCount = Number(row?.output_count);
  const filteredCount = Number(row?.filtered_count);
  if (Number.isFinite(inputCount)) items.push({ label: '输入', text: fmtInt(inputCount) });
  if (Number.isFinite(outputCount)) items.push({ label: '保留', text: fmtInt(outputCount) });
  if (Number.isFinite(filteredCount)) items.push({ label: '过滤', text: fmtInt(filteredCount) });
  if (key === 's2') {
    items.push(
      { label: 'MAIN_DAYS', text: fmtInt(counters?.trade_mode_main_days ?? 0) },
      { label: 'LIGHT_DAYS', text: fmtInt(counters?.trade_mode_light_days ?? 0) },
      { label: 'NO_TRADE_DAYS', text: fmtInt(counters?.trade_mode_notrade_days ?? 0) },
    );
  }
  if (key === 's3' && !items.length) items.push({ label: '状态', text: '未启用/未单独计数' });
  return items;
}

function stagePills(row, counters) {
  const key = String(row?.stage_key || '').toLowerCase();
  if (key === 's2') {
    return [
      ...normalizeMetricItems([{ label: 'GATE_ON_RATE', value: counters?.gate_on_rate ?? 0 }], fmtPct),
      ...normalizeMetricItems([
        { label: 'BULL_DAYS', value: counters?.market_state_bull_days ?? 0 },
        { label: 'TRANS_DOWN_DAYS', value: counters?.market_state_trans_down_days ?? 0 },
        { label: 'TRANS_UP_DAYS', value: counters?.market_state_trans_up_days ?? 0 },
      ]),
    ];
  }
  return normalizeMetricItems(row?.raw_items || []);
}

function executionBuckets(counters) {
  return {
    buySide: normalizeMetricItems([
      { label: '现金不足', value: counters?.cash_skip_count ?? 0 },
      { label: '整手不足', value: counters?.lot_skip_count ?? 0 },
      { label: '单票上限', value: counters?.cap_hit_single ?? 0 },
      { label: '行业上限', value: counters?.cap_hit_industry ?? 0 },
    ]),
    sellSide: normalizeMetricItems([
      { label: 'DD_REDUCED', value: counters?.dd_reduced_count ?? 0 },
      { label: 'DD_SCALE_08', value: counters?.dd_scale_08_count ?? 0 },
      { label: 'DD_SCALE_06', value: counters?.dd_scale_06_count ?? 0 },
      { label: 'DD_FIXED_03', value: counters?.dd_fixed_03_count ?? 0 },
      { label: 'DD_STOP', value: counters?.dd_stop_count ?? 0 },
    ]),
  };
}

function exitReasonItems(exitRows) {
  const normalized = (Array.isArray(exitRows) ? exitRows : [])
    .map((row) => ({
      code: reasonCodeOf(row),
      label: reasonZh(reasonCodeOf(row)),
      value: Number(row?.count ?? 0),
    }))
    .filter((row) => row.code && row.value > 0)
    .sort((a, b) => b.value - a.value);
  const total = normalized.reduce((sum, row) => sum + row.value, 0);
  return normalized.map((row) => ({
    ...row,
    ratio: total > 0 ? row.value / total : 0,
    ratioText: total > 0 ? fmtPct(row.value / total) : '-',
    text: fmtInt(row.value),
  }));
}

function completenessNotes(stageRows, counters) {
  const missingStages = (Array.isArray(stageRows) ? stageRows : [])
    .filter((row) => row?.available === false)
    .map((row) => String(row?.stage_label || row?.stage_key || '').trim())
    .filter(Boolean);
  const notes = [];
  if (missingStages.length) notes.push(`当前仍缺少候选级单独计数的阶段: ${missingStages.join(' / ')}`);
  if (Number(counters?.cash_skip_count ?? 0) > 0) notes.push('S8 买入侧主要损耗来自现金约束；这里已直接展示原始阻塞计数。');
  if (Number(counters?.mf_topk_reject_count ?? 0) > 0) notes.push('S5 已补入多因子/TopK 截断计数，不再只看 buy_stage_funnel 原值。');
  if (Number(counters?.sell_orders_count ?? 0) > 0) notes.push('S9 退出分布独立来自 reason_codes，和买入主链拆开展示。');
  return notes;
}

export function buildUnifiedStageFunnelModel(snapshot) {
  const artifacts = snapshot?.artifacts || {};
  const counters = artifacts?.run_meta?.counters || {};
  const stageRows = buildStageRows(artifacts, counters);
  const exitRows = reasonByPrefix(artifacts.reasonRows || []).exit || [];
  const rowMap = new Map(stageRows.map((row) => [String(row?.stage_key || '').toLowerCase(), row]));
  const rawSignalCount = (Array.isArray(artifacts?.dailyRows) ? artifacts.dailyRows : []).reduce(
    (sum, row) => sum + (Number(row?.raw_buy_signal_count) || 0),
    0,
  );
  const stageOrder = ['s1', 's2', 's3', 's4', 's5', 's6', 's7'];
  const chainStages = stageOrder.map((key) => {
    const row = rowMap.get(key) || {
      stage_key: key,
      stage_label: key.toUpperCase(),
      available: false,
      note: '当前无该阶段数据',
    };
    return {
      key,
      title: row.stage_label || key.toUpperCase(),
      note: String(row.note || ''),
      status: stageStatus(row),
      metrics: stageMetrics(row, counters),
      pills: stagePills(row, counters),
    };
  });
  return {
    meta: `买入 ${fmtInt(counters?.buy_orders_count ?? 0)} 笔 | 卖出 ${fmtInt(counters?.sell_orders_count ?? 0)} 笔 | 主链=${fmtInt(chainStages.length)} 阶段`,
    summaryCards: [
      { label: '股票池', value: fmtInt(rowMap.get('s1')?.output_count ?? artifacts?.run_meta?.universe?.after_filters_symbols ?? 0) },
      { label: '原始买点', value: fmtInt(rawSignalCount) },
      { label: '排序后候选', value: fmtInt(rowMap.get('s5')?.output_count ?? 0) },
      { label: '实际买入', value: fmtInt(counters?.buy_orders_count ?? 0) },
      { label: '实际卖出', value: fmtInt(counters?.sell_orders_count ?? 0) },
    ],
    chainStages,
    execution: executionBuckets(counters),
    exitReasons: exitReasonItems(exitRows),
    completenessNotes: completenessNotes(stageRows, counters),
  };
}

function buildReadableStageMetrics(row, counters) {
  const metrics = [];
  const inputCount = Number(row?.input_count);
  const outputCount = Number(row?.output_count);
  const filteredCount = Number(row?.filtered_count);
  if (Number.isFinite(inputCount)) metrics.push({ label: '输入', text: fmtInt(inputCount) });
  if (Number.isFinite(outputCount)) metrics.push({ label: '保留', text: fmtInt(outputCount) });
  if (Number.isFinite(filteredCount)) metrics.push({ label: '过滤', text: fmtInt(filteredCount) });
  if (String(row?.stage_key || '').toLowerCase() === 's2') {
    metrics.push(
      { label: '主模式天数', text: fmtInt(counters?.trade_mode_main_days ?? 0) },
      { label: '轻仓天数', text: fmtInt(counters?.trade_mode_light_days ?? 0) },
      { label: '空仓天数', text: fmtInt(counters?.trade_mode_notrade_days ?? 0) },
    );
  }
  return metrics;
}

function buildReadableStagePills(row, counters) {
  if (String(row?.stage_key || '').toLowerCase() === 's2') {
    return normalizeMetricItems([
      { label: 'Gate On', value: counters?.gate_on_rate ?? 0 },
      { label: 'Bull', value: counters?.market_state_bull_days ?? 0 },
      { label: 'TransDown', value: counters?.market_state_trans_down_days ?? 0 },
      { label: 'TransUp', value: counters?.market_state_trans_up_days ?? 0 },
    ], (value) => (String(value).includes('.') ? fmtPct(value) : fmtInt(value)));
  }
  return normalizeMetricItems(row?.raw_items || []);
}

function buildReadableCompletenessNotes(stageRows, counters) {
  const missingStages = (Array.isArray(stageRows) ? stageRows : [])
    .filter((row) => row?.available === false)
    .map((row) => String(row?.stage_label || row?.stage_key || '').trim())
    .filter(Boolean);
  const notes = [];
  if (missingStages.length) notes.push(`当前仍缺少独立计数的阶段：${missingStages.join(' / ')}`);
  if (Number(counters?.cash_skip_count ?? 0) > 0) notes.push('S8 买入侧直接展示现金和整手约束，不再和主链保留数混在一起。');
  if (Number(counters?.mf_topk_reject_count ?? 0) > 0) notes.push('S5 已补充排序截断信息，避免只看到阶段保留数却不知道候选是怎么被砍掉的。');
  if (Number(counters?.sell_orders_count ?? 0) > 0) notes.push('S9 退出分布独立来自 reason_codes，只解释卖出链路，不再冒充买入漏斗的一部分。');
  if (!notes.length) notes.push('当前实验没有额外的漏斗口径告警。');
  return notes;
}

export function buildReadableStageFunnelModel(snapshot) {
  const artifacts = snapshot?.artifacts || {};
  const counters = artifacts?.run_meta?.counters || {};
  const stageRows = buildStageRows(artifacts, counters);
  const exitRows = reasonByPrefix(artifacts.reasonRows || []).exit || [];
  const rowMap = new Map(stageRows.map((row) => [String(row?.stage_key || '').toLowerCase(), row]));
  const rawSignalCount = (Array.isArray(artifacts?.dailyRows) ? artifacts.dailyRows : []).reduce(
    (sum, row) => sum + (Number(row?.raw_buy_signal_count) || 0),
    0,
  );
  const chainStages = ['s1', 's2', 's3', 's4', 's5', 's6', 's7'].map((key) => {
    const row = rowMap.get(key) || {
      stage_key: key,
      stage_label: key.toUpperCase(),
      available: false,
      note: '当前没有该阶段数据',
    };
    const tone = key === 's1' ? 'derived' : row.available === false ? 'missing' : 'ok';
    const label = tone === 'derived' ? '汇总口径' : tone === 'missing' ? '未单独计数' : '真实计数';
    return {
      key,
      title: row.stage_label || key.toUpperCase(),
      note: String(row.note || '当前没有额外说明。'),
      status: { tone, label },
      metrics: buildReadableStageMetrics(row, counters),
      pills: buildReadableStagePills(row, counters),
    };
  });
  const exitReasonItems = (Array.isArray(exitRows) ? exitRows : [])
    .map((row) => ({
      code: reasonCodeOf(row),
      label: reasonZh(reasonCodeOf(row)),
      value: Number(row?.count ?? 0),
    }))
    .filter((row) => row.code && row.value > 0)
    .sort((a, b) => b.value - a.value);
  const exitTotal = exitReasonItems.reduce((sum, row) => sum + row.value, 0);
  return {
    meta: `买入 ${fmtInt(counters?.buy_orders_count ?? 0)} 笔 | 卖出 ${fmtInt(counters?.sell_orders_count ?? 0)} 笔 | 主链 ${fmtInt(chainStages.length)} 阶段`,
    summaryCards: [
      { label: '股票池', value: fmtInt(rowMap.get('s1')?.output_count ?? artifacts?.run_meta?.universe?.after_filters_symbols ?? 0) },
      { label: '原始买点', value: fmtInt(rawSignalCount) },
      { label: '排序后候选', value: fmtInt(rowMap.get('s5')?.output_count ?? 0) },
      { label: '实际买入', value: fmtInt(counters?.buy_orders_count ?? 0) },
      { label: '实际卖出', value: fmtInt(counters?.sell_orders_count ?? 0) },
    ],
    chainStages,
    execution: {
      buySide: normalizeMetricItems([
        { label: '现金不足', value: counters?.cash_skip_count ?? 0 },
        { label: '整手不足', value: counters?.lot_skip_count ?? 0 },
        { label: '单票上限', value: counters?.cap_hit_single ?? 0 },
        { label: '行业上限', value: counters?.cap_hit_industry ?? 0 },
      ]),
      sellSide: normalizeMetricItems([
        { label: '轻度缩仓', value: counters?.dd_reduced_count ?? 0 },
        { label: '0.8 缩放', value: counters?.dd_scale_08_count ?? 0 },
        { label: '0.6 缩放', value: counters?.dd_scale_06_count ?? 0 },
        { label: '固定 0.3', value: counters?.dd_fixed_03_count ?? 0 },
        { label: '停止开仓', value: counters?.dd_stop_count ?? 0 },
      ]),
    },
    exitReasons: exitReasonItems.map((row) => ({
      ...row,
      ratio: exitTotal > 0 ? row.value / exitTotal : 0,
      ratioText: exitTotal > 0 ? fmtPct(row.value / exitTotal) : '-',
      text: fmtInt(row.value),
    })),
    completenessNotes: buildReadableCompletenessNotes(stageRows, counters),
  };
}
