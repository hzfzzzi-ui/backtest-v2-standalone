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
        <div class="wb-detail-title">总控摘要</div>
        <dl class="wb-detail-kv">
          <div>
            <dt>资产范围</dt>
            <dd>{{ model.assetScope }}</dd>
          </div>
          <div>
            <dt>预算 Owner</dt>
            <dd>{{ model.budgetOwner }}</dd>
          </div>
          <div>
            <dt>消费者 Sleeve</dt>
            <dd>{{ model.consumerSleeveId }}</dd>
          </div>
          <div>
            <dt>系统角色</dt>
            <dd>{{ model.consumerRole }}</dd>
          </div>
          <div>
            <dt>总风险预算</dt>
            <dd>{{ model.totalRiskBudget }}</dd>
          </div>
          <div>
            <dt>总暴露上限</dt>
            <dd>{{ model.totalExposureCap }}</dd>
          </div>
          <div>
            <dt>硬上限仓位数</dt>
            <dd>{{ model.hardMaxPositions }}</dd>
          </div>
          <div>
            <dt>当前有效仓位数</dt>
            <dd>{{ model.effectiveMaxPositions }}</dd>
          </div>
        </dl>
      </article>

      <article class="wb-detail-card">
        <div class="wb-detail-title">风险状态</div>
        <dl class="wb-detail-kv">
          <div>
            <dt>当前回撤</dt>
            <dd>{{ model.drawdown }}</dd>
          </div>
          <div>
            <dt>回撤状态</dt>
            <dd>{{ model.drawdownState }}</dd>
          </div>
          <div>
            <dt>恢复状态</dt>
            <dd>{{ model.recoveryState }}</dd>
          </div>
          <div>
            <dt>冷却状态</dt>
            <dd>{{ model.cooldownState }}</dd>
          </div>
          <div>
            <dt>防守下限</dt>
            <dd>{{ model.defenseFloor }}</dd>
          </div>
          <div>
            <dt>防守下限状态</dt>
            <dd>{{ model.defenseFloorState }}</dd>
          </div>
          <div>
            <dt>防守偏置</dt>
            <dd>{{ model.defenseBias }}</dd>
          </div>
        </dl>
      </article>

      <article class="wb-detail-card">
        <div class="wb-detail-title">Budget Reason Codes</div>
        <div class="wb-chip-list">
          <span v-for="code in model.budgetReasonCodes" :key="code" class="wb-chip">{{ code }}</span>
          <span v-if="!model.budgetReasonCodes.length" class="wb-chip">无</span>
        </div>
        <div>
          <div class="wb-field-label">Local Budget Controls</div>
          <div class="wb-chip-list">
            <span v-for="control in model.localBudgetControls" :key="control" class="wb-chip">{{ control }}</span>
            <span v-if="!model.localBudgetControls.length" class="wb-chip">无</span>
          </div>
        </div>
      </article>

      <article class="wb-detail-card">
        <div class="wb-detail-title">Sleeve Budget 摘要</div>
        <dl class="wb-detail-list">
          <div v-for="item in model.sleeveBudgets" :key="item.sleeveId">
            <dt>{{ item.sleeveId }}</dt>
            <dd>{{ item.systemRole }} | slots {{ item.slotCap }} / {{ item.availableSlots }} | candidates {{ item.candidateCount }} | selected {{ item.selectedCount }} | share {{ item.budgetShare }}</dd>
          </div>
          <div v-if="!model.sleeveBudgets.length">
            <dt>Sleeve Budget</dt>
            <dd>暂无</dd>
          </div>
        </dl>
      </article>
    </section>

    <section v-else class="wb-empty">
      <span>当前结果未提供正式 Governor snapshot。</span>
    </section>
  </section>
</template>
