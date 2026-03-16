(function initActiveExperimentStateSlice(globalScope) {
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
      compare_selected_ids: [],
    };
  };
})(window);
