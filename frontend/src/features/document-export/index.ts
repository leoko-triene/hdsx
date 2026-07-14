import {registerFeature} from '../registry'
import ExportButtons from './ExportButtons.vue'

registerFeature({
  name: 'document-export',
  actions: {
    'lesson-resource-actions': ExportButtons
  }
})
