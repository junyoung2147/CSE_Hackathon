# LLM 상담·로드맵 모듈 (`data/llm/`)

Gemini로 상담 채팅 2종과 로드맵 짜기를 처리하는 순수 Python 함수 모음입니다. FastAPI에 의존하지 않으므로 백엔드는 라우트로 감싸기만 하면 됩니다.

## 설정
- 의존성: `pip install google-genai pydantic` (확인한 버전: google-genai 3.6.1, pydantic 2.12)
- 키: `data/.env`에 `GEMINI_API_KEY=...`를 둡니다. 이미 설정된 환경변수가 있으면 그쪽을 씁니다. `data/.gitignore`에 들어 있어 커밋되지 않습니다.
- 모델: 기본값은 `gemini-3.5-flash-lite`(무료 플랜. 3.6·3.8-flash는 테스트 때 503)이고 `GEMINI_MODEL` 환경변수로 바꿀 수 있습니다.
- 무료 플랜에서는 입력이 Google의 모델 개선에 쓰입니다. 그래서 과목 코드와 대화 내용만 보냅니다. `completed`·`targets`에 들어온 값 중 과목 코드가 아닌 것은 버립니다.
- 캐시: 같은 입력의 응답은 `data/llm/cache/`에 저장해 다시 호출하지 않습니다. 발표 전에 데모 시나리오를 한 번 돌려 두면 데모 중에는 캐시에서 바로 나옵니다.
- 429(한도 초과)·503(수요 과다)이 오면 5초 뒤 한 번 다시 시도하고, 그래도 실패하면 `client.LLMError`가 납니다. 백엔드에서는 503으로 바꿔 주세요.

## 함수
`conversation`은 `[{"role": "user"|"assistant", "text": str}]` 형식이고, 대화 기록은 프론트가 들고 있다가 매번 보냅니다.

| 함수 | 용도 | 반환 |
|---|---|---|
| `chat("general", conversation, completed, major=, targets=)` | 일반 상담 (진로·과목·졸업요건) | `{reply, suggest_action}` |
| `chat("prereq", conversation, completed, subject=, unmet=)` | 안 들은 선수과목을 건너뛰어도 되는지 상담. 대화가 비어 있으면 첫 판단을 만듦 | `{reply, suggest_action: None}` |
| `plan_roadmap(conversation, major, current_targets, completed)` | 대화를 보고 목표 과목을 새로 짜거나 수정. 진로는 LLM이 대화에서 판단 | `{add, remove, reasons: {code: 이유}, outside_curriculum, dropped}` |

- `suggest_action == "plan_roadmap"`이면 프론트에 "로드맵 짜기" 버튼을 띄웁니다.
- `plan_roadmap`의 add에는 실제 과목 코드(subjects)만 남고, 그중 해당 전공 교육과정 밖 과목은 `outside_curriculum`에도 들어갑니다. 프론트는 이 과목에 "교육과정 밖 과목"이라고 안내해 주세요. 로드맵 화면이 전공 교육과정으로 과목을 거르고 있다면 이 과목들도 보이게 해야 합니다. remove에는 현재 목표에 있는 코드만 남습니다. 지어낸 코드처럼 버린 코드는 `dropped`에 들어갑니다. 경로(선수과목 체인)는 기존 edges 로직으로 계산합니다.
- 잘못된 입력(role, 모르는 전공·과목)이 들어오면 `ValueError`가 납니다. 백엔드에서는 400으로 바꿔 주세요.

## 백엔드 제안
```python
import sys; sys.path.append("<repo>/data")
from llm import api, client
```
- `POST /api/chat` body `{mode, conversation, user_id, subject?, unmet?}`: 서버가 user_id로 major, completed, targets를 DB에서 꺼내 `api.chat`에 넘깁니다.
- `POST /api/roadmap/plan` body `{conversation, user_id}`: `api.plan_roadmap` 결과를 미리보기로 돌려줍니다. 저장하지 않습니다.
- `PUT /api/roadmap/targets` body `{user_id, targets}`: 사용자가 미리보기를 보고 적용하면 저장합니다.
- 테이블과 seed
  - `careers`: `data/career_data/careers.csv`에서 seed
  - `career_subjects`: `data/career_data/career_subjects.csv`에서 seed
  - `user_roadmap(user_id, subject_code, source)`: source는 `preset`이나 `llm`
- 백엔드는 `requirements.txt`에 `google-genai`를 추가해야 합니다.

## 프론트 제안
- 일반 상담 채팅 화면: `suggest_action`이 오면 "로드맵 짜기" 버튼을 보여 줍니다. 누르면 `/api/roadmap/plan`을 호출하고, add/remove 미리보기를 보여 준 뒤 적용합니다.
- 선수과목 상담: 다음에 들을 과목을 누르면 표시되는 "안 들은 선수과목" 옆에서 엽니다. 처음에는 빈 대화로 호출해 첫 판단을 받습니다.

## 파일
- `client.py`: Gemini 호출, 캐시, 재시도
- `context.py`: CSV를 읽어 prompt용 텍스트를 만듦
- `api.py`: 위 함수 3개
- `prompts/`: 시스템 prompt 3개
- `test_api.py`: 가짜 client로 돌리는 오프라인 테스트. `data/`에서 `python -m llm.test_api`로 실행합니다.
