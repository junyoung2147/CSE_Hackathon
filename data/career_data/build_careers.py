"""frontend/src/careers.ts의 진로 프리셋을 careers.csv, career_subjects.csv로 옮기고 검증한다."""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TS = ROOT / "frontend/src/careers.ts"
SUBJECTS = ROOT / "data/lecture_data/lecture_data_csv/subjects.csv"
OUT = Path(__file__).resolve().parent

# careers.ts의 객체 리터럴 하나: id, name, description, targets 순서
PATTERN = re.compile(
    r"id:\s*'([^']+)',\s*name:\s*'([^']+)',\s*description:\s*'([^']+)',\s*targets:\s*\[([^\]]*)\]"
)


def parse_ts(text):
    """ts 원문에서 (id, name, description, [코드...]) 목록을 뽑는다."""
    return [
        (cid, name, desc, re.findall(r"'([^']+)'", targets))
        for cid, name, desc, targets in PATTERN.findall(text)
    ]


def main():
    """CSV 두 개를 쓰고, 개수와 과목 코드 존재 여부를 assert로 확인한다."""
    text = TS.read_text(encoding="utf-8")
    careers = parse_ts(text)
    # 파싱 누락 방지: ts에 있는 id 개수와 같아야 함
    assert len(careers) == len(re.findall(r"\bid:\s*'", text)), "careers.ts 파싱 누락"

    with open(SUBJECTS, encoding="utf-8-sig") as f:
        known = {r["subject_code"] for r in csv.DictReader(f)}

    rows = [(cid, code) for cid, _, _, codes in careers for code in codes]
    missing = [r for r in rows if r[1] not in known]
    assert not missing, f"subjects.csv에 없는 코드: {missing}"

    with open(OUT / "careers.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["career_id", "name", "description", "source"])
        w.writerows((cid, name, desc, "careers.ts") for cid, name, desc, _ in careers)

    with open(OUT / "career_subjects.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["career_id", "subject_code", "source"])
        w.writerows((cid, code, "careers.ts") for cid, code in rows)

    print(f"careers {len(careers)}건, career_subjects {len(rows)}건")


if __name__ == "__main__":
    main()
