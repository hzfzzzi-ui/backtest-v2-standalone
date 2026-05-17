(function initDesktopAppShellState(globalScope) {
  globalScope.createWorkbenchConfigDraftState = function createWorkbenchConfigDraftState() {
    return {
      loaded_source_meta: null,
      loaded_source_asset_context: null,
      loaded_source_config: null,
      loaded_source_snapshot: '',
      loaded_source_sync_mode: 'draft-only',
      loaded_source_dirty: false,
      selected_locked_candidate_preset: '',
      config_draft: {},
      universe_stats: null,
      multi_alpha_module_state: {},
      multi_alpha_validation_errors: [],
    };
  };

  globalScope.createRunSessionState = function createRunSessionState() {
    return {
      execution_preview: null,
      execution_api_enabled: true,
      market_data_sync_status: null,
      status_items: [],
      manual_status_items: [],
      validation_status_items: [],
      api_status: {},
      status_open: false,
    };
  };

  globalScope.createActiveExperimentState = function createActiveExperimentState() {
    return {
      active_exp: null,
      active_result: null,
      active_artifacts: null,
      active_manifest: null,
      active_surface_summary: null,
      active_asset_context: null,
      runtime_source_kind: '',
      runtime_source_id: '',
      loaded_source_kind: '',
      loaded_source_id: '',
    };
  };

  globalScope.createViewState = function createViewState() {
    return {
      mode: 'experiment',
      strategy_pack: 'EMA_CROSS',
      universe_mode: 'ALL_A',
      drawer_panel: 's1',
      drawer_pinned: false,
      main_tab: 'overview',
      dock_tab: 'explain',
      chart_show_benchmark: true,
      chart_range: 'D',
      chart_mode: 'portfolio',
      symbol_filter: '',
      symbol_sort: 'return_desc',
      selected_symbol: '',
      symbol_series_cache: {},
      symbol_series_loading: false,
    };
  };

  const DEFAULT_STAGE_IDS = ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9'];
  const DEFAULT_STAGE_CATALOG = [
    { panel: 's1', label: '资产池', title: '资产池与基础过滤' },
    { panel: 's2', label: '环境', title: '高级环境参数', hidden: true },
    { panel: 's3', label: '行业', title: '行业门控', hidden: true },
    { panel: 's4', label: '信号', title: '入场信号与组合' },
    { panel: 's5', label: '排序', title: '排序与候选保留' },
    { panel: 's6', label: '建仓', title: '建仓与组合约束' },
    { panel: 's7', label: '预算', title: '高级预算参数', hidden: true },
    { panel: 's8', label: '风险', title: '风险保护' },
    { panel: 's9', label: '退出', title: '退出规则' },
  ];
  const DEFAULT_WORKSPACE_REGISTRY = [
    { id: 'desktop_shell', role: 'host_shell' },
    { id: 'config_workspace', role: 'config_editor' },
    { id: 'run_orchestration', role: 'run_loader_save_hydrate' },
    { id: 'results_workspace', role: 'results_display' },
    { id: 'study_journal_workspace', role: 'research_journal_display' },
    { id: 'status_center', role: 'status_summary_only' },
  ];

  globalScope.createDesktopAppShellState = function createDesktopAppShellState() {
    return {
      desktop_shell: {
        shell_version: 'desktop-app-shell-v1',
        module_root: 'desktop_shell',
        root_mount_id: 'wbDesktopAppShell',
        results_mount_id: 'wbResultsWorkbenchMount',
        active_workspace: 'config_workspace',
        active_panel: 'config_workspace',
        mount_state: 'booting',
        shell_ready: false,
        api_boundary_owner: 'desktop_api_adapter',
        workspace_registry: DEFAULT_WORKSPACE_REGISTRY.map((item) => ({ ...item })),
      },
      config_workspace: {
        workspace_kind: 'config_workspace',
        source_mode: 'desktop_shell_config_workspace',
        shell_mode: 'single_page_desktop',
        active_stage: 's1',
        stage_ids: DEFAULT_STAGE_IDS.slice(),
        stage_catalog: DEFAULT_STAGE_CATALOG.map((item) => ({ ...item })),
        draft_source_kind: '',
        draft_source_id: '',
        draft_loaded: false,
        draft_dirty: false,
      },
      run_orchestration: {
        workspace_kind: 'run_orchestration',
        queue: [],
        active_job: null,
        history: [],
        loading: false,
        can_dispatch: true,
      },
      results_workspace: {
        workspace_kind: 'results_workspace',
        active_tab: 'overview',
        active_panel: 'overview',
        mounted: false,
        source_mode: 'desktop_shell_snapshot',
        bridge_ready: true,
      },
      study_journal_workspace: {
        workspace_kind: 'study_journal_workspace',
        mounted: false,
        source_mode: 'embedded_research_journal',
      },
      status_center: {
        workspace_kind: 'status_center',
        open: false,
        items: [],
        source: 'desktop_shell_status_center',
      },
    };
  };
})(window);
