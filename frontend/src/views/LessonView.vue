<script setup lang="ts">
import {computed,onActivated,ref} from 'vue'
import {useRouter} from 'vue-router'
import {api} from '../api/client'
const router=useRouter(),courses=ref<any[]>([]),history=ref<any[]>([]),result=ref<any>(),error=ref(''),message=ref(''),loading=ref(false),showHistory=ref(true)
const form=ref({course_id:0,chapter_title:'',resource_type:'lesson_plan',audience:'本科生',duration_minutes:45,requirements:''})
const typeHelp=computed(()=>({lesson_plan:'完整教案：目标、重难点、流程、互动和作业',lecture:'课堂讲稿：按授课节奏组织自然讲解文本',ppt_outline:'PPT 提纲：逐页标题、要点、图示与讲解提示',exercise:'课堂练习：例题、练习、思考题、答案与解析'} as any)[form.value.resource_type])
const typeName=(type:string)=>({lesson_plan:'完整教案',lecture:'课堂讲稿',ppt_outline:'PPT 提纲',exercise:'课堂练习'} as any)[type]||'备课资料'
function legacyText(value:any,level=0):string{if(value==null)return'';if(typeof value==='string')return value;if(Array.isArray(value))return value.map((item,index)=>typeof item==='object'?`${index+1}. ${legacyText(item,level+1)}`:`${index+1}. ${item}`).join('\n');if(typeof value==='object')return Object.entries(value).filter(([key])=>!['format','resource_type','title'].includes(key)).map(([key,item])=>`${'#'.repeat(Math.min(level+2,5))} ${key}\n${legacyText(item,level+1)}`).join('\n\n');return String(value)}
function contentText(item:any){return item?.content?.text||legacyText(item?.content||item)}
async function load(){courses.value=(await api.get('/courses/managed')).data;if(courses.value.length&&!form.value.course_id)form.value.course_id=courses.value[0].id;history.value=(await api.get('/lesson-resources')).data}
async function run(){loading.value=true;error.value='';try{result.value=(await api.post('/lesson-resources/generate',form.value)).data;message.value='文本生成完成，并已加入历史记录。';await load();await openPreview(result.value)}catch(e:any){error.value=e.message}finally{loading.value=false}}
async function toggleSave(item:any){await api.patch(`/lesson-resources/${item.id}/save?saved=${!item.is_saved}`);item.is_saved=!item.is_saved;if(result.value?.id===item.id)result.value.is_saved=item.is_saved;message.value=item.is_saved?'已加入收藏夹':'已取消收藏'}
async function remove(item:any){if(!confirm(`确定删除《${item.title}》吗？`))return;await api.delete(`/lesson-resources/${item.id}`);history.value=history.value.filter(x=>x.id!==item.id);if(result.value?.id===item.id)result.value=null}
async function download(item:any){const response=await api.get(`/lesson-resources/${item.id}/download`,{responseType:'blob'});const url=URL.createObjectURL(response.data);const link=document.createElement('a');link.href=url;link.download=`${item.title||'备课资料'}.md`;link.click();URL.revokeObjectURL(url)}
async function openPreview(item:any){await router.push({path:`/lesson/preview/${item.id}`,query:{from:'lesson',title:item.content?.title||item.title||'备课文件预览'}})}
function preview(item:any){void openPreview(item)}
onActivated(()=>load().catch(e=>error.value=e.message))
</script>
<template><div class="page"><div class="page-title"><div><h1>智能备课</h1><p>按内容类型生成适合直接阅读、编辑和下载的备课文本。</p></div></div><p v-if="message" class="notice success-box">{{message}}</p><p v-if="error" class="notice error">{{error}}</p><div class="lesson-layout"><div><div class="card"><h2>生成设置</h2><label>课程名称<select v-model.number="form.course_id"><option v-for="c in courses" :value="c.id">{{c.name}} · {{c.subject}}</option></select></label><label>章节或主题 <span class="field-help">例如“第三章 监督学习”；该内容会作为历史记录标题</span><input v-model="form.chapter_title"></label><label>生成内容类型 <span class="field-help">{{typeHelp}}</span><select v-model="form.resource_type"><option value="lesson_plan">完整教案</option><option value="lecture">课堂讲稿</option><option value="ppt_outline">PPT 提纲</option><option value="exercise">课堂练习</option></select></label><div class="form-grid"><label>授课对象<input v-model="form.audience"></label><label>课时长度（分钟）<input type="number" min="10" max="240" v-model.number="form.duration_minutes"></label></div><label>补充要求<textarea v-model="form.requirements"></textarea></label><button :disabled="loading||!form.course_id||!form.chapter_title" @click="run">{{loading?'正在生成文本…':'生成备课文本'}}</button></div><article v-if="result" class="card lesson-result"><div class="section-header"><div><span class="eyebrow">{{typeName(result.content?.resource_type||result.resource_type)}}预览</span><h2>{{result.content?.title||result.title}}</h2></div><span :class="['status',result.is_saved?'approved':'draft']">{{result.is_saved?'已收藏':'临时记录'}}</span></div><div class="lesson-text">{{contentText(result)}}</div><div class="inline-actions"><button @click="toggleSave(result)">{{result.is_saved?'取消收藏':'收藏保存'}}</button><button class="secondary" @click="download(result)">下载 Markdown</button><button class="danger" @click="remove(result)">删除</button></div></article></div><div><div class="lesson-header-actions"><button class="history-toggle" @click="showHistory=!showHistory">{{showHistory?'收起历史':'查看历史'}}（{{history.length}}）</button><router-link class="button-link favorite-folder-button" to="/lesson/favorites">★ 收藏夹</router-link></div><aside v-if="showHistory" class="card lesson-history"><div class="history-card-header"><h2>备课历史</h2><p class="muted">标题来自生成时填写的"章节或主题"。收藏只修改状态，请使用上方"收藏夹"进入收藏页面。</p></div><div v-if="!history.length" class="empty">暂无生成记录</div><article v-for="item in history" :key="item.id" class="history-item"><div class="history-main"><span :class="['history-star',item.is_saved?'saved':'']">{{item.is_saved?'★':'☆'}}</span><span><strong>{{item.title}}</strong><small>{{item.course_name}} · {{typeName(item.resource_type)}} · {{new Date(item.created_at).toLocaleString()}}</small></span></div><div class="lesson-history-actions"><button class="icon-button preview-button" @click="preview(item)">预览</button><button class="icon-button" @click="toggleSave(item)">{{item.is_saved?'取消收藏':'收藏'}}</button><button class="icon-button" @click="download(item)">下载</button><button class="icon-button danger-text" @click="remove(item)">删除</button></div></article></aside></div></div></div></template>

<style scoped>
.lesson-history {
  margin-top: 12px;
}
.history-card-header {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5ebf0;
}
.history-card-header h2 {
  margin: 0 0 4px;
  color: #172033;
  font-size: 17px;
}
.history-card-header p {
  margin: 0;
  font-size: 12px;
}
</style>
