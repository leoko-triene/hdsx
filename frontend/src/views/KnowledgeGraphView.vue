<script setup lang="ts">
import {ref, onMounted, computed} from 'vue'
import {api} from '../api/client'
import {useRoute} from 'vue-router'
import KnowledgeGraphChart from '../components/KnowledgeGraphChart.vue'

const route = useRoute()
const courseId = Number(route.params.courseId)
const graph = ref<any>(null)
const loading = ref(false)
const generating = ref(false)

const nodeMap = computed(() => {
  const map: Record<number, string> = {}
  if (graph.value?.nodes) {
    for (const n of graph.value.nodes) {
      map[n.id] = n.name || n.code
    }
  }
  return map
})

async function load() {
  loading.value = true
  try {
    graph.value = (await api.get(`/knowledge-graphs/course/${courseId}`)).data
  } catch (e: any) {
    if (e.message.includes('404')) graph.value = null
  }
  loading.value = false
}

async function generate() {
  generating.value = true
  try {
    await api.post('/knowledge-graphs/generate', {course_id: courseId})
    await load()
  } catch (e: any) {
    alert(e.message)
  } finally {
    generating.value = false
  }
}

async function approve() {
  if (!graph.value) return
  await api.post(`/knowledge-graphs/approve/${graph.value.id}`)
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-title">
      <h1>知识点图谱</h1>
    </div>

    <div v-if="!graph" class="card">
      <p>该课程尚未生成知识点图谱。</p>
      <button :disabled="generating" @click="generate">
        {{ generating ? 'AI 正在生成...' : '从教材生成知识点图谱' }}
      </button>
    </div>

    <div v-else class="card">
      <div class="section-header">
        <h2>
          图谱 v{{ graph.version }}
          <span :class="['status', graph.status]">{{ graph.status }}</span>
        </h2>
        <div>
          <button v-if="graph.status === 'draft'" @click="approve">审核通过</button>
          <button @click="generate">重新生成</button>
        </div>
      </div>

      <KnowledgeGraphChart :nodes="graph.nodes" :edges="graph.edges" />

      <h3>知识点列表</h3>
      <table class="data-table">
        <thead>
          <tr><th>编码</th><th>名称</th><th>描述</th><th>层级</th></tr>
        </thead>
        <tbody>
          <tr v-for="n in graph.nodes" :key="n.id">
            <td>{{ n.code }}</td>
            <td>{{ n.name }}</td>
            <td>{{ n.description }}</td>
            <td>{{ n.level }}</td>
          </tr>
        </tbody>
      </table>

      <h3>知识关系</h3>
      <table class="data-table">
        <thead>
          <tr><th>前置</th><th>关系</th><th>后续</th><th>置信度</th></tr>
        </thead>
        <tbody>
          <tr v-for="e in graph.edges" :key="e.from + '-' + e.to">
            <td>{{ nodeMap[e.from] || e.from }}</td>
            <td>{{ e.type }}</td>
            <td>{{ nodeMap[e.to] || e.to }}</td>
            <td>{{ e.confidence }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>