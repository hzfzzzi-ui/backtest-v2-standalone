<script setup>
defineProps({
  summary: {
    type: Object,
    required: true,
  },
});
</script>

<template>
  <section class="wb-result-overview">
    <article class="wb-overview-card">
      <div class="wb-overview-title">运行概览</div>
      <dl class="wb-overview-grid">
        <div>
          <dt>实验ID</dt>
          <dd>{{ summary.expId }}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>{{ summary.status }}</dd>
        </div>
        <div>
          <dt>有效起点</dt>
          <dd>{{ summary.effectiveExecutionStartDate }}</dd>
        </div>
      </dl>
    </article>

    <article class="wb-overview-card">
      <div class="wb-overview-title">股票池口径</div>
      <dl class="wb-overview-grid">
        <div>
          <dt>区间</dt>
          <dd>{{ summary.universeRange }}</dd>
        </div>
        <div>
          <dt>基准</dt>
          <dd>{{ summary.benchmark }}</dd>
        </div>
        <div>
          <dt>股票池</dt>
          <dd>{{ summary.universeMode }}</dd>
        </div>
        <div>
          <dt>标的数</dt>
          <dd>{{ summary.universeCount }}</dd>
        </div>
      </dl>
    </article>

    <article class="wb-overview-card">
      <div class="wb-overview-title">策略口径</div>
      <dl class="wb-overview-grid">
        <div>
          <dt>策略</dt>
          <dd>{{ summary.strategy }}</dd>
        </div>
        <div>
          <dt>主参数</dt>
          <dd>{{ summary.strategyCore }}</dd>
        </div>
        <div>
          <dt>组合模式</dt>
          <dd>{{ summary.portfolioMode }}</dd>
        </div>
        <div>
          <dt>补充信息</dt>
          <dd>{{ summary.strategySummary }}</dd>
        </div>
      </dl>
    </article>
  </section>

  <section class="wb-kpi-grid">
    <article class="wb-kpi-card wb-kpi-pair">
      <div class="wb-kpi-pair-grid">
        <div>
          <span class="wb-kpi-sub">期初资金</span>
          <strong>{{ summary.initialCapital }}</strong>
        </div>
        <div>
          <span class="wb-kpi-sub">期末资金</span>
          <strong>{{ summary.finalCapital }}</strong>
        </div>
      </div>
    </article>

    <article class="wb-kpi-card wb-kpi-pair">
      <div class="wb-kpi-pair-grid">
        <div>
          <span class="wb-kpi-sub">年化收益</span>
          <strong>{{ summary.cagr }}</strong>
        </div>
        <div>
          <span class="wb-kpi-sub">总收益</span>
          <strong>{{ summary.totalReturn }}</strong>
        </div>
      </div>
    </article>

    <article class="wb-kpi-card wb-kpi-pair">
      <div class="wb-kpi-pair-grid">
        <div>
          <span class="wb-kpi-sub">最大回撤</span>
          <strong>{{ summary.maxDrawdown }}</strong>
        </div>
        <div>
          <span class="wb-kpi-sub">最大回撤时长</span>
          <strong>{{ summary.maxDrawdownDuration }}</strong>
        </div>
      </div>
    </article>

    <article class="wb-kpi-card wb-kpi-pair">
      <div class="wb-kpi-pair-grid">
        <div>
          <span class="wb-kpi-sub">夏普比率</span>
          <strong>{{ summary.sharpe }}</strong>
        </div>
        <div>
          <span class="wb-kpi-sub">卡玛比率</span>
          <strong>{{ summary.calmar }}</strong>
        </div>
      </div>
    </article>

    <article class="wb-kpi-card">
      <div class="wb-kpi-single">
        <span class="wb-kpi-sub">滚动夏普(126D)</span>
        <strong class="wb-kpi-value">{{ summary.rollingSharpe }}</strong>
      </div>
    </article>

    <article class="wb-kpi-card wb-kpi-pair">
      <div class="wb-kpi-pair-grid">
        <div>
          <span class="wb-kpi-sub">Alpha</span>
          <strong>{{ summary.alpha }}</strong>
        </div>
        <div>
          <span class="wb-kpi-sub">Beta</span>
          <strong>{{ summary.beta }}</strong>
        </div>
      </div>
    </article>

    <article class="wb-kpi-card">
      <div class="wb-kpi-single">
        <span class="wb-kpi-sub">单笔交易期望</span>
        <strong class="wb-kpi-value">{{ summary.expectancyPerTrade }}</strong>
      </div>
    </article>

    <article class="wb-kpi-card">
      <div class="wb-kpi-single">
        <span class="wb-kpi-sub">Profit Factor</span>
        <strong class="wb-kpi-value">{{ summary.profitFactor }}</strong>
      </div>
    </article>

    <article class="wb-kpi-card">
      <div class="wb-kpi-single">
        <span class="wb-kpi-sub">Win Rate</span>
        <strong class="wb-kpi-value">{{ summary.winRate }}</strong>
      </div>
    </article>

    <article class="wb-kpi-card">
      <div class="wb-kpi-single">
        <span class="wb-kpi-sub">交易次数</span>
        <strong class="wb-kpi-value">{{ summary.trades }}</strong>
      </div>
    </article>

    <article class="wb-kpi-card">
      <div class="wb-kpi-single">
        <span class="wb-kpi-sub">换手率</span>
        <strong class="wb-kpi-value">{{ summary.turnover }}</strong>
      </div>
    </article>

    <article class="wb-kpi-card">
      <div class="wb-kpi-single">
        <span class="wb-kpi-sub">TOP10收益集中度</span>
        <strong class="wb-kpi-value">{{ summary.top10ProfitConcentration }}</strong>
      </div>
    </article>
  </section>
</template>
