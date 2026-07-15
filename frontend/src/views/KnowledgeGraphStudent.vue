<script setup lang="ts">
import {ref, onMounted} from 'vue'
import {api} from '../api/client'
import {useAuthStore} from '../stores/auth'

const auth = useAuthStore()
const courseId = ref(0)
const courses = ref<any[]>([])
const mastery = ref<any>(null)
const loading = ref(false)

async function loadCourses() {
  courses.value = (await api.get('/courses')).data
}

async function loadMastery() {
  if (!courseId.value) return
  loading.value = true
  try {
    if (!auth.user) return
    mastery.value = (await api.get(`/knowledge-graphs/student-mastery/${auth.user.id}/course/${courseId.value}`)).data
  } catch (e: any) {
    alert(e.message)
  }
  loading.value = false
}

onMounted(loadCourses)
</script>

<template>
  <div class="page">
    <div class="page-title"><h1>我的知识点掌握度</h1></div>

    <div class="card">
      <label>选择课程
        <select v-model.number="courseId" @change="loadMastery">
          <option :value="0">请选择</option>
          <option v-for="c in courses" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </label>
    </div>

    <div v-if="loading" class="card">加载中...</div>

    <div v-else-if="mastery" class="card">
      <h3>知识点掌握度</h3>
      <div v-if="mastery.knowledge_points.length === 0" class="empty">
        该课程暂无知识点关联的题目数据。
      </div>
      <div v-for="kp in mastery.knowledge_points" :key="kp.knowledge_point_id" class="mastery-bar">
        <span>{{ kp.knowledge_point_name }}</span>
        <div class="progress-bar">
          <div :style="{ width: kp.accuracy_rate * 100 + '%' }" :class="kp.level"></div>
        </div>
        <span>{{ Math.round(kp.accuracy_rate * 100) }}%</span>
      </div>

      <div v-if="mastery.weak_areas.length" class="notice">
        <strong>薄弱知识点：</strong>{{ mastery.weak_areas.join('、') }}
      </div>

      <div v-if="mastery.recommended_path.length" class="notice success-box">
        <strong>推荐优先学习：</strong>{{ mastery.recommended_path.join(' -> ') }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.mastery-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin: 0.5rem 0;
}
.progress-bar {
  flex: 1;
  height: 16px;
  background: #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.progress-bar > div {
  height: 100%;
  border-radius: 8px;
  transition: width 0.3s;
}
.progress-bar .mastered { background: #22c55e; }
.progress-bar .proficient { background: #3b82f6; }
.progress-bar .developing { background: #f59e0b; }
.progress-bar .weak { background: #ef4444; }
</style>