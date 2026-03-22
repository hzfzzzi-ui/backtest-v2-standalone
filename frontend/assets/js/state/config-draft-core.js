/* config-draft-core.js: sole owner of desktop config compile/validate truth. */
(function initConfigDraftCore(globalScope) {
  function validateConfigDraftCore(draft) {
    const errors = [];
    const multiAlphaEnabled = hasPhase1MultiAlphaIntent(draft);
    if (multiAlphaEnabled) {
      errors.push(...validateMultiAlphaDraft(draft));
      return Array.from(new Set(errors));
    }
    const trend = (draft && draft.signal_generation && (draft.signal_generation.trend || draft.signal_generation.sma)) || {};
    const strategyPack = String((draft && (draft.strategy_pack || (draft.signal_generation && draft.signal_generation.strategy))) || '').toUpperCase();
    const regimeOn = !!(draft && draft.signal_generation && draft.signal_generation.regime_detection && draft.signal_generation.regime_detection.enabled);
    const fast = Number(trend.fast_ma);
    const slow = Number(trend.slow_ma);
    if (!(Number.isFinite(fast) && Number.isFinite(slow) && fast < slow)) errors.push('fast_ma must be smaller than slow_ma');
    const maxPos = Number(draft && draft.position_risk && draft.position_risk.max_positions);
    if (!(Number.isFinite(maxPos) && maxPos > 0)) errors.push('max_positions must be > 0');
    const singlePct = Number(draft && draft.position_risk && draft.position_risk.single_stock_cap) * 100;
    if (!(Number.isFinite(singlePct) && singlePct >= 0 && singlePct <= 100)) errors.push('single/industry cap must be within 0-100');
    const indPct = Number(draft && draft.position_risk && draft.position_risk.industry_cap) * 100;
    if (!(Number.isFinite(indPct) && indPct >= 0 && indPct <= 100)) errors.push('industry_cap must be within 0-100');
    const entry = Number((((draft && draft.signal_generation && (draft.signal_generation.trend || draft.signal_generation.sma)) || {}).entry_buffer_pct));
    if (!(Number.isFinite(entry) && entry >= 0 && entry <= 5)) errors.push('entry_buffer% must be within 0-5');
    if (strategyPack === 'RSI_REVERSAL' && !regimeOn) errors.push('RSI_REVERSAL is only supported as the MR arm under Regime Router');
    if (regimeOn && !['EMA_CROSS', 'SMA_CROSS'].includes(String(trend.strategy || '').toUpperCase())) {
      errors.push('Regime Router trend arm only supports EMA_CROSS / SMA_CROSS');
    }
    return errors;
  }

  function buildConfigDraftCore() {
    const loadedBase = cloneJson(state.loaded_source_config) || {};
    const loadedUniverse = loadedBase.universe || {};
    const loadedUniverseFilters = loadedUniverse.filters || {};
    const loadedSignalGeneration = loadedBase.signal_generation || {};
    const loadedSignalRegimeDetection = loadedSignalGeneration.regime_detection || {};
    const loadedSignalRegimeFilter = loadedSignalRegimeDetection.regime_filter || {};
    const loadedTrend = loadedSignalGeneration.trend || {};
    const loadedMr = loadedSignalGeneration.mr || {};
    const loadedSma = loadedSignalGeneration.sma || {};
    const loadedEma = loadedSignalGeneration.ema || {};
    const loadedBreakout = loadedSignalGeneration.breakout || {};
    const loadedEntryFilter = loadedSignalGeneration.entry_filter || {};
    const loadedRanking = loadedSignalGeneration.ranking || {};
    const loadedExitRules = loadedBase.exit_rules || {};
    const loadedAtrStop = loadedExitRules.atr_stop || {};
    const loadedTrailing = loadedExitRules.trailing || {};
    const loadedTimeExit = loadedExitRules.time_exit || {};
    const loadedHoldConstraint = loadedExitRules.hold_constraint || {};
    const loadedTakeProfit = loadedExitRules.take_profit || {};
    const loadedFixedStop = loadedExitRules.fixed_stop || {};
    const loadedMa20Exit = loadedExitRules.ma20_exit || {};
    const loadedLow10Exit = loadedExitRules.low10_exit || {};
    const loadedPositionRisk = loadedBase.position_risk || {};
    const loadedRiskBudget = loadedPositionRisk.risk_budget || {};
    const loadedMarketFilter = loadedPositionRisk.market_filter || {};
    const loadedBreadth = loadedPositionRisk.breadth || {};
    const loadedSizing = loadedBase.sizing || {};
    const loadedSignalComposition = loadedBase.signal_composition || {};
    const loadedRegimeEngine = loadedBase.regime_engine || {};
    const loadedRegimeTrendBlock = loadedRegimeEngine.trend_block || {};
    const loadedRegimeRiskBlock = loadedRegimeEngine.risk_block || {};
    const loadedRegimeBreadthBlock = loadedRegimeEngine.breadth_block || {};
    const loadedRegimeParticipationBlock = loadedRegimeEngine.participation_block || {};
    const loadedRegimePersistence = loadedRegimeEngine.persistence || {};
    const loadedRegimeFallback = loadedRegimeEngine.fallback || {};
    const loadedWeeklyFiveState = loadedRegimeEngine.weekly_five_state || {};
    const breadthEnabled = !!byId('wbBreadthEnabled')?.checked;
    const weightMode = byId('wbWeightMode')?.value || loadedSizing.weight_mode || 'equal';
    const minPositions = Number(byId('wbMinPositions')?.value || loadedSizing.min_positions || 10);
    const includeBreadth = !!loadedPositionRisk.breadth || breadthEnabled;
    const includeSizing = !!loadedBase.sizing || weightMode !== 'equal' || minPositions !== 10;
    const multiAlphaEnabled = !!byId('wbEnableComposition')?.checked;
    const composeRows = multiAlphaEnabled ? ensurePhase1ComposeRows(currentComposeRows()) : currentComposeRows();
    const strategyPack = multiAlphaEnabled ? 'COMPOSITE' : getStrategyPackValue();
    const composeNames = composeRowNames(composeRows);
    const composeMode = multiAlphaEnabled
      ? coercePhase1MultiAlphaOption(byId('wbComposeMode')?.value, MULTI_ALPHA_COMPOSE_MODE)
      : normalizeMultiAlphaOption(byId('wbComposeMode')?.value, MULTI_ALPHA_COMPOSE_MODE);
    const sameSymbolPolicy = multiAlphaEnabled
      ? coercePhase1MultiAlphaOption(byId('wbSameSymbolPolicy')?.value, MULTI_ALPHA_SAME_SYMBOL_POLICY)
      : normalizeMultiAlphaOption(byId('wbSameSymbolPolicy')?.value, MULTI_ALPHA_SAME_SYMBOL_POLICY);
    const holdingOwnership = multiAlphaEnabled
      ? coercePhase1MultiAlphaOption(byId('wbHoldingOwnership')?.value, MULTI_ALPHA_HOLDING_OWNERSHIP)
      : normalizeMultiAlphaOption(byId('wbHoldingOwnership')?.value, MULTI_ALPHA_HOLDING_OWNERSHIP);
    const regimeMatrix = multiAlphaEnabled
      ? normalizePhase1MultiAlphaRegimeMatrix(buildRegimeMatrixFromUi(composeNames), composeRows)
      : buildRegimeMatrixFromUi(composeNames);
    const portfolioMode = multiAlphaEnabled
      ? MULTI_ALPHA_PORTFOLIO_MODE
      : String(byId('wbPortfolioMode')?.value || loadedPositionRisk.portfolio_mode || 'equal_10').trim();
    const rankingScoreSourceMode = readOptionalInputValue('wbScoreSourceMode');
    const rankingResidualWindow = readOptionalNumberInput('wbResidualWindow');
    const trailingActivateProfitPct = readOptionalNumberInput('wbTrailingActivateProfitPct');
    const preProfitBreakoutFailureEnabled = !!byId('wbPreProfitBreakoutFailureEnabled')?.checked;
    const preProfitBreakoutFailureMaxBarsInput = readOptionalNumberInput('wbPreProfitBreakoutFailureMaxBars');
    const preProfitBreakoutFailureAtrBufferInput = readOptionalNumberInput('wbPreProfitBreakoutFailureAtrBufferK');
    const selectedRegimeEngine = String(byId('wbRegimeEngine')?.value || loadedRegimeEngine.engine || 'ma200_legacy').trim().toLowerCase() || 'ma200_legacy';
    const shouldEmitRegimeEngine = ['market_regime_framework', 'weekly_five_state'].includes(selectedRegimeEngine) || hasOwnConfigKey(loadedBase, 'regime_engine');
    if (multiAlphaEnabled) {
      if (byId('wbComposeMode')) byId('wbComposeMode').value = composeMode;
      if (byId('wbSameSymbolPolicy')) byId('wbSameSymbolPolicy').value = sameSymbolPolicy;
      if (byId('wbHoldingOwnership')) byId('wbHoldingOwnership').value = holdingOwnership;
      if (byId('wbPortfolioMode')) byId('wbPortfolioMode').value = portfolioMode;
      hydrateRegimeMatrix(regimeMatrix, composeRows, { useDefault: true });
    }
    const signalModules = multiAlphaEnabled
      ? composeRows.map((row) => ({
        name: row.name,
        enabled: row.enabled,
        alpha_id: normalizeMultiAlphaOption(row.alpha_id, row.name),
        family: normalizeMultiAlphaOption(row.family, ''),
        params: buildKnownModuleParams(row.name, row.params),
      }))
      : [];
    if (multiAlphaEnabled) {
      state.multi_alpha_module_state = Object.fromEntries(signalModules.map((module) => [module.name, {
        alpha_id: module.alpha_id,
        family: module.family,
        params: cloneJson(module.params) || {},
      }]));
    }
    const signalGenerationDraft = multiAlphaEnabled
      ? {
        enabled: !!byId('wbEnableSignal')?.checked,
        strategy: 'COMPOSITE',
        modules: signalModules,
      }
      : {
        ...loadedSignalGeneration,
        enabled: !!byId('wbEnableSignal')?.checked,
        strategy: strategyPack,
        regime_detection: {
          ...loadedSignalRegimeDetection,
          enabled: !!byId('wbRegimeEnabled')?.checked,
          regime_ma: Number(byId('wbRegimeMa')?.value || 60),
          regime_filter: {
            ...loadedSignalRegimeFilter,
            enabled: !!byId('wbRegimeFilterEnabled')?.checked,
            regime_threshold: Number(byId('wbRfThreshold')?.value || 0.3),
            alpha_m: Number(byId('wbRfAlpha')?.value || 2.0),
            alpha_sec: Number(byId('wbRfAlpha')?.value || 2.0),
            alpha_i: Number(byId('wbRfAlpha')?.value || 2.0),
          },
        },
        trend: {
          ...loadedTrend,
          strategy: (byId('wbTrendStrategy')?.value || 'EMA_CROSS').toUpperCase(),
          fast_ma: Number(byId('wbFastMa')?.value || 20),
          slow_ma: Number(byId('wbSlowMa')?.value || 60),
          entry_buffer_pct: Number(byId('wbEntryBuffer')?.value || 1),
        },
        mr: {
          ...loadedMr,
          strategy: (byId('wbMrStrategy')?.value || 'RSI_REVERSAL').toUpperCase(),
          rsi_period: Number(byId('wbMrRsiPeriod')?.value || 6),
          rsi_buy_threshold: Number(byId('wbMrRsiBuy')?.value || 20),
          rsi_sell_threshold: Number(byId('wbMrRsiSell')?.value || 80),
          mr_max_hold_days: Number(byId('wbMrMaxHold')?.value || 5),
          mr_stop_loss_pct: Number(byId('wbMrStopLoss')?.value || 3) / 100,
        },
        sma: {
          ...loadedSma,
          fast_ma: Number(byId('wbFastMa')?.value || 20),
          slow_ma: Number(byId('wbSlowMa')?.value || 60),
          entry_buffer_pct: Number(byId('wbEntryBuffer')?.value || 1),
        },
        ema: {
          ...loadedEma,
          fast_ma: Number(byId('wbFastMa')?.value || 20),
          slow_ma: Number(byId('wbSlowMa')?.value || 60),
          entry_buffer_pct: Number(byId('wbEntryBuffer')?.value || 1),
        },
        breakout: {
          ...loadedBreakout,
          breakout_window: Number(byId('wbBreakoutWindow')?.value || 55),
          enable_dual_breakout: !!byId('wbDualBreakout')?.checked,
          breakout_window_short: Number(byId('wbBreakoutWindowShort')?.value || 20),
          breakout_window_long: Number(byId('wbBreakoutWindowLong')?.value || 55),
          breakout_entry_buffer_pct: Number(byId('wbBreakoutBuffer')?.value || 0),
          entry_confirm_mode: byId('wbEntryConfirmMode')?.value || 'none',
          entry_delay_mode: byId('wbEntryDelayMode')?.value || 'none',
        },
        entry_filter: {
          ...loadedEntryFilter,
          enable_entry_above_slow_ma: !!byId('wbEntryAboveSlowMa')?.checked,
          enable_entry_slow_ma_slope: !!byId('wbEntrySlowMaSlope')?.checked,
          entry_slope_lookback: Number(byId('wbEntrySlopeLookback')?.value || 5),
        },
        ranking: {
          ...loadedRanking,
          momentum_top_pct: Number(byId('wbMomentumTopPct')?.value || 0),
        },
      };
    if (!multiAlphaEnabled) {
      if (rankingScoreSourceMode != null || hasOwnConfigKey(loadedRanking, 'score_source_mode')) {
        signalGenerationDraft.ranking.score_source_mode = rankingScoreSourceMode != null
          ? rankingScoreSourceMode
          : loadedRanking.score_source_mode;
      }
      if (rankingResidualWindow != null || hasOwnConfigKey(loadedRanking, 'residual_window')) {
        signalGenerationDraft.ranking.residual_window = rankingResidualWindow != null
          ? rankingResidualWindow
          : loadedRanking.residual_window;
      }
    }
    const signalCompositionDraft = multiAlphaEnabled
      ? {
        enabled: true,
        compose_mode: composeMode,
        same_symbol_policy: sameSymbolPolicy,
        holding_ownership: holdingOwnership,
        modules: composeRows.map((row) => ({
          name: row.name,
          enabled: row.enabled,
          role: row.role,
          weight: Number(row.weight),
          priority: Number(row.priority),
        })),
        regime_matrix: regimeMatrix,
      }
      : (Object.keys(loadedSignalComposition).length ? cloneJson(loadedSignalComposition) : { enabled: false });
    const universeMode = byId('wbUniverseMode')?.value || 'ALL_A';
    const excludeStarMarket = !!byId('wbExcludeStarMarket')?.checked;
    const loadedHasExcludeStarMarket = Object.prototype.hasOwnProperty.call(loadedUniverseFilters, 'exclude_star_market');
    const universeDraft = {
      ...loadedUniverse,
      start: byId('wbStartDate')?.value || '2021-01-01',
      end: byId('wbEndDate')?.value || '2026-02-01',
      benchmark: byId('wbBenchmark')?.value || '000300.SH',
      symbols: (byId('wbSymbols')?.value || '').split(',').map((s) => s.trim()).filter(Boolean),
      limit: Number(byId('wbUniverseLimit')?.value || 1000),
      price_adj: byId('wbPriceAdj')?.value || 'hfq',
      filters: {
        ...loadedUniverseFilters,
        exclude_st: !!byId('wbExcludeSt')?.checked,
        exclude_suspended: !!byId('wbExcludeSuspended')?.checked,
        min_list_days: Number(byId('wbMinListDays')?.value || 120),
        min_avg_turnover_20d: Number(byId('wbMinTurnover')?.value || 1e8),
        price_min: Number(byId('wbPriceMin')?.value || 0),
        price_max: Number(byId('wbPriceMax')?.value || 99999),
        atr_pct_range: byId('wbAtrRange')?.value || '0,100',
        limit_rule: byId('wbLimitRule')?.value || 'ignore',
      },
    };
    if (excludeStarMarket || loadedHasExcludeStarMarket) {
      universeDraft.filters.exclude_star_market = excludeStarMarket;
    } else {
      delete universeDraft.filters.exclude_star_market;
    }
    if (supportsMembershipMode(universeMode)) {
      universeDraft.membership_mode = membershipModeFromUiValue(byId('wbConstituent')?.value || 'dynamic');
    } else {
      delete universeDraft.membership_mode;
    }

    const exitPriorityItems = Array.from(byId('wbExitPriorityList')?.querySelectorAll('li') || [])
      .map((li) => li.textContent.replace(/^\d+\s*/, '').trim())
      .filter(Boolean);
    const draft = {
      ...loadedBase,
      asset_scope: String(loadedBase.asset_scope || state.loaded_source_asset_context?.asset_scope || 'cn_a_equity').trim() || 'cn_a_equity',
      mode: state.mode,
      strategy_pack: strategyPack,
      universe_mode: universeMode,
      industries: getSelectedIndustries(),
      initial_capital: Number(loadedBase.initial_capital ?? state.config_draft?.initial_capital ?? 100000),
      universe: universeDraft,
      signal_generation: signalGenerationDraft,
      benchmark_regime: {
        ...(loadedBase.benchmark_regime || {}),
        enabled: !!byId('wbBenchmarkRegimeEnabled')?.checked,
        fast_period: Number(byId('wbBenchmarkRegimeFast')?.value || 20),
        slow_period: Number(byId('wbBenchmarkRegimeSlow')?.value || 120),
        slope_window: Number(byId('wbBenchmarkRegimeSlope')?.value || 5),
      },
      stock_trend_filter: {
        ...(loadedBase.stock_trend_filter || {}),
        enabled: !!byId('wbStockTrendEnabled')?.checked,
        short_ma: Number(byId('wbStockTrendShortMa')?.value || 20),
        long_ma: Number(byId('wbStockTrendLongMa')?.value || 60),
      },
      sector_gate: {
        ...(loadedBase.sector_gate || {}),
        enabled: !!byId('wbSectorGateEnabled')?.checked,
        rank_window: Number(byId('wbSectorRankWindow')?.value || 60),
        top_pct: Number(byId('wbSectorTopPct')?.value || 0.3),
      },
      signal_composition: signalCompositionDraft,
      exit_rules: {
        ...loadedExitRules,
        enabled: !!byId('wbEnableExit')?.checked,
        signal_reverse: !!byId('wbExitReverse')?.checked,
        atr_stop: {
          ...loadedAtrStop,
          enabled: !!byId('wbExitAtr')?.checked,
          k: Number(byId('wbAtrK')?.value || 0.8),
        },
        trailing: {
          ...loadedTrailing,
          enabled: !!byId('wbExitTrail')?.checked,
          k: Number(byId('wbTrailK')?.value || 2.0),
        },
        time_exit: {
          ...loadedTimeExit,
          enabled: !!byId('wbExitTime')?.checked,
          n_days: Number(byId('wbExitDays')?.value || 20),
        },
        hold_constraint: {
          ...loadedHoldConstraint,
          min_hold_days: Number(byId('wbMinHoldDays')?.value || 0),
          cooldown_days: Number(byId('wbCooldownDays')?.value || 0),
        },
        take_profit: {
          ...loadedTakeProfit,
          enabled: !!byId('wbExitTakeProfit')?.checked,
          mode: byId('wbTakeProfitMode')?.value || 'pct',
          pct: Number(byId('wbTakeProfitPct')?.value || 10) / 100,
          atr_k: Number(byId('wbTakeProfitAtrK')?.value || 3.0),
        },
        fixed_stop: {
          ...loadedFixedStop,
          enabled: !!byId('wbExitFixedStop')?.checked,
          pct: Number(byId('wbFixedStopPct')?.value || 5) / 100,
        },
        ma20_exit: {
          ...loadedMa20Exit,
          enabled: !!byId('wbExitMa20')?.checked,
        },
        low10_exit: {
          ...loadedLow10Exit,
          enabled: !!byId('wbExitLow10')?.checked,
        },
      },
      universe_filter: {
        ...(loadedBase.universe_filter || {}),
        min_price: Number(byId('wbPriceMin')?.value || 0),
      },
      position_risk: {
        ...loadedPositionRisk,
        enabled: !!byId('wbEnableRisk')?.checked,
        max_positions: Number(byId('wbMaxPositions')?.value || 10),
        single_stock_cap: Number(byId('wbSingleCap')?.value || 10) / 100,
        industry_cap: Number(byId('wbIndustryCap')?.value || 30) / 100,
        lot: Number(byId('wbLot')?.value || 100),
        cash_shortage_policy: byId('wbCashPolicy')?.value || 'skip',
        portfolio_mode: portfolioMode,
        risk_budget: {
          ...loadedRiskBudget,
          enabled: !!byId('wbRiskBudget')?.checked,
          base_portfolio_risk: Number(byId('wbBasePortfolioRisk')?.value || 6) / 100,
          atr_stop_k: Number(byId('wbAtrStopK')?.value || 2.0),
          min_active_ratio: Number(byId('wbMinActiveRatio')?.value || 60) / 100,
          dd_scale_10: Number(byId('wbDdScale10')?.value || 0.8),
          dd_scale_15: Number(byId('wbDdScale15')?.value || 0.6),
          dd_fixed_20: Number(byId('wbDdFixed20')?.value || 3) / 100,
          dd_stop_pct: Number(byId('wbDdStopPct')?.value || 35) / 100,
          dd_stop_cooldown_days: Number(byId('wbDdStopCooldown')?.value || 60),
          dd_stop_protect_days: Number(byId('wbDdStopProtect')?.value || 30),
        },
        market_filter: {
          ...loadedMarketFilter,
          enabled: !!byId('wbMarketFilter')?.checked,
          slope_ma_period: Number(byId('wbMfSlopeMaPeriod')?.value || 50),
          slope_window: Number(byId('wbMfSlopeWindow')?.value || 10),
          bull_multiplier: Number(byId('wbMfBullMult')?.value || 1.5),
          light_multiplier: Number(byId('wbMfLightMult')?.value || 0.6),
          ema_light_fast: Number(byId('wbMfEmaFast')?.value || 5),
          ema_light_slow: Number(byId('wbMfEmaSlow')?.value || 20),
        },
        cost_model: {
          commission: 'fixed_assumption',
          stamp_tax: 'fixed_assumption',
          slippage: 'fixed_assumption',
          matching: 'next_open',
        },
        ...(includeBreadth ? { breadth: {
          ...loadedBreadth,
          enabled: !!byId('wbBreadthEnabled')?.checked,
          mode: byId('wbBreadthMode')?.value || 'dynamic_maxpos',
          score_type: byId('wbBreadthScoreType')?.value || 'B',
          mapping_mode: byId('wbBreadthMappingMode')?.value || 'smooth',
          min_positions: Number(byId('wbBreadthMinPositions')?.value || 3),
          max_positions: Number(byId('wbBreadthMaxPositions')?.value || 15),
          step_high: Number(byId('wbBreadthStepHigh')?.value || 0.6),
          step_mid: Number(byId('wbBreadthStepMid')?.value || 0.45),
          smooth_lo: Number(byId('wbBreadthSmoothLo')?.value || 0.4),
          smooth_range: Number(byId('wbBreadthSmoothRange')?.value || 0.2),
          ema_fast: Number(byId('wbBreadthEmaFast')?.value || 8),
          ema_slow: Number(byId('wbBreadthEmaSlow')?.value || 25),
          gate_threshold: Number(byId('wbBreadthGateThreshold')?.value || 0.45),
          gate_quantile_window: Number(byId('wbBreadthGateWindow')?.value || 252),
          gate_quantile_pct: Number(byId('wbBreadthGatePct')?.value || 0.2),
          gate_persist_days: Number(byId('wbBreadthGatePersist')?.value || 3),
          size_scale_floor: Number(byId('wbBreadthScaleFloor')?.value || 0.3),
        } } : {}),
      },
      ...(includeSizing ? { sizing: {
        ...loadedSizing,
        weight_mode: weightMode,
        min_positions: minPositions,
      } } : {}),
      exit_priority: exitPriorityItems.length ? exitPriorityItems : (cloneJson(loadedBase.exit_priority) || []),
    };
    if (trailingActivateProfitPct != null || hasOwnConfigKey(loadedTrailing, 'activate_profit_pct')) {
      draft.exit_rules.trailing.activate_profit_pct = trailingActivateProfitPct != null
        ? trailingActivateProfitPct / 100
        : loadedTrailing.activate_profit_pct;
    }
    if (preProfitBreakoutFailureEnabled || hasOwnConfigKey(loadedTrailing, 'pre_profit_breakout_failure_enabled')) {
      draft.exit_rules.trailing.pre_profit_breakout_failure_enabled = preProfitBreakoutFailureEnabled;
    }
    if (preProfitBreakoutFailureEnabled || hasOwnConfigKey(loadedTrailing, 'pre_profit_breakout_failure_max_bars')) {
      draft.exit_rules.trailing.pre_profit_breakout_failure_max_bars = preProfitBreakoutFailureMaxBarsInput != null
        ? preProfitBreakoutFailureMaxBarsInput
        : (loadedTrailing.pre_profit_breakout_failure_max_bars ?? 5);
    }
    if (preProfitBreakoutFailureEnabled || hasOwnConfigKey(loadedTrailing, 'pre_profit_breakout_failure_atr_buffer_k')) {
      draft.exit_rules.trailing.pre_profit_breakout_failure_atr_buffer_k = preProfitBreakoutFailureAtrBufferInput != null
        ? preProfitBreakoutFailureAtrBufferInput
        : (loadedTrailing.pre_profit_breakout_failure_atr_buffer_k ?? 0.5);
    }
    if (shouldEmitRegimeEngine) {
      if (selectedRegimeEngine === 'weekly_five_state') {
        draft.regime_engine = {
          ...loadedRegimeEngine,
          engine: 'weekly_five_state',
          benchmark: '000001.SH',
          weekly_five_state: {
            ...loadedWeeklyFiveState,
            benchmark: '000001.SH',
            ma_window: Number(loadedWeeklyFiveState.ma_window || 120),
            ma_slope_lookback: Number(loadedWeeklyFiveState.ma_slope_lookback || 20),
            ret_short_window: Number(loadedWeeklyFiveState.ret_short_window || 60),
            ret_long_window: Number(loadedWeeklyFiveState.ret_long_window || 120),
            adx_window: Number(loadedWeeklyFiveState.adx_window || 20),
            weekly_rule: String(loadedWeeklyFiveState.weekly_rule || 'W-FRI'),
            upgrade_confirm_weeks: Number(loadedWeeklyFiveState.upgrade_confirm_weeks || 2),
            downgrade_confirm_weeks: Number(loadedWeeklyFiveState.downgrade_confirm_weeks || 1),
            turn_weak_budget: Number(byId('wbWeeklyTurnWeakBudget')?.value || loadedWeeklyFiveState.turn_weak_budget || 0.15),
          },
          fallback: {
            ...loadedRegimeFallback,
            on_feature_unavailable: String(loadedRegimeFallback.on_feature_unavailable || 'ma200_legacy').trim() || 'ma200_legacy',
            required_blocks: [],
            emit_feature_availability: loadedRegimeFallback.emit_feature_availability !== false,
          },
        };
      } else {
        draft.regime_engine = {
          ...loadedRegimeEngine,
          engine: selectedRegimeEngine,
          benchmark: String(byId('wbFormalRegimeBenchmark')?.value || loadedRegimeEngine.benchmark || universeDraft.benchmark || '').trim(),
          trend_block: {
            ...loadedRegimeTrendBlock,
            enabled: !!byId('wbRegimeTrendEnabled')?.checked,
            long_ma_window: Number(byId('wbRegimeLongMaWindow')?.value || loadedRegimeTrendBlock.long_ma_window || 200),
            slope_window: Number(byId('wbRegimeSlopeWindow')?.value || loadedRegimeTrendBlock.slope_window || 20),
            breakout_lookback: Number(byId('wbRegimeBreakoutLookback')?.value || loadedRegimeTrendBlock.breakout_lookback || 20),
          },
          risk_block: {
            ...loadedRegimeRiskBlock,
            enabled: !!byId('wbRegimeRiskEnabled')?.checked,
            realized_vol_window: Number(byId('wbRegimeRealizedVolWindow')?.value || loadedRegimeRiskBlock.realized_vol_window || 20),
            atr_window: Number(byId('wbRegimeAtrWindow')?.value || loadedRegimeRiskBlock.atr_window || 14),
            drawdown_window: Number(byId('wbRegimeDrawdownWindow')?.value || loadedRegimeRiskBlock.drawdown_window || 60),
          },
          breadth_block: {
            ...loadedRegimeBreadthBlock,
            enabled: !!byId('wbRegimeBreadthEnabledFormal')?.checked,
            universe: String(byId('wbRegimeBreadthUniverse')?.value || loadedRegimeBreadthBlock.universe || 'benchmark_constituents').trim() || 'benchmark_constituents',
            above_ma_short_window: Number(byId('wbRegimeAboveMaShort')?.value || loadedRegimeBreadthBlock.above_ma_short_window || 50),
            above_ma_long_window: Number(byId('wbRegimeAboveMaLong')?.value || loadedRegimeBreadthBlock.above_ma_long_window || 200),
            new_high_low_window: Number(byId('wbRegimeNewHighLowWindow')?.value || loadedRegimeBreadthBlock.new_high_low_window || 20),
          },
          participation_block: {
            ...loadedRegimeParticipationBlock,
            enabled: !!byId('wbRegimeParticipationEnabled')?.checked,
            turnover_window: Number(byId('wbRegimeTurnoverWindow')?.value || loadedRegimeParticipationBlock.turnover_window || 20),
            amount_window: Number(byId('wbRegimeAmountWindow')?.value || loadedRegimeParticipationBlock.amount_window || 20),
            use_turnover_rate: !!byId('wbRegimeUseTurnoverRate')?.checked,
          },
          persistence: {
            ...loadedRegimePersistence,
            entry_confirm_bars: Number(byId('wbRegimeEntryConfirmBars')?.value || loadedRegimePersistence.entry_confirm_bars || 3),
            exit_confirm_bars: Number(byId('wbRegimeExitConfirmBars')?.value || loadedRegimePersistence.exit_confirm_bars || 2),
            min_state_duration: Number(byId('wbRegimeMinStateDuration')?.value || loadedRegimePersistence.min_state_duration || 5),
            confidence_floor: Number(byId('wbRegimeConfidenceFloor')?.value || loadedRegimePersistence.confidence_floor || 0.55),
            transition_cooldown: Number(byId('wbRegimeTransitionCooldown')?.value || loadedRegimePersistence.transition_cooldown || 3),
          },
          fallback: {
            ...loadedRegimeFallback,
            on_feature_unavailable: String(byId('wbRegimeFallbackMode')?.value || loadedRegimeFallback.on_feature_unavailable || (selectedRegimeEngine === 'market_regime_framework' ? 'ma200_legacy' : 'disabled')).trim() || 'ma200_legacy',
            required_blocks: regimeRequiredBlocksFromUi(),
            emit_feature_availability: !!byId('wbRegimeEmitFeatureAvailability')?.checked,
          },
        };
      }
    } else {
      delete draft.regime_engine;
    }
    state.config_draft = draft;
    state.strategy_pack = draft.strategy_pack;
    state.universe_mode = draft.universe_mode;
    if (byId('wbStrategyPack')) byId('wbStrategyPack').value = draft.strategy_pack;
    syncExitLinkage();
    refreshConfigPanels();
    syncLoadedSourceUI();
    if (typeof syncResultsWorkbenchSurface === 'function') {
      syncResultsWorkbenchSurface({ perf: false, explain: false, execution: false });
    } else {
      renderSummaryBar();
    }
    return draft;
  }

  globalScope.configDraftCore = Object.freeze({
    buildConfigDraft: buildConfigDraftCore,
    validateConfigDraft: validateConfigDraftCore,
  });
})(window);
