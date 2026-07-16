<script setup lang="ts">
import {ref, onMounted, computed} from 'vue'
import {api} from '../api/client'
import {useRoute} from 'vue-router'
import KnowledgeGraphChart from '../components/KnowledgeGraphChart.vue'

const route = useRoute()
const courseId = Number(route.params.courseId)
const graph = ref<any>(null)
const versions = ref<any[]>([])
const selectedGraphId = ref<number | null>(null)
const loading = ref(false)
const generating = ref(false)
const error = ref('')
const message = ref('')

const isLatest = computed(() => {
  if (!graph.value || !versions.value.length) return true
  return graph.value.id === versions.value[0].id
})

const showPointDialog = ref(false)
const pointForm = ref<any>({id: 0, code: '', name: '', description: '', chapter_id: null})
const editingPoint = computed(() => !!pointForm.value.id)

const showRelationDialog = ref(false)
const relationForm = ref<any>({id: 0, from_id: null as number | null, to_id: null as number | null, relation_type: 'prerequisite', confidence: 0.85})
const editingRelation = computed(() => !!relationForm.value.id)

const relationTypes = [
  {value: 'prerequisite', label: '前置依赖'},
  {value: 'related', label: '关联'},
  {value: 'contains', label: '包含'},
]

const nodeMap = computed(() => {
  const map: Record<number, string> = {}
  if (graph.value?.nodes) {
    for (const n of graph.value.nodes) {
      map[n.id] = n.name || n.code
    }
  }
  return map
})

const knowledgePoints = computed(() => graph.value?.nodes || [])

async function load(versionId?: number | null) {
  loading.value = true
  error.value = ''
  try {
    if (versionId) {
      graph.value = (await api.get(`/knowledge-graphs/${versionId}`)).data
      selectedGraphId.value = versionId
    } else {
      graph.value = (await api.get(`/knowledge-graphs/course/${courseId}`)).data
      selectedGraphId.value = graph.value?.id || null
    }
    const versionsRes = await api.get(`/knowledge-graphs/course/${courseId}/versions`)
    versions.value = versionsRes.data || []
  } catch (e: any) {
    if (e.message.includes('404')) graph.value = null
    else error.value = e.message
  }
  loading.value = false
}

async function generate() {
  generating.value = true
  error.value = ''
  try {
    await api.post('/knowledge-graphs/generate', {course_id: courseId})
    await load()
    message.value = '知识点图谱已重新生成'
  } catch (e: any) {
    error.value = e.message
  } finally {
    generating.value = false
  }
}

async function onSelectVersion(event: Event) {
  const target = event.target as HTMLSelectElement
  const value = target.value
  if (!value) {
    await load()
    return
  }
  await load(Number(value))
}

async function approve() {
  if (!graph.value) return
  try {
    await api.post(`/knowledge-graphs/approve/${graph.value.id}`)
    message.value = '图谱已审核通过'
    await load()
  } catch (e: any) {
    error.value = e.message
  }
}

function openPointDialog(point?: any) {
  error.value = ''
  if (point) {
    pointForm.value = {id: point.id, code: point.code, name: point.name, description: point.description || '', chapter_id: point.chapter_id || null}
  } else {
    pointForm.value = {id: 0, code: '', name: '', description: '', chapter_id: null}
  }
  showPointDialog.value = true
}

function closePointDialog() {
  showPointDialog.value = false
}

async function savePoint() {
  error.value = ''
  if (!pointForm.value.code.trim() || !pointForm.value.name.trim()) {
    error.value = '请填写知识点编码和名称'
    return
  }
  try {
    const payload = {
      code: pointForm.value.code.trim(),
      name: pointForm.value.name.trim(),
      description: pointForm.value.description?.trim() || null,
      chapter_id: pointForm.value.chapter_id,
    }
    if (editingPoint.value) {
      await api.put(`/knowledge-graphs/points/${pointForm.value.id}`, payload)
      message.value = '知识点已更新'
    } else {
      await api.post(`/knowledge-graphs/course/${courseId}/points`, payload)
      message.value = '知识点已添加'
    }
    closePointDialog()
    await load()
  } catch (e: any) {
    error.value = e.message
  }
}

async function deletePoint(point: any) {
  if (!confirm(`确定删除知识点「${point.name}」吗？相关的边也会被删除。`)) return
  try {
    await api.delete(`/knowledge-graphs/points/${point.id}`)
    message.value = '知识点已删除'
    await load()
  } catch (e: any) {
    error.value = e.message
  }
}

function openRelationDialog(relation?: any) {
  error.value = ''
  if (relation) {
    relationForm.value = {id: relation.id || 0, from_id: relation.from, to_id: relation.to, relation_type: relation.type, confidence: relation.confidence}
  } else {
    relationForm.value = {id: 0, from_id: null, to_id: null, relation_type: 'prerequisite', confidence: 0.85}
  }
  showRelationDialog.value = true
}

function closeRelationDialog() {
  showRelationDialog.value = false
}

async function saveRelation() {
  error.value = ''
  if (!relationForm.value.from_id || !relationForm.value.to_id) {
    error.value = '请选择前置知识点和后续知识点'
    return
  }
  try {
    const payload = {
      from_id: Number(relationForm.value.from_id),
      to_id: Number(relationForm.value.to_id),
      relation_type: relationForm.value.relation_type,
      confidence: Number(relationForm.value.confidence),
    }
    if (editingRelation.value) {
      await api.put(`/knowledge-graphs/relations/${relationForm.value.id}`, payload)
      message.value = '关系已更新'
    } else {
      await api.post(`/knowledge-graphs/course/${courseId}/relations`, payload)
      message.value = '关系已添加'
    }
    closeRelationDialog()
    await load()
  } catch (e: any) {
    error.value = e.message
  }
}

async function deleteRelation(relation: any) {
  const fromName = nodeMap.value[relation.from] || relation.from
  const toName = nodeMap.value[relation.to] || relation.to
  if (!confirm(`确定删除「${fromName}」→「${toName}」的${relationTypes.find(t => t.value === relation.type)?.label || relation.type}关系吗？`)) return
  try {
    await api.delete(`/knowledge-graphs/relations/${relation.id}`)
    message.value = '关系已删除'
    await load()
  } catch (e: any) {
    error.value = e.message
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-title">
      <h1>知识点图谱</h1>
    </div>

    <div v-if="error" class="notice error">{{error}} <button class="text-button" @click="error=''">关闭</button></div>
    <div v-if="message" class="notice success-box">{{message}} <button class="text-button" @click="message=''">关闭</button></div>

    <div v-if="!graph" class="card">
      <p>该课程尚未生成知识点图谱。</p>
      <button :disabled="generating" @click="generate">
        {{ generating ? 'AI 正在生成...' : '从教材生成知识点图谱' }}
      </button>
    </div>

    <div v-else class="card">
      <div v-if="!isLatest" class="notice info">
        当前正在查看历史版本 v{{ graph.version }}，手动编辑已禁用。
      </div>

      <div class="section-header">
        <h2>
          图谱 v{{ graph.version }}
          <span :class="['status', graph.status]">{{ graph.status }}</span>
        </h2>
        <div class="header-actions">
          <select :value="selectedGraphId" @change="onSelectVersion" class="version-select">
            <option :value="null">最新版本</option>
            <option v-for="v in versions" :key="v.id" :value="v.id">
              v{{ v.version }} - {{ v.status }} ({{ new Date(v.created_at).toLocaleString() }})
            </option>
          </select>
          <button v-if="graph.status === 'draft' && isLatest" @click="approve">审核通过</button>
          <button @click="generate">重新生成</button>
        </div>
      </div>

      <KnowledgeGraphChart :nodes="graph.nodes" :edges="graph.edges" />

      <div class="section-header">
        <h3>知识点列表</h3>
        <button v-if="isLatest" @click="openPointDialog()">＋ 添加知识点</button>
      </div>
      <table class="data-table">
        <thead>
          <tr><th>编码</th><th>名称</th><th>描述</th><th>层级</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="n in graph.nodes" :key="n.id">
            <td>{{ n.code }}</td>
            <td>{{ n.name }}</td>
            <td>{{ n.description }}</td>
            <td>{{ n.level }}</td>
            <td>
              <button v-if="isLatest" class="secondary small" @click="openPointDialog(n)">编辑</button>
              <button v-if="isLatest" class="danger small" @click="deletePoint(n)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="section-header">
        <h3>知识关系</h3>
        <button v-if="isLatest" @click="openRelationDialog()">＋ 添加关系</button>
      </div>
      <table class="data-table">
        <thead>
          <tr><th>前置</th><th>关系</th><th>后续</th><th>置信度</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="e in graph.edges" :key="e.id || (e.from + '-' + e.to + '-' + e.type)">
            <td>{{ nodeMap[e.from] || e.from }}</td>
            <td>{{ relationTypes.find(t => t.value === e.type)?.label || e.type }}</td>
            <td>{{ nodeMap[e.to] || e.to }}</td>
            <td>{{ e.confidence }}</td>
            <td>
              <button v-if="isLatest" class="secondary small" @click="openRelationDialog(e)">编辑</button>
              <button v-if="isLatest" class="danger small" @click="deleteRelation(e)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Point Dialog -->
    <div v-if="showPointDialog" class="modal-backdrop" @click.self="closePointDialog">
      <div class="modal">
        <button class="modal-close" @click="closePointDialog">×</button>
        <h2>{{ editingPoint ? '编辑知识点' : '添加知识点' }}</h2>
        <div class="form-grid">
          <label>编码<input v-model="pointForm.code" placeholder="如 PY-01"></label>
          <label>名称<input v-model="pointForm.name" placeholder="知识点名称"></label>
        </div>
        <label>描述<textarea v-model="pointForm.description" placeholder="可选"></textarea></label>
        <div class="dialog-actions">
          <button class="secondary" @click="closePointDialog">取消</button>
          <button @click="savePoint">{{ editingPoint ? '保存' : '添加' }}</button>
        </div>
      </div>
    </div>

    <!-- Relation Dialog -->
    <div v-if="showRelationDialog" class="modal-backdrop" @click.self="closeRelationDialog">
      <div class="modal">
        <button class="modal-close" @click="closeRelationDialog">×</button>
        <h2>{{ editingRelation ? '编辑关系' : '添加关系' }}</h2>
        <div class="form-grid">
          <label>前置知识点
            <select v-model.number="relationForm.from_id">
              <option :value="null">请选择</option>
              <option v-for="p in knowledgePoints" :key="p.id" :value="p.id">{{ p.code }} {{ p.name }}</option>
            </select>
          </label>
          <label>后续知识点
            <select v-model.number="relationForm.to_id">
              <option :value="null">请选择</option>
              <option v-for="p in knowledgePoints" :key="p.id" :value="p.id">{{ p.code }} {{ p.name }}</option>
            </select>
          </label>
        </div>
        <div class="form-grid">
          <label>关系类型
            <select v-model="relationForm.relation_type">
              <option v-for="t in relationTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </label>
          <label>置信度<input type="number" min="0" max="1" step="0.05" v-model.number="relationForm.confidence"></label>
        </div>
        <div class="dialog-actions">
          <button class="secondary" @click="closeRelationDialog">取消</button>
          <button @click="saveRelation">{{ editingRelation ? '保存' : '添加' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.small {
  padding: 4px 10px;
  font-size: 12px;
  margin-right: 6px;
}
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.version-select {
  padding: 6px 10px;
  border-radius: 4px;
  border: 1px solid #ccc;
  background: white;
  min-width: 220px;
}
.info {
  background: #e8f4fd;
  color: #2e75b6;
}
</style>
