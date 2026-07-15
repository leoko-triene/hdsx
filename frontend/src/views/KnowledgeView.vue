<script setup lang="ts">
import{computed,onActivated,onUnmounted,ref,watch}from'vue'
import{useRoute}from'vue-router'
import{api}from'../api/client'
import{useAuthStore}from'../stores/auth'
import{renderMarkdown}from'../utils/markdown'
const auth=useAuthStore(),route=useRoute(),courses=ref<any[]>([]),courseId=ref(Number(route.query.course)||0),category=ref('textbook')
const files=ref<File[]>([]),documents=ref<any[]>([]),query=ref(''),result=ref<any[]>([]),batch=ref<any>(),message=ref(''),loading=ref(false),webLoading=ref(false)
const webKeyword=ref(''),webUrl=ref(''),webResults=ref<any[]>([]),webDrafts=ref<any[]>([]),previewDraft=ref<any>(),previewDocument=ref<any>()
const pdfPreviewUrl=ref('')
const canUpload=computed(()=>['teacher','admin'].includes(auth.user?.role||'')&&Boolean(courses.value.find(c=>c.id===courseId.value)?.is_manager)),previewHtml=computed(()=>renderMarkdown(previewDraft.value?.content||'')),documentPreviewHtml=computed(()=>previewDocument.value?.format==='markdown'?renderMarkdown(previewDocument.value.content||''):'')
async function loadCourses(){courses.value=(await api.get('/courses')).data;if(!courseId.value&&courses.value.length)courseId.value=courses.value[0].id}
async function loadDocuments(){documents.value=courseId.value?(await api.get(`/courses/${courseId.value}/documents`)).data:[]}
async function loadWebDrafts(){webDrafts.value=courseId.value&&canUpload.value?(await api.get(`/courses/${courseId.value}/web-imports`)).data:[]}
function selectFiles(event:Event){files.value=Array.from((event.target as HTMLInputElement).files||[])}
async function upload(){if(!files.value.length)return;loading.value=true;message.value='';const form=new FormData();form.append('category',category.value);files.value.forEach(file=>form.append('files',file));try{batch.value=(await api.post(`/courses/${courseId.value}/documents/batch`,form)).data;message.value=`上传完成：成功 ${batch.value.uploaded}，重复 ${batch.value.duplicates}，失败 ${batch.value.failed}`;files.value=[];await loadDocuments()}catch(e:any){message.value=e.message}finally{loading.value=false}}
async function search(){if(!query.value.trim())return;loading.value=true;message.value='';try{result.value=(await api.post('/knowledge/search',{course_id:courseId.value,query:query.value,top_k:8})).data;message.value=result.value.length?`已按相关性和来源多样性筛选出 ${result.value.length} 条结果`:'未找到达到相关性要求的知识片段'}catch(e:any){message.value=e.message}finally{loading.value=false}}
async function searchWeb(){if(!webKeyword.value.trim())return;webLoading.value=true;message.value='';try{webResults.value=(await api.post(`/courses/${courseId.value}/web-imports/search`,{keyword:webKeyword.value,limit:10})).data;if(!webResults.value.length)message.value='未找到可用网页结果，可以直接粘贴网页地址。'}catch(e:any){message.value=e.message}finally{webLoading.value=false}}
async function fetchWeb(url?:string){const value=(url||webUrl.value).trim();if(!value)return;webLoading.value=true;message.value='';try{const data=(await api.post(`/courses/${courseId.value}/web-imports/preview`,{url:value})).data;webUrl.value='';previewDraft.value=data;message.value='网页正文已抓取，请预览渲染结果并确认是否入库。';await loadWebDrafts()}catch(e:any){message.value=e.message}finally{webLoading.value=false}}
async function confirmWeb(id:number){webLoading.value=true;message.value='';try{const{data}=await api.post(`/web-imports/${id}/confirm`,{category:'web_reference'});message.value=`已确认入库：${data.document.filename}，生成 ${data.document.chunks} 个知识块`;previewDraft.value=undefined;await Promise.all([loadWebDrafts(),loadDocuments()])}catch(e:any){message.value=e.message}finally{webLoading.value=false}}
async function deleteWeb(draft:any){if(!confirm(`确定删除抓取记录《${draft.title}》吗？${draft.status==='confirmed'?'已入库的知识库文档不会随记录删除。':''}`))return;webLoading.value=true;try{await api.delete(`/web-imports/${draft.id}`);if(previewDraft.value?.id===draft.id)previewDraft.value=undefined;message.value='抓取记录已删除';await loadWebDrafts()}catch(e:any){message.value=e.message}finally{webLoading.value=false}}
async function removeDocument(doc:any){if(!confirm(`确定从知识库删除《${doc.filename}》吗？`))return;try{await api.delete(`/courses/${courseId.value}/documents/${doc.id}`);message.value='知识库文档已删除';await loadDocuments()}catch(e:any){message.value=e.message}}
function closeDocumentPreview(){previewDocument.value=undefined;if(pdfPreviewUrl.value){URL.revokeObjectURL(pdfPreviewUrl.value);pdfPreviewUrl.value=''}}
async function openDocumentPreview(doc:any){loading.value=true;message.value='';closeDocumentPreview();try{const data=(await api.get(`/courses/${courseId.value}/documents/${doc.id}/preview`)).data;if(data.format==='pdf'){const response=await api.get(data.content_url,{responseType:'blob'});pdfPreviewUrl.value=URL.createObjectURL(new Blob([response.data],{type:'application/pdf'}))}previewDocument.value=data}catch(e:any){message.value=e.message;closeDocumentPreview()}finally{loading.value=false}}
watch(courseId,()=>{Promise.all([loadDocuments(),loadWebDrafts()]).catch(e=>message.value=e.message);result.value=[];webResults.value=[];previewDraft.value=undefined;closeDocumentPreview()})
onActivated(async()=>{try{await loadCourses();await Promise.all([loadDocuments(),loadWebDrafts()])}catch(e:any){message.value=e.message}})
onUnmounted(closeDocumentPreview)
</script>
<template><div class="page knowledge-page"><div class="page-title"><div><h1>课程知识库</h1><p>{{canUpload?'上传本地文件，或抓取网页并确认后建立课程索引。':'查看教师确认的课程资料并进行知识检索。'}}</p></div></div><nav class="knowledge-course-tabs" aria-label="选择课程知识库"><button v-for="course in courses" :key="course.id" :class="{active:course.id===courseId}" @click="courseId=course.id"><strong>{{course.name}}</strong><strong v-if="!course.subject" class="tab-fallback">课程知识库</strong><strong v-else class="tab-subtitle">{{course.subject}}</strong></button></nav><p v-if="message" class="notice">{{message}}</p>
<div class="knowledge-workspace"><div class="knowledge-column knowledge-inputs"><section v-if="canUpload" class="card"><h2>批量上传学习文件</h2><div class="upload-zone"><input id="multi-files" type="file" multiple accept=".txt,.md,.pdf,.docx" @change="selectFiles"><label for="multi-files"><strong>点击选择多个文件</strong><span>支持 TXT、Markdown、PDF、DOCX；单次最多 20 个</span></label></div><div v-if="files.length" class="selected-files"><span v-for="file in files" :key="file.name">{{file.name}} · {{(file.size/1024).toFixed(1)}}KB</span></div><div class="inline-actions"><select v-model="category"><option value="textbook">教材</option><option value="courseware">课件</option><option value="question_bank">题库</option></select><button :disabled="loading||!files.length" @click="upload">{{loading?'处理中…':`上传${files.length?' '+files.length+' 个文件':''}`}}</button></div></section>
<section v-if="canUpload" class="card web-import"><div class="section-header"><div><h2>从网络获取学习资料</h2><p class="muted">实际抓取引擎位于 plugins/spider；抓取结果必须预览并确认后才会进入知识库。</p></div><span class="badge">24 小时内确认</span></div><div class="notice web-warning">请确认网页允许使用，尊重版权与站点规则。系统会拦截内网地址、异常重定向和超大内容。</div><div class="search-bar"><input v-model="webKeyword" placeholder="搜索学习主题" @keyup.enter="searchWeb"><button :disabled="webLoading" @click="searchWeb">搜索网页</button></div><div v-if="webResults.length" class="web-search-results"><article v-for="item in webResults" :key="item.url" class="web-result"><div><strong>{{item.title}}</strong><a :href="item.url" target="_blank" rel="noopener noreferrer">原网页</a></div><small>{{item.url}}</small><button class="secondary" :disabled="webLoading" @click="fetchWeb(item.url)">抓取并预览</button></article></div><div class="search-bar direct-url"><input v-model="webUrl" type="url" placeholder="也可以直接粘贴 http/https 网页地址" @keyup.enter="fetchWeb()"><button :disabled="webLoading||!webUrl.trim()" @click="fetchWeb()">抓取地址</button></div><div class="web-drafts"><h3>待确认与历史抓取 <span class="badge">{{webDrafts.length}}</span></h3><div v-if="!webDrafts.length" class="empty">暂无抓取记录</div><article v-for="draft in webDrafts" :key="draft.id" class="web-draft"><div class="section-header"><div><strong>{{draft.title}}</strong><p><a :href="draft.resolved_url" target="_blank" rel="noopener noreferrer">{{draft.source_domain}}</a> · {{draft.metadata?.character_count||draft.content.length}} 字符</p></div><span :class="['status',draft.status]">{{draft.status}}</span></div><p class="web-draft-excerpt">{{draft.content.slice(0,220)}}{{draft.content.length>220?'…':''}}</p><div class="web-draft-actions"><button class="secondary" @click="previewDraft=draft">预览 Markdown</button><button v-if="draft.status==='pending'" :disabled="webLoading" @click="confirmWeb(draft.id)">确认入库</button><button class="danger" :disabled="webLoading" @click="deleteWeb(draft)">删除记录</button></div></article></div></section><section v-if="!canUpload" class="card empty">学生可检索并查看已加入课程的资料；上传与网页入库仅对课程负责人开放。</section></div>
<div class="knowledge-column knowledge-results"><section class="card knowledge-search"><h2>知识检索</h2><div class="search-bar"><input v-model="query" placeholder="例如：过拟合有哪些解决方法？" @keyup.enter="search"><button :disabled="loading" @click="search">检索</button></div><div v-if="!result.length" class="search-placeholder">输入知识点，在当前高亮课程中查找相关资料。</div><div v-for="item in result" :key="item.chunk_id" class="search-result"><div><strong>{{item.filename}}</strong><span>第 {{item.chunk_index+1}} 块 · 相关度 {{item.rerank_score?.toFixed(2)}}</span></div><p>{{item.content}}</p></div></section><section class="card"><h2>知识库文件 <span class="badge">{{documents.length}}</span></h2><div v-if="!documents.length" class="empty">当前课程尚未上传资料</div><div class="document-table" v-else><div class="document-row heading"><span>文件名</span><span>类型</span><span>分块</span><span>状态</span><span>上传时间</span><span>操作</span></div><div class="document-row" v-for="doc in documents" :key="doc.id"><span class="document-name">📄 {{doc.filename}} <a v-if="doc.source_url" :href="doc.source_url" target="_blank" rel="noopener noreferrer">↗</a></span><span>{{doc.category}}</span><span>{{doc.chunks}}</span><span :class="['status',doc.status]">{{doc.status}}</span><span>{{new Date(doc.created_at).toLocaleString()}}</span><span class="document-actions"><button class="secondary" @click="openDocumentPreview(doc)">预览</button><button v-if="canUpload" class="danger" @click="removeDocument(doc)">删除</button></span></div></div></section></div></div>
<div v-if="previewDraft" class="modal-backdrop" @click.self="previewDraft=undefined"><article class="modal wide web-markdown-modal"><button class="modal-close" @click="previewDraft=undefined">×</button><div class="section-header"><div><span class="eyebrow">网页 Markdown 预览</span><h2>{{previewDraft.title}}</h2></div><span :class="['status',previewDraft.status]">{{previewDraft.status}}</span></div><div class="markdown-preview" v-html="previewHtml"></div><div class="inline-actions"><button v-if="previewDraft.status==='pending'" @click="confirmWeb(previewDraft.id)">确认并写入知识库</button><button class="danger" @click="deleteWeb(previewDraft)">删除记录</button><a :href="previewDraft.resolved_url" target="_blank" rel="noopener noreferrer" class="button-link secondary">查看原网页</a></div></article></div>
<div v-if="previewDocument" class="modal-backdrop" @click.self="closeDocumentPreview"><article class="modal wide document-preview-modal"><button class="modal-close" @click="closeDocumentPreview">×</button><div class="section-header"><div><span class="eyebrow">知识库文档预览 · {{previewDocument.format==='pdf'?'PDF':previewDocument.format==='word'?'Word':previewDocument.format==='markdown'?'Markdown':'文本'}}</span><h2>{{previewDocument.filename}}</h2><p class="muted">{{previewDocument.chunks}} 个知识块<span v-if="previewDocument.truncated"> · 内容较长，当前展示前 100000 字符</span></p></div><a v-if="previewDocument.source_url" :href="previewDocument.source_url" target="_blank" rel="noopener noreferrer" class="button-link secondary">原始网页</a></div><iframe v-if="previewDocument.format==='pdf'&&pdfPreviewUrl" class="pdf-document-preview" :src="pdfPreviewUrl" :title="`${previewDocument.filename} PDF 预览`"></iframe><div v-else-if="previewDocument.format==='markdown'" class="markdown-preview" v-html="documentPreviewHtml"></div><article v-else-if="previewDocument.format==='word'" class="word-document-preview"><pre>{{previewDocument.content}}</pre></article><pre v-else class="plain-document-preview">{{previewDocument.content}}</pre></article></div></div></template>

<style scoped>
/* ===== 页面标题居中对齐 ===== */
.knowledge-page .page-title {
  margin-bottom: 18px;
}
.knowledge-page .page-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: #172033;
}

/* ===== 课程标签：字体与标题一致 ===== */
.knowledge-course-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.knowledge-course-tabs button {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 14px 18px;
  border: 1px solid #dde6ee;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  min-width: 160px;
  min-height: 64px;
  transition: .2s;
  color: #41566a;
  line-height: 1.3;
}
.knowledge-course-tabs button:hover {
  border-color: #8bb8d0;
  background: #f5fafc;
}
.knowledge-course-tabs button.active {
  border-color: #1677a6;
  background: #e0edf6;
  color: #0a3348;
}
/* 大标题：课程名 */
.knowledge-course-tabs button strong {
  font-size: 17px;
  font-weight: 700;
  color: inherit;
}
/* 小标题：科目，颜色逻辑同大标题 */
.knowledge-course-tabs button strong.tab-subtitle {
  font-size: 13px;
  font-weight: 500;
  color: inherit;
  margin-top: 3px;
}
/* 独立控制：无科目时的默认文字 */
.knowledge-course-tabs button strong.tab-fallback {
  font-size: 20px;
  font-weight: 700;
  color: inherit;
}

/* ===== 双栏布局 ===== */
.knowledge-workspace {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  align-items: start;
}
@media(max-width:860px) {
  .knowledge-workspace { grid-template-columns: 1fr; }
}

/* ===== 上传区间距 ===== */
.upload-zone {
  margin-bottom: 14px;
}
.selected-files {
  margin-bottom: 14px !important;
}
.upload-zone label {
  padding: 32px 24px;
  font-size: 14px;
}
.upload-zone label strong {
  font-size: 15px;
  margin-bottom: 4px;
}

/* ===== 操作行间距 ===== */
.inline-actions {
  margin-top: 4px;
}
.inline-actions select {
  height: 42px;
  font-size: 14px;
  padding-right: 36px;
  padding-left: 12px;
}
.inline-actions button {
  height: 42px;
  font-size: 14px;
  white-space: nowrap;
}

/* ===== 爬虫抓取区 ===== */
.web-import .web-warning {
  background: #fff8e6;
  color: #856000;
  border: 1px solid #f0d78c;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  margin-bottom: 16px;
}
.web-import .search-bar {
  margin-bottom: 12px;
}
.web-import .direct-url {
  margin-top: 14px;
}
.web-draft {
  border: 1px solid #e5ebf0;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 10px;
  background: #fafcfd;
}
.web-draft .web-draft-excerpt {
  font-size: 13px;
  color: #607286;
  line-height: 1.6;
  margin: 8px 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.web-draft-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.web-draft-actions button,
.web-draft-actions .button-link {
  font-size: 13px;
  padding: 6px 14px;
}
.web-search-results {
  margin-bottom: 12px;
}
.web-result {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid #e5ebf0;
  border-radius: 8px;
  margin-bottom: 6px;
  background: #fff;
}
.web-result strong {
  font-size: 14px;
  color: #172033;
}
.web-result small {
  display: block;
  color: #748493;
  font-size: 12px;
  margin-top: 3px;
  word-break: break-all;
}

/* ===== 知识检索区 ===== */
.knowledge-search .search-placeholder {
  text-align: center;
  padding: 40px 20px;
  color: #9aacbc;
  font-size: 14px;
}

/* ===== 文档表操作列 ===== */
.document-actions {
  display: flex;
  gap: 6px;
}
.document-actions button {
  font-size: 12px;
  padding: 4px 10px;
}

/* ===== Markdown 预览弹窗 ===== */
.markdown-preview {
  max-height: 65vh;
  overflow: auto;
  padding: 20px;
  border: 1px solid #e0e6ec;
  border-radius: 8px;
  background: #fcfdfe;
  line-height: 1.8;
  font-size: 15px;
  margin: 14px 0;
}
.web-markdown-modal .markdown-preview {
  max-width: 100%;
}
.web-markdown-modal .inline-actions {
  justify-content: flex-end;
}

/* ===== 文档预览弹窗 ===== */
.document-preview-modal .pdf-document-preview {
  width: 100%;
  height: 70vh;
  border: none;
  border-radius: 8px;
  margin: 14px 0;
}
.document-preview-modal .plain-document-preview {
  max-height: 65vh;
  overflow: auto;
  background: #f8f9fa;
  padding: 16px;
  border-radius: 8px;
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.7;
}
</style>
