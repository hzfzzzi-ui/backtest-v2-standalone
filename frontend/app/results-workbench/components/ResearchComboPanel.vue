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
      <div class="wb-overview-title">组合研究锚点</div>
      <dl class="wb-overview-grid">
        <div>
          <dt>结果类型</dt>
          <dd>Research Combo</dd>
        </div>
        <div>
          <dt>组合模式</dt>
          <dd>{{ summary.comboMode }}</dd>
        </div>
        <div>
          <dt>覆盖窗口</dt>
          <dd>{{ summary.comboWindow }}</dd>
        </div>
        <div>
          <dt>说明</dt>
          <dd>{{ summary.comboReadOnlyNote }}</dd>
        </div>
      </dl>
    </article>

    <article class="wb-overview-card">
      <div class="wb-overview-title">组件实验</div>
      <dl class="wb-overview-grid">
        <div>
          <dt>个股 Alpha</dt>
          <dd>{{ summary.comboStockExpId }}</dd>
        </div>
        <div>
          <dt>ETF Beta</dt>
          <dd>{{ summary.comboEtfExpId }}</dd>
        </div>
        <div>
          <dt>假设口径</dt>
          <dd>{{ summary.comboAssumption }}</dd>
        </div>
      </dl>
    </article>
  </section>

  <section class="wb-kpi-grid">
    <article class="wb-kpi-card wb-kpi-pair">
      <div class="wb-kpi-pair-grid">
        <div>
          <span class="wb-kpi-sub">组合总收益</span>
          <strong>{{ summary.totalReturn }}</strong>
        </div>
        <div>
          <span class="wb-kpi-sub">年化收益</span>
          <strong>{{ summary.cagr }}</strong>
        </div>
      </div>
    </article>

    <article class="wb-kpi-card wb-kpi-pair">
      <div class="wb-kpi-pair-grid">
        <div>
          <span class="wb-kpi-sub">个股 Sleeve</span>
          <strong>{{ summary.comboStockTotalReturn }}</strong>
        </div>
        <div>
          <span class="wb-kpi-sub">ETF Sleeve</span>
          <strong>{{ summary.comboEtfTotalReturn }}</strong>
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
          <span class="wb-kpi-sub">夏普</span>
          <strong>{{ summary.sharpe }}</strong>
        </div>
      </div>
    </article>
  </section>
</template>
