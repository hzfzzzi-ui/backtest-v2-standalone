(function initDesktopConfigControls(globalScope) {
  async function loadConfig(configId) {
    const j = await apiRequestJson('configs_get', `/api/backtest_v2/configs/${encodeURIComponent(configId)}`);
    state.loaded_config_json = cloneJson(j.config_json || {});
    const applied = applyConfigToUI(j.config_json || {});
    if (applied?.unsupportedStrategy) {
      clearLoadedConfig(`配置 ${j.config_id} 使用已移除策略 ${applied.unsupportedStrategy}；请改用 REGIME_ROUTER 重新配置`);
      byId('wbRunStatus').textContent = `配置 ${j.config_id} 使用已移除策略 ${applied.unsupportedStrategy}`;
      return;
    }
    setSelectedLockedCandidatePreset('');
    rememberLoadedConfig(j, stableSerializeConfig(state.config_draft || {}), j.config_json || {});
    addLog(`已加载配置: ${j.config_id}`);
  }

  async function loadConfigList() {
    const j = await apiRequestJson('configs_list', '/api/backtest_v2/configs?latest=50');
    const items = Array.isArray(j.items) ? j.items : [];
    const sel = byId('wbConfigList');
    if (!sel) return items;
    sel.innerHTML = '<option value="">选择配置...</option>' + items.map((x) => {
      const label = `${configMetaLabel(x)} ${configDisplayName(x) || x.config_id}`;
      return `<option value="${esc(x.config_id)}">${esc(label)} | ${esc(x.saved_at || '')}</option>`;
    }).join('');
    return items;
  }

  function configCenterBadgeText(item) {
    const sourceMap = { baseline: '基线', search: '搜索', template: '内置', derived: '保存' };
    const ownerMap = { manual: '手工', claude: 'Codex', script: '脚本', builtin: '内置' };
    const parts = [];
    const source = sourceMap[String(item?.source_type || '').trim()] || String(item?.source_type || '').trim() || '保存';
    const owner = ownerMap[String(item?.owner || '').trim()] || String(item?.owner || '').trim() || '手工';
    parts.push(source, owner);
    if (item?.locked) parts.push('锁定');
    return parts.join(' / ');
  }

  function buildConfigCenterGroups(items) {
    const builtin = [];
    const saved = [];
    (Array.isArray(items) ? items : []).forEach((item) => {
      const tags = new Set((Array.isArray(item?.tags) ? item.tags : []).map((tag) => String(tag || '').trim().toLowerCase()));
      if (String(item?.owner || '').trim().toLowerCase() === 'builtin' || tags.has('builtin') || String(item?.source_type || '').trim().toLowerCase() === 'template') {
        builtin.push(item);
        return;
      }
      saved.push(item);
    });
    return {
      draft: [
        {
          key: 'draft',
          title: '当前草稿',
          desc: state.loaded_config_meta?.config_id ? '脱离已加载配置 provenance，后续运行只认当前页面草稿' : '直接使用当前页面草稿作为运行真相',
          active: !String(state.selected_locked_candidate_preset || '').trim() && (!state.loaded_config_meta || currentConfigSourceMode() === 'loaded-dirty'),
          onClick: () => {
            setSelectedLockedCandidatePreset('');
            clearLoadedConfig('已切换到当前草稿');
          },
        },
      ],
      candidate: Object.keys(LOCKED_CANDIDATE_PRESETS).map((preset) => ({
        key: `candidate:${preset}`,
        title: preset === 'v2-breakout-br35-atr10-candidate' ? '候选 BR35 + ATR1.0' : '候选 ATR 1.0',
        desc: lockedCandidatePresetMeta(preset)?.hint || '锁定候选入口',
        active: String(state.selected_locked_candidate_preset || '').trim() === preset,
        onClick: () => {
          setSelectedLockedCandidatePreset(preset);
          addLog(`已选择锁定候选: ${preset}`);
        },
      })),
      builtin: builtin.map((item) => ({
        key: `config:${item.config_id}`,
        title: configDisplayName(item) || item.config_id,
        desc: `${configCenterBadgeText(item)} | ${item.saved_at || ''}`,
        active: !String(state.selected_locked_candidate_preset || '').trim() && currentConfigSourceMode() === 'loaded-clean' && String(state.loaded_config_meta?.config_id || '') === String(item.config_id || ''),
        onClick: async () => {
          await loadConfig(item.config_id);
        },
      })),
      saved: saved.map((item) => ({
        key: `config:${item.config_id}`,
        title: configDisplayName(item) || item.config_id,
        desc: `${configCenterBadgeText(item)} | ${item.saved_at || ''}`,
        active: !String(state.selected_locked_candidate_preset || '').trim() && currentConfigSourceMode() === 'loaded-clean' && String(state.loaded_config_meta?.config_id || '') === String(item.config_id || ''),
        onClick: async () => {
          await loadConfig(item.config_id);
        },
      })),
    };
  }

  async function openConfigCenterDropdown(anchorEl = null) {
    const existing = document.getElementById('wbConfigCenterDropdown');
    if (existing) {
      existing.remove();
      return;
    }
    const items = await loadConfigList();
    const groups = buildConfigCenterGroups(items);
    const dd = document.createElement('div');
    dd.id = 'wbConfigCenterDropdown';
    dd.className = 'wb-load-dropdown wb-config-center-dropdown';
    const sections = [
      ['当前草稿', groups.draft],
      ['锁定 Candidate', groups.candidate],
      ['内置模板', groups.builtin],
      ['已保存配置', groups.saved],
    ];
    sections.forEach(([label, rows]) => {
      if (!Array.isArray(rows) || !rows.length) return;
      const head = document.createElement('div');
      head.className = 'wb-config-center-section';
      head.textContent = label;
      dd.appendChild(head);
      rows.forEach((row) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = `wb-load-item wb-config-center-item${row.active ? ' active' : ''}`;
        item.innerHTML = `<span class="wb-config-center-title">${esc(row.title)}</span><span class="wb-config-center-desc">${esc(row.desc)}</span>`;
        item.addEventListener('click', async () => {
          dd.remove();
          try {
            await row.onClick();
          } catch (e) {
            addLog(`配置中心操作失败: ${e?.message || e}`);
          }
        });
        dd.appendChild(item);
      });
    });
    (anchorEl || byId('wbConfigCenterBtn') || byId('wbQuickLoad') || byId('wbRunBtn'))?.parentElement?.appendChild(dd);
    const dismiss = (e) => {
      const btn = anchorEl || byId('wbConfigCenterBtn') || byId('wbQuickLoad');
      if (!dd.contains(e.target) && e.target !== btn) {
        dd.remove();
        document.removeEventListener('click', dismiss);
      }
    };
    setTimeout(() => document.addEventListener('click', dismiss), 0);
  }

  function copyConfigJson() {
    navigator.clipboard?.writeText(JSON.stringify(state.config_draft || {}, null, 2));
    addLog('配置 JSON 已复制');
  }

  async function pasteConfigJson() {
    try {
      const text = await navigator.clipboard.readText();
      const obj = JSON.parse(text);
      applyConfigToUI(obj || {});
      clearLoadedConfig();
      addLog('已从剪贴板粘贴配置 JSON');
    } catch (e) {
      addLog(`粘贴 JSON 失败: ${e.message || e}`);
    }
  }

  globalScope.loadConfig = loadConfig;
  globalScope.loadConfigList = loadConfigList;
  globalScope.configCenterBadgeText = configCenterBadgeText;
  globalScope.buildConfigCenterGroups = buildConfigCenterGroups;
  globalScope.openConfigCenterDropdown = openConfigCenterDropdown;
  globalScope.copyConfigJson = copyConfigJson;
  globalScope.pasteConfigJson = pasteConfigJson;
})(window);
