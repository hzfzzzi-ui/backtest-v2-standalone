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
        <div class="wb-detail-title">归因摘要</div>
        <dl class="wb-detail-kv">
          <div v-for="entry in model.summaryCards" :key="entry.label">
            <dt>{{ entry.label }}</dt>
            <dd>{{ entry.value }}</dd>
          </div>
          <div>
            <dt>最近状态日志日期</dt>
            <dd>{{ model.latestStateDate }}</dd>
          </div>
          <div>
            <dt>最近预算日志日期</dt>
            <dd>{{ model.latestBudgetDate }}</dd>
          </div>
          <div>
            <dt>最近人工覆盖日期</dt>
            <dd>{{ model.latestManualOverrideDate }}</dd>
          </div>
        </dl>
      </article>

      <article class="wb-detail-card">
        <div class="wb-detail-title">Reason Code Families</div>
        <dl class="wb-detail-list">
          <div v-for="entry in model.budgetReasonCodes" :key="`budget-${entry.name}`">
            <dt>Budget · {{ entry.name }}</dt>
            <dd>{{ entry.value }}</dd>
          </div>
          <div v-for="entry in model.sleeveReasonCodes" :key="`sleeve-${entry.name}`">
            <dt>Sleeve · {{ entry.name }}</dt>
            <dd>{{ entry.value }}</dd>
          </div>
          <div v-for="entry in model.stateReasonCodes" :key="`state-${entry.name}`">
            <dt>State · {{ entry.name }}</dt>
            <dd>{{ entry.value }}</dd>
          </div>
          <div v-for="entry in model.manualOverrideReasons" :key="`override-${entry.name}`">
            <dt>Override · {{ entry.name }}</dt>
            <dd>{{ entry.value }}</dd>
          </div>
          <div v-if="!model.budgetReasonCodes.length && !model.sleeveReasonCodes.length && !model.stateReasonCodes.length && !model.manualOverrideReasons.length">
            <dt>Reason Codes</dt>
            <dd>暂无</dd>
          </div>
        </dl>
      </article>

      <article class="wb-detail-card">
        <div class="wb-detail-title">Sleeves / Refs</div>
        <div>
          <div class="wb-field-label">Sleeves</div>
          <div class="wb-chip-list">
            <span v-for="sleeve in model.sleeves" :key="sleeve" class="wb-chip">{{ sleeve }}</span>
            <span v-if="!model.sleeves.length" class="wb-chip">无</span>
          </div>
        </div>
        <div>
          <div class="wb-field-label">引用产物</div>
          <ul class="wb-code-list">
            <li v-for="ref in model.refs" :key="ref.name"><strong>{{ ref.name }}</strong>: {{ ref.value }}</li>
            <li v-if="!model.refs.length">暂无</li>
          </ul>
        </div>
      </article>
    </section>

    <section v-else class="wb-empty">
      <span>当前结果未提供 Attribution 审计摘要。</span>
    </section>
  </section>
</template>
