(function setupResultsNavChartOverride() {
  const PORTFOLIO_VISIBLE_BARS = 60;

  function buildFixedPriceRangeProvider(minValue, maxValue) {
    if (!Number.isFinite(minValue) || !Number.isFinite(maxValue) || maxValue <= minValue) return null;
    return () => ({
      priceRange: {
        minValue,
        maxValue,
      },
    });
  }

  function deriveExpandedBenchRange(benchWindow) {
    const rows = Array.isArray(benchWindow) ? benchWindow : [];
    const lows = rows
      .map((row) => (Number.isFinite(Number(row?.low)) ? Number(row.low) : Number(row?.close)))
      .filter((value) => Number.isFinite(value));
    const highs = rows
      .map((row) => (Number.isFinite(Number(row?.high)) ? Number(row.high) : Number(row?.close)))
      .filter((value) => Number.isFinite(value));
    if (!lows.length || !highs.length) return null;
    const rawMin = Math.min(...lows);
    const rawMax = Math.max(...highs);
    const rawSpan = Math.max(rawMax - rawMin, Math.max(Math.abs(rawMax), 1) * 0.02, 1e-6);
    const expandedSpan = rawSpan / 0.9;
    const mid = (rawMax + rawMin) / 2;
    return {
      min: mid - (expandedSpan / 2),
      max: mid + (expandedSpan / 2),
    };
  }

  function sliceRowsByVisibleRange(rows, chart) {
    const arr = Array.isArray(rows) ? rows : [];
    if (!arr.length) return [];
    const logicalRange = chart?.timeScale?.()?.getVisibleLogicalRange?.();
    if (!logicalRange || !Number.isFinite(logicalRange.from) || !Number.isFinite(logicalRange.to)) {
      return arr.slice(-Math.min(PORTFOLIO_VISIBLE_BARS, arr.length));
    }
    const from = Math.max(0, Math.floor(logicalRange.from));
    const to = Math.min(arr.length - 1, Math.ceil(logicalRange.to));
    if (to < from) return arr.slice(-Math.min(PORTFOLIO_VISIBLE_BARS, arr.length));
    return arr.slice(from, to + 1);
  }

  function derivePortfolioOverlayConfig(benchOhlc, navLineData, chart) {
    const benchRows = Array.isArray(benchOhlc) ? benchOhlc : [];
    const navRows = Array.isArray(navLineData) ? navLineData : [];
    if (!benchRows.length || !navRows.length) return null;
    const benchWindow = sliceRowsByVisibleRange(benchRows, chart);
    const navWindow = sliceRowsByVisibleRange(navRows, chart);
    const windowBars = Math.max(1, Math.max(benchWindow.length, navWindow.length));
    const leftRange = deriveExpandedBenchRange(benchWindow);
    const benchLast = Number(benchWindow[benchWindow.length - 1]?.close);
    const navLast = Number(navWindow[navWindow.length - 1]?.value);
    if (!leftRange || !Number.isFinite(benchLast) || benchLast <= 0 || !Number.isFinite(navLast) || navLast <= 0) {
      return { leftRange, rightRange: null, scaleFactor: null, windowBars };
    }
    const scaleFactor = benchLast / navLast;
    if (!Number.isFinite(scaleFactor) || scaleFactor <= 0) {
      return { leftRange, rightRange: null, scaleFactor: null, windowBars };
    }
    return {
      leftRange,
      rightRange: {
        min: leftRange.min / scaleFactor,
        max: leftRange.max / scaleFactor,
      },
      scaleFactor,
      windowBars,
    };
  }

  function ensurePortfolioBenchmarkCandles(navState, chart, LWC) {
    if (navState._portfolioBenchmarkKind === 'candlestick-left' && navState.benchmarkSeries) return;
    if (navState.benchmarkSeries && typeof chart.removeSeries === 'function') {
      try { chart.removeSeries(navState.benchmarkSeries); } catch (_) {}
    }
    navState.benchmarkSeries = typeof chart.addCandlestickSeries === 'function'
      ? chart.addCandlestickSeries({
          upColor: '#ef4444',
          downColor: '#22c55e',
          borderDownColor: '#22c55e',
          borderUpColor: '#ef4444',
          wickDownColor: '#22c55e',
          wickUpColor: '#ef4444',
          priceScaleId: 'left',
          priceLineVisible: false,
          lastValueVisible: true,
        })
      : chart.addSeries(LWC.CandlestickSeries, {
          upColor: '#ef4444',
          downColor: '#22c55e',
          borderDownColor: '#22c55e',
          borderUpColor: '#ef4444',
          wickDownColor: '#22c55e',
          wickUpColor: '#ef4444',
          priceScaleId: 'left',
          priceLineVisible: false,
          lastValueVisible: true,
        });
    navState._portfolioBenchmarkKind = 'candlestick-left';
  }

  function applyMarkers(series, markers) {
    const LWC = window.LightweightCharts;
    if (!series || !Array.isArray(markers) || !markers.length) return;
    if (typeof series.setMarkers === 'function') {
      try { series.setMarkers(markers); } catch (_) {}
      return;
    }
    if (typeof LWC?.createSeriesMarkers === 'function') {
      try { LWC.createSeriesMarkers(series, markers); } catch (_) {}
    }
  }

  function renderPortfolioChart(navState, container, chart, benchOhlc, navSeries, showBenchmark, opts) {
    const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;
    const lineData = (Array.isArray(navSeries) ? navSeries : [])
      .map((point) => ({ time: point.date, value: Number(point.value) }))
      .filter((point) => Number.isFinite(point.value));
    const dynamicOverlayConfig = () => derivePortfolioOverlayConfig(benchOhlc, lineData, chart);
    const leftRangeProvider = showBenchmark
      ? (() => {
          const overlay = dynamicOverlayConfig();
          return overlay?.leftRange
            ? { priceRange: { minValue: overlay.leftRange.min, maxValue: overlay.leftRange.max } }
            : null;
        })
      : null;
    const rightRangeProvider = showBenchmark
      ? (() => {
          const overlay = dynamicOverlayConfig();
          return overlay?.rightRange
            ? { priceRange: { minValue: overlay.rightRange.min, maxValue: overlay.rightRange.max } }
            : null;
        })
      : null;

    try {
      chart.applyOptions({
        leftPriceScale: {
          visible: !!showBenchmark && hasBench,
          borderColor: '#334155',
          autoScale: true,
        },
        rightPriceScale: {
          visible: true,
          borderColor: '#334155',
          autoScale: true,
        },
      });
    } catch (_) {}

    if (navState.benchmarkSeries) {
      ensurePortfolioBenchmarkCandles(navState, chart, window.LightweightCharts);
    } else if (showBenchmark && hasBench) {
      ensurePortfolioBenchmarkCandles(navState, chart, window.LightweightCharts);
    }

    if (navState.benchmarkSeries) {
      try {
        navState.benchmarkSeries.applyOptions({
          priceScaleId: 'left',
          priceLineVisible: false,
          lastValueVisible: true,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
          autoscaleInfoProvider: leftRangeProvider || undefined,
        });
      } catch (_) {}
      navState.benchmarkSeries.setData(Array.isArray(benchOhlc) ? benchOhlc : []);
    }

    if (navState.primarySeries) {
      try {
        navState.primarySeries.applyOptions({
          priceScaleId: 'right',
          color: '#f59e0b',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
          crosshairMarkerVisible: true,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
          autoscaleInfoProvider: rightRangeProvider || undefined,
        });
      } catch (_) {}
      navState.primarySeries.setData(lineData);
      applyMarkers(navState.primarySeries, []);

      if (navState.marketOverlay) {
        navState.marketOverlay.setData(Array.isArray(opts.marketStates) ? opts.marketStates : []);
      }

      if (lineData.length) {
        const lastValue = Number(lineData[lineData.length - 1]?.value);
        navState.symbolBadgeUpdater = () => renderChartValueBadge(
          container,
          navState.primarySeries,
          lastValue,
          `NAV ${num(lastValue, 2)}`,
        );
      }
    }

    const totalBars = Math.max(Array.isArray(benchOhlc) ? benchOhlc.length : 0, lineData.length);
    const visibleBars = Math.max(1, Math.min(PORTFOLIO_VISIBLE_BARS, totalBars || 1));
    const visibleKey = [
      totalBars,
      benchOhlc[0]?.time || '',
      benchOhlc[benchOhlc.length - 1]?.time || '',
      lineData[0]?.time || '',
      lineData[lineData.length - 1]?.time || '',
      showBenchmark ? 'bench' : 'no-bench',
      `portfolio:${visibleBars}`,
    ].join('|');

    if (navState.visibleKey !== visibleKey) {
      if (totalBars > 0 && typeof chart.timeScale()?.setVisibleLogicalRange === 'function') {
        chart.timeScale().setVisibleLogicalRange({
          from: Math.max(0, totalBars - visibleBars) - 0.5,
          to: totalBars - 1 + 2.5,
        });
      } else {
        chart.timeScale().fitContent();
      }
      navState.visibleKey = visibleKey;
    }
  }

  function renderSymbolChart(navState, container, chart, benchOhlc, navSeries, showBenchmark, opts) {
    const LWC = window.LightweightCharts;
    const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;
    const benchFirstClose = Number(benchOhlc[0]?.close) || 1;
    const benchmarkLineData = hasBench
      ? benchOhlc.map((point) => ({ time: point.time, value: Number(point.close) / benchFirstClose }))
      : [];
    const lineData = (Array.isArray(navSeries) ? navSeries : [])
      .map((point) => ({ time: point.date, value: Number(point.value) }))
      .filter((point) => Number.isFinite(point.value));
    const suspensionRanges = Array.isArray(opts.suspensionRanges) ? opts.suspensionRanges : [];
    const hasSuspension = suspensionRanges.length > 0 && !!navState.suspensionSeries;

    try {
      chart.applyOptions({
        leftPriceScale: {
          visible: !!showBenchmark && hasBench,
          borderColor: '#334155',
          autoScale: true,
        },
        rightPriceScale: {
          visible: true,
          borderColor: '#334155',
          autoScale: true,
        },
      });
    } catch (_) {}

    if (navState.benchmarkSeries) {
      try {
        navState.benchmarkSeries.applyOptions({
          priceScaleId: 'left',
          color: '#58a6ff',
          lineWidth: 2,
          crosshairMarkerVisible: false,
          priceLineVisible: false,
          lastValueVisible: false,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
        });
      } catch (_) {}
      navState.benchmarkSeries.setData(benchmarkLineData);
    }

    if (navState.primarySeries) {
      try {
        navState.primarySeries.applyOptions({
          priceScaleId: 'right',
          color: '#f59e0b',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: !hasSuspension,
          crosshairMarkerVisible: !hasSuspension,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
        });
        navState.suspensionSeries?.applyOptions({
          priceScaleId: 'right',
          color: '#999',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
        });
      } catch (_) {}

      if (hasSuspension) {
        const suspSet = new Set();
        for (const range of suspensionRanges) {
          for (const point of lineData) {
            if (point.time >= range.start && point.time <= range.end) suspSet.add(point.time);
          }
        }
        const normalData = [];
        const suspensionData = [];
        for (let i = 0; i < lineData.length; i += 1) {
          const point = lineData[i];
          const isSusp = suspSet.has(point.time);
          const prevSusp = i > 0 && suspSet.has(lineData[i - 1].time);
          const nextSusp = i < lineData.length - 1 && suspSet.has(lineData[i + 1].time);
          if (isSusp) {
            suspensionData.push(point);
            if (!prevSusp || !nextSusp) normalData.push(point);
          } else {
            normalData.push(point);
            if (prevSusp || nextSusp) suspensionData.push(point);
          }
        }
        const dedup = (rows) => {
          const byTime = new Map();
          for (const point of rows) byTime.set(point.time, point);
          return Array.from(byTime.values()).sort((left, right) => (left.time < right.time ? -1 : 1));
        };
        navState.suspensionSeries.setData(dedup(suspensionData));
        navState.primarySeries.setData(dedup(normalData));
      } else {
        navState.primarySeries.setData(lineData);
      }

      applyMarkers(navState.primarySeries, Array.isArray(opts.markers) ? opts.markers : []);
      if (navState.marketOverlay) {
        navState.marketOverlay.setData([]);
      }

      if (lineData.length) {
        const lastValue = Number(lineData[lineData.length - 1]?.value);
        const lastClose = Number(opts?.symbolLastClose);
        const label = Number.isFinite(lastClose)
          ? `个股收盘价 ${num(lastClose, 2)}`
          : `个股净值 ${num(lastValue, 2)}x`;
        navState.symbolBadgeUpdater = () => renderChartValueBadge(container, navState.primarySeries, lastValue, label);
      }
    }

    const totalBars = Math.max(benchmarkLineData.length, lineData.length);
    const maxVisibleBars = Math.floor((container.clientWidth || 600) / 6);
    const visibleKey = [
      totalBars,
      benchmarkLineData[0]?.time || '',
      benchmarkLineData[benchmarkLineData.length - 1]?.time || '',
      lineData[0]?.time || '',
      lineData[lineData.length - 1]?.time || '',
      showBenchmark ? 'bench' : 'no-bench',
      'symbol:auto',
    ].join('|');
    if (navState.visibleKey !== visibleKey) {
      if (totalBars > maxVisibleBars) chart.timeScale().scrollToPosition(5, false);
      else chart.timeScale().fitContent();
      navState.visibleKey = visibleKey;
    }
  }

  const renderNavChartLWOverride = function renderNavChartLWOverride(containerId, benchOhlc, navSeries, showBenchmark, opts = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;
    clearChartValueBadge(container);

    const hasNav = Array.isArray(navSeries) && navSeries.length > 0;
    const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;
    const mode = String(opts.mode || 'portfolio');
    const isPortfolioMode = mode === 'portfolio';
    const hasSuspension = mode === 'symbol' && Array.isArray(opts.suspensionRanges) && opts.suspensionRanges.length > 0;

    if (!hasNav && !hasBench) {
      destroyNavChartState();
      container.innerHTML = '<div class="wb-empty"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg><span>运行实验后，这里显示净值与参考指数走势。</span></div>';
      return;
    }

    const LWC = window.LightweightCharts;
    if (!LWC) {
      destroyNavChartState();
      container.innerHTML = '<div class="wb-empty"><span>lightweight-charts 加载失败</span></div>';
      return;
    }

    const shape = {
      key: [
        mode,
        hasNav ? 'nav' : 'no-nav',
        showBenchmark && hasBench ? 'bench-line-left' : 'bench-none',
        hasSuspension ? 'susp' : 'plain',
      ].join('|'),
      mode,
      hasNav,
      hasSuspension,
      benchmarkKind: showBenchmark && hasBench ? 'line-left' : 'none',
    };

    let navState = _lwNavState;
    if (!navState || navState.container !== container) {
      destroyNavChartState();
      navState = createNavChartState(container, LWC);
    }
    if (!navState) return;
    if (navState.shapeKey !== shape.key) {
      navState = resetNavChartSeries(navState, LWC, shape);
    }
    if (!navState?.chart) return;

    const chart = navState.chart;
    navState.showLeftBenchmarkScale = !!showBenchmark && hasBench;
    navState.symbolBadgeUpdater = null;

    if (isPortfolioMode) {
      renderPortfolioChart(navState, container, chart, benchOhlc, navSeries, showBenchmark, opts);
    } else {
      renderSymbolChart(navState, container, chart, benchOhlc, navSeries, showBenchmark, opts);
    }

    if (typeof navState.symbolBadgeUpdater === 'function') {
      requestAnimationFrame(navState.symbolBadgeUpdater);
    }
  };

  window.renderNavChartLW = renderNavChartLWOverride;
  try { renderNavChartLW = renderNavChartLWOverride; } catch (_) {}
})();

(function setupPortfolioDualChartOverride() {
  const PORTFOLIO_VISIBLE_BARS = 60;
  let dualState = null;

  function destroyChart(chart) {
    if (!chart) return;
    try { chart.remove(); } catch (_) {}
  }

  function disconnectObserver(observer) {
    if (!observer) return;
    try { observer.disconnect(); } catch (_) {}
  }

  function unsubscribeLogical(chart, handler) {
    if (!chart || !handler) return;
    const timeScale = typeof chart.timeScale === 'function' ? chart.timeScale() : null;
    if (!timeScale || typeof timeScale.unsubscribeVisibleLogicalRangeChange !== 'function') return;
    try { timeScale.unsubscribeVisibleLogicalRangeChange(handler); } catch (_) {}
  }

  function logicalRangeEqual(left, right) {
    if (!left || !right) return false;
    const fromEqual = Math.abs(Number(left.from) - Number(right.from)) < 1e-3;
    const toEqual = Math.abs(Number(left.to) - Number(right.to)) < 1e-3;
    return fromEqual && toEqual;
  }

  function destroyPortfolioDualChartLW() {
    if (!dualState) return;
    unsubscribeLogical(dualState.topChart, dualState.topLogicalHandler);
    unsubscribeLogical(dualState.bottomChart, dualState.bottomLogicalHandler);
    disconnectObserver(dualState.topResizeObserver);
    disconnectObserver(dualState.bottomResizeObserver);
    destroyChart(dualState.topChart);
    destroyChart(dualState.bottomChart);
    if (dualState.topContainer) clearChartValueBadge(dualState.topContainer);
    if (dualState.bottomContainer) clearChartValueBadge(dualState.bottomContainer);
    dualState = null;
  }

  function createBaseChart(
    container,
    LWC,
    { leftScaleVisible = false, rightScaleVisible = true, showTimeScale = true, interactive = true } = {},
  ) {
    container.innerHTML = '';
    return LWC.createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight || 260,
      layout: {
        background: { type: LWC.ColorType ? LWC.ColorType.Solid : 'solid', color: 'transparent' },
        textColor: '#94a3b8',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(51,65,85,0.4)' },
        horzLines: { color: 'rgba(51,65,85,0.4)' },
      },
      crosshair: { mode: LWC.CrosshairMode ? LWC.CrosshairMode.Normal : 0 },
      leftPriceScale: { visible: leftScaleVisible, borderColor: '#334155', autoScale: true },
      rightPriceScale: { visible: rightScaleVisible, borderColor: '#334155', autoScale: true },
      handleScale: {
        mouseWheel: interactive,
        pinch: interactive,
        axisPressedMouseMove: {
          time: interactive,
          price: interactive,
        },
        axisDoubleClickReset: {
          time: interactive,
          price: interactive,
        },
      },
      handleScroll: {
        mouseWheel: interactive,
        pressedMouseMove: interactive,
        horzTouchDrag: interactive,
        vertTouchDrag: false,
      },
      timeScale: {
        borderColor: '#334155',
        timeVisible: false,
        secondsVisible: false,
        barSpacing: 6,
        minBarSpacing: 2,
        rightOffset: 5,
        visible: showTimeScale,
        lockVisibleTimeRangeOnResize: true,
        rightBarStaysOnScroll: true,
      },
    });
  }

  function addLineSeriesCompat(chart, LWC, options) {
    return typeof chart.addLineSeries === 'function'
      ? chart.addLineSeries(options)
      : chart.addSeries(LWC.LineSeries, options);
  }

  function addCandlestickSeriesCompat(chart, LWC, options) {
    return typeof chart.addCandlestickSeries === 'function'
      ? chart.addCandlestickSeries(options)
      : chart.addSeries(LWC.CandlestickSeries, options);
  }

  function addHistogramSeriesCompat(chart, LWC, options) {
    return typeof chart.addHistogramSeries === 'function'
      ? chart.addHistogramSeries(options)
      : chart.addSeries(LWC.HistogramSeries, options);
  }

  function buildMarketMaskData(rows) {
    const input = Array.isArray(rows) ? rows : [];
    const colorMap = typeof MARKET_STATE_COLORS === 'object' && MARKET_STATE_COLORS ? MARKET_STATE_COLORS : {};
    return input
      .map((row) => {
        const time = String(row?.time || '').trim();
        const mode = String(row?.mode || '').trim().toUpperCase();
        const color = colorMap[mode] || null;
        if (!time || !color) return null;
        return { time, value: 1, color };
      })
      .filter(Boolean);
  }

  function ensureMarketMaskLayer(container, key) {
    if (!container) return null;
    if (!container.style.position) container.style.position = 'relative';
    let layer = container.querySelector(`.wb-market-mask-layer[data-mask-key="${key}"]`);
    if (!layer) {
      layer = document.createElement('div');
      layer.className = 'wb-market-mask-layer';
      layer.dataset.maskKey = key;
      layer.style.position = 'absolute';
      layer.style.left = '0';
      layer.style.right = '0';
      layer.style.top = '0';
      layer.style.bottom = '0';
      layer.style.pointerEvents = 'none';
      layer.style.zIndex = '1';
      layer.style.overflow = 'hidden';
      container.appendChild(layer);
    }
    return layer;
  }

  function clearMarketMaskLayer(container, key) {
    const layer = container?.querySelector?.(`.wb-market-mask-layer[data-mask-key="${key}"]`);
    if (layer) layer.innerHTML = '';
  }

  function estimateBarWidth(chart, rows) {
    const timeScale = chart?.timeScale?.();
    if (!timeScale || typeof timeScale.timeToCoordinate !== 'function') return 6;
    const coords = (Array.isArray(rows) ? rows : [])
      .map((row) => timeScale.timeToCoordinate(row.time))
      .filter((value) => Number.isFinite(value));
    if (coords.length < 2) return 6;
    let total = 0;
    let count = 0;
    for (let i = 1; i < coords.length; i += 1) {
      const diff = Math.abs(coords[i] - coords[i - 1]);
      if (diff > 0) {
        total += diff;
        count += 1;
      }
    }
    return count > 0 ? Math.max(2, total / count) : 6;
  }

  function renderMarketMaskLayer(container, chart, rows, key) {
    const layer = ensureMarketMaskLayer(container, key);
    if (!layer) return;
    const input = Array.isArray(rows) ? rows : [];
    const timeScale = chart?.timeScale?.();
    if (!input.length || !timeScale || typeof timeScale.timeToCoordinate !== 'function') {
      layer.innerHTML = '';
      return;
    }
    const barWidth = estimateBarWidth(chart, input);
    const bands = [];
    let i = 0;
    while (i < input.length) {
      const current = input[i];
      const mode = String(current?.mode || '').trim().toUpperCase();
      const color = (typeof MARKET_STATE_COLORS === 'object' && MARKET_STATE_COLORS ? MARKET_STATE_COLORS[mode] : null) || null;
      let j = i + 1;
      while (j < input.length && String(input[j]?.mode || '').trim().toUpperCase() === mode) j += 1;
      if (color) {
        const x1 = timeScale.timeToCoordinate(current.time);
        const x2 = timeScale.timeToCoordinate(input[j - 1].time);
        if (Number.isFinite(x1) && Number.isFinite(x2)) {
          const left = Math.round(Math.min(x1, x2) - (barWidth / 2));
          const width = Math.max(1, Math.round(Math.abs(x2 - x1) + barWidth));
          bands.push({ left, width, color });
        }
      }
      i = j;
    }
    layer.innerHTML = bands.map((band) => (
      `<div style="position:absolute;top:0;bottom:0;left:${band.left}px;width:${band.width}px;background:${band.color};"></div>`
    )).join('');
  }

  function renderDualMarketMasks(state) {
    if (!state) return;
    renderMarketMaskLayer(state.topContainer, state.topChart, state.marketStates, 'top');
    if (state.bottomContainer && state.bottomChart) {
      renderMarketMaskLayer(state.bottomContainer, state.bottomChart, state.marketStates, 'bottom');
    } else if (state.bottomContainer) {
      clearMarketMaskLayer(state.bottomContainer, 'bottom');
    }
  }

  function ensureDualState(topContainer, bottomContainer, LWC) {
    const needsReset = !dualState
      || dualState.topContainer !== topContainer
      || dualState.bottomContainer !== bottomContainer;
    if (!needsReset) return dualState;

    destroyPortfolioDualChartLW();

    const topChart = createBaseChart(topContainer, LWC, {
      leftScaleVisible: false,
      rightScaleVisible: true,
      showTimeScale: false,
      interactive: true,
    });

    const topMaskSeries = addHistogramSeriesCompat(topChart, LWC, {
      priceScaleId: 'overlay-mask-top',
      base: 0,
      color: 'rgba(0,0,0,0)',
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
      autoscaleInfoProvider: () => ({
        priceRange: { minValue: 0, maxValue: 1 },
      }),
    });
    try {
      topChart.priceScale('overlay-mask-top').applyOptions({
        visible: false,
        autoScale: false,
        scaleMargins: { top: 0, bottom: 0 },
      });
    } catch (_) {}

    const topNavSeries = addLineSeriesCompat(topChart, LWC, {
      priceScaleId: 'right',
      color: '#f59e0b',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    });

    const topBenchmarkSeries = addLineSeriesCompat(topChart, LWC, {
      priceScaleId: 'right',
      color: '#60a5fa',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: false,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    });

    let bottomChart = null;
    let bottomBenchmarkSeries = null;
    let bottomMaskSeries = null;
    if (bottomContainer) {
      bottomChart = createBaseChart(bottomContainer, LWC, {
        leftScaleVisible: true,
        rightScaleVisible: false,
        showTimeScale: true,
        interactive: false,
      });
      bottomMaskSeries = addHistogramSeriesCompat(bottomChart, LWC, {
        priceScaleId: 'overlay-mask-bottom',
        base: 0,
        color: 'rgba(0,0,0,0)',
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        autoscaleInfoProvider: () => ({
          priceRange: { minValue: 0, maxValue: 1 },
        }),
      });
      try {
        bottomChart.priceScale('overlay-mask-bottom').applyOptions({
          visible: false,
          autoScale: false,
          scaleMargins: { top: 0, bottom: 0 },
        });
      } catch (_) {}
      bottomBenchmarkSeries = addCandlestickSeriesCompat(bottomChart, LWC, {
        upColor: '#ef4444',
        downColor: '#22c55e',
        borderDownColor: '#22c55e',
        borderUpColor: '#ef4444',
        wickDownColor: '#22c55e',
        wickUpColor: '#ef4444',
        priceScaleId: 'left',
        priceLineVisible: false,
        lastValueVisible: true,
      });
    }

    dualState = {
      topContainer,
      bottomContainer,
      topChart,
      bottomChart,
      topMaskSeries,
      topNavSeries,
      topBenchmarkSeries,
      bottomBenchmarkSeries,
      bottomMaskSeries,
      topResizeObserver: null,
      bottomResizeObserver: null,
      topLogicalHandler: null,
      syncLock: false,
      bottomBenchRows: [],
      marketStates: [],
      visibleKey: '',
      initialized: false,
    };

    dualState.topResizeObserver = null;
    dualState.bottomResizeObserver = null;

    const syncFromTop = (range) => {
      if (!dualState || dualState.syncLock || !dualState.bottomChart || !range) return;
      const bottomRange = dualState.bottomChart.timeScale()?.getVisibleLogicalRange?.();
      if (logicalRangeEqual(range, bottomRange)) {
        renderDualMarketMasks(dualState);
        return;
      }
      dualState.syncLock = true;
      try {
        dualState.bottomChart.timeScale().setVisibleLogicalRange(range);
      } catch (_) {
      } finally {
        dualState.syncLock = false;
      }
      renderDualMarketMasks(dualState);
    };
    dualState.topLogicalHandler = syncFromTop;

    if (typeof dualState.topChart.timeScale()?.subscribeVisibleLogicalRangeChange === 'function') {
      dualState.topChart.timeScale().subscribeVisibleLogicalRangeChange(syncFromTop);
    }

    return dualState;
  }

  function normalizeBenchmarkLine(benchOhlc) {
    const rows = Array.isArray(benchOhlc) ? benchOhlc : [];
    if (!rows.length) return [];
    const firstClose = Number(rows[0]?.close);
    if (!Number.isFinite(firstClose) || firstClose <= 0) return [];
    return rows
      .map((row) => {
        const close = Number(row?.close);
        if (!Number.isFinite(close)) return null;
        return { time: row.time, value: close / firstClose };
      })
      .filter(Boolean);
  }

  function sliceVisibleRows(rows, chart) {
    const arr = Array.isArray(rows) ? rows : [];
    if (!arr.length || !chart) return [];
    const logicalRange = chart.timeScale()?.getVisibleLogicalRange?.();
    if (!logicalRange || !Number.isFinite(logicalRange.from) || !Number.isFinite(logicalRange.to)) {
      return arr.slice(-Math.min(PORTFOLIO_VISIBLE_BARS, arr.length));
    }
    const from = Math.max(0, Math.floor(logicalRange.from));
    const to = Math.min(arr.length - 1, Math.ceil(logicalRange.to));
    return to >= from ? arr.slice(from, to + 1) : arr.slice(-Math.min(PORTFOLIO_VISIBLE_BARS, arr.length));
  }

  function buildExpandedPriceRange(rows) {
    const arr = Array.isArray(rows) ? rows : [];
    if (!arr.length) return null;
    const lows = arr.map((row) => Number.isFinite(Number(row?.low)) ? Number(row.low) : Number(row?.close)).filter(Number.isFinite);
    const highs = arr.map((row) => Number.isFinite(Number(row?.high)) ? Number(row.high) : Number(row?.close)).filter(Number.isFinite);
    if (!lows.length || !highs.length) return null;
    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const span = Math.max(max - min, Math.max(Math.abs(max), 1) * 0.02, 1e-6);
    const expanded = span / 0.9;
    const mid = (min + max) / 2;
    return {
      min: mid - expanded / 2,
      max: mid + expanded / 2,
    };
  }

  function setInitialVisibleRange(state, totalBars) {
    if (!state?.topChart || totalBars <= 0) return;
    const visibleBars = Math.max(1, Math.min(PORTFOLIO_VISIBLE_BARS, totalBars));
    const range = {
      from: Math.max(0, totalBars - visibleBars) - 0.5,
      to: totalBars - 1 + 2.5,
    };
    try { state.topChart.timeScale().setVisibleLogicalRange(range); } catch (_) {}
  }

  function updateTopBadge(state, navLineData, benchmarkLineData) {
    if (!state?.topContainer || !Array.isArray(navLineData) || !navLineData.length) return;
    const navLast = Number(navLineData[navLineData.length - 1]?.value);
    const benchLast = Number(benchmarkLineData[benchmarkLineData.length - 1]?.value);
    const label = Number.isFinite(benchLast)
      ? `NAV ${num(navLast, 2)} | 上证 ${num(benchLast, 2)}x`
      : `NAV ${num(navLast, 2)}`;
    renderChartValueBadge(state.topContainer, state.topNavSeries, navLast, label);
  }

  function updateBottomBadge(state, benchOhlc, benchmarkSymbol) {
    if (!state?.bottomContainer || !state.bottomBenchmarkSeries || !Array.isArray(benchOhlc) || !benchOhlc.length) return;
    const lastClose = Number(benchOhlc[benchOhlc.length - 1]?.close);
    if (!Number.isFinite(lastClose)) return;
    renderChartValueBadge(state.bottomContainer, state.bottomBenchmarkSeries, lastClose, `${benchmarkSymbol || '上证'} ${num(lastClose, 2)}`);
  }

  function renderPortfolioDualChartLW(topContainerId, bottomContainerId, benchOhlc, navSeries, opts = {}) {
    const topContainer = document.getElementById(topContainerId);
    const bottomContainer = bottomContainerId ? document.getElementById(bottomContainerId) : null;
    if (!topContainer) return;
    clearChartValueBadge(topContainer);
    if (bottomContainer) clearChartValueBadge(bottomContainer);

    const LWC = window.LightweightCharts;
    if (!LWC) {
      destroyPortfolioDualChartLW();
      topContainer.innerHTML = '<div class="wb-empty"><span>lightweight-charts 加载失败</span></div>';
      if (bottomContainer) bottomContainer.innerHTML = '<div class="wb-empty"><span>lightweight-charts 加载失败</span></div>';
      return;
    }

    const hasBench = Array.isArray(benchOhlc) && benchOhlc.length > 0;
    const showBenchmark = !!opts.showBenchmark && hasBench;
    const state = ensureDualState(topContainer, showBenchmark ? bottomContainer : null, LWC);
    if (!state) return;

    const navLineData = (Array.isArray(navSeries) ? navSeries : [])
      .map((point) => ({ time: point.date, value: Number(point.value) }))
      .filter((point) => Number.isFinite(point.value));
    const benchmarkLineData = showBenchmark ? normalizeBenchmarkLine(benchOhlc) : [];
    const marketStates = Array.isArray(opts.marketStates) ? opts.marketStates : [];
    const marketMaskData = buildMarketMaskData(marketStates);
    state.marketStates = marketStates;

    state.topMaskSeries?.setData(marketMaskData);
    state.topNavSeries.setData(navLineData);
    state.topBenchmarkSeries.setData(benchmarkLineData);
    try {
      state.topBenchmarkSeries.applyOptions({
        visible: showBenchmark,
        lastValueVisible: showBenchmark,
      });
      state.topChart.applyOptions({
        rightPriceScale: { visible: true, borderColor: '#334155', autoScale: true },
      });
    } catch (_) {}

    if (showBenchmark && state.bottomChart && state.bottomBenchmarkSeries) {
      state.bottomBenchRows = Array.isArray(benchOhlc) ? benchOhlc : [];
      state.bottomMaskSeries?.setData(marketMaskData);
      try {
        state.bottomBenchmarkSeries.applyOptions({
          priceScaleId: 'left',
          priceLineVisible: false,
          lastValueVisible: true,
          priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
          autoscaleInfoProvider: () => {
            const visibleRows = sliceVisibleRows(state.bottomBenchRows, state.bottomChart);
            const range = buildExpandedPriceRange(visibleRows);
            return range ? { priceRange: { minValue: range.min, maxValue: range.max } } : null;
          },
        });
      } catch (_) {}
      state.bottomBenchmarkSeries.setData(benchOhlc);
      updateBottomBadge(state, benchOhlc, opts.benchmarkSymbol);
    } else if (state.bottomContainer) {
      state.bottomMaskSeries?.setData([]);
      clearChartValueBadge(state.bottomContainer);
    }

    updateTopBadge(state, navLineData, benchmarkLineData);

    const totalBars = Math.max(navLineData.length, showBenchmark ? benchOhlc.length : 0);
    const visibleKey = [
      totalBars,
      navLineData[0]?.time || '',
      navLineData[navLineData.length - 1]?.time || '',
      showBenchmark ? (benchOhlc[0]?.time || '') : '',
      showBenchmark ? (benchOhlc[benchOhlc.length - 1]?.time || '') : '',
      showBenchmark ? 'with-bench' : 'nav-only',
    ].join('|');

    if (state.visibleKey !== visibleKey) {
      if (!state.initialized) {
        setInitialVisibleRange(state, totalBars);
        state.initialized = true;
      }
      state.visibleKey = visibleKey;
    }
    renderDualMarketMasks(state);
  }

  window.renderPortfolioDualChartLW = renderPortfolioDualChartLW;
  window.destroyPortfolioDualChartLW = destroyPortfolioDualChartLW;
})();
