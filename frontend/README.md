# 컴공지도 프론트엔드

React + Vite + TypeScript + React Flow(@xyflow/react) + dagre

## 실행
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

## 데이터
- 교육과정: `../data/curriculum_data/curriculum.csv` → 전공별 과목과 권장 학년·학기(= x축 열)
- 간선: `../data/graph_data/edges.csv` (`pre` 선수→후수, `rel` 관련, `or_with` 대안 과목)
- 과목 이름·학점·개설 학기: `../data/lecture_data/lecture_data_csv/subjects.csv`
- CSV를 빌드 때 그대로 읽는다(`src/data.ts`).
- 전공을 고르면 그 전공 교육과정 과목만 노드로 쓴다. 선수과목이 다른 전공 과목이면
  `or_with` 대안 중 이 전공에 있는 과목으로 바꿔서 잇는다(예: 프로그래밍기초 → 기초프로그래밍).

## 백엔드 연결 (선택)
`.env.example`을 `.env.local`로 복사하고 `VITE_API_URL`을 채우면
- 이수 체크 → `POST /api/roadmap/complete`, 시작할 때 `GET /api/roadmap`
- 과목 상세(계획서·주차별) → `GET /api/subjects/{code}`

비워두면 이수 체크는 브라우저 저장소(localStorage)에만 저장된다.

## 화면
- 위: 전공 선택 + 진로 버튼(AI 엔지니어 / 시스템·AI 인프라 / 보안·네트워크 / 웹·앱 서비스 / 데이터 사이언스)
- 로드맵: x축 = 권장 학기(1-1 ~ 4-2). 초록=이수, 주황=수강 중, 파란 테두리=다음 후보(선수과목을 하나라도 들음), 주황 '필수'=전공필수
- 기본 화면 선: 들었거나 듣고 있는 과목에서 나가는 선만 (아무것도 안 들었으면 1학년 과목 선만 옅게)
- 진로 클릭: 그 진로의 도착 과목 + 거기까지 가는 선수과목만 진하게, 나머지는 흐리게. 오른쪽에 학기별 정리·남은 학점
- 과목 클릭: 그 과목까지 가는 선수과목 경로 강조 + 상세 패널
  - 선수과목을 '들은 것 / 아직 안 들은 것(권장)'으로 나누고, 다른 전공 교육과정에만 있는 과목은 '타 전공' 표시
  - 'AI에게 물어보기' → `POST /api/chat` (mode=prereq, 처음엔 빈 대화 → 첫 판단, 이후 대화 이어가기)
  - 서버가 없거나 아직 엔드포인트가 없으면(404) 계획서의 선수과목 문구·수강 참고사항을 대신 보여줌

## AI 상담 (data/llm — 준영님 모듈, 엔드포인트는 백엔드)
- 'AI 상담' 탭: `POST /api/chat` (mode=general, major, targets) → `{reply, suggest_action}`
- `suggest_action = plan_roadmap`이거나 대화가 오가면 '이 대화로 로드맵 짜기' → `POST /api/roadmap/plan` → 추가·삭제 미리보기(이유, 교육과정 밖 표시)
- '적용' → 진로 줄에 '★ 내 로드맵'이 생기고 지도에 경로 표시. 교육과정 밖 과목은 지도 오른쪽 끝 '교육과정 밖' 열에 표시
- 내 로드맵은 브라우저에 저장 (`PUT /api/roadmap/targets` 저장은 백엔드 준비되면 연결)
- 요청에 `completed`, `targets`도 같이 보낸다 (로컬 모드 사용자용). 백엔드는 DB 값을 써도 됨
- 503 → "AI가 바빠요", 404 → "서버 준비 전" 안내

## 내 현황 · 시간표
- 과목 이수 체크 → 성적(A+~F, P) 선택 → 오른쪽 '내 현황'에 평점과 졸업요건(`data/curriculum_data/out/graduation_credits.csv`) 진행률
- '내 시간표' 탭: 에브리타임 공유 링크 → 백엔드 `GET /api/everytime?link=` → 학기별 시간표 격자
  - '로드맵에 반영': 마지막 학기 = 수강 중(주황), 이전 학기 = 이수
  - 백엔드 없이도 '샘플로 보기'로 화면 확인 가능 (`src/sampleTimetable.json`, data/timetable/fixtures에서 만든 가짜 데이터)
- 성적·수강 중·기타 학점은 브라우저(localStorage)에만 저장된다. 이수 여부는 백엔드가 있으면 거기에도 저장

## 파일
- `src/data.ts` CSV 파싱, 전공별 그래프 만들기, 선수/후수/조상 계산, 이수 상태
- `src/careers.ts` 진로 프리셋 (진로별 도착 과목 코드) ← 진로를 바꾸거나 추가하려면 여기만 고치면 됨
- `src/layout.ts` 학기 열 배치(열 안 순서는 바리센터 정렬), 간선 스타일
- `src/nodes.tsx` 과목 노드, 학기 제목, 학기 사이 점선
- `src/CareerPanel.tsx` 진로를 골랐을 때 오른쪽 패널
- `src/SearchBox.tsx` 과목 검색 (진로 줄 오른쪽)
- `src/AdviceBox.tsx` 선수과목 상담 (prereq 채팅)
- `src/ChatView.tsx` AI 상담 탭 (general 채팅 + 로드맵 짜기 미리보기)
- `src/StatusPanel.tsx` 아무것도 안 골랐을 때 오른쪽 패널(평점·졸업요건·전공필수)
- `src/progress.ts` 성적 저장, 평점 계산(4.5/4.3), 졸업요건 계산
- `src/syllabus.ts` 강의계획서·분반·주차별 CSV (과목을 처음 열 때 불러옴)
- `src/TimetableView.tsx` 에브리타임 시간표 화면
- `../backend/everytime_router.py` 에브리타임 링크 → 시간표 API (`data/timetable/everytime.py` 사용)
- `src/api.ts` 백엔드 호출 (없으면 localStorage)
- `src/App.tsx` 로드맵 화면
- `src/SubjectPanel.tsx` 오른쪽 상세 패널

## 다음 할 일
- [ ] 백엔드 `/api/roadmap` 응답에 edges 포함되면 CSV 대신 API 사용
- [x] 진로 선택 → 추천 경로 강조 (프리셋)
- [x] 전공별 교육과정 기준 학기 열 배치
- [ ] 진로 자유 입력(AI 검색) — 시간 남으면
- [x] 시간표 화면 (에브리타임 링크 → 격자 → 로드맵 반영)
- [x] 성적 입력 · 평점 · 졸업요건
- [ ] 강점·약점 기반 추천 — 시간 남으면
- [ ] 과목 검색창
