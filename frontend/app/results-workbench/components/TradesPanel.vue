<script setup>
import { computed } from 'vue';
import { fmtInt, fmtMoney, normalizeTradesRows, stockZh } from '../helpers/resultsFormatting.js';

const props = defineProps({
  snapshot: {
    type: Object,
    required: true,
  },
  patchViewState: {
    type: Function,
    required: true,
  },
});

const view = computed(() => props.snapshot?.view || {});
const open = computed(() => !!view.value.openPanels?.tradesPanel);
const rows = computed(() => normalizeTradesRows(props.snapshot));

function togglePanel() {
  props.patchViewState({ openPanels: { tradesPanel: !open.value } });
}
</script>

<template>
  <section class="wb-result-acc" :class="{ 'wb-open': open }">
    <button type="button" class="wb-result-acc-toggle" :aria-expanded="String(open)" @click="togglePanel">
      <span class="wb-acc-summary-main">
        <span class="wb-acc-summary-title">详细交易明细</span>
      </span>
      <span class="wb-mini wb-acc-summary-meta">全部交易 {{ fmtInt(rows.length) }} 条</span>
    </button>
    <div class="wb-result-acc-body" :hidden="!open">
      <div class="wb-table-wrap wb-trades-table-wrap wb-scrollbox">
        <table class="wb-table wb-table-compact">
          <thead>
            <tr>
              <th>日期</th>
              <th>标的</th>
              <th>方向</th>
              <th>价格</th>
              <th>数量</th>
              <th>金额</th>
              <th>原因</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length">
              <td colspan="7" class="wb-symbol-empty">暂无交易明细</td>
            </tr>
            <tr v-for="(row, idx) in rows" :key="`${row.date || ''}-${row.symbol || ''}-${idx}`">
              <td>{{ row.date || '-' }}</td>
              <td>
                {{ stockZh(row.symbol || '-') }}
                <span v-if="stockZh(row.symbol || '-') !== (row.symbol || '-')" class="wb-mini" style="margin-left:6px">{{ row.symbol }}</span>
              </td>
              <td>{{ row.side || '-' }}</td>
              <td class="num">{{ fmtMoney(row.price) }}</td>
              <td class="num">{{ fmtInt(row.qty) }}</td>
              <td class="num">{{ fmtMoney(row.amount) }}</td>
              <td>{{ row.reason_code || row.reason || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
