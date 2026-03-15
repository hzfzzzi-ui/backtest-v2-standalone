(function initWorkbenchStateSlice(globalScope) {
  globalScope.createWorkbenchConfigDraftState = function createWorkbenchConfigDraftState() {
    return {
      config_id: null,
      loaded_config_meta: null,
      loaded_config_json: null,
      loaded_config_snapshot: '',
      config_source_mode: 'draft-only',
      config_dirty: false,
      selected_locked_candidate_preset: '',
      config_draft: {},
      universe_stats: null,
      multi_alpha_module_state: {},
      multi_alpha_validation_errors: [],
    };
  };
})(window);
