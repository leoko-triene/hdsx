import {ref} from 'vue'
import {api} from '../../api/client'

export function useExport() {
  const exporting = ref<Record<number, boolean>>({})

  function exportTypes(resourceType: string): string[] {
    const map: Record<string, string[]> = {
      lesson_plan: ['docx'],
      lecture: ['docx'],
      ppt_outline: ['pptx'],
      exercise: ['docx']
    }
    return map[resourceType] || []
  }

  async function exportDoc(item: any, docType: string, onMessage?: (msg: string) => void) {
    exporting.value[item.id] = true
    try {
      const response = await api.post(
        `/lesson-resources/${item.id}/export`,
        {doc_type: docType},
        {responseType: 'blob'}
      )
      const url = URL.createObjectURL(response.data)
      const link = document.createElement('a')
      link.href = url
      link.download = `${item.title || '备课资料'}.${docType}`
      link.click()
      URL.revokeObjectURL(url)
      onMessage?.(`已导出 ${docType.toUpperCase()}`)
    } catch (e: any) {
      throw new Error(e.message || '导出失败')
    } finally {
      exporting.value[item.id] = false
    }
  }

  return {exporting, exportTypes, exportDoc}
}
