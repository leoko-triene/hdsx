import axios from 'axios'

export const api = axios.create({baseURL:'/api/v1',timeout:300000})
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use(r=>r, error=>{
  if(error.response?.status===401){localStorage.removeItem('access_token');location.href='/login'}
  const detail=error.response?.data?.detail
  const validation=Array.isArray(detail)?detail.map((x:any)=>`${x.loc?.slice(1).join('.')||'参数'}：${x.msg}`).join('；'):undefined
  const message=error.response?.data?.error?.message || validation || (error.response?.status?`请求失败（HTTP ${error.response.status}）`:error.message) || '请求失败'
  return Promise.reject(new Error(message))
})
