<script setup lang="ts">
import {useExport} from './useExport'

const props = defineProps<{
  item: any
  compact?: boolean
}>()

const emit = defineEmits<{
  (e: 'message', msg: string): void
  (e: 'error', msg: string): void
}>()

const {exporting, exportTypes, exportDoc} = useExport()

async function handleExport(docType: string) {
  try {
    await exportDoc(props.item, docType, msg => emit('message', msg))
  } catch (e: any) {
    emit('error', e.message)
  }
}
</script>

<template>
  <button
    v-for="t in exportTypes(item.resource_type)"
    :key="t"
    class="secondary"
    :class="{'icon-button': compact}"
    :disabled="exporting[item.id]"
    @click="handleExport(t)"
  >
    {{exporting[item.id] ? (compact ? '…' : '导出中…') : (compact ? t.toUpperCase() : '导出 ' + t.toUpperCase())}}
  </button>
</template>
