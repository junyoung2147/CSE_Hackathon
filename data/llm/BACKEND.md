# 백엔드 연동 명세: LLM 상담·로드맵

`data/llm/`은 **요청을 받아 응답을 돌려주는 함수만** 제공합니다. 응답 저장, 대화 기록, 사용자 데이터 조회는 백엔드가 맡습니다. 이 문서는 무엇을 주고받는지만 정하고, 구현 방식은 백엔드가 정합니다. 함수의 자세한 동작은 [README.md](README.md)에 있습니다.

## 1. 준비

| 항목 | 내용 |
|---|---|
| 의존성 | `google-genai>=3.6.0`, `pydantic>=2` (확인한 버전: 3.6.1 / 2.12). **`backend/requirements.txt`에 `google-genai` 추가 필요** (지금 없음) |
| 키 | 환경변수 `GOOGLE_API_KEY` 또는 `GEMINI_API_KEY`. SDK가 직접 읽기 때문에 코드에서 키를 다루지 않음. `data/.env`에 두어도 됨(gitignore 처리됨) |
| 모델 | 기본값 `gemini-3.5-flash-lite`. 환경변수 `GEMINI_MODEL`로 변경 |
| import 경로 | `data/`를 `sys.path`에 넣은 뒤 `from llm import api, client, context` |
| 호출 시간 | 동기 함수이고 보통 수 초가 걸림. 호출 한 번의 timeout은 60초이고, general 모드는 tool 때문에 최대 3번 연달아 호출함. 이벤트 루프를 막지 않게 호출해 주세요(FastAPI라면 `async def` 대신 `def` 엔드포인트) |

## 2. 함수 계약

### 입력 공통
- `conversation`: `[{"role": "user" | "assistant", "text": str}]` 형식입니다. 다른 role이 오거나 text가 문자열이 아니면 `ValueError`가 납니다.
- 길이 상한: 메시지 **40개**(20턴)까지, 메시지 하나에 **2,000자**까지입니다. 넘으면 `ValueError`가 납니다. 공개 서버에서 무료 한도를 지키기 위한 장치입니다. 넘으면 프론트에서 새 대화로 시작하게 해 주세요.
- `completed`, `targets`, `taking`: 과목 코드 목록입니다. `taking`은 이번 학기 수강 중인 과목이고, 선수과목 판단에서 이수와 같게 충족으로 봅니다. 과목 코드가 아닌 값은 함수 안에서 버려지므로, 이름이나 학번 같은 값을 넣어도 Gemini로 가지 않습니다.
- `major`: `curriculum.major_name` 값입니다(예: `심화컴퓨팅전공`). 사용자 정보에 전공이 없으면 요청에서 받아야 합니다.

### `api.chat(mode, conversation, completed, major=, targets=, subject=, unmet=, taking=)`
| mode | 필요한 인자 | 동작 |
|---|---|---|
| `general` | `major`, `targets` | 진로·과목·졸업요건을 상담합니다. 로드맵을 짜 달라는 요청을 알아채면 `suggest_action`을 채웁니다. 대화가 비어 있으면 `ValueError` |
| `prereq` | `subject`, `unmet` | `subject`를 듣기 전에 안 들은 선수과목 `unmet`을 건너뛰어도 되는지 상담합니다. 대화가 비어 있으면 첫 판단을 만듭니다 |

- 반환: `{"reply": str, "suggest_action": "plan_roadmap" | null}`
- `unmet`은 백엔드가 계산해서 넘깁니다. `course_edges`에서 `to_code = subject`, `type = "pre"`인 간선 중 사용자가 충족하지 못한 것들입니다(`or_with` 대체 과목 반영). 기존 `_is_edge_satisfied` 기준과 같습니다. 비어 있으면 `ValueError`가 납니다. **수강 중(`taking`)인 선수과목은 백엔드도 충족으로 보고 `unmet`에서 빼 주세요.** 함수 안에서도 한 번 걸러 주지만, 전부 걸러져 비면 `ValueError`가 나므로 백엔드가 먼저 빼서 상담 버튼을 숨기는 편이 낫습니다.
- prereq 모드에서 후속 질문을 보낼 때는 대화를 이렇게 구성해야 맥락이 이어집니다.
  ```
  [{"role":"user","text": api.FIRST_PREREQ_MSG}, {"role":"assistant","text": 첫 판단}, {"role":"user","text": 후속 질문}, ...]
  ```

### `api.plan_roadmap(conversation, major, current_targets, completed, taking=)`
- 대화를 보고 목표 과목을 새로 짜거나 고칩니다. 진로는 LLM이 대화에서 판단합니다.
- 반환:
  ```json
  {"add": [코드], "remove": [코드], "reasons": {"코드": "이유"},
   "outside_curriculum": [코드], "dropped": [코드]}
  ```
- `add`에는 실제 과목이면서 현재 목표에 없고 이수하지도, 수강 중이지도 않은 과목만 남습니다.
- `remove`에는 현재 목표에 있는 과목만 남습니다.
- `outside_curriculum`은 add 중 해당 전공 교육과정에 없는 과목입니다. 화면에 "교육과정 밖 과목"이라고 안내해야 합니다.
- `dropped`는 LLM이 냈지만 걸러진 코드입니다(지어낸 코드 등). 디버깅용입니다.
- 적용 후 목표는 `current_targets - remove + add`입니다. 저장은 사용자가 미리보기를 보고 적용했을 때 합니다.

### 예외
| 예외 | 의미 | 권장 HTTP |
|---|---|---|
| `ValueError` | 잘못된 입력 (형식, 길이 상한 초과, 빈 general 대화, 모르는 전공·과목, 안 들은 선수과목 없음) | 400 |
| `client.LLMError` | Gemini 실패 (한도 초과, 수요 과다, timeout·연결 오류, 빈 응답, 키 없음). 429·503·timeout·연결 오류는 함수 안에서 5초 뒤 1회 재시도한 뒤의 실패입니다 | 503 |

## 3. 제안 엔드포인트

| 메서드·경로 | 요청 | 응답 | 하는 일 |
|---|---|---|---|
| `POST /api/chat` | `{user_id, mode, conversation, major?, subject?}` | `api.chat` 반환값 | 이수 과목·목표 과목은 DB에서, `unmet`은 간선으로 계산해서 호출 |
| `POST /api/roadmap/plan` | `{user_id, major, conversation}` | `api.plan_roadmap` 반환값 | 미리보기만, 저장 안 함 |
| `PUT /api/roadmap/targets` | `{user_id, targets, source}` | `{user_id, targets}` | 적용한 목표 과목 전체를 덮어씀. source는 `preset` 또는 `llm` |

## 4. 제안: LLM 응답을 DB에 저장

`data/llm/`은 응답을 저장하지 않습니다. 대신 백엔드가 **사용자별 요청·응답을 한 테이블에 저장**하는 방식을 제안합니다. 테이블 하나로 두 가지를 할 수 있습니다.

1. **대화 기록**: 다른 기기에서 접속해도 이전 상담을 이어 볼 수 있습니다.
2. **같은 요청 재사용**: 입력이 완전히 같은 요청이 오면 Gemini를 부르지 않고 저장된 응답을 돌려줍니다.
   - 무료 플랜 한도를 아낄 수 있습니다.
   - **발표 대비**가 됩니다. 발표 전에 데모 시나리오를 한 번 돌려 두면, 발표 중 Gemini가 503을 내도 저장된 응답이 나갑니다. 11/21 테스트 때 상위 모델 두 개가 실제로 503을 냈습니다.

### 테이블 `llm_logs` (제안)
| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | int PK | |
| `user_id` | str, index | |
| `kind` | str | `general` / `prereq` / `plan` |
| `subject_code` | str, null | prereq일 때 대상 과목 |
| `request_key` | str, index | 아래 입력 전체의 해시 (예: sha256) |
| `request` | JSON 텍스트 | 함수에 넘긴 인자 전체 |
| `response` | JSON 텍스트 | 함수 반환값 |
| `model` | str | `client.MODEL` |
| `created_at` | datetime | |

- **`request_key`에 넣어야 할 것**: kind, model, major, subject, 정렬한 completed·taking·targets·unmet, conversation 전체. 하나라도 빠지면 다른 상황의 응답이 재사용됩니다.
- **오류 응답은 저장하지 않습니다.** `LLMError`가 나면 저장하지 말아야 다음 요청에서 다시 시도됩니다.
- **prompt나 데이터를 바꾼 뒤에는** 이 테이블을 비우거나, 재사용 조건에 날짜를 추가해야 합니다. `request_key`에는 prompt 내용이 들어가지 않기 때문입니다.
- 대화 기록을 서버에 저장하더라도, 함수 입력은 여전히 대화 전체입니다. 프론트가 보내든 백엔드가 이 테이블에서 조립하든 상관없습니다.

## 5. 필요한 테이블

LLM 모듈이 읽는 데이터는 10개 테이블입니다.

| 테이블 | 백엔드 현황 | 출처 CSV |
|---|---|---|
| `subjects`, `sections`, `syllabus`, `syllabus_weeks`, `curriculum`, `course_edges` | 있음 | 기존 seed |
| `careers` | **없음** | `data/career_data/careers.csv` (`career_id, name, description, source`) |
| `career_subjects` | **없음** | `data/career_data/career_subjects.csv` (`career_id, subject_code, source`) |
| `graduation_credits` | **없음** | `data/curriculum_data/out/graduation_credits.csv` (`major_name, track, from, to, category, credits_min, credits_max, note`) |
| `graduation_rules` | **없음** | `data/curriculum_data/out/graduation_rules.csv` (`major_name, track, from, to, item, requirement, footnotes`) |

엔드포인트용으로 아래 두 테이블도 필요합니다.
- `user_roadmaps` (`user_id, subject_code, source`, (user_id, subject_code) 유니크): 사용자의 목표 과목
- `llm_logs`: 4절의 제안

## 6. 데이터를 CSV에서 DB로 전환 (선택)

지금 LLM 모듈은 `data/` 안의 CSV를 직접 읽습니다. 백엔드 DB도 같은 CSV로 seed하므로 전환하지 않아도 내용은 같습니다. 전환하면 데이터 출처가 DB 하나로 합쳐집니다.

**전환 방법**: `context.use_loader(fn)`에 함수 하나를 넘기면 됩니다. `fn(테이블명) -> [dict, ...]`이고, **`data/llm/` 코드는 바꿀 필요가 없습니다.** 다음 규칙만 지키면 됩니다.

1. **테이블 이름**은 5절 표의 이름과 같아야 합니다(기존 테이블은 `__tablename__`).
2. **dict의 키는 CSV 헤더와 같은 DB 컬럼명**이어야 합니다. `graduation_*`의 `from`/`to`는 파이썬 예약어입니다. 모델 속성 이름은 다르게 지어도 되지만, DB 컬럼명은 `from`/`to`로 두고 컬럼명 기준으로 읽어야 합니다.
3. **행은 primary key 순서(= CSV에 넣은 순서)로** 돌려줘야 합니다. 순서가 바뀌면 같은 데이터라도 prompt 텍스트가 달라집니다.
4. 값의 타입은 신경 쓰지 않아도 됩니다. `None`, `int`, `bool`(예: `is_required`)이 와도 CSV 문자열과 같은 결과가 나옵니다.
5. DB에 아직 없는 테이블은 `context.csv_loader(테이블명)`을 대신 돌려주면 됩니다. 그러면 한 번에 다 바꾸지 않고 조금씩 전환할 수 있습니다.
6. 데이터는 처음 읽을 때 메모리에 올려 둡니다. 서버가 켜진 상태에서 DB를 바꿨다면 `use_loader`를 다시 호출하거나 서버를 재시작해야 반영됩니다.
