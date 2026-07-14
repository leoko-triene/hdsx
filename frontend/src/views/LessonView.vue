<script setup lang="ts">
import {computed, onActivated, ref} from 'vue'
import {api} from '../api/client'
import {getFeatureActions} from '../features/registry'

const courses = ref<any[]>([])
const history = ref<any[]>([])
const result = ref<any>()
const error = ref('')
const message = ref('')
const loading = ref(false)
const showHistory = ref(true)
const lessonResourceActions = getFeatureActions('lesson-resource-actions')

const form = ref({
  course_id: 0,
  chapter_title: '',
  resource_type: 'lesson_plan',
  audience: '本科生',
  duration_minutes: 45,
  requirements: ''
})

const typeHelp = computed(() =>
  ({
    lesson_plan: '生成完整教学目标、重点难点、流程与作业',
    lecture: '生成教师可直接参考的课堂讲稿',
    ppt_outline: '生成按页组织的演示文稿提纲',
    exercise: '生成例题、练习题与参考答案'
  } as any)[form.value.resource_type]
)



async function load() {
  courses.value = (await api.get('/courses/managed')).data
  if (courses.value.length && !form.value.course_id) {
    form.value.course_id = courses.value[0].id
  }
  history.value = (await api.get('/lesson-resources')).data
}

async function run() {
  loading.value = true
  error.value = ''
  try {
    result.value = (await api.post('/lesson-resources/generate', form.value)).data
    message.value = '生成完成。未收藏记录自动保留最近 30 条。'
    await load()
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function toggleSave(item: any) {
  await api.patch(`/lesson-resources/${item.id}/save?saved=${!item.is_saved}`)
  item.is_saved = !item.is_saved
  if (result.value?.id === item.id) result.value.is_saved = item.is_saved
  message.value = item.is_saved ? '已收藏，记录不会被自动清理' : '已取消收藏'
}

async function remove(item: any) {
  if (!confirm(`确定删除《${item.title}》吗？`)) return
  await api.delete(`/lesson-resources/${item.id}`)
  history.value = history.value.filter(x => x.id !== item.id)
  if (result.value?.id === item.id) result.value = null
}

async function download(item: any) {
  const response = await api.get(`/lesson-resources/${item.id}/download`, {responseType: 'blob'})
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = `${item.title || '备课资料'}.md`
  link.click()
  URL.revokeObjectURL(url)
}



function view(item: any) {
  result.value = {...item, content: item.content}
  window.scrollTo({top: 0, behavior: 'smooth'})
}

onActivated(() => load().catch(e => error.value = e.message))
</script>

<template>
  <div class="page">
    <div class="page-title">
      <div>
        <h1>智能备课</h1>
        <p>选择自己负责的课程，填写章节与教学情境，生成结果会自动进入历史记录。</p>
      </div>
      <button class="secondary" @click="showHistory=!showHistory">
        {{showHistory?'收起历史':'查看历史'}}（{{history.length}}）
      </button>
    </div>

    <p class="notice success-box" v-if="message">{{message}}</p>
    <p class="notice error" v-if="error">{{error}}</p>

    <div class="lesson-layout">
      <div>
        <div class="card">
          <h2>生成设置</h2>
          <label>课程名称 <span class="field-help">选择本次备课所属课程</span>
            <select v-model.number="form.course_id">
              <option v-for="c in courses" :value="c.id">{{c.name}} · {{c.subject}}</option>
            </select>
          </label>
          <label>章节或主题 <span class="field-help">填写教材章节名或本节课主题，例如“第三章 监督学习”</span>
            <input v-model="form.chapter_title" placeholder="请输入章节或教学主题">
          </label>
          <label>生成内容类型 <span class="field-help">{{typeHelp}}</span>
            <select v-model="form.resource_type">
              <option value="lesson_plan">完整教案</option>
              <option value="lecture">课堂讲稿</option>
              <option value="ppt_outline">PPT 大纲</option>
              <option value="exercise">课堂练习</option>
            </select>
          </label>
          <div class="form-grid">
            <label>授课对象 <span class="field-help">学生年级、专业或基础水平</span>
              <input v-model="form.audience" placeholder="例如：本科二年级，具备 Python 基础">
            </label>
            <label>课时长度（分钟） <span class="field-help">用于分配教学环节时间</span>
              <input type="number" min="10" max="240" v-model.number="form.duration_minutes">
            </label>
          </div>
          <label>补充要求 <span class="field-help">可填写教学风格、互动方式、难度和必须覆盖的内容</span>
            <textarea v-model="form.requirements" placeholder="例如：增加小组讨论，案例贴近日常生活，包含两道课堂练习"></textarea>
          </label>
          <button :disabled="loading||!form.course_id||!form.chapter_title" @click="run">
            {{loading?'正在检索教材并生成…':'生成备课内容'}}
          </button>
        </div>

        <div v-if="result" class="card lesson-result">
          <div class="section-header">
            <div>
              <span class="eyebrow">生成结果</span>
              <h2>{{result.content?.title||result.title}}</h2>
            </div>
            <span :class="['status',result.is_saved?'approved':'draft']">
              {{result.is_saved?'已收藏':'临时记录'}}
            </span>
          </div>
          <pre class="answer">{{JSON.stringify(result.content,null,2)}}</pre>
          <div class="inline-actions">
            <button @click="toggleSave(result)">{{result.is_saved?'取消收藏':'收藏保存'}}</button>
            <button class="secondary" @click="download(result)">下载 Markdown</button>
            <component
              v-for="(ActionComponent, idx) in lessonResourceActions"
              :key="idx"
              :is="ActionComponent"
              :item="result"
              @message="message = $event"
              @error="error = $event"
            />
            <button class="danger" @click="remove(result)">删除</button>
          </div>
        </div>
      </div>

      <aside v-if="showHistory" class="card lesson-history">
        <h2>备课历史</h2>
        <p class="muted">收藏记录永久保留；未收藏记录只保留最近 30 条。</p>
        <div v-if="!history.length" class="empty">暂无生成记录</div>
        <article v-for="item in history" :key="item.id" class="history-item">
          <button class="history-main" @click="view(item)">
            <span :class="['history-star',item.is_saved?'saved':'']">{{item.is_saved?'★':'☆'}}</span>
            <span>
              <strong>{{item.title}}</strong>
              <small>{{item.course_name}} · {{new Date(item.created_at).toLocaleString()}}</small>
            </span>
          </button>
          <div>
            <button class="icon-button" @click="toggleSave(item)" :title="item.is_saved?'取消收藏':'收藏'">
              {{item.is_saved?'取消收藏':'收藏'}}
            </button>
            <button class="icon-button" @click="download(item)">下载</button>
            <component
              v-for="(ActionComponent, idx) in lessonResourceActions"
              :key="idx"
              :is="ActionComponent"
              :item="item"
              compact
              @message="message = $event"
              @error="error = $event"
            />
            <button class="icon-button danger-text" @click="remove(item)">删除</button>
          </div>
        </article>
      </aside>
    </div>
  </div>
</template>
