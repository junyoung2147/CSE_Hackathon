# 발표용 다이어그램

`.mmd`가 원본이고 `.png`는 렌더링 결과다. 숫자는 2026-11-23 기준 데이터와 코드에서 가져왔다.

| 파일 | 내용 |
|---|---|
| `01_flowchart_data_pipeline` | 공개 원본 → CSV 전처리 → 간선 해석·검수 → SQLite |
| `02_flowchart_service_architecture` | 프론트 · 백엔드 · data 모듈 · Gemini · 에브리타임 |
| `03_sequence_chat_request` | 상담 요청 한 번의 흐름 (tool 호출, 코드가 선수과목 계산) |
| `04_flowchart_career_to_roadmap` | 진로 질문 → 꼬리 질문 → 진로 제안 → 로드맵 검증 |
| `05_flowchart_hallucination_guard` | 입력·프롬프트·출력 3단계 환각 방지 |
| `06_er_data_model` | 핵심 테이블 관계 (backend/models.py 기준) |
| `09_flowchart_data_pipeline` | 데이터 전처리: 공개 페이지 수집 · 정리 → 선수 관계 만들기(Claude 해석 → 사람 검수 → 자동 검증) → SQLite |
| `08_flowchart_ai_answer_pipeline` | AI 상담이 답을 만드는 과정 6단계 (코드가 하는 일과 AI가 하는 일 구분) |
| `07_flowchart_system_architecture` | PPT 시스템 구성도 개선판 (학생 · 프론트 · 백엔드 · DB · 외부 서비스 · 데이터 준비) |

## 다시 그리기

```bash
npx -y @mermaid-js/mermaid-cli@11.4.2 -i 01_flowchart_data_pipeline.mmd -o 01_flowchart_data_pipeline.png \
  -c mermaid-config.json -b white -s 3 -w 1600
```
