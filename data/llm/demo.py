"""데모 시나리오 실호출 (돌릴 때마다 약 10회 호출). 실행: python -m llm.demo (data/ 에서)"""
from . import api
from . import context as ctx

MAJOR = "심화컴퓨팅전공"
# 가짜 학생: 2학년까지 들었다고 가정 (실존 인물 아님)
COMPLETED = ["COMP0206", "COMP0207", "COME0301", "COME0331", "CLTR0819", "COMP0218"]


def show(title, out):
    """결과를 사람이 읽기 좋게 출력한다."""
    print(f"\n===== {title} =====")
    if "reply" in out:
        print(out["reply"])
        print(f"[suggest_action] {out['suggest_action']}")
    else:
        for c in out["add"]:
            mark = " [교육과정 밖]" if c in out["outside_curriculum"] else ""
            print(f"+ {c} {ctx.name(c)}{mark}: {out['reasons'].get(c, '')}")
        for c in out["remove"]:
            print(f"- {c} {ctx.name(c)}: {out['reasons'].get(c, '')}")
        print(f"[dropped] {out['dropped']}")


def main():
    """상담 2, 선수과목 3, 로드맵 2 시나리오를 돌린다."""
    ai = [{"role": "user", "text": "AI 엔지니어 쪽으로 가고 싶어. 3학년부터 뭘 들으면 좋을지 로드맵 짜 줘."}]
    out = api.chat("general", ai, COMPLETED, major=MAJOR)
    show("상담1: AI 진로 + 로드맵 요청", out)
    ai.append({"role": "assistant", "text": out["reply"]})

    show("상담2: 졸업요건", api.chat("general", [{"role": "user", "text": "졸업하려면 전공 몇 학점 들어야 해? 필수 과목도 알려줘."}],
                                    COMPLETED, major=MAJOR))

    dl = ("MOBI0224", ["COMP0319", "COME0311", "COMP0324"])
    first = api.chat("prereq", [], COMPLETED, subject=dl[0], unmet=dl[1])
    show("선수1: 딥러닝 첫 판단", first)
    show("선수2: 컴퓨터그래픽스 첫 판단", api.chat("prereq", [], COMPLETED, subject="COMP0413", unmet=["COMP0312", "COMP0319"]))
    follow = [{"role": "user", "text": api.FIRST_PREREQ_MSG}, {"role": "assistant", "text": first["reply"]},
              {"role": "user", "text": "확률통계는 고등학교 때 잘했고, 파이썬으로 머신러닝을 독학해 봤어요. 그래도 들어야 하나요?"}]
    show("선수3: 딥러닝 후속 질문", api.chat("prereq", follow, COMPLETED, subject=dl[0], unmet=dl[1]))

    plan = api.plan_roadmap(ai, MAJOR, [], COMPLETED)
    show("로드맵1: 새로 짜기", plan)
    revise = ai + [{"role": "user", "text": "컴퓨터비전은 빼고 자연어처리 쪽 과목을 더 넣어 줘."}]
    show("로드맵2: 수정", api.plan_roadmap(revise, MAJOR, plan["add"], COMPLETED))


if __name__ == "__main__":
    main()
