<script setup>
import { computed } from 'vue';
import { buildUnifiedStageFunnelHtml } from '../helpers/resultsFormatting.js';

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
const open = computed(() => !!view.value.openPanels?.funnelPanel);
const funnel = computed(() => buildUnifiedStageFunnelHtml(props.snapshot));

function togglePanel() {
  props.patchViewState({ openPanels: { funnelPanel: !open.value } });
}
</script>

<template>
  <section class="wb-result-acc" :class="{ 'wb-open': open }">
    <button type="button" class="wb-result-acc-toggle" :aria-expanded="String(open)" @click="togglePanel">
      <span class="wb-acc-summary-main">
        <span class="wb-acc-summary-title">9阶段漏斗</span>
      </span>
      <span class="wb-mini wb-acc-summary-meta">{{ funnel.meta }}</span>
    </button>
    <div class="wb-result-acc-body" :hidden="!open">
      <div class="wb-mini" v-html="funnel.html"></div>
    </div>
  </section>
</template>
