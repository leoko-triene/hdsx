<script setup lang="ts">
import{computed,onActivated,ref}from'vue'
import{useRoute}from'vue-router'
import{api}from'../api/client'
import{useAuthStore}from'../stores/auth'
const route=useRoute(),auth=useAuthStore(),courses=ref<any[]>([]),error=ref('')
const title=computed(()=>String(route.meta.title||'课程功能')),description=computed(()=>String(route.meta.description||'先选择课程，再进入功能页面。')),base=computed(()=>String(route.meta.base||`/${String(route.path).split('/')[1]}`))
async function load(){courses.value=(await api.get(auth.user?.role==='student'?'/courses':'/courses/managed')).data}
onActivated(()=>load().catch((e:any)=>error.value=e.message))
</script>
<template><div class="page"><div class="page-title"><div><h1>{{title}}</h1><p>{{description}}</p></div></div><p v-if="error" class="notice error">{{error}}</p><div v-if="!courses.length" class="card empty">暂无可进入的课程</div><div class="course-grid module-course-grid"><router-link v-for="course in courses" :key="course.id" class="course-card module-course-card" :to="{path:`${base}/course/${course.id}`,query:{courseName:course.name}}"><div class="course-subject">{{course.subject}}</div><h2>{{course.name}}</h2><p>{{course.description}}</p><div class="meta"><span>{{course.grade_level}}</span><strong>点击进入 {{title}} →</strong></div></router-link></div></div></template>
