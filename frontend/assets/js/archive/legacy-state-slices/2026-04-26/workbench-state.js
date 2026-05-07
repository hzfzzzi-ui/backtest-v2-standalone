(function initWorkbenchStateSlice(globalScope) {
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
})(window);
