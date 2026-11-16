# 컴공지도 프론트엔드

React + Vite + TypeScript + React Flow(@xyflow/react) + dagre

## 실행
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

## 데이터
- 노드: `../data/lecture_data/lecture_data_csv/subjects.csv`
- 간선: `../data/graph_data/edges.csv` (`pre` 선수→후수, `rel` 관련, `or_with` 대안 과목)
- CSV를 빌드 때 그대로 읽는다(`src/data.ts`). 백엔드가 간선을 내려주면 그쪽으로 바꾸면 된다.

## 백엔드 연결 (선택)
`.env.example`을 `.env.local`로 복사하고 `VITE_API_URL`을 채우면
- 이수 체크 → `POST /api/roadmap/complete`, 시작할 때 `GET /api/roadmap`
- 과목 상세(계획서·주차별) → `GET /api/subjects/{code}`

비워두면 이수 체크는 브라우저 저장소(localStorage)에만 저장된다.

## 화면
- 로드맵: 왼쪽→오른쪽으로 선수과목 순서. 초록=이수, 파랑=수강 가능(선수과목 다 들음), 회색=선수과목 필요
- 과목 클릭: 그 과목까지 가는 선수과목 경로가 주황색으로 강조되고 화면이 그 경로로 확대됨
- 오른쪽 패널: 선수과목(또는 묶음), 다음 과목, 관련 과목, 이수 체크, (백엔드 연결 시) 계획서

## 파일
- `src/data.ts` CSV 파싱, 선수/후수/조상 계산
- `src/layout.ts` dagre 배치, 간선 스타일
- `src/api.ts` 백엔드 호출 (없으면 localStorage)
- `src/App.tsx` 로드맵 화면
- `src/SubjectPanel.tsx` 오른쪽 상세 패널

## 다음 할 일
- [ ] 백엔드 `/api/roadmap` 응답에 edges 포함되면 CSV 대신 API 사용
- [ ] 진로 선택 → 추천 경로 강조
- [ ] 시간표 업로드 화면 (OCR 결과 확인·수정 → 이수 반영)
- [ ] 과목 검색창
