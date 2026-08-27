import axios from 'axios'

export const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  withCredentials: true,
})
