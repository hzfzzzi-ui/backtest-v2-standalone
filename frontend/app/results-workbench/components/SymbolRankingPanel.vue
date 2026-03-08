<script setup>
import { computed } from 'vue';
import { fmtInt, fmtPct, normalizeSymbolRows, stockZh } from '../helpers/resultsFormatting.js';

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

const rows = computed(() => normalizeSymbolRows(props.snapshot));
const view = computed(() => props.snapshot?.view || {});
const open = computed(() => !!view.value.openPanels?.symbolPanel);

const filteredRows = computed(() => {
  const keyword = String(view.value.symbolFilter || '').trim().toLowerCase();
  const list = keyword
    ? rows.value.filter((row) => String(row.symbol || '').toLowerCase().includes(keyword) || String(stockZh(row.symbol) || '').toLowerCase().includes(keyword))
    : rows.value.slice();
  const sorter = String(view.value.symbolSort || 'return_desc');
  if (sorter === 'drawdown_asc') list.sort((a, b) => Number(a.max_drawdown || 0) - Number(b.max_drawdown || 0));
  else if (sorter === 'trades_desc') list.sort((a, b) => Number(b.trades || 0) - Number(a.trades || 0));
  else list.sort((a, b) => Number(b.return_pct || 0) - Number(a.return_pct || 0));
  return list;
});

function togglePanel() {
  props.patchViewState({ openPanels: { symbolPanel: !open.value } });
}

function onFilter(event) {
  props.patchViewState({ symbolFilter: String(event.target.value || '') });
}

function onSort(event) {
  props.patchViewState({ symbolSort: String(event.target.value || 'return_desc') });
}

function selectSymbol(symbol) {
  props.patchViewState({
    chartMode: 'symbol',
    selectedSymbol: String(symbol || '').toLowerCase(),
  });
}
</script>

<template>
  <section class="wb-result-acc wb-symbol-rank-acc" :class="{ 'wb-open': open }">
    <button type="button" class="wb-result-acc-toggle" :aria-expanded="String(open)" @click="togglePanel">
      <span class="wb-acc-summary-main">
        <span class="wb-acc-summary-title">个股排名</span>
        <span class="wb-mini wb-acc-summary-meta">默认收起 | {{ fmtInt(filteredRows.length) }} 只</span>
      </span>
    </button>
    <div class="wb-result-acc-body wb-symbol-panel-body" :hidden="!open">
      <div class="wb-symbol-head">
        <div>
          <div class="wb-symbol-title">个股排名</div>
          <div class="wb-mini">展开后查看个股收益、回撤和交易数，点击任一行可切到对应个股。</div>
        </div>
        <div class="wb-inline wb-symbol-tools">
          <input :value="view.symbolFilter || ''" type="text" class="formInput wb-input-sm" placeholder="筛选标的" @input="onFilter" />
          <select :value="view.symbolSort || 'return_desc'" class="formInput wb-input-sm" @change="onSort">
            <option value="return_desc">收益优先</option>
            <option value="drawdown_asc">回撤更小</option>
            <option value="trades_desc">交易更多</option>
          </select>
        </div>
      </div>
      <div class="wb-table-wrap wb-gap-top wb-symbol-table-wrap wb-scrollbox">
        <table class="wb-table wb-table-compact">
          <thead>
            <tr>
              <th>标的</th>
              <th>收益</th>
              <th>回撤</th>
              <th>交易数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!filteredRows.length">
              <td colspan="4" class="wb-symbol-empty">暂无个股绩效数据</td>
            </tr>
            <tr
              v-for="row in filteredRows"
              :key="row.symbol"
              class="wb-symbol-row"
              :class="{ active: String(view.selectedSymbol || '') === String(row.symbol || '').toLowerCase() }"
              @click="selectSymbol(row.symbol)"
            >
              <td>
                {{ stockZh(row.symbol) }}
                <span v-if="stockZh(row.symbol) !== row.symbol" class="wb-mini" style="margin-left:6px">{{ row.symbol }}</span>
              </td>
              <td class="num">{{ fmtPct(row.return_pct) }}</td>
              <td class="num">{{ fmtPct(row.max_drawdown) }}</td>
              <td class="num">{{ fmtInt(row.trades) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
