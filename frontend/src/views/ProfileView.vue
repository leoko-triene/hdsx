<script setup lang="ts">
import{onMounted,ref}from'vue'
import{api}from'../api/client'
import{useAuthStore}from'../stores/auth'
const auth=useAuthStore(),profile=ref({username:'',display_name:'',email:'',role:''}),password=ref({current_password:'',new_password:'',confirm:''}),message=ref(''),error=ref('')
onMounted(async()=>{const {data}=await api.get('/auth/me');profile.value={...data,email:data.email||''}})
async function save(){try{const {data}=await api.patch('/auth/profile',{display_name:profile.value.display_name,email:profile.value.email||null});auth.setUser(data);message.value='账号资料已保存';error.value=''}catch(e:any){error.value=e.message}}
async function change(){if(password.value.new_password!==password.value.confirm){error.value='两次新密码不一致';return}try{const {data}=await api.post('/auth/change-password',{current_password:password.value.current_password,new_password:password.value.new_password});message.value=data.message;error.value='';password.value={current_password:'',new_password:'',confirm:''}}catch(e:any){error.value=e.message}}
</script>
<template><div class="page"><div class="page-title"><div><h1>账号设置</h1><p>管理个人资料和登录密码。</p></div></div><p class="notice success-box" v-if="message">{{message}}</p><p class="notice error" v-if="error">{{error}}</p><div class="settings-grid"><div class="card"><h2>基本资料</h2><label>用户名<input :value="profile.username" disabled></label><label>账号角色<input :value="profile.role" disabled></label><label>显示姓名<input v-model="profile.display_name"></label><label>邮箱<input type="email" v-model="profile.email"></label><button @click="save">保存资料</button></div><div class="card"><h2>修改密码</h2><label>当前密码<input type="password" v-model="password.current_password"></label><label>新密码<input type="password" minlength="8" v-model="password.new_password"></label><label>确认新密码<input type="password" v-model="password.confirm"></label><button @click="change">修改密码</button><p class="muted">密码至少 8 位，修改后请妥善保管。</p></div></div></div></template>
