<script setup>
defineProps({
  model: {
    type: Object,
    required: true,
  },
});
</script>

<template>
  <section class="wb-workbench-panel">
    <section v-if="model.available" class="wb-detail-grid">
      <article class="wb-detail-card">
        <div class="wb-detail-title">状态摘要</div>
        <dl class="wb-detail-kv">
          <div>
            <dt>基础五状态</dt>
            <dd>{{ model.baseState }}</dd>
          </div>
          <div>
            <dt>生效五状态</dt>
            <dd>{{ model.effectiveState }}</dd>
          </div>
          <div>
            <dt>基础三状态</dt>
            <dd>{{ model.coarseState }}</dd>
          </div>
          <div>
            <dt>生效三状态</dt>
            <dd>{{ model.effectiveCoarseState }}</dd>
          </div>
          <div>
            <dt>置信度</dt>
            <dd>{{ model.confidence }}</dd>
          </div>
          <div>
            <dt>预算倍率</dt>
            <dd>{{ model.riskBudgetMultiplier }}</dd>
          </div>
          <div>
            <dt>防守偏置</dt>
            <dd>{{ model.defenseBias }}</dd>
          </div>
          <div>
            <dt>持续 bar 数</dt>
            <dd>{{ model.durationBars }}</dd>
          </div>
          <div class="wb-global-grid-span">
            <dt>切换原因</dt>
            <dd>{{ model.transitionReason }}</dd>
          </div>
        </dl>
      </article>

      <article class="wb-detail-card">
        <div class="wb-detail-title">原因与人工覆盖</div>
        <div>
          <div class="wb-field-label">Reason Codes</div>
          <div class="wb-chip-list">
            <span v-for="code in model.reasonCodes" :key="code" class="wb-chip">{{ code }}</span>
            <span v-if="!model.reasonCodes.length" class="wb-chip">无</span>
          </div>
        </div>
        <div>
          <div class="wb-field-label">人工覆盖摘要</div>
          <div>{{ model.manualOverrideSummary }}</div>
        </div>
        <div class="wb-note">Regime 面板只消费正式 snapshot / run_meta 字段，不从旧 market_state 或 trade_mode 反推状态。</div>
      </article>

      <article class="wb-detail-card">
        <div class="wb-detail-title">子分数</div>
        <dl class="wb-detail-list">
          <div v-for="entry in model.subscores" :key="entry.name">
            <dt>{{ entry.name }}</dt>
            <dd>{{ entry.value }}</dd>
          </div>
          <div v-if="!model.subscores.length">
            <dt>subscores</dt>
            <dd>暂无</dd>
          </div>
        </dl>
      </article>

      <article class="wb-detail-card">
        <div class="wb-detail-title">Block Scores / Stability</div>
        <dl class="wb-detail-list">
          <div v-for="entry in model.blockScores" :key="`block-${entry.name}`">
            <dt>{{ entry.name }}</dt>
            <dd>{{ entry.value }}</dd>
          </div>
          <div v-for="entry in model.stability" :key="`stability-${entry.name}`">
            <dt>{{ entry.name }}</dt>
            <dd>{{ entry.value }}</dd>
          </div>
          <div v-if="!model.blockScores.length && !model.stability.length">
            <dt>状态稳定性</dt>
            <dd>暂无</dd>
          </div>
        </dl>
      </article>
    </section>

    <section v-else class="wb-empty">
      <span>当前结果未提供正式 Regime payload。</span>
    </section>
  </section>
</template>
