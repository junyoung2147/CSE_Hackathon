# LLM 상담·로드맵 모듈 (`data/llm/`)

Gemini로 상담 채팅 2종과 로드맵 짜기를 처리하는 순수 Python 함수 모음입니다. FastAPI나 DB에 의존하지 않고, 요청을 받아 응답만 돌려줍니다.

## 설정
- 의존성: `pip install google-genai pydantic` (확인한 버전: google-genai 3.6.1, pydantic 2.12)
- 모델: 기본값은 `gemini-3.5-flash-lite`(무료 플랜. 3.6·3.8-flash는 테스트 때 503)이고 `GEMINI_MODEL` 환경변수로 바꿀 수 있습니다.
- 무료 플랜에서는 입력이 Google의 모델 개선에 쓰입니다. 그래서 과목 코드와 대화 내용만 보냅니다. `completed`·`targets`에 들어온 값 중 과목 코드가 아닌 것은 버립니다.
- 저장 없음: 이 모듈은 요청을 받아 응답만 돌려줍니다. 응답 저장과 같은 요청 재사용은 백엔드가 맡습니다([BACKEND.md](BACKEND.md) 4절 제안).
- 429(한도 초과)·503(수요 과다)이 오면 5초 뒤 한 번 다시 시도하고, 그래도 실패하면 `client.LLMError`가 납니다. 백엔드에서는 503으로 바꿔 주세요.

## 함수
`conversation`은 `[{"role": "user"|"assistant", "text": str}]` 형식이고, 함수에는 매번 대화 전체를 넘깁니다(대화 기록 보관은 프론트나 백엔드 몫).

| 함수 | 용도 | 반환 |
|---|---|---|
| `chat("general", conversation, completed, major=, targets=)` | 일반 상담 (진로·과목·졸업요건) | `{reply, suggest_action}` |
| `chat("prereq", conversation, completed, subject=, unmet=)` | 안 들은 선수과목을 건너뛰어도 되는지 상담. 대화가 비어 있으면 첫 판단을 만듦 | `{reply, suggest_action: None}` |
| `plan_roadmap(conversation, major, current_targets, completed)` | 대화를 보고 목표 과목을 새로 짜거나 수정. 진로는 LLM이 대화에서 판단 | `{add, remove, reasons: {code: 이유}, outside_curriculum, dropped}` |

- `suggest_action == "plan_roadmap"`이면 프론트에 "로드맵 짜기" 버튼을 띄웁니다.
- `plan_roadmap`의 add에는 실제 과목 코드(subjects)만 남고, 그중 해당 전공 교육과정 밖 과목은 `outside_curriculum`에도 들어갑니다. 프론트는 이 과목에 "교육과정 밖 과목"이라고 안내해 주세요. 로드맵 화면이 전공 교육과정으로 과목을 거르고 있다면 이 과목들도 보이게 해야 합니다. remove에는 현재 목표에 있는 코드만 남습니다. 지어낸 코드처럼 버린 코드는 `dropped`에 들어갑니다. 경로(선수과목 체인)는 기존 edges 로직으로 계산합니다.
- 잘못된 입력(role, 모르는 전공·과목)이 들어오면 `ValueError`가 납니다. 백엔드에서는 400으로 바꿔 주세요.

## 백엔드 연동
함수 계약, 제안 엔드포인트, 응답 저장 제안, 필요한 테이블, CSV에서 DB로 전환하는 규칙은 [BACKEND.md](BACKEND.md)에 있습니다.

## 프론트 제안
- 일반 상담 채팅 화면: `suggest_action`이 오면 "로드맵 짜기" 버튼을 보여 줍니다. 누르면 `/api/roadmap/plan`을 호출하고, add/remove 미리보기를 보여 준 뒤 적용합니다.
- 선수과목 상담: 다음에 들을 과목을 누르면 표시되는 "안 들은 선수과목" 옆에서 엽니다. 처음에는 빈 대화로 호출해 첫 판단을 받습니다.

## 파일
- `client.py`: Gemini 호출, timeout, 재시도
- `context.py`: 데이터(기본 CSV, `use_loader`로 DB)를 읽어 prompt용 텍스트를 만듦
- `api.py`: 위 함수 3개
- `prompts/`: 시스템 prompt 3개
- `cli.py`: 터미널에서 직접 써 보는 테스트 스크립트. `data/`에서 `python -m llm.cli chat|prereq|roadmap`로 실행합니다. 사용법은 `-h`로 볼 수 있습니다. **입력할 때마다 실제로 호출합니다.**
- `demo.py`: 데모 시나리오 7개를 실제로 호출합니다. **돌릴 때마다 약 10회 호출합니다.**
- `test_api.py`: 가짜 client로 돌리는 오프라인 테스트. `data/`에서 `python -m llm.test_api`로 실행합니다.
