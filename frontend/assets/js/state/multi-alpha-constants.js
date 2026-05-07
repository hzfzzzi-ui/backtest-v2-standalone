/* formal owner for shared multi-alpha constants */
(function initMultiAlphaConstants(globalScope) {
  const exportScope = typeof globalThis === 'object' && globalThis ? globalThis : globalScope;
  const expose = (name, value) => {
    globalScope[name] = value;
    if (exportScope && exportScope !== globalScope) exportScope[name] = value;
  };

  expose('COMPOSE_MODULES', [
    {
      name: 'breakout_55',
      label: 'Breakout 55',
      alpha_id: 'breakout_55',
      family: 'trend',
      role: 'trend',
      weight: 0.7,
      priority: 100,
    },
    {
      name: 'rsi_reversal',
      label: 'RSI Reversal',
      alpha_id: 'rsi_reversal',
      family: 'mean_revert',
      role: 'mean_revert',
      weight: 0.3,
      priority: 80,
    },
  ]);
  expose('MULTI_ALPHA_COMPOSE_MODE', 'REGIME_ROUTE');
  expose('MULTI_ALPHA_SAME_SYMBOL_POLICY', 'PREFER_HIGHER_SCORE');
  expose('MULTI_ALPHA_HOLDING_OWNERSHIP', 'SOURCE_ONLY');
  expose('MULTI_ALPHA_PORTFOLIO_MODE', 'hard_sleeve_budget');
  expose('MULTI_ALPHA_REGIMES', ['TREND_UP', 'RANGE', 'WEAK_DOWN']);
  expose('DEFAULT_MULTI_ALPHA_REGIME_MATRIX', {
    TREND_UP: ['breakout_55'],
    RANGE: ['breakout_55', 'rsi_reversal'],
    WEAK_DOWN: ['rsi_reversal'],
  });
})(window);
