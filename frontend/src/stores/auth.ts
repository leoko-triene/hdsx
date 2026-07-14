import {defineStore} from 'pinia'
import {api} from '../api/client'
export const useAuthStore=defineStore('auth',{
  state:()=>({user:JSON.parse(localStorage.getItem('auth_user')||'null') as null|{id:number;display_name:string;role:string},loading:false}),
  actions:{
    setUser(user:any){this.user=user;localStorage.setItem('auth_user',JSON.stringify(user))},
    async login(username:string,password:string){const {data}=await api.post('/auth/login',{username,password});localStorage.setItem('access_token',data.access_token);this.setUser(data.user)},
    async load(){if(!localStorage.getItem('access_token'))return;this.loading=true;try{const {data}=await api.get('/auth/me');this.setUser(data)}finally{this.loading=false}},
    logout(){localStorage.removeItem('access_token');localStorage.removeItem('auth_user');this.user=null;location.href='/login'}
  }
})
