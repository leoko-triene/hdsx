<script setup lang="ts">
import {ref, watch, onMounted} from 'vue'
import {api} from '../api/client'

const props = defineProps<{ courseId: number, modelValue: number[] }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: number[]): void }>()

const points = ref<any[]>([])
const selected = ref<number[]>(props.modelValue || [])

async function load() {
  if (!props.courseId) return
  points.value = (await api.get(`/knowledge-graphs/course/${props.courseId}/points`)).data
}

watch(selected, (v) => emit('update:modelValue', v))
watch(() => props.courseId, load)
onMounted(load)
</script>

<template>
  <div class="kp-selector">
    <label v-for="kp in points" :key="kp.id" class="kp-option">
      <input
        type="checkbox"
        :value="kp.id"
        v-model="selected"
      />
      <span class="kp-code">{{ kp.code }}</span>
      <span class="kp-name">{{ kp.name }}</span>
    </label>
    <div v-if="!points.length" class="empty">该课程暂无知识点</div>
  </div>
</template>

<style scoped>
.kp-selector {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 0.5rem;
}
.kp-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0;
  cursor: pointer;
}
.kp-code {
  font-family: monospace;
  font-size: 0.85rem;
  color: #6b7280;
  min-width: 4rem;
}
.kp-name {
  flex: 1;
}
</style>