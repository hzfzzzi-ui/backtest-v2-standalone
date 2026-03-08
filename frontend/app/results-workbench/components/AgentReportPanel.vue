<script setup>
import { computed } from 'vue';
import { buildAgentMarkdown, normalizeSymbolRows } from '../helpers/resultsFormatting.js';

const props = defineProps({
  snapshot: {
    type: Object,
    required: true,
  },
});

const markdown = computed(() => buildAgentMarkdown(props.snapshot));
const meta = computed(() => {
  const expId = props.snapshot?.result?.exp_id || '-';
  const count = normalizeSymbolRows(props.snapshot).length;
  return `实验=${expId} | 个股=${count} | Markdown已就绪`;
});

async function copyMarkdown() {
  try {
    await navigator.clipboard.writeText(markdown.value);
  } catch (_) {
    // noop
  }
}

function downloadMarkdown() {
  const expId = props.snapshot?.result?.exp_id || 'report';
  const blob = new Blob([markdown.value], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${expId}_agent_report.md`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <section class="wb-agent-report-section">
    <div class="wb-agent-report-head">
      <div>
        <div class="wb-symbol-title">AI分析报告（Markdown）</div>
        <div class="wb-mini">{{ meta }}</div>
      </div>
      <div class="wb-inline">
        <button class="pill" @click="copyMarkdown">复制 Markdown</button>
        <button class="pill" @click="downloadMarkdown">导出 Markdown</button>
      </div>
    </div>
    <textarea class="wb-agent-report-box wb-scrollbox" readonly :value="markdown" />
  </section>
</template>
