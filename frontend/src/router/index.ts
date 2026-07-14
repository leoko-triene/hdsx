import {createRouter,createWebHistory} from 'vue-router'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import CoursesView from '../views/CoursesView.vue'
import KnowledgeView from '../views/KnowledgeView.vue'
import LessonView from '../views/LessonView.vue'
import AssignmentView from '../views/AssignmentView.vue'
import ChatView from '../views/ChatView.vue'
import AnalyticsView from '../views/AnalyticsView.vue'
import ReportsView from '../views/ReportsView.vue'
import RegisterView from '../views/RegisterView.vue'
import ProfileView from '../views/ProfileView.vue'
import TeacherQAView from '../views/TeacherQAView.vue'
import NotificationsView from '../views/NotificationsView.vue'
import {useAuthStore} from '../stores/auth'
import {getFeatureRoutes} from '../features/registry'
import type {RouteRecordRaw} from 'vue-router'
type Role='admin'|'teacher'|'student'|'parent'
const routes: RouteRecordRaw[]=[
  {path:'/login',component:LoginView,meta:{public:true}},{path:'/register',component:RegisterView,meta:{public:true}}, {path:'/',component:DashboardView},
  {path:'/profile',component:ProfileView},
  {path:'/courses',component:CoursesView,meta:{roles:['teacher','admin','student']}},
  {path:'/knowledge',component:KnowledgeView,meta:{roles:['teacher','admin','student']}},
  {path:'/lesson',component:LessonView,meta:{roles:['teacher','admin']}},
  {path:'/assignments',component:AssignmentView,meta:{roles:['teacher','admin','student']}},
  {path:'/chat',component:ChatView,meta:{roles:['teacher','admin','student']}},
  {path:'/analytics',component:AnalyticsView,meta:{roles:['teacher','admin','student']}},
  {path:'/reports',component:ReportsView,meta:{roles:['teacher','admin','parent']}}
  ,{path:'/classroom-ops',component:TeacherQAView,meta:{roles:['teacher','admin']}}
  ,{path:'/notifications',component:NotificationsView,meta:{roles:['teacher','admin','student','parent']}}
]
routes.push(...getFeatureRoutes())
const router=createRouter({history:createWebHistory(),routes})
router.beforeEach(async to=>{
  if(to.meta.public)return
  if(!localStorage.getItem('access_token'))return '/login'
  const auth=useAuthStore()
  if(!auth.user){try{await auth.load()}catch{return '/login'}}
  const roles=to.meta.roles as Role[]|undefined
  if(roles&&auth.user&&!roles.includes(auth.user.role as Role))return '/'
})
export default router
