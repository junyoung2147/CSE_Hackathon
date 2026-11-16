"""경북대 수업시간표·강의계획서 공개 페이지에서 강의 목록과 강의계획서 원본(JSON)을 수집한다.

사용법:
    python data/scripts/crawl_lectures.py --year 2026 --smstr 1 2             # 목록만
    python data/scripts/crawl_lectures.py --year 2026 --smstr 1 2 --syllabus  # 목록 + 강의계획서
    --refresh: 해당 학기 raw를 무시하고 다시 받음

강의계획서 상세 API는 직접 호출하면 401이라, 사이트가 비로그인 사용자에게 여는 팝업을 그대로 열고
팝업이 받는 응답을 저장한다.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PAGE_URL = "https://knuin.knu.ac.kr/public/stddm/lectPlnInqr.knu"
LIST_API = "/public/web/stddm/lsspr/syllabus/lectPlnInqr/selectListLectPlnInqr"
SMSTR_CODES = {"1": "CMBS001400001", "2": "CMBS001400002"}

# 학과 개편 시 여기만 고친다. 강의계획서까지 수집하는 대상.
CSE_DEPTS = {
    "1O02": "컴퓨터학부",
    "1O0204": "컴퓨터학부 글로벌소프트웨어융합전공",
    "1O0205": "컴퓨터학부 플랫폼소프트웨어전공",
    "1O0206": "컴퓨터학부 데이터과학전공",
    "1O0208": "컴퓨터학부 인공지능컴퓨팅전공",
    "1O0209": "컴퓨터학부 심화컴퓨팅전공",
    "1O0210": "컴퓨터학부 첨단컴퓨팅연구전공",
}
# 컴퓨터학부 전공에 필요한 교양과목. 전교 분반 목록을 받고, 계획서는 과목·학기당 1개만 받는다
# (공통 교양이라 분반 간 내용이 비슷함). 선형대수 등 전공 수학은 CSE_DEPTS 목록에 포함됨.
BASIC_SUBJECTS = {
    "CLTR0819": "기초수학2",
    "CLTR0211": "수학 I",
    "CLTR0212": "수학 II",
    "CLTR0213": "물리학 I",
    "CLTR0214": "물리학 II",
}
# 컴퓨터학부 목록에 나오지만 전공 지도와 무관한 교양 (수집·CSV에서 제외)
EXCLUDED_SUBJECTS = {
    "CLTR0003": "실용화법",
    "CLTR0043": "서양의 역사와 문화",
    "CLTR0045": "논리와 비판적 사고",
    "CLTR0089": "회계와사회생활",
    "CLTR0205": "대학글쓰기",
}
# 컴퓨터학부 분반이 없을 때 계획서를 받을 분반의 개설학과 우선순위 (비슷한 공학 계열)
BASIC_PREFERRED_DEPTS = ("전자공학부", "전기공학과", "기계공학부")
# 팝업 응답 중 저장할 것. Qsttm(공통 강의평가 문항)은 과목과 무관해 제외.
SYLLABUS_EPS = ["Pub", "Ablty", "WekCntns", "SrchBooks"]
# 클릭해야 Ablty(핵심역량)·WekCntns(주별강의)를 불러옴. 영어 강의는 탭 이름이 영어라 id로 지정.
SYLLABUS_TABS = ["#popupContent_tabCon_tab_tabs2_tabHTML", "#popupContent_tabCon_tab_tabs5_tabHTML"]

RAW = Path(__file__).resolve().parents[1] / "raw"
DELAY = 1.2  # 요청 간 최소 간격(초)


def fetch_list(page, year, smstr_cd, **cond):
    """목록 API를 페이지 안에서 호출해 응답 JSON 전체를 돌려준다."""
    body = page.evaluate(
        """async ([api, over]) => {
            const s = {...dma_SearchParam.getJSON(), ...over};
            const r = await fetch(api, {method: 'POST',
                headers: {'Content-Type': 'application/json; charset=UTF-8'},
                body: JSON.stringify({search: s})});
            return {status: r.status, json: await r.json()};
        }""",
        [LIST_API, {"estblYear": year, "estblSmstrSctcd": smstr_cd, **cond}],
    )
    if body["status"] != 200 or not isinstance(body["json"].get("data"), list):
        sys.exit(f"목록 API 응답 형식이 바뀜: status={body['status']} cond={cond}")
    return body["json"]


def collect_lists(page, year, smstr, refresh):
    """학과별·교과구분별 목록을 raw에 저장하고 {key: rows}를 돌려준다."""
    out = {}
    jobs = [(f"dept_{cd}", {"estblDprtnCd": cd}) for cd in CSE_DEPTS]
    jobs += [(f"subj_{cd}", {"sbjetCd": cd}) for cd in BASIC_SUBJECTS]
    for key, cond in jobs:
        path = RAW / "lectures" / f"list_{year}_{smstr}_{key}.json"
        if path.exists() and not refresh:
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = fetch_list(page, year, SMSTR_CODES[smstr], **cond)
            data["_query"] = {"year": year, "smstr": smstr, **cond, "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            time.sleep(DELAY)
        out[key] = data["data"]
        print(f"  {year}-{smstr} {key}: {len(data['data'])}건")
    return out


def collect_syllabus(page, ctx, row, outdir):
    """강좌 하나의 계획서 팝업을 열어 응답 JSON을 outdir에 저장한다. 성공 여부 반환."""
    got = {}

    def on_resp(r):
        for ep in SYLLABUS_EPS:
            if r.url.split("?")[0].endswith("selectListLectPlnInputDtl" + ep) and r.ok:
                try:
                    got[ep] = r.json()
                except Exception:
                    pass

    page.evaluate("row => { dlt_01.setJSON([row]); dlt_01.setRowPosition(0); }", row)
    with ctx.expect_page(timeout=20000) as pi:
        page.evaluate("scwin.openLectPlnInputDtlPop(0)")
    pop = pi.value
    pop.on("response", on_resp)
    try:
        pop.wait_for_load_state("networkidle", timeout=30000)
        for sel in SYLLABUS_TABS:
            tab = pop.locator(sel)
            if tab.count() and tab.first.is_visible():
                tab.first.click()
                pop.wait_for_load_state("networkidle", timeout=15000)
        deadline = time.time() + 10
        while len(got) < len(SYLLABUS_EPS) and time.time() < deadline:
            pop.wait_for_timeout(300)
    finally:
        pop.close()
    if "Pub" not in got:
        return False
    outdir.mkdir(parents=True, exist_ok=True)
    for ep, data in got.items():
        (outdir / f"{ep}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def main():
    """인자를 읽어 목록(+계획서)을 수집한다."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True)
    ap.add_argument("--smstr", nargs="+", choices=list(SMSTR_CODES), required=True)
    ap.add_argument("--syllabus", action="store_true", help="컴퓨터학부 강좌의 강의계획서까지 수집")
    ap.add_argument("--refresh", action="store_true", help="이미 받은 raw도 다시 받음")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(PAGE_URL, wait_until="networkidle")
        failed = []
        for smstr in args.smstr:
            lists = collect_lists(page, args.year, smstr, args.refresh)
            if not args.syllabus:
                continue
            # 컴퓨터학부 강좌 전부 (crseNo 기준 중복 제거)
            rows = {r["crseNo"]: r for k, v in lists.items() if k.startswith("dept_") for r in v
                    if r["sbjetCd"] not in EXCLUDED_SUBJECTS}
            # 교양: 컴퓨터학부 분반이 없으면 전자·전기·기계 순으로, 그것도 없으면 강좌번호가 가장 앞선 분반 1개 추가
            for cd in BASIC_SUBJECTS:
                secs = sorted((r for r in lists[f"subj_{cd}"] if r["sbjetCd"] == cd), key=lambda r: r["crseNo"])
                if secs and not any(r["sbjetCd"] == cd for r in rows.values()):
                    pick = next((r for d in BASIC_PREFERRED_DEPTS for r in secs
                                 if (r["estblDprtnNm"] or "").startswith(d)), secs[0])
                    rows[pick["crseNo"]] = pick
            todo = [r for no, r in rows.items()
                    if args.refresh or not (RAW / "syllabus" / f"{args.year}_{smstr}_{no}" / "Pub.json").exists()]
            print(f"  {args.year}-{smstr} 계획서: 전체 {len(rows)} / 수집 대상 {len(todo)}")
            for i, r in enumerate(todo, 1):
                outdir = RAW / "syllabus" / f"{args.year}_{smstr}_{r['crseNo']}"
                try:
                    ok = collect_syllabus(page, ctx, r, outdir)
                except Exception as e:  # 한 강좌 실패로 전체를 멈추지 않음
                    ok = False
                    print(f"    오류 {r['crseNo']}: {e}")
                if not ok:
                    failed.append(f"{args.year}-{smstr} {r['crseNo']} {r['sbjetNm']}")
                print(f"    [{i}/{len(todo)}] {r['crseNo']} {r['sbjetNm']} {'OK' if ok else '실패'}")
                time.sleep(DELAY)
        browser.close()
    if failed:
        print(f"\n계획서 수집 실패 {len(failed)}건:")
        print("\n".join("  " + f for f in failed))


if __name__ == "__main__":
    main()
