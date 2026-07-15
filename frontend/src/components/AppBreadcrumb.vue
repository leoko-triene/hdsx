<script setup lang="ts">
import{computed}from'vue'
import{useRoute}from'vue-router'
const props=defineProps<{label:string}>(),route=useRoute()
const parts=computed<any[]>(()=>{
  if(route.params.resourceId){const values:any[]=[{label:'智能备课',to:{path:'/lesson'}}];if(route.query.from==='favorites')values.push({label:'收藏',to:{path:'/lesson/favorites'}});values.push({label:String(route.query.title||'备课文件预览')});return values}
  if(route.path==='/lesson/favorites')return[{label:'智能备课',to:{path:'/lesson'}},{label:'收藏'}]
  const firstSegment=String(route.path).split('/')[1]
  const moduleBase=firstSegment==='knowledge-graph'?'/courses':`/${firstSegment}`,values:any[]=[{label:props.label,to:route.params.courseId?{path:moduleBase}:undefined}]
  if(route.params.courseId)values.push({label:String(route.query.courseName||`课程 ${route.params.courseId}`),to:route.params.assignmentId?{path:route.path.replace(/\/assignment\/.*$/,''),query:{courseName:route.query.courseName}}:undefined})
  if(route.params.assignmentId)values.push({label:String(route.query.assignmentTitle||`作业 ${route.params.assignmentId}`)})
  return values
})
</script>
<template><nav class="breadcrumb" aria-label="当前位置"><router-link to="/">工作台</router-link><template v-for="part in parts" :key="part.label"><span>›</span><router-link v-if="part.to" :to="part.to">{{part.label}}</router-link><strong v-else>{{part.label}}</strong></template></nav></template>
