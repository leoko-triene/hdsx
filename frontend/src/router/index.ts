import {createRouter,createWebHistory} from 'vue-router'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import CoursesView from '../views/CoursesView.vue'
import KnowledgeView from '../views/KnowledgeView.vue'
import LessonView from '../views/LessonView.vue'
import LessonFavoritesView from '../views/LessonFavoritesView.vue'
import LessonPreviewView from '../views/LessonPreviewView.vue'
import AssignmentView from '../views/AssignmentView.vue'
import ChatView from '../views/ChatView.vue'
import AnalyticsView from '../views/AnalyticsView.vue'
import ReportsView from '../views/ReportsView.vue'
import RegisterView from '../views/RegisterView.vue'
import ProfileView from '../views/ProfileView.vue'
import TeacherQAView from '../views/TeacherQAView.vue'
import NotificationsView from '../views/NotificationsView.vue'
import AgentCapabilitiesView from '../views/AgentCapabilitiesView.vue'
import CourseModuleEntryView from '../views/CourseModuleEntryView.vue'
import ModelSettingsView from '../views/ModelSettingsView.vue'
import KnowledgeGraphView from '../views/KnowledgeGraphView.vue'
import KnowledgeGraphStudent from '../views/KnowledgeGraphStudent.vue'
import {useAuthStore} from '../stores/auth'
type Role='admin'|'teacher'|'student'|'parent'
const router=createRouter({history:createWebHistory(),routes:[
  {path:'/login',component:LoginView,meta:{public:true}},{path:'/register',component:RegisterView,meta:{public:true}}, {path:'/',component:DashboardView},
  {path:'/profile',component:ProfileView},
  {path:'/courses',component:CoursesView,meta:{roles:['teacher','admin','student']}},
  {path:'/knowledge',component:KnowledgeView,meta:{roles:['teacher','admin','student']}},
  {path:'/lesson',component:LessonView,meta:{roles:['teacher','admin']}},
  {path:'/lesson/favorites',component:LessonFavoritesView,meta:{roles:['teacher','admin'],title:'智能备课'}},
  {path:'/lesson/preview/:resourceId',component:LessonPreviewView,meta:{roles:['teacher','admin'],title:'智能备课'}},
  {path:'/assignments',component:CourseModuleEntryView,meta:{roles:['teacher','admin','student'],title:'作业中心',base:'/assignments',description:'选择课程后查看、创建和提交该课程作业。'}},
  {path:'/assignments/course/:courseId',component:AssignmentView,meta:{roles:['teacher','admin','student'],title:'作业中心'}},
  {path:'/assignments/course/:courseId/assignment/:assignmentId',component:AssignmentView,meta:{roles:['teacher','admin','student'],title:'作业中心'}},
  {path:'/chat',component:ChatView,meta:{roles:['teacher','admin','student']}},
  {path:'/analytics',component:CourseModuleEntryView,meta:{roles:['teacher','admin','student'],title:'学情分析',base:'/analytics',description:'选择课程后查看掌握度、薄弱画像和学习路径。'}},
  {path:'/analytics/course/:courseId',component:AnalyticsView,meta:{roles:['teacher','admin','student'],title:'学情分析'}},
  {path:'/reports',component:CourseModuleEntryView,meta:{roles:['teacher','admin'],title:'学习报告',base:'/reports',description:'选择课程后生成和审核学习报告。'}},
  {path:'/reports/course/:courseId',component:ReportsView,meta:{roles:['teacher','admin'],title:'学习报告'}},
  {path:'/reports/family',component:ReportsView,meta:{roles:['parent'],title:'学习报告'}},
  {path:'/classroom-ops',component:CourseModuleEntryView,meta:{roles:['teacher','admin'],title:'课堂运营',base:'/classroom-ops',description:'选择课程后查看高频问题、答疑记录并修正 AI 回答。'}},
  {path:'/classroom-ops/course/:courseId',component:TeacherQAView,meta:{roles:['teacher','admin'],title:'课堂运营'}},
  {path:'/notifications',component:NotificationsView,meta:{roles:['teacher','admin','student','parent']}}
  ,{path:'/agent-capabilities',component:AgentCapabilitiesView,meta:{roles:['admin']}},{path:'/model-settings',component:ModelSettingsView,meta:{roles:['admin'],title:'模型服务'}}
  ,{path:'/knowledge-graph',component:CourseModuleEntryView,meta:{roles:['teacher','admin'],title:'知识点图谱',base:'/knowledge-graph',description:'选择课程后查看该课程的知识点图谱。'}}
  ,{path:'/knowledge-graph/course/:courseId',component:KnowledgeGraphView,meta:{roles:['teacher','admin'],title:'知识点图谱'}}
  ,{path:'/knowledge-graph/mastery',component:KnowledgeGraphStudent,meta:{roles:['student'],title:'我的知识点掌握度'}}
]})
router.beforeEach(async to=>{
  if(to.meta.public)return
  if(!localStorage.getItem('access_token'))return '/login'
  const auth=useAuthStore()
  if(!auth.user){try{await auth.load()}catch{return '/login'}}
  const roles=to.meta.roles as Role[]|undefined
  if(roles&&auth.user&&!roles.includes(auth.user.role as Role))return '/'
})
export default router
