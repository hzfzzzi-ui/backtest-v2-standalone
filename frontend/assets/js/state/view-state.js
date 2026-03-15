(function initViewStateSlice(globalScope) {
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
})(window);
