<script setup lang="ts">
import {computed} from 'vue'
import {useAuthStore} from '../stores/auth'
import {getFeatureDashboardCards} from '../features/registry'
const auth=useAuthStore()
const cards=computed(()=>{
  const role=auth.user?.role
  const all=[
    {to:'/courses',title:'课程管理',text:role==='student'?'查看我参与的课程':'创建课程并维护教学内容',roles:['teacher','admin','student'],icon:'课'},
    {to:'/knowledge',title:'课程知识库',text:role==='student'?'查看课程资料并进行检索':'批量上传教材，自动去重并构建检索索引',roles:['teacher','admin','student'],icon:'知'},
    {to:'/lesson',title:'智能备课',text:'根据教材生成教案、讲稿和练习',roles:['teacher','admin'],icon:'备'},
    {to:'/assignments',title:role==='student'?'我的作业':'作业中心',text:role==='student'?'查看并填写老师布置的作业':'创建、发布并批改学生作业',roles:['teacher','admin','student'],icon:'作'},
    {to:'/chat',title:'课堂答疑',text:'基于课程资料进行有引用的智能问答',roles:['teacher','admin','student'],icon:'问'},
    {to:'/classroom-ops',title:'课堂运营',text:'汇总高频问题，审核并修正 AI 答疑',roles:['teacher','admin'],icon:'审'},
    {to:'/analytics',title:'学情分析',text:role==='student'?'查看我的知识点掌握情况':'查看学生薄弱知识点和学习路径',roles:['teacher','admin','student'],icon:'析'},
    {to:'/reports',title:'学习报告',text:role==='parent'?'查看已审核发布的学习报告':'生成、审核并发布周报和月报',roles:['teacher','admin','parent'],icon:'报'},
    {to:'/notifications',title:'通知中心',text:'查看作业截止与教师修正提醒',roles:['teacher','admin','student','parent'],icon:'知'},
    ...getFeatureDashboardCards()
  ]
  return all.filter(x=>role&&x.roles.includes(role))
})
</script>
<template><div class="page"><div class="page-title"><div><h1>欢迎回来，{{auth.user?.display_name}}</h1><p>选择下方功能开始今天的工作。</p></div></div><div class="action-grid"><router-link v-for="card in cards" :key="card.to" :to="card.to" class="action-card"><span class="action-icon">{{card.icon}}</span><div><h2>{{card.title}}</h2><p>{{card.text}}</p><span class="action-link">进入功能 →</span></div></router-link></div></div></template>
