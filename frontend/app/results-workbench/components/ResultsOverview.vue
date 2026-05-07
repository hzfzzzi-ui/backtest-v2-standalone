<script setup>
import { computed } from 'vue';

const props = defineProps({
  summary: {
    type: Object,
    required: true,
  },
  mode: {
    type: String,
    default: 'full',
  },
});

const isHeadlineMode = computed(() => props.mode === 'headline');
</script>

<template>
  <section class="wb-result-overview">
    <article class="wb-overview-card">
      <div class="wb-overview-title">运行概览</div>
      <dl class="wb-overview-grid">
        <div>
          <dt>实验</dt>
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
        <div v-if="summary.assetScope === 'cn_etf'">
          <dt>资产范围</dt>
          <dd>A股ETF</dd>
        </div>
      </dl>
    </article>

    <article v-if="!isHeadlineMode" class="wb-overview-card">
      <div class="wb-overview-title">{{ summary.universeSectionTitle }}</div>
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
          <dt>{{ summary.universeModeLabel }}</dt>
          <dd>{{ summary.universeMode }}</dd>
        </div>
        <div>
          <dt>{{ summary.universeCountLabel }}</dt>
          <dd>{{ summary.universeCount }}</dd>
        </div>
        <template v-if="summary.assetScope === 'cn_etf'">
          <div>
            <dt>ETF批次</dt>
            <dd>{{ summary.etfBatch }}</dd>
          </div>
          <div>
            <dt>覆盖区间</dt>
            <dd>{{ summary.coverageWindow }}</dd>
          </div>
          <div>
            <dt>价格语义</dt>
            <dd>{{ summary.priceSeriesSemantics }}</dd>
          </div>
          <div>
            <dt>ETF列表</dt>
            <dd>{{ summary.etfSymbols }}</dd>
          </div>
        </template>
      </dl>
    </article>

    <article v-if="!isHeadlineMode" class="wb-overview-card">
      <div class="wb-overview-title">策略上下文</div>
      <dl class="wb-overview-grid">
        <div>
          <dt>策略</dt>
          <dd>{{ summary.strategy }}</dd>
        </div>
        <div>
          <dt>核心参数</dt>
          <dd>{{ summary.strategyCore }}</dd>
        </div>
        <div>
          <dt>组合模式</dt>
          <dd>{{ summary.portfolioMode }}</dd>
        </div>
        <div>
          <dt>备注</dt>
          <dd>{{ summary.strategySummary }}</dd>
        </div>
      </dl>
    </article>
  </section>

  <section class="wb-kpi-grid" :class="{ 'wb-kpi-grid-headline': isHeadlineMode }">
    <article class="wb-kpi-card wb-kpi-pair">
      <div class="wb-kpi-pair-grid">
        <div>
          <span class="wb-kpi-sub">初始资金</span>
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
          <span class="wb-kpi-sub">CAGR</span>
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
          <span class="wb-kpi-sub">回撤时长</span>
          <strong>{{ summary.maxDrawdownDuration }}</strong>
        </div>
      </div>
    </article>

    <article class="wb-kpi-card wb-kpi-pair">
      <div class="wb-kpi-pair-grid">
        <div>
          <span class="wb-kpi-sub">夏普</span>
          <strong>{{ summary.sharpe }}</strong>
        </div>
        <div>
          <span class="wb-kpi-sub">Calmar</span>
          <strong>{{ summary.calmar }}</strong>
        </div>
      </div>
    </article>

    <article v-if="isHeadlineMode" class="wb-kpi-card wb-kpi-pair">
      <div class="wb-kpi-pair-grid">
        <div>
          <span class="wb-kpi-sub">胜率</span>
          <strong>{{ summary.winRate }}</strong>
        </div>
        <div>
          <span class="wb-kpi-sub">交易数</span>
          <strong>{{ summary.trades }}</strong>
        </div>
      </div>
    </article>

    <template v-else>
      <article class="wb-kpi-card">
        <div class="wb-kpi-single">
          <span class="wb-kpi-sub">滚动夏普（126日）</span>
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
          <span class="wb-kpi-sub">单笔期望</span>
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
          <span class="wb-kpi-sub">胜率</span>
          <strong class="wb-kpi-value">{{ summary.winRate }}</strong>
        </div>
      </article>

      <article class="wb-kpi-card">
        <div class="wb-kpi-single">
          <span class="wb-kpi-sub">交易数</span>
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
          <span class="wb-kpi-sub">前十盈利集中度</span>
          <strong class="wb-kpi-value">{{ summary.top10ProfitConcentration }}</strong>
        </div>
      </article>
    </template>
  </section>
</template>
