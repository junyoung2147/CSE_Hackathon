import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// ../data 의 CSV를 직접 import 하기 위해 상위 폴더 접근을 허용한다
export default defineConfig({
  plugins: [react()],
  server: { fs: { allow: ['..'] } },
})
