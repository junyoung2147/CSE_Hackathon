#!/usr/bin/env python3
"""
경북대학교 컴퓨터학부(aicollege.knu.ac.kr) 전공별 졸업요건 / 교육과정 크롤러

- 전공 목록은 사이트 메뉴(sub3_N_a.php / sub3_N_b.php)에서 자동으로 찾는다.
  → 전공이 추가/삭제/개명되어도 코드 수정 없이 동작.
- 표는 rowspan/colspan을 펼친 뒤 '헤더 텍스트'를 기준으로 열을 찾는다.
  → 열 순서/개수가 바뀌어도, 학기 블록이 늘어나도 동작.

출력(CSV, utf-8-sig → 엑셀에서 한글 정상 표시)
  majors.csv                 전공 목록
  graduation_requirements.csv 전공별 졸업요건
  curriculum.csv             전공별 교육과정(과목 단위)
  curriculum_files.csv       교육과정 첨부파일(PDF 등) 링크
  curriculum_pdf.csv         PDF에서 뽑은 과목 목록(보조, --pdf 옵션)

사용법
  pip install requests beautifulsoup4 pdfplumber   # pdfplumber는 PDF 보조 추출용
  python knu_cse_crawler.py --out out --save-raw
"""
import argparse
import csv
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://aicollege.knu.ac.kr/"
SEED = "sub3_2_a.php"  # 메뉴 구조를 읽기 위한 시작 페이지
HEADINGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
GENERIC_LINK_TEXTS = {"", "전공소개", "교육과정", "학부소개"}
FILE_RE = re.compile(r"\.(pdf|hwp|hwpx|xlsx?|zip|jpe?g|png)(\?|$)", re.I)

# 전공/연도마다 표 헤더 표기가 달라서(교과목코드 / 과목번호 / Course number ...) 동의어로 판별
CODE_HDR = ("교과목코드", "과목번호", "과목코드", "coursenumber", "coursecode")
NAME_HDR = ("교과목명", "과목명", "subjectname", "coursename")
CRED_HDR = ("학점체계", "학점", "creditsystem", "credit")
CODE_RE = re.compile(r"^[A-Z]{3,5}\d{3,5}$")


def has_any(text, keys):
    t = norm(text).lower()
    return any(k in t for k in keys)

FIELDS = {
    "majors": ["major_code", "major_name", "status_note", "valid_until",
               "intro_url", "curriculum_url"],
    "graduation_requirements": ["major_code", "major_name", "basis_year", "item",
                                "condition", "requirement", "credits",
                                "credits_qualifier", "footnote_refs", "footnotes",
                                "source_url", "crawled_at"],
    "curriculum": ["major_code", "major_name", "basis_year", "grade", "category",
                   "semester", "course_code", "course_name_ko", "course_name_en",
                   "credits", "theory_hours", "lab_hours", "credit_raw",
                   "is_required", "grading", "note", "source_url", "crawled_at"],
    "curriculum_pdf": ["major_code", "major_name", "pdf_year", "course_code",
                       "course_name_ko", "course_name_en", "credits", "theory_hours",
                       "lab_hours", "credit_raw", "pdf_url", "crawled_at"],
    "curriculum_files": ["major_code", "major_name", "year", "title", "url",
                         "source_url", "crawled_at"],
}


# ───────────────────────── 공통 유틸 ─────────────────────────
def clean(s):
    return re.sub(r"[ \t\u00a0]+", " ", s or "").strip()


def norm(s):
    return re.sub(r"\s+", "", s or "")


def log(msg):
    print(msg, file=sys.stderr)


def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; KNU-CSE-crawler/1.0; academic use)"})
    return s


def fetch(session, url, delay, retries=3):
    """성공 시 bytes, 404/실패 시 None."""
    for i in range(retries):
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            time.sleep(delay)
            return r.content
        except requests.RequestException as e:
            log(f"  [재시도 {i + 1}/{retries}] {url}: {e}")
            time.sleep(2 ** i)
    return None


def soup_of(html):
    return BeautifulSoup(html, "html.parser")


# ───────────────────────── 전공 자동 탐색 ─────────────────────────
def split_major_name(raw):
    """'플랫폼SW데이터과학전공(~2025학년)' → ('플랫폼SW데이터과학전공', '~2025학년', 2025)"""
    m = re.match(r"^(.*?)\s*[\(（]\s*(.*?)\s*[\)）]\s*$", raw)
    name, note = (clean(m.group(1)), clean(m.group(2))) if m else (clean(raw), "")
    u = re.search(r"~\s*(\d{4})", note)
    return name, note, int(u.group(1)) if u else ""


def discover_majors(session, delay, probe_extra):
    html = fetch(session, urljoin(BASE, SEED), delay)
    if not html:
        sys.exit("시작 페이지를 가져오지 못했습니다. 네트워크/URL을 확인하세요.")
    soup = soup_of(html)

    found = {}
    for a in soup.find_all("a", href=True):
        m = re.search(r"sub3_(\d+)_([ab])\.php", a["href"])
        if not m:
            continue
        n, kind = int(m.group(1)), m.group(2)
        text = clean(a.get_text(" "))
        d = found.setdefault(n, {"a": None, "b": None, "names": [], "b_texts": []})
        url = urljoin(BASE, a["href"])
        if kind == "a":
            d["a"] = d["a"] or url
            if text not in GENERIC_LINK_TEXTS:
                d["names"].append(text)
        else:
            d["b"] = d["b"] or url
            d["b_texts"].append(text)

    majors = []
    for n in sorted(found):
        d = found[n]
        # '교육과정' 하위 메뉴가 있는 항목만 전공으로 간주 (sub3_1 '컴퓨터학부 소개' 제외)
        if not (d["names"] and any("교육과정" in t for t in d["b_texts"])):
            continue
        name, note, until = split_major_name(d["names"][0])
        majors.append({"major_code": f"sub3_{n}", "major_name": name,
                       "status_note": note, "valid_until": until,
                       "intro_url": d["a"], "curriculum_url": d["b"] or urljoin(BASE, f"sub3_{n}_b.php")})

    # 안전망: 메뉴에 아직 안 보이는 다음 번호 페이지가 있는지 몇 개 더 탐색
    last = max(found) if found else 1
    for n in range(last + 1, last + 1 + probe_extra):
        url = urljoin(BASE, f"sub3_{n}_a.php")
        html = fetch(session, url, delay, retries=1)
        if html and f"sub3_{n}_b.php" in html.decode("utf-8", "ignore"):
            h5 = soup_of(html).find("h5")
            name, note, until = split_major_name(clean(h5.get_text(" ")) if h5 else f"sub3_{n}")
            majors.append({"major_code": f"sub3_{n}", "major_name": name, "status_note": note,
                           "valid_until": until, "intro_url": url,
                           "curriculum_url": urljoin(BASE, f"sub3_{n}_b.php")})
            log(f"  메뉴에 없던 전공 페이지 발견: {url} ({name})")
    return majors


# ───────────────────────── 표 파싱 ─────────────────────────
def cell_text(cell):
    if cell is None:
        return ""
    for br in cell.find_all("br"):
        br.replace_with("\n")
    lines = [clean(l) for l in cell.get_text("").splitlines()]
    return "\n".join(l for l in lines if l)


def expand_table(table):
    """rowspan/colspan을 펼친 2차원 셀(Tag) 격자. 빈 칸은 None."""
    spans = {}  # col -> (남은 행 수, cell)
    grid = []
    for tr in table.find_all(["tr", "thead", "tbody", "tfoot"]):
        if tr.find_parent("table") is not table:
            continue
        cells = tr.find_all(["td", "th"], recursive=False)
        if not cells:          # <tr>를 담은 thead/tbody 등은 건너뜀 (<tr> 없이 셀이 바로 있는 경우만 행으로 취급)
            continue
        row, col, idx = [], 0, 0
        while idx < len(cells) or any(k >= col for k in spans):
            if col in spans:
                rem, cell = spans[col]
                row.append(cell)
                if rem - 1 > 0:
                    spans[col] = (rem - 1, cell)
                else:
                    del spans[col]
                col += 1
            elif idx < len(cells):
                cell = cells[idx]
                idx += 1
                cs = max(int(re.sub(r"\D", "", cell.get("colspan", "1")) or 1), 1)
                rs = max(int(re.sub(r"\D", "", cell.get("rowspan", "1")) or 1), 1)
                for j in range(cs):
                    row.append(cell)
                    if rs > 1:
                        spans[col + j] = (rs - 1, cell)
                col += cs
            else:
                row.append(None)
                col += 1
        if row:
            grid.append(row)
    return grid


def year_near(table, heading_text):
    m = re.search(r"(\d{4})\s*학년", heading_text)
    if m:
        return int(m.group(1))
    s = table.find_previous(string=re.compile(r"\d{4}\s*학년도"))
    if s:
        return int(re.search(r"(\d{4})", s).group(1))
    return ""


# ── 졸업요건 ──
REF_RE = re.compile(r"(?<=[가-힣A-Za-z])(\d{1,2})\)")


def strip_refs(text):
    refs = REF_RE.findall(text)
    return clean(REF_RE.sub(" ", text)), refs


def parse_footnotes(table):
    """표 뒤 ~ 다음 제목/표 전까지의 각주(ol/li 또는 '1. 내용' 형태 문단)."""
    notes, n = {}, 0
    for el in table.find_all_next():
        if el.name in HEADINGS or el.name == "table":
            break
        if el.name == "li":
            n += 1
            notes[n] = cell_text(el).replace("\n", " ")
        elif el.name == "p" and not el.find_parent("li"):
            m = re.match(r"^\s*(\d{1,2})[.)]\s*(.+)", cell_text(el))
            if m:
                notes[int(m.group(1))] = clean(m.group(2))
    return notes


def parse_graduation(table, grid, ctx):
    """
    열이 [구분 | 졸업요건] 2개뿐이면 항목당 1행.
    [구분 | 입학년도A | 입학년도B ...]처럼 값 열이 여러 개면, 값 열마다 1행씩 만들고
    헤더 문구를 condition 열에 넣는다. '구분'이 가로로 병합된(2단) 표는 key 열을 합쳐 item으로 쓴다.
    """
    texts = [[cell_text(c) for c in r] for r in grid]

    def is_th_row(r):
        return all(c is not None and c.name == "th" for c in grid[r])

    hdr_rows = []
    for i, r in enumerate(texts):
        if r and (norm(r[0]) in ("구분", "항목") or is_th_row(i)):
            hdr_rows.append(i)
        else:
            break
    if not hdr_rows:
        hdr_rows = [0] if texts and texts[0] and norm(texts[0][0]) in ("구분", "항목") else []
    start = (hdr_rows[-1] + 1) if hdr_rows else 0
    ncol = max(len(r) for r in texts)

    # '구분' 헤더 셀이 차지하는 열 수 = key 열 수
    key_n = 1
    for i in hdr_rows:
        if norm(texts[i][0]) in ("구분", "항목"):
            while key_n < len(grid[i]) and grid[i][key_n] is grid[i][0]:
                key_n += 1
            break

    # 값 열별 헤더 라벨 ('졸업요건' 같은 일반 라벨은 제외)
    labels = []
    for j in range(ncol):
        parts = []
        for i in hdr_rows:
            if j < len(texts[i]) and j >= key_n and texts[i][j] and norm(texts[i][j]) not in ("졸업요건", "요건", "기준"):
                if texts[i][j] not in parts:
                    parts.append(texts[i][j])
        labels.append(" ".join(parts))

    notes = parse_footnotes(table)
    out = []
    for i in range(start, len(grid)):
        r, cells = texts[i], grid[i]
        if not any(r):
            continue
        key = list(dict.fromkeys(x for x in r[:key_n] if x))
        item = " / ".join(key)
        vals, seen = [], set()
        for j in range(key_n, len(r)):
            if not r[j] or id(cells[j]) in seen or r[j] in key:
                continue
            seen.add(id(cells[j]))
            span = [jj for jj in range(key_n, len(r)) if cells[jj] is cells[j]]
            cond = " / ".join(dict.fromkeys(labels[jj] for jj in span if labels[jj]))
            vals.append((cond, r[j]))
        if not vals:        # 가로 병합 행 (예: '졸업자격인정제 충족')
            vals = [("", "")]
        for cond, v in vals:
            it, r1 = strip_refs(item)
            rq, r2 = strip_refs(v)
            refs = sorted({int(x) for x in r1 + r2})
            out.append({**ctx, "item": it, "condition": cond,
                        "requirement": rq.replace("\n", " "),
                        "footnote_refs": ";".join(map(str, refs)),
                        "footnotes": " | ".join(f"{k}) {notes[k]}" for k in refs if k in notes)})
    return out


# ── 졸업학점 분해 ──
CREDIT_ITEMS = {"졸업학점", "총이수학점", "이수학점", "학점구성"}
TOTAL_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*학점\s*(이상)?")
COMP_RE = re.compile(r"([가-힣][가-힣 ]*?)\s*(\d+(?:\.\d+)?)\s*학점\s*(이상)?")
SINGLE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*학점\s*(이상)?\s*(?:[※(\[].*)?$")


def _credit_text(num, q):
    return f"{num}학점" + (" 이상" if q else "")


def normalize_credit_rows(rows):
    """
    '졸업학점 | 130학점(전공 72학점, 교양 30학점, 그 외 28학점)' 같은 행을
      졸업학점 | 130학점 / 전공 | 72학점 / 교양 | 30학점 / 그 외 | 28학점
    으로 분해하고, 숫자만 credits 열에 따로 넣는다(credits_qualifier: '이상').
    '총 이수학점'은 '졸업학점'으로 통일. 그 외 행도 값이 'N학점[ 이상]'뿐이면 credits를 채운다.
    """
    out = []
    for r in rows:
        req = r.get("requirement", "")
        if norm(r["item"]) in CREDIT_ITEMS and req:
            m = TOTAL_RE.match(req)
            rest = req[m.end():] if m else req
            comps = COMP_RE.findall(rest)
            if not m and not comps:
                out.append(r)
                continue
            if m:
                out.append({**r, "item": "졸업학점", "requirement": _credit_text(m.group(1), m.group(2)),
                            "credits": m.group(1), "credits_qualifier": m.group(2) or ""})
            for label, num, q in comps:
                label = "그 외" if norm(label) == "그외" else clean(label)
                out.append({**r, "item": label, "requirement": _credit_text(num, q),
                            "credits": num, "credits_qualifier": q or "",
                            "footnote_refs": "", "footnotes": ""})
            continue
        m = SINGLE_RE.match(req)
        if m:
            r = {**r, "credits": m.group(1), "credits_qualifier": m.group(2) or ""}
        out.append(r)
    return out


# ── 교육과정 ──
CREDIT_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)")
GRADING_RE = re.compile(r"\b(S/U|P/NP|Pass/Fail)\s*평가?", re.I)


REQ_END = re.compile(r"\s*(?:전공필수|필수|Required)$", re.I)
REQ_MID = re.compile(r"\s(?:전공필수|필수|Required)\s", re.I)


def parse_course_cell(raw, bold):
    required, grading, notes = bold, "", []
    m = GRADING_RE.search(raw)
    if m:
        grading = m.group(1).upper()
        raw = GRADING_RE.sub("", raw)
    m = re.search(r"K[UN]{2}\s*미래설계", raw)
    if m:
        notes.append("KNU미래설계")
        raw = raw.replace(m.group(0), " ")
    lines = []
    for line in raw.splitlines():
        line = clean(line)
        if REQ_END.search(line):
            required, line = True, clean(REQ_END.sub("", line))
        elif REQ_MID.search(line):
            required, line = True, clean(REQ_MID.sub(" ", line))
        if line:
            lines.append(line)
    en, ko_lines = "", []
    for line in lines:
        if line.startswith("(") and line.endswith(")") and not en:
            en = line[1:-1].strip()
        else:
            ko_lines.append(line)
    ko = " ".join(ko_lines)
    if not en:   # '이름 (English) 설계', '수학Ⅰ(CalculusⅠ)', '이름(English)' 한 줄 형태
        m = re.match(r"^(.*?)\s*\(([^()가-힣]*[A-Za-z][^()가-힣]*)\)\s*([^()]{0,12})$", ko)
        if m and m.group(1):
            ko, en = clean(m.group(1)), clean(m.group(2))
            for t in re.split(r"[\s,/·]+", m.group(3)):
                if not t:
                    continue
                if re.fullmatch(r"전공필수|필수|Required", t, re.I):
                    required = True
                else:
                    notes.append(f"tag:{t}")           # 설계, 창업 등
    if not en:   # '대학글쓰기 첨성인기초(글쓰기) 인문교양' 처럼 교양 영역 라벨이 붙은 경우
        m = re.match(r"^(.*?)\s+(첨성인[가-힣]+\([^)]*\))(?:\s+(\S+))?$", ko)
        if m:
            ko = clean(m.group(1))
            notes.append(f"area:{m.group(2)}")
            if m.group(3):
                notes.append(f"tag:{m.group(3)}")
    return ko, en, required, grading, notes


def parse_curriculum(grid, ctx):
    texts = [[cell_text(c) for c in r] for r in grid]
    hdr = next((i for i, r in enumerate(texts) if any(has_any(t, CODE_HDR) for t in r)), None)
    if hdr is None:
        return []
    hrow = texts[hdr]
    # 학기 블록(코드/이름/학점 열 묶음) 찾기 — colspan으로 중복된 헤더는 제외
    code_cols = [j for j, t in enumerate(hrow)
                 if has_any(t, CODE_HDR) and (j == 0 or grid[hdr][j] is not grid[hdr][j - 1])]
    blocks = []
    for k, s in enumerate(code_cols):
        e = code_cols[k + 1] if k + 1 < len(code_cols) else len(hrow)
        name_c = next((j for j in range(s + 1, e) if has_any(hrow[j], NAME_HDR)), s + 1)
        cred_c = next((j for j in range(s + 1, e) if has_any(hrow[j], CRED_HDR)), s + 2)
        sem = ""
        for r in range(hdr - 1, -1, -1):      # 헤더 위쪽 줄에서 '1학기/2학기' 라벨 탐색
            for j in range(s, min(e, len(texts[r]))):
                m = re.search(r"(\d)\s*학기", texts[r][j])
                if m:
                    sem = f"{m.group(1)}학기"
                    break
            if sem:
                break
        blocks.append((s, name_c, cred_c, sem or f"{k + 1}학기"))

    head_cells = [norm(t) for r in texts[: hdr + 1] for t in r[: code_cols[0]]]
    lead = code_cols[0]
    grade_c = next((j for j in range(lead) if any("학년" in norm(texts[r][j]) for r in range(hdr + 1))), 0)
    cat_c = next((j for j in range(lead) if any("구분" in norm(texts[r][j]) for r in range(hdr + 1))),
                 1 if lead > 1 else None)
    del head_cells
    # '구분' 열이 없는 표(예: 'AI입문' 같은 트랙별 표)는 좌상단 제목을 구분으로 사용
    label = texts[0][0] if hdr > 0 and texts[0] else ""
    table_label = "" if (cat_c is not None or "학년" in norm(label) or "구분" in norm(label)) else label

    out, cur_grade, cur_cat = [], "", ""
    for r in range(hdr + 1, len(grid)):
        row, cells = texts[r], grid[r]
        g = row[grade_c] if grade_c < len(row) else ""
        if norm(g) in ("-", "–", "—"):
            g = ""
        c = row[cat_c] if cat_c is not None and cat_c < len(row) else ""
        if g and g != cur_grade:
            cur_grade, cur_cat = g, ""
        if c and norm(c) not in ("-", "–"):
            cur_cat = c
        for (s, nc, cc, sem) in blocks:
            if max(s, nc, cc) >= len(row):
                continue
            code, name_raw, credit_raw = row[s], row[nc], row[cc]
            if norm(code) in ("", "-") and norm(name_raw) in ("", "-"):
                continue
            bold = bool(cells[nc] is not None and cells[nc].find(["b", "strong"]))
            ko, en, required, grading, notes = parse_course_cell(name_raw, bold)
            code = code.replace(" ", "")
            if code and not CODE_RE.match(code):      # '신규', 'ITEC' 같은 비정상 코드는 note로 이동
                notes.append(f"code:{code}")
                code = ""
            cm = CREDIT_RE.match(credit_raw)
            out.append({**ctx,
                        "grade": re.sub(r"\D", "", cur_grade) or cur_grade,
                        "category": cur_cat or table_label, "semester": sem,
                        "course_code": code,
                        "course_name_ko": ko, "course_name_en": en,
                        "credits": cm.group(1) if cm else "",
                        "theory_hours": cm.group(2) if cm else "",
                        "lab_hours": cm.group(3) if cm else "",
                        "credit_raw": credit_raw,
                        "is_required": "Y" if required else "N",
                        "grading": grading, "note": ";".join(notes)})
    return out


# ── 첨부파일
def is_file_link(a):
    href = a.get("href", "")
    if not href or href.startswith(("#", "javascript:", "mailto:")) or href.split("?")[0].endswith("/"):
        return False
    return bool(FILE_RE.search(href)) or "download" in href.lower()


def parse_files(table, ctx, page_url):
    out = []
    for a in table.find_all("a", href=True):
        if not is_file_link(a):
            continue
        url = urljoin(page_url, a["href"])
        year = ""
        cell = a.find_parent(["td", "th"])
        for sib in (cell.find_previous_siblings(["th", "td"]) if cell else []):   # 같은 행의 앞쪽 셀에서 연도
            m = re.search(r"20\d{2}(?:\s*[~\-]\s*20\d{2})?", clean(sib.get_text(" ")))   # '2026', '2020~2021'
            if m:
                year = re.sub(r"\s+", "", m.group(0))
                break
        if not year:
            m = re.search(r"(20\d{2})", url)
            year = m.group(1) if m else ""
        out.append({**ctx, "year": year, "title": clean(a.get_text(" ")), "url": url})
    return out


# ── 페이지 단위 ──
def parse_tables(soup, major, page_url, crawled_at):
    base = {"major_code": major["major_code"], "major_name": major["major_name"],
            "source_url": page_url, "crawled_at": crawled_at}
    grad, curr, files = [], [], []
    for table in soup.find_all("table"):
        if table.find_parent("table"):
            continue
        grid = expand_table(table)
        if not grid:
            continue
        head = norm(" ".join(cell_text(c) for r in grid[:3] for c in r))
        heading = table.find_previous(HEADINGS)
        h_txt = clean(heading.get_text(" ")) if heading else ""
        year = year_near(table, h_txt)
        if has_any(head, CODE_HDR):
            curr += parse_curriculum(grid, {**base, "basis_year": year})
        elif "졸업요건" in head or "졸업요건" in norm(h_txt):
            grad += parse_graduation(table, grid, {**base, "basis_year": year})
        elif any(is_file_link(a) for a in table.find_all("a", href=True)) or has_any(head, ("파일", "file")):
            got = parse_files(table, base, page_url)
            files += got
            if not got:
                hrefs = [a["href"] for a in table.find_all("a", href=True)][:5]
                log(f"    ⚠ 파일 표인데 링크를 못 찾음: {hrefs}")
        else:
            log(f"    (분류하지 못한 표 건너뜀: {head[:70]})")
    return grad, curr, files


# ───────────────────────── PDF (보조 수단) ─────────────────────────
# PDF는 리플릿 형태라 텍스트만 뽑으면 학기/학년/전공필수 표시가 분리되어 사라진다.
# 그래서 '과목코드·과목명·학점' 목록 + 연도별 과거 자료 확보용으로만 쓴다.
PDF_COURSE_RE = re.compile(
    r"([A-Z]{3,5}\d{3,5})\s+((?:(?![A-Z]{3,5}\d{3,5}\b).)+?)\s+(\d{1,2}-\d{1,2}-\d{1,2})(?!\d)")


def pdf_text(content):
    import io
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    except ImportError:
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(content)).pages)


def parse_pdf_courses(text, ctx):
    flat = re.sub(r"\s+", " ", text)
    year = re.search(r"(\d{4})\s*학년도\s*기준", flat)
    out, seen = [], set()
    for code, name, credit in PDF_COURSE_RE.findall(flat):
        if (code, credit) in seen:
            continue
        seen.add((code, credit))
        ko, en, _, _, _ = parse_course_cell(name, False)
        cm = CREDIT_RE.match(credit)
        out.append({**ctx, "pdf_year": ctx.get("pdf_year") or (year.group(1) if year else ""),
                    "course_code": code, "course_name_ko": ko, "course_name_en": en,
                    "credits": cm.group(1), "theory_hours": cm.group(2),
                    "lab_hours": cm.group(3), "credit_raw": credit})
    return out


# ───────────────────────── 실행 ─────────────────────────
def write_csv(path, key, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS[key], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--delay", type=float, default=0.7, help="요청 간 대기(초)")
    ap.add_argument("--probe-extra", type=int, default=3, help="메뉴에 없는 다음 번호 전공 페이지 탐색 개수")
    ap.add_argument("--pdf", choices=["off", "fallback", "all"], default="fallback",
                    help="교육과정 PDF 추출: off=안 함, fallback=HTML 표 파싱 실패 전공만, all=모든 PDF")
    ap.add_argument("--save-raw", action="store_true", help="원본 HTML을 out/raw 에 저장(디버깅용)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.save_raw:
        (out / "raw").mkdir(exist_ok=True)

    session = make_session()
    now = datetime.now().isoformat(timespec="seconds")

    majors = discover_majors(session, args.delay, args.probe_extra)
    log(f"발견한 전공 {len(majors)}개: " + ", ".join(f"{m['major_name']}({m['major_code']})" for m in majors))

    all_grad, all_curr, all_files, all_pdf = [], [], [], []
    for m in majors:
        log(f"\n▶ {m['major_name']}")
        for url in (m["intro_url"], m["curriculum_url"]):
            html = fetch(session, url, args.delay)
            if html is None:
                log(f"  ! 가져오기 실패: {url}")
                continue
            if args.save_raw:
                (out / "raw" / f"{Path(url).stem}.html").write_bytes(html)
            g, c, f = parse_tables(soup_of(html), m, url, now)
            all_grad += g
            all_curr += c
            all_files += f
            log(f"  {Path(url).name}: 졸업요건 {len(g)}행 / 교육과정 {len(c)}과목 / 파일 {len(f)}개")
        n_g = sum(1 for r in all_grad if r["major_code"] == m["major_code"])
        n_c = sum(1 for r in all_curr if r["major_code"] == m["major_code"])
        # PDF 보조 추출
        need_pdf = args.pdf == "all" or (args.pdf == "fallback" and not n_c)
        if need_pdf:
            pdfs = [f for f in all_files if f["major_code"] == m["major_code"]
                    and f["url"].lower().split("?")[0].endswith(".pdf")]
            if not pdfs:
                log("  (받을 PDF 링크가 없습니다)")
            for f in pdfs:
                log(f"  PDF 처리: {f['url']}")
                data = fetch(session, f["url"], args.delay)
                if not data:
                    continue
                if args.save_raw:
                    (out / "raw" / Path(f["url"]).name).write_bytes(data)
                try:
                    rows = parse_pdf_courses(pdf_text(data), {
                        "major_code": m["major_code"], "major_name": m["major_name"],
                        "pdf_year": f["year"], "pdf_url": f["url"], "crawled_at": now})
                except Exception as e:   # noqa
                    log(f"  ! PDF 해석 실패: {e}")
                    continue
                all_pdf += rows
                log(f"    → {len(rows)}과목")
        if not n_g:
            log("  ⚠ 졸업요건 표를 찾지 못했습니다 (--save-raw 로 HTML 확인)")
        if not n_c:
            log("  ⚠ 교육과정 표를 찾지 못했습니다 (--save-raw 로 HTML 확인)")

    all_grad = normalize_credit_rows(all_grad)
    write_csv(out / "majors.csv", "majors", majors)
    write_csv(out / "graduation_requirements.csv", "graduation_requirements", all_grad)
    write_csv(out / "curriculum.csv", "curriculum", all_curr)
    write_csv(out / "curriculum_files.csv", "curriculum_files", all_files)
    if args.pdf != "off":
        write_csv(out / "curriculum_pdf.csv", "curriculum_pdf", all_pdf)
    log(f"\n완료 → {out.resolve()}  (졸업요건 {len(all_grad)}행, 과목 {len(all_curr)}행)")


if __name__ == "__main__":
    main()