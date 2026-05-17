(function initStudyJournal() {
  if (new URLSearchParams(window.location.search).get('embedded') === '1') {
    document.body.classList.add('sj-embedded');
  }

  const state = {
    rounds: [],
    active: null,
    activeIsNew: false,
    conclusions: [],
    showAllConclusions: false,
    filter: '',
  };

  const $ = (id) => document.getElementById(id);

  function splitList(value) {
    return String(value || '')
      .split(/[\n,，]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function joinList(values) {
    return Array.isArray(values) ? values.join('\n') : '';
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function toast(message) {
    const el = $('sjToast');
    el.textContent = message;
    el.hidden = false;
    window.clearTimeout(toast._timer);
    toast._timer = window.setTimeout(() => {
      el.hidden = true;
    }, 2600);
  }

  async function apiJson(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...(options.headers || {}),
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.detail || `HTTP ${response.status}`);
    }
    return payload;
  }

  function fmtDate(value) {
    if (!value) return '-';
    return String(value).replace('T', ' ').replace(/\+.*/, '');
  }

  function fmtPct(value) {
    if (value === null || value === undefined || value === '') return '-';
    const num = Number(value);
    if (!Number.isFinite(num)) return '-';
    return `${(num * 100).toFixed(2)}%`;
  }

  function currentStudyId() {
    return String((state.active && state.active.study_id) || ($('sjStudyId') && $('sjStudyId').value) || '').trim();
  }

  function humanizeWindow(value) {
    const key = String(value || '').trim();
    const labels = {
      1217: '2012-2017 硬门槛',
      1226: '2012-2026 全周期',
      1626: '2016-2026 主开发',
    };
    return labels[key] || key || '-';
  }

  function humanizeVariant(value) {
    const key = String(value || '').trim();
    const labels = {
      CURRENT_FORMAL_COMBO_REPLAY: '正式组合回放',
      DOMESTIC_POOL_BASE: '剔除跨境 ETF',
      FORMAL_POOL_ROTATION_CONTROL: '正式 ETF 池轮动对照',
      INDUSTRY_THEME_POOL_V2: '行业主题扩展池',
      REALWORLD_POOL_V1: '真实世界 ETF 池',
      SHADOW_POOL_V1: '影子 ETF 池',
      STYLE_SMART_BETA_POOL_V2: '风格 / Smart Beta 扩展池',
    };
    return labels[key] || key || '-';
  }

  function linkedExpIds() {
    const evidence = state.active && Array.isArray(state.active.evidence) ? state.active.evidence : [];
    return new Set(evidence.map((item) => String(item && item.exp_id || '').trim()).filter(Boolean));
  }

  function renderList() {
    const host = $('sjRoundList');
    const needle = state.filter.trim().toLowerCase();
    const items = state.rounds.filter((item) => {
      const haystack = [
        item.title,
        item.round_id,
        item.study_id,
        item.baseline_id,
        ...(Array.isArray(item.tags) ? item.tags : []),
      ].join(' ').toLowerCase();
      return !needle || haystack.includes(needle);
    });
    $('sjRoundCount').textContent = String(items.length);
    if (!items.length) {
      host.innerHTML = '<div class="sj-empty">没有研究轮次</div>';
      return;
    }
    host.innerHTML = items.map((item) => {
      const active = state.active && state.active.round_id === item.round_id ? ' active' : '';
      return `
        <button type="button" class="sj-round-row${active}" data-round-id="${escapeHtml(item.round_id)}">
          <strong>${escapeHtml(item.title || item.round_id)}</strong>
          <div class="sj-row-meta">${escapeHtml(item.status || '-') } · ${escapeHtml(item.reliability || '-')}</div>
          <div class="sj-row-meta sj-mono">${escapeHtml(item.study_id || '-')}</div>
          <div class="sj-row-meta">${escapeHtml(fmtDate(item.updated_at))}</div>
        </button>
      `;
    }).join('');
    host.querySelectorAll('[data-round-id]').forEach((button) => {
      button.addEventListener('click', () => loadRound(button.dataset.roundId));
    });
  }

  function setValue(id, value) {
    $(id).value = value == null ? '' : String(value);
  }

  function setChecked(id, value) {
    $(id).checked = Boolean(value);
  }

  function renderArrayList(id, values) {
    const list = Array.isArray(values) ? values : [];
    $(id).innerHTML = list.length
      ? list.map((item) => `<li>${escapeHtml(item)}</li>`).join('')
      : '<li class="sj-muted">-</li>';
  }

  function renderMetrics(summary) {
    const rows = Array.isArray(summary.metric_highlights) ? summary.metric_highlights : [];
    if (!rows.length) {
      $('sjMetricTable').innerHTML = '<div class="sj-empty">没有可展示指标</div>';
      return;
    }
    $('sjMetricTable').innerHTML = `
      <table>
        <thead>
          <tr>
            <th>exp_id</th>
            <th>window</th>
            <th>variant</th>
            <th>CAGR Δ</th>
            <th>Sharpe Δ</th>
            <th>MaxDD Δ</th>
            <th>Calmar Δ</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td class="sj-mono">${escapeHtml(row.exp_id || '-')}</td>
              <td class="sj-mono">${escapeHtml(row.window_key || '-')}</td>
              <td class="sj-mono">${escapeHtml(row.variant_name || '-')}</td>
              <td>${escapeHtml(fmtPct(row.cagr && row.cagr.delta))}</td>
              <td>${escapeHtml(row.sharpe && row.sharpe.delta != null ? Number(row.sharpe.delta).toFixed(3) : '-')}</td>
              <td>${escapeHtml(fmtPct(row.max_drawdown && row.max_drawdown.delta))}</td>
              <td>${escapeHtml(row.calmar && row.calmar.delta != null ? Number(row.calmar.delta).toFixed(3) : '-')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  function renderEvidence(record) {
    const items = Array.isArray(record.evidence) ? record.evidence : [];
    $('sjEvidenceList').innerHTML = items.length ? items.map((item) => `
      <div class="sj-evidence-item">
        <div class="sj-mono">${escapeHtml(item.exp_id || '-')}</div>
        <div class="sj-row-meta">${escapeHtml(item.window_key || '-') } · ${escapeHtml(item.variant_name || '-')}</div>
        <div class="sj-row-meta">${escapeHtml(item.note || item.path || '')}</div>
      </div>
    `).join('') : '<div class="sj-empty">没有关联证据</div>';
  }

  function renderNotes(record) {
    const notes = Array.isArray(record.notes) ? record.notes : [];
    $('sjNotes').innerHTML = notes.length ? notes.map((note) => `
      <div class="sj-note">
        <div class="sj-row-meta">${escapeHtml(note.kind || 'note')} · ${escapeHtml(fmtDate(note.created_at))}</div>
        <div>${escapeHtml(note.body || '')}</div>
      </div>
    `).join('') : '<div class="sj-empty">没有备注</div>';
  }

  function renderConclusions() {
    const items = state.conclusions.slice(0, 50);
    const scope = state.showAllConclusions
      ? `显示全部 registry：${state.conclusions.length} 条`
      : `当前 study：${currentStudyId() || '未填写'}，匹配 ${state.conclusions.length} 条`;
    const scopeEl = $('sjConclusionScope');
    if (scopeEl) scopeEl.textContent = scope;
    const linked = linkedExpIds();
    $('sjConclusionList').innerHTML = items.length ? items.map((item, index) => {
      const expId = String(item.exp_id || '').trim();
      const alreadyLinked = expId && linked.has(expId);
      const disabled = !expId || alreadyLinked;
      const buttonText = !expId ? '无 exp_id' : (alreadyLinked ? '已关联' : '关联');
      return `
      <div class="sj-conclusion-item${alreadyLinked ? ' is-linked' : ''}">
        <div class="sj-conclusion-title">
          <span class="sj-mono">${escapeHtml(item.exp_id || '-')}</span>
          <span class="sj-badge sj-badge-small">${escapeHtml(item.verdict || 'UNKNOWN')}</span>
        </div>
        <div class="sj-row-meta">窗口：${escapeHtml(humanizeWindow(item.window_key))}</div>
        <div class="sj-row-meta">变体：${escapeHtml(humanizeVariant(item.variant_name))}</div>
        <div class="sj-row-meta sj-mono">${escapeHtml(item.study_id || '')}</div>
        <button type="button" class="sj-btn sj-btn-small" data-conclusion-index="${index}" ${disabled ? 'disabled' : ''}>${buttonText}</button>
      </div>
    `;
    }).join('') : '<div class="sj-empty">当前 study 没有可关联 registry 记录，可勾选“显示全部”查看相邻研究。</div>';
    $('sjConclusionList').querySelectorAll('[data-conclusion-index]').forEach((button) => {
      button.addEventListener('click', () => linkConclusion(Number(button.dataset.conclusionIndex)));
    });
  }

  function renderDetail(record) {
    state.active = record;
    state.activeIsNew = false;
    $('sjRoundId').textContent = record.round_id || '未保存';
    setValue('sjTitle', record.title);
    setValue('sjStatus', record.status || 'draft');
    setValue('sjAssetScope', record.asset_scope);
    setValue('sjStudyId', record.study_id);
    setValue('sjBaselineId', record.baseline_id);
    setValue('sjQuestion', record.primary_question);
    setValue('sjPrimaryVariable', record.primary_variable);
    setValue('sjTags', (record.tags || []).join(', '));
    setValue('sjWindows', (record.windows || []).join(','));
    setValue('sjVariants', (record.variants || []).join(','));
    setValue('sjAssumptions', joinList(record.fixed_assumptions));
    setValue('sjFindings', joinList(record.key_findings));
    const audit = record.audit || {};
    setChecked('sjAuditSameWindow', audit.same_window_compare);
    setChecked('sjAuditConfig', audit.config_truth_checked);
    setChecked('sjAuditNav', audit.nav_lineage_checked);
    setChecked('sjAuditDocker', audit.docker_run_checked);
    const decision = record.decision || {};
    setValue('sjDecisionStatus', decision.status || 'draft');
    setValue('sjDecisionReason', decision.reason || '');

    const summary = record.auto_summary || {};
    $('sjSummaryHeadline').textContent = summary.headline || '-';
    $('sjSummaryDraft').textContent = summary.conclusion_draft || '-';
    $('sjReliability').textContent = summary.reliability || record.reliability || 'low';
    $('sjGeneratedAt').textContent = fmtDate(summary.generated_at);
    renderArrayList('sjFacts', summary.facts || []);
    renderArrayList('sjRisks', summary.risks || []);
    renderArrayList('sjNextActions', summary.next_actions || []);
    renderMetrics(summary);
    renderEvidence(record);
    renderNotes(record);
    renderConclusions();
    renderList();
  }

  function collectForm() {
    return {
      round_id: state.active && state.active.round_id,
      title: $('sjTitle').value.trim(),
      status: $('sjStatus').value,
      asset_scope: $('sjAssetScope').value.trim(),
      study_id: $('sjStudyId').value.trim(),
      baseline_id: $('sjBaselineId').value.trim(),
      primary_question: $('sjQuestion').value.trim(),
      primary_variable: $('sjPrimaryVariable').value.trim(),
      tags: splitList($('sjTags').value),
      windows: splitList($('sjWindows').value),
      variants: splitList($('sjVariants').value),
      fixed_assumptions: splitList($('sjAssumptions').value),
      key_findings: splitList($('sjFindings').value),
      audit: {
        same_window_compare: $('sjAuditSameWindow').checked,
        config_truth_checked: $('sjAuditConfig').checked,
        nav_lineage_checked: $('sjAuditNav').checked,
        docker_run_checked: $('sjAuditDocker').checked,
      },
      decision: {
        status: $('sjDecisionStatus').value,
        reason: $('sjDecisionReason').value.trim(),
      },
    };
  }

  async function loadRounds() {
    const payload = await apiJson('/api/research/study-rounds');
    state.rounds = Array.isArray(payload.items) ? payload.items : [];
    renderList();
    if (!state.active && state.rounds.length) {
      await loadRound(state.rounds[0].round_id);
    }
  }

  async function loadRound(roundId) {
    const payload = await apiJson(`/api/research/study-rounds/${encodeURIComponent(roundId)}`);
    renderDetail(payload.item);
    await loadConclusions();
  }

  async function loadConclusions() {
    const params = new URLSearchParams({ limit: '200' });
    const studyId = currentStudyId();
    if (!state.showAllConclusions && !studyId) {
      state.conclusions = [];
      renderConclusions();
      return;
    }
    if (!state.showAllConclusions && studyId) {
      params.set('study_id', studyId);
    }
    const payload = await apiJson(`/api/research/study-conclusions?${params.toString()}`);
    state.conclusions = Array.isArray(payload.items) ? payload.items : [];
    renderConclusions();
  }

  function newRound() {
    const now = new Date();
    const roundId = `sr_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`;
    renderDetail({
      round_id: roundId,
      title: '未命名研究轮次',
      status: 'draft',
      audit: {},
      decision: { status: 'draft', reason: '' },
      evidence: [],
      notes: [],
      auto_summary: {
        headline: '未命名研究轮次',
        conclusion_draft: '尚未保存。',
        reliability: 'low',
        facts: [],
        risks: [],
        next_actions: [],
        metric_highlights: [],
      },
    });
    state.activeIsNew = true;
  }

  async function saveCurrent(event) {
    event.preventDefault();
    const body = collectForm();
    const isNew = state.activeIsNew;
    const url = isNew
      ? '/api/research/study-rounds'
      : `/api/research/study-rounds/${encodeURIComponent(state.active.round_id)}`;
    const payload = await apiJson(url, {
      method: isNew ? 'POST' : 'PATCH',
      body: JSON.stringify(body),
    });
    state.activeIsNew = false;
    await loadRounds();
    renderDetail(payload.item);
    await loadConclusions();
    toast('已保存');
  }

  async function refreshSummary() {
    if (!state.active || state.activeIsNew) {
      toast('先保存轮次');
      return;
    }
    const payload = await apiJson(`/api/research/study-rounds/${encodeURIComponent(state.active.round_id)}/summary/refresh`, {
      method: 'POST',
    });
    await loadRounds();
    renderDetail(payload.item);
    toast('总结已刷新');
  }

  async function addNote() {
    if (!state.active || state.activeIsNew) {
      toast('先保存轮次');
      return;
    }
    const body = $('sjNewNote').value.trim();
    if (!body) return;
    const payload = await apiJson(`/api/research/study-rounds/${encodeURIComponent(state.active.round_id)}/notes`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    });
    $('sjNewNote').value = '';
    await loadRounds();
    renderDetail(payload.item);
    toast('备注已追加');
  }

  async function linkExperiment(body) {
    if (!state.active || state.activeIsNew) {
      toast('先保存轮次');
      return;
    }
    const payload = await apiJson(`/api/research/study-rounds/${encodeURIComponent(state.active.round_id)}/links/experiment`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    await loadRounds();
    renderDetail(payload.item);
    await loadConclusions();
    toast('证据已关联');
  }

  async function linkManualExperiment() {
    const expId = $('sjLinkExpId').value.trim();
    if (!expId) return;
    await linkExperiment({
      exp_id: expId,
      study_id: $('sjStudyId').value.trim(),
      window_key: $('sjLinkWindow').value.trim(),
      variant_name: $('sjLinkVariant').value.trim(),
    });
    setValue('sjLinkExpId', '');
    setValue('sjLinkWindow', '');
    setValue('sjLinkVariant', '');
  }

  async function linkConclusion(index) {
    const item = state.conclusions[index];
    if (!item) return;
    await linkExperiment({
      exp_id: item.exp_id,
      study_id: item.study_id,
      window_key: item.window_key,
      variant_name: item.variant_name,
      note: item.summary_short || item.verdict || '',
    });
  }

  async function init() {
    $('sjRefreshBtn').addEventListener('click', async () => {
      await loadRounds();
      await loadConclusions();
      toast('已刷新');
    });
    $('sjNewBtn').addEventListener('click', newRound);
    $('sjRoundForm').addEventListener('submit', saveCurrent);
    $('sjRefreshSummaryBtn').addEventListener('click', refreshSummary);
    $('sjAddNoteBtn').addEventListener('click', addNote);
    $('sjLinkExpBtn').addEventListener('click', linkManualExperiment);
    $('sjReloadConclusionsBtn').addEventListener('click', loadConclusions);
    $('sjShowAllConclusions').addEventListener('change', async (event) => {
      state.showAllConclusions = event.target.checked;
      await loadConclusions();
    });
    $('sjFilter').addEventListener('input', (event) => {
      state.filter = event.target.value;
      renderList();
    });

    await loadRounds();
    await loadConclusions();
    if (!state.active) {
      newRound();
    }
  }

  init().catch((error) => {
    toast(error.message || String(error));
  });
})();
