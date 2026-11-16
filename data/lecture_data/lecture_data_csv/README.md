# 강의 데이터 CSV

출처: 경북대 [수업시간표 및 강의계획서 조회](https://knuin.knu.ac.kr/public/stddm/lectPlnInqr.knu) (비로그인 공개 페이지)
범위: 2026 1·2학기, 컴퓨터학부(학부 + 하위 전공 6개) 개설 분반, 전공에 필요한 교양 5과목(기초수학2, 수학 I·II, 물리학 I·II)

## 다시 만들기
```
python data/scripts/crawl_lectures.py --year 2026 --smstr 1 2 --syllabus   # raw 수집 (이미 받은 것은 건너뜀)
python data/scripts/build_csv.py                                          # raw → CSV
```
새 학기는 `--year`·`--smstr`만 바꿔 실행한다. 학기 중 계획서가 바뀌었으면 `--refresh`를 붙인다.
`data/raw/syllabus/`(약 23MB)는 git에 올리지 않는다. 필요하면 위 명령으로 다시 받는다.

## 파일과 키
- 학기는 `term`(`2026-1`), 분반은 `term + course_no`, 과목은 `subject_code`로 연결한다.
- 모든 텍스트는 원문 그대로다(HTML 태그만 제거). 영어 강의는 계획서도 영어다.
- 출처: 각 행의 `source_file`은 `data/` 기준 raw 경로다. 사이트는 SPA라 계획서별 URL이 없다. 원문을 보려면 조회 페이지에서 학기를 고르고 강좌번호(course_no)로 검색한 뒤 행을 더블클릭한다.

| 파일 | 한 행 | 주요 컬럼 |
|---|---|---|
| `subjects.csv` | 과목 | subject_name, credit(학점), lecture_hours(이론 시수), practice_hours(실습 시수), offered_terms(개설 학기), section_count(분반 수), prerequisites(선수과목), followups(후수과목) |
| `sections.csv` | 분반 | subject_code, section(분반), professor, time_slots(교시), time_real(실제 시간), room, language(`Kor`/`Eng`/`Pre`), capacity(정원), listed_in(이 분반이 조회된 전공 코드들, 교양 과목 목록에서 나온 분반은 `교양`), has_syllabus |
| `syllabus.csv` | 분반의 계획서 일반사항 | professor(교수), credit_system(학점-이론-실습), summary(개요), goals(목표), textbooks_references(교재·참고문헌), evaluation(평가 방법), notes(수강 참고사항) |
| `syllabus_weeks.csv` | 분반 × 주차 | week, content(주차 내용), method(수업 방법) |
| `syllabus_books.csv` | 분반 × 교재 | title, author, publisher, year, isbn, book_type_code(원본 코드) |

### 교양 5과목
기초수학2(CLTR0819), 수학 I(CLTR0211), 수학 II(CLTR0212), 물리학 I(CLTR0213), 물리학 II(CLTR0214)는 전교 분반을 모두 sections에 넣었다. 계획서는 과목·학기마다 1개만 받았다. 고르는 순서는 컴퓨터학부 분반, 그다음 전자공학부·전기공학과·기계공학부 분반, 그것도 없으면 강좌번호가 가장 앞선 분반이다. 그래서 교양 분반 대부분은 `has_syllabus=N`이다.

### prerequisites / followups 형식
분반마다 계획서에 적힌 문구가 달라서, 서로 다른 문구를 한 줄씩 넣고 뒤에 그 문구를 쓴 분반을 붙였다. 공백만 다른 문구는 하나로 합쳤다.
```
프로그래밍기초 또는 기초프로그래밍 (C 또는 C++ 이론과 실습과목을 모두 선수강해야 함) (2026-1 003, 2026-2 003)
프로그래밍기초 (2026-1 004, 2026-1 005, 2026-2 005)
```

### 전공 컬럼 코드
`1O02` 컴퓨터학부, `1O0204` 글로벌소프트웨어융합, `1O0205` 플랫폼소프트웨어, `1O0206` 데이터과학, `1O0208` 인공지능컴퓨팅, `1O0209` 심화컴퓨팅, `1O0210` 첨단컴퓨팅연구

## 넣지 않은 것
- 전공별 교과구분·학년: 같은 과목도 전공마다 다르다. 전공별 교육과정 데이터를 기준으로 한다.
- 핵심역량(코드만 있음), 평가 비율(항목 이름을 알 수 없음). raw에는 남아 있다.
