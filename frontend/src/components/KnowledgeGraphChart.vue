<script setup lang="ts">
import {ref, onMounted, watch, onUnmounted} from 'vue'

const props = defineProps<{ nodes: any[], edges: any[] }>()
const container = ref<HTMLElement>()
let chartInstance: any = null

async function initChart() {
  if (!container.value || !props.nodes.length) return
  const echarts = await import('echarts')
  if (!chartInstance) {
    chartInstance = echarts.init(container.value)
  }

  const colorMap: Record<string, string> = {
    prerequisite: '#ef4444',
    related: '#3b82f6',
    contains: '#22c55e',
  }

  const option = {
    tooltip: {},
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      label: { show: true, position: 'bottom' },
      force: { repulsion: 200, edgeLength: 100 },
      data: props.nodes.map((n: any) => ({
        id: String(n.id),
        name: n.name || n.code,
        symbolSize: 20 + (n.level || 1) * 8,
        itemStyle: { color: ['#3b82f6', '#8b5cf6', '#f59e0b'][Math.min((n.level || 1) - 1, 2)] },
      })),
      links: props.edges.map((e: any) => ({
        source: String(e.from),
        target: String(e.to),
        lineStyle: { color: colorMap[e.type] || '#999', width: 1 + (e.confidence || 0.5) },
        label: { show: true, formatter: e.type },
      })),
    }],
  }

  chartInstance.setOption(option)
}

onMounted(initChart)
watch(() => [props.nodes, props.edges], initChart, { deep: true })
onUnmounted(() => chartInstance?.dispose())
</script>

<template>
  <div ref="container" style="width:100%; height:500px;"></div>
</template>