<script setup lang="ts">
import{computed,onActivated,ref}from'vue'
import{useRouter}from'vue-router'
import{api}from'../api/client'
const router=useRouter(),items=ref<any[]>([]),error=ref(''),unreadOnly=ref(false)
const visible=computed(()=>unreadOnly.value?items.value.filter(x=>!x.read):items.value)
async function load(){items.value=(await api.get('/notifications')).data}
async function open(item:any){if(!item.read){await api.patch(`/notifications/${item.id}/read`);item.read=true}if(item.link)router.push(item.link)}
onActivated(()=>load().catch((e:any)=>error.value=e.message))
</script>
<template><div class="page"><div class="page-title"><div><h1>通知中心</h1><p>集中查看作业截止提醒、教师修正回答等重要消息。</p></div><label class="toggle"><input type="checkbox" v-model="unreadOnly"> 只看未读</label></div><p v-if="error" class="notice error">{{error}}</p><div class="card"><div class="section-header"><h2>我的通知</h2><button class="ghost" @click="load">刷新</button></div><div v-if="!visible.length" class="empty">暂无{{unreadOnly?'未读':''}}通知</div><button v-for="item in visible" :key="item.id" :class="['notification-item',{unread:!item.read}]" @click="open(item)"><span class="notification-dot"></span><span><strong>{{item.title}}</strong><small>{{item.content}}</small><time>{{new Date(item.created_at).toLocaleString()}}</time></span><span>查看 →</span></button></div></div></template>
