function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function fmtInt(value) {
  const num = toFiniteNumber(value);
  return num === null ? '-' : Math.round(num).toLocaleString('en-US');
}

function fmtPct(value) {
  const num = toFiniteNumber(value);
  return num === null ? '-' : `${(num * 100).toFixed(2)}%`;
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
    const value = toFiniteNumber(row?.[key]);
    return sum + (value === null ? 0 : value);
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
    const value = toFiniteNumber(item?.value);
    return !!label && value !== null;
  });
  if (!normalized.length) {
    return `<div class="wb-funnel-row-stats"><span>${esc(emptyText)}</span></div>`;
  }
  return `<div class="wb-funnel-row-stats">${normalized.map((item) => (
    `<span>${esc(String(item.label))}=${fmtInt(item.value)}</span>`
  )).join('')}</div>`;
}

function buildBaseRawItems(row) {
  return [
    { label: 'INPUT_CNT', value: toFiniteNumber(row?.input_count) },
    { label: 'KEEP_CNT', value: toFiniteNumber(row?.output_count) },
    { label: 'FILTERED_CNT', value: toFiniteNumber(row?.filtered_count) },
  ].filter((item) => item.value !== null);
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
  // Display-only aggregation for the stage funnel; canonical counters are backend-owned.
  const buyStageRows = Array.isArray(artifacts?.funnelRows) && artifacts.funnelRows.length
    ? artifacts.funnelRows
    : (Array.isArray(counters?.buy_stage_funnel) ? counters.buy_stage_funnel : []);
  const dailyRows = Array.isArray(artifacts?.dailyRows) ? artifacts.dailyRows : [];
  const rawSignals = sumDailyInt(dailyRows, 'raw_buy_signal_count');
  const buyCandidates = sumDailyInt(dailyRows, 'buy_candidate_count');
  const buyOrders = toFiniteNumber(counters?.buy_orders_count) ?? 0;
  const minHoldBlockCount = toFiniteNumber(counters?.min_hold_block_count) ?? 0;
  const cooldownBlockCount = toFiniteNumber(counters?.cooldown_block_count) ?? 0;
  const heldDupBlockCount = Math.max(rawSignals - buyCandidates - minHoldBlockCount - cooldownBlockCount, 0);
  const mfRankAppliedDays = toFiniteNumber(counters?.mf_rank_applied_days) ?? 0;
  const mfTopkRejectCount = toFiniteNumber(counters?.mf_topk_reject_count) ?? 0;
  const rankActuallyApplied = mfRankAppliedDays > 0 || mfTopkRejectCount > 0;

  return buyStageRows.map((rowDef) => {
    const key = String(rowDef?.stage_key || '').toLowerCase();
    const inputCount = toFiniteNumber(rowDef?.input_count);
    const outputCount = toFiniteNumber(rowDef?.output_count);
    const filteredCount = toFiniteNumber(rowDef?.filtered_count);
    let note = String(rowDef?.note || '');
    let rawItems = buildBaseRawItems({
      input_count: inputCount,
      output_count: outputCount,
      filtered_count: filteredCount,
    });
    if (key === 's4') {
      const noRawSignalCount = inputCount === null ? null : Math.max(inputCount - rawSignals, 0);
      if (!note) {
        note = `Tradable stock-day events compressed into raw buy signals; no raw trigger=${fmtInt(noRawSignalCount)}, held/cooldown blocks=${fmtInt(heldDupBlockCount + minHoldBlockCount + cooldownBlockCount)}`;
      }
      rawItems = rawItems.concat([
        { label: 'RAW_SIGNAL_CNT', value: rawSignals },
        { label: 'NO_RAW_SIGNAL', value: noRawSignalCount },
        { label: 'HELD_DUP_BLOCK', value: heldDupBlockCount },
        { label: 'MIN_HOLD_BLOCK', value: minHoldBlockCount },
        { label: 'COOLDOWN_BLOCK', value: cooldownBlockCount },
      ].filter((item) => toFiniteNumber(item.value) !== null));
    }
    if (key === 's5') {
      if (!note) {
        note = rankActuallyApplied
          ? `Ranking actually applied; top-k truncation=${fmtInt(mfTopkRejectCount)}`
          : 'No independent rank truncation was applied on this baseline.';
      }
      rawItems = rawItems.concat([
        { label: 'MF_RANK_APPLIED_DAYS', value: mfRankAppliedDays },
        { label: 'MF_TOPK_REJECT_CNT', value: mfTopkRejectCount },
      ].filter((item) => toFiniteNumber(item.value) !== null));
    }
    if (key === 's6') {
      rawItems = rawItems.concat([
        { label: 'BUY_ORDER_CNT', value: buyOrders },
        { label: 'ABOVE_SLOW_MA_BLOCK', value: toFiniteNumber(counters?.entry_above_slow_ma_block_count) },
        { label: 'SLOPE_BLOCK', value: toFiniteNumber(counters?.entry_slope_block_count) },
      ].filter((item) => toFiniteNumber(item.value) !== null));
    }
    if (key === 's7') {
      rawItems = rawItems.concat([
        { label: 'BUY_ORDER_CNT', value: buyOrders },
        { label: 'AVG_POSITIONS', value: toFiniteNumber(counters?.avg_positions) },
        { label: 'MAX_POSITIONS', value: toFiniteNumber(counters?.max_positions) },
      ].filter((item) => toFiniteNumber(item.value) !== null));
    }
    return {
      ...rowDef,
      input_count: inputCount,
      output_count: outputCount,
      filtered_count: filteredCount,
      note,
      raw_items: rawItems,
    };
  });
}

export function renderUnifiedStageFunnel(stageRows, counters, exitRows) {
  const rows = Array.isArray(stageRows) ? stageRows.map((row) => ({ ...row })) : [];
  if (!rows.length) {
    return '<div class="wb-mini">No stage counters are available for this experiment.</div>';
  }

  const maxValue = Math.max(1, ...rows.map((row) => (
    toFiniteNumber(row.output_count)
    ?? toFiniteNumber(row.input_count)
    ?? toFiniteNumber(row.filtered_count)
    ?? 0
  )));
  const ratioText = (numerator, denominator) => {
    const n = toFiniteNumber(numerator);
    const d = toFiniteNumber(denominator);
    return n !== null && d !== null && d > 0 ? fmtPct(n / d) : '-';
  };

  const body = rows.map((row) => {
    const key = String(row.stage_key || '').toLowerCase();
    const available = row.available !== false;
    const note = String(row.note || (available ? 'Counted by backend.' : 'Unavailable in current runtime.'));
    const inputCount = toFiniteNumber(row.input_count);
    const outputCount = toFiniteNumber(row.output_count);
    const filteredCount = toFiniteNumber(row.filtered_count);
    let extraHtml = '';
    let rawItems = Array.isArray(row.raw_items) ? row.raw_items : [];

    if (key === 's8') {
      extraHtml = `<div class="wb-stage-track-grid">${renderStageTrackCard('S8 Buy Side', [
        { label: 'CASH_SKIP', value: toFiniteNumber(counters?.cash_skip_count) },
        { label: 'LOT_SKIP', value: toFiniteNumber(counters?.lot_skip_count) },
        { label: 'SINGLE_CAP', value: toFiniteNumber(counters?.cap_hit_single) },
        { label: 'INDUSTRY_CAP', value: toFiniteNumber(counters?.cap_hit_industry) },
      ], 'No separate buy-side counts')}${renderStageTrackCard('S8 Sell Side', [
        { label: 'DD_REDUCED', value: toFiniteNumber(counters?.dd_reduced_count) },
        { label: 'DD_SCALE_08', value: toFiniteNumber(counters?.dd_scale_08_count) },
        { label: 'DD_SCALE_06', value: toFiniteNumber(counters?.dd_scale_06_count) },
        { label: 'DD_FIXED_03', value: toFiniteNumber(counters?.dd_fixed_03_count) },
        { label: 'DD_STOP', value: toFiniteNumber(counters?.dd_stop_count) },
      ], 'No separate sell-side counts')}</div>`;
    } else if (key === 's9') {
      rawItems = [
        { label: 'SELL_ORDER_CNT', value: toFiniteNumber(counters?.sell_orders_count) },
        { label: 'CLOSED_TRADE_CNT', value: toFiniteNumber(counters?.closed_trades) },
      ].filter((item) => item.value !== null);
      const normalizedExitRows = (Array.isArray(exitRows) ? exitRows : [])
        .map((item) => ({
          code: reasonCodeOf(item),
          value: toFiniteNumber(item?.count) ?? 0,
        }))
        .filter((item) => item.code && item.value > 0)
        .sort((a, b) => b.value - a.value);
      const exitTotal = normalizedExitRows.reduce((sum, item) => sum + item.value, 0);
      extraHtml = normalizedExitRows.length
        ? `<div class="wb-stage-exit-stack"><div class="wb-stage-exit-head">S9 Exit Reasons | Total ${fmtInt(exitTotal)}</div>${normalizedExitRows.map((item) => {
            const ratio = exitTotal > 0 ? item.value / exitTotal : 0;
            return `<div class="wb-stage-exit-row"><div class="wb-stage-exit-meta"><span class="wb-stage-exit-name">${esc(reasonZh(item.code))} <span class="wb-stage-exit-code">${esc(item.code)}</span></span><span class="wb-stage-exit-count">${fmtInt(item.value)} | ${fmtPct(ratio)}</span></div><div class="wb-stage-exit-bar"><span style="width:${Math.max(6, ratio * 100)}%"></span></div></div>`;
          }).join('')}</div>`
        : '';
    }

    const inputText = inputCount !== null ? fmtInt(inputCount) : '-';
    const outputText = outputCount !== null ? fmtInt(outputCount) : '-';
    const filteredText = filteredCount !== null ? fmtInt(filteredCount) : '-';
    const width = outputCount !== null ? Math.max(6, (outputCount / maxValue) * 100) : 0;

    return `<div class="wb-funnel-row ${stageClass(key)}${available ? '' : ' wb-funnel-unavailable'}"><div class="wb-funnel-row-head"><div class="wb-funnel-row-title">${esc(row.stage_label || row.title || row.stage_key || 'Stage')}</div><div class="wb-funnel-row-note">${esc(note)}</div></div><div class="wb-bar"><span style="width:${width}%"></span></div><div class="wb-funnel-row-meta"><div><span>Input</span><strong>${inputText}</strong></div><div><span>Keep</span><strong>${outputText}</strong></div><div><span>Filtered</span><strong>${filteredText}</strong></div></div>${renderStageCountPills(rawItems, available ? 'No extra counters' : 'No separate counters')}${inputCount !== null ? `<div class="wb-funnel-row-stats"><span>Keep rate ${ratioText(outputCount, inputCount)}</span><span>Filter rate ${ratioText(filteredCount, inputCount)}</span></div>` : ''}${extraHtml}</div>`;
  }).join('');

  const totals = rows.reduce((acc, row) => {
    acc.input += toFiniteNumber(row.input_count) ?? 0;
    acc.output += toFiniteNumber(row.output_count) ?? 0;
    acc.filtered += toFiniteNumber(row.filtered_count) ?? 0;
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
    meta: `Buy ${fmtInt(counters?.buy_orders_count ?? 0)} | Sell ${fmtInt(counters?.sell_orders_count ?? 0)} | Stage=${fmtInt(stageRows.length)}`,
    stageRows,
    exitRows,
  };
}
function normalizeMetricItems(items = [], formatter = fmtInt) {
  return (Array.isArray(items) ? items : [])
    .map((item) => {
      const label = String(item?.label || '').trim();
      const value = toFiniteNumber(item?.value);
      if (!label || value === null) return null;
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
  if (key === 's1') return { label: 'Derived', tone: 'derived' };
  if (row?.available === false) return { label: 'Unavailable', tone: 'missing' };
  return { label: 'Counted', tone: 'ok' };
}

function stageMetrics(row, counters) {
  const key = String(row?.stage_key || '').toLowerCase();
  const items = [];
  const inputCount = toFiniteNumber(row?.input_count);
  const outputCount = toFiniteNumber(row?.output_count);
  const filteredCount = toFiniteNumber(row?.filtered_count);
  if (inputCount !== null) items.push({ label: 'Input', text: fmtInt(inputCount) });
  if (outputCount !== null) items.push({ label: 'Keep', text: fmtInt(outputCount) });
  if (filteredCount !== null) items.push({ label: 'Filtered', text: fmtInt(filteredCount) });
  if (key === 's2') {
    items.push(
      { label: 'MAIN_DAYS', text: fmtInt(counters?.trade_mode_main_days ?? 0) },
      { label: 'LIGHT_DAYS', text: fmtInt(counters?.trade_mode_light_days ?? 0) },
      { label: 'NO_TRADE_DAYS', text: fmtInt(counters?.trade_mode_notrade_days ?? 0) },
    );
  }
  if (key === 's3' && !items.length) items.push({ label: 'State', text: 'Unavailable' });
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
      value: toFiniteNumber(row?.count) ?? 0,
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
  if (missingStages.length) notes.push(`Missing separate counts: ${missingStages.join(' / ')}`);
  if (Number(counters?.cash_skip_count ?? 0) > 0) notes.push('S8 buy-side losses are dominated by cash or lot constraints.');
  if (Number(counters?.mf_topk_reject_count ?? 0) > 0) notes.push('S5 includes rank/top-k truncation diagnostics.');
  if (Number(counters?.sell_orders_count ?? 0) > 0) notes.push('S9 is sourced from exit reason counts, not the buy funnel.');
  return notes;
}

export function buildUnifiedStageFunnelModel(snapshot) {
  const artifacts = snapshot?.artifacts || {};
  const counters = artifacts?.run_meta?.counters || {};
  const stageRows = buildStageRows(artifacts, counters);
  const exitRows = reasonByPrefix(artifacts.reasonRows || []).exit || [];
  const rowMap = new Map(stageRows.map((row) => [String(row?.stage_key || '').toLowerCase(), row]));
  const rawSignalCount = (Array.isArray(artifacts?.dailyRows) ? artifacts.dailyRows : []).reduce(
    (sum, row) => sum + (toFiniteNumber(row?.raw_buy_signal_count) ?? 0),
    0,
  );
  const stageOrder = ['s1', 's2', 's3', 's4', 's5', 's6', 's7'];
  const chainStages = stageOrder.map((key) => {
    const row = rowMap.get(key) || {
      stage_key: key,
      stage_label: key.toUpperCase(),
      available: false,
      note: 'No data for this stage.',
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
    meta: `Buy ${fmtInt(counters?.buy_orders_count ?? 0)} | Sell ${fmtInt(counters?.sell_orders_count ?? 0)} | Stages=${fmtInt(chainStages.length)}`,
    summaryCards: [
      { label: 'Universe', value: fmtInt(toFiniteNumber(rowMap.get('s1')?.output_count) ?? toFiniteNumber(artifacts?.run_meta?.universe?.after_filters_symbols) ?? 0) },
      { label: 'Raw Buys', value: fmtInt(rawSignalCount) },
      { label: 'Post Rank', value: fmtInt(rowMap.get('s5')?.output_count) },
      { label: 'Buy Orders', value: fmtInt(counters?.buy_orders_count ?? 0) },
      { label: 'Sell Orders', value: fmtInt(counters?.sell_orders_count ?? 0) },
    ],
    chainStages,
    execution: executionBuckets(counters),
    exitReasons: exitReasonItems(exitRows),
    completenessNotes: completenessNotes(stageRows, counters),
  };
}

function buildReadableStageMetrics(row, counters) {
  const metrics = [];
  const inputCount = toFiniteNumber(row?.input_count);
  const outputCount = toFiniteNumber(row?.output_count);
  const filteredCount = toFiniteNumber(row?.filtered_count);
  if (inputCount !== null) metrics.push({ label: 'Input', text: fmtInt(inputCount) });
  if (outputCount !== null) metrics.push({ label: 'Keep', text: fmtInt(outputCount) });
  if (filteredCount !== null) metrics.push({ label: 'Filtered', text: fmtInt(filteredCount) });
  if (String(row?.stage_key || '').toLowerCase() === 's2') {
    metrics.push(
      { label: 'Main Days', text: fmtInt(counters?.trade_mode_main_days ?? 0) },
      { label: 'Light Days', text: fmtInt(counters?.trade_mode_light_days ?? 0) },
      { label: 'No Trade Days', text: fmtInt(counters?.trade_mode_notrade_days ?? 0) },
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
  if (missingStages.length) notes.push(`Missing separate counts: ${missingStages.join(' / ')}`);
  if (Number(counters?.cash_skip_count ?? 0) > 0) notes.push('S8 directly shows cash and lot constraints.');
  if (Number(counters?.mf_topk_reject_count ?? 0) > 0) notes.push('S5 includes rank truncation diagnostics.');
  if (Number(counters?.sell_orders_count ?? 0) > 0) notes.push('S9 is sourced from exit reasons only.');
  if (!notes.length) notes.push('No additional funnel warnings.');
  return notes;
}

export function buildReadableStageFunnelModel(snapshot) {
  const artifacts = snapshot?.artifacts || {};
  const counters = artifacts?.run_meta?.counters || {};
  const stageRows = buildStageRows(artifacts, counters);
  const exitRows = reasonByPrefix(artifacts.reasonRows || []).exit || [];
  const rowMap = new Map(stageRows.map((row) => [String(row?.stage_key || '').toLowerCase(), row]));
  const rawSignalCount = (Array.isArray(artifacts?.dailyRows) ? artifacts.dailyRows : []).reduce(
    (sum, row) => sum + (toFiniteNumber(row?.raw_buy_signal_count) ?? 0),
    0,
  );
  const chainStages = ['s1', 's2', 's3', 's4', 's5', 's6', 's7'].map((key) => {
    const row = rowMap.get(key) || {
      stage_key: key,
      stage_label: key.toUpperCase(),
      available: false,
      note: 'No data for this stage.',
    };
    const tone = key === 's1' ? 'derived' : row.available === false ? 'missing' : 'ok';
    const label = tone === 'derived' ? 'Derived' : tone === 'missing' ? 'Unavailable' : 'Counted';
    return {
      key,
      title: row.stage_label || key.toUpperCase(),
      note: String(row.note || 'No additional note.'),
      status: { tone, label },
      metrics: buildReadableStageMetrics(row, counters),
      pills: buildReadableStagePills(row, counters),
    };
  });
  const normalizedExitReasons = (Array.isArray(exitRows) ? exitRows : [])
    .map((row) => ({
      code: reasonCodeOf(row),
      label: reasonZh(reasonCodeOf(row)),
      value: toFiniteNumber(row?.count) ?? 0,
    }))
    .filter((row) => row.code && row.value > 0)
    .sort((a, b) => b.value - a.value);
  const exitTotal = normalizedExitReasons.reduce((sum, row) => sum + row.value, 0);
  return {
    meta: `Buy ${fmtInt(counters?.buy_orders_count ?? 0)} | Sell ${fmtInt(counters?.sell_orders_count ?? 0)} | Main chain ${fmtInt(chainStages.length)} stages`,
    summaryCards: [
      { label: 'Universe', value: fmtInt(toFiniteNumber(rowMap.get('s1')?.output_count) ?? toFiniteNumber(artifacts?.run_meta?.universe?.after_filters_symbols) ?? 0) },
      { label: 'Raw Buys', value: fmtInt(rawSignalCount) },
      { label: 'Post Rank', value: fmtInt(rowMap.get('s5')?.output_count) },
      { label: 'Buy Orders', value: fmtInt(counters?.buy_orders_count ?? 0) },
      { label: 'Sell Orders', value: fmtInt(counters?.sell_orders_count ?? 0) },
    ],
    chainStages,
    execution: {
      buySide: normalizeMetricItems([
        { label: 'Cash Skip', value: counters?.cash_skip_count ?? 0 },
        { label: 'Lot Skip', value: counters?.lot_skip_count ?? 0 },
        { label: 'Single Cap', value: counters?.cap_hit_single ?? 0 },
        { label: 'Industry Cap', value: counters?.cap_hit_industry ?? 0 },
      ]),
      sellSide: normalizeMetricItems([
        { label: 'DD Reduced', value: counters?.dd_reduced_count ?? 0 },
        { label: 'DD Scale 0.8', value: counters?.dd_scale_08_count ?? 0 },
        { label: 'DD Scale 0.6', value: counters?.dd_scale_06_count ?? 0 },
        { label: 'DD Fixed 0.3', value: counters?.dd_fixed_03_count ?? 0 },
        { label: 'DD Stop', value: counters?.dd_stop_count ?? 0 },
      ]),
    },
    exitReasons: normalizedExitReasons.map((row) => ({
      ...row,
      ratio: exitTotal > 0 ? row.value / exitTotal : 0,
      ratioText: exitTotal > 0 ? fmtPct(row.value / exitTotal) : '-',
      text: fmtInt(row.value),
    })),
    completenessNotes: buildReadableCompletenessNotes(stageRows, counters),
  };
}
