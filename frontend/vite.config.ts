import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// ../data 의 CSV를 직접 import 하기 위해 상위 폴더 접근을 허용한다
export default defineConfig({
  plugins: [react()],
  server: { fs: { allow: ['..'] } },
  // 강의계획서 데이터(syllabus)는 따로 나눠서 필요할 때만 불러오므로 큰 청크 경고는 끔
  build: { chunkSizeWarningLimit: 800 },
})
