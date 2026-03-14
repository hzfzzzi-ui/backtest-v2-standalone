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
const stockNames = computed(() => props.snapshot?.artifacts?.stockNames || {});

function displayName(symbol) {
  return stockZh(symbol, stockNames.value);
}

function togglePanel() {
  props.patchViewState({ openPanels: { tradesPanel: !open.value } });
}
</script>

<template>
  <section class="wb-result-acc" data-result-panel="tradesPanel" :class="{ 'wb-open': open }">
    <button type="button" class="wb-result-acc-toggle" :aria-expanded="String(open)" @click="togglePanel">
      <span class="wb-acc-summary-main">
        <span class="wb-acc-summary-title">Detailed Trades</span>
      </span>
      <span class="wb-mini wb-acc-summary-meta">{{ fmtInt(rows.length) }} rows</span>
    </button>
    <div class="wb-result-acc-body" :hidden="!open">
      <div class="wb-table-wrap wb-trades-table-wrap wb-scrollbox">
        <table class="wb-table wb-table-compact">
          <thead>
            <tr>
              <th>Date</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Price</th>
              <th>Qty</th>
              <th>Amount</th>
              <th>Reason</th>
              <th>Entry Alpha</th>
              <th>Sleeve</th>
              <th>Entry Reason</th>
              <th>Exit Owner</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!rows.length">
              <td colspan="11" class="wb-symbol-empty">No trades</td>
            </tr>
            <tr v-for="(row, idx) in rows" :key="`${row.date || ''}-${row.symbol || ''}-${idx}`">
              <td>{{ row.date || '-' }}</td>
              <td>
                {{ displayName(row.symbol || '-') }}
                <span v-if="displayName(row.symbol || '-') !== (row.symbol || '-')" class="wb-mini" style="margin-left:6px">{{ row.symbol }}</span>
              </td>
              <td>{{ row.side || '-' }}</td>
              <td class="num">{{ fmtMoney(row.price) }}</td>
              <td class="num">{{ fmtInt(row.qty) }}</td>
              <td class="num">{{ fmtMoney(row.amount) }}</td>
              <td>{{ row.reason_code || row.reason || '-' }}</td>
              <td>{{ row.entry_alpha_id || '-' }}</td>
              <td>{{ row.entry_sleeve_id || '-' }}</td>
              <td>{{ row.entry_reason_code || '-' }}</td>
              <td>{{ row.exit_owner || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>