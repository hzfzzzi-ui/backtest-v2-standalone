(function initActiveExperimentStateSlice(globalScope) {
  globalScope.createActiveExperimentState = function createActiveExperimentState() {
    return {
      active_exp: null,
      active_result: null,
      active_artifacts: null,
      loaded_source_kind: '',
      loaded_source_id: '',
      compare_selected_ids: [],
    };
  };
})(window);
