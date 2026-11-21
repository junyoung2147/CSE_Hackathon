"""터미널에서 LLM 기능을 직접 써 보는 테스트 스크립트. data/ 에서 실행.

  python -m llm.cli chat                                   # 일반 상담 (대화형)
  python -m llm.cli prereq --subject MOBI0224 --unmet COMP0319,COME0311
  python -m llm.cli roadmap "AI 쪽으로 로드맵 짜 줘" --targets ITEC0424

공통 옵션: --major, --completed (쉼표 구분 과목 코드). 기본값은 demo.py의 가짜 학생.
대화형 모드는 빈 줄 또는 q 를 입력하면 끝난다.
"""
import argparse

from . import api, client
from .demo import COMPLETED, MAJOR, show


def codes(s):
    """'A,B, C' → ['A', 'B', 'C']"""
    return [c.strip() for c in s.split(",") if c.strip()]


def ask(prompt):
    """한 줄 입력. 빈 줄·q·EOF면 None."""
    try:
        line = input(prompt).strip()
    except EOFError:
        return None
    return None if line in ("", "q") else line


def run_chat(args):
    """일반 상담을 대화형으로 돌린다. 로드맵 버튼 신호가 오면 바로 plan_roadmap까지 이어서 실행한다."""
    conv, targets = [], list(args.targets)
    while (text := ask("\n나> ")) is not None:
        conv.append({"role": "user", "text": text})
        out = api.chat("general", conv, args.completed, major=args.major, targets=targets)
        show("상담", out)
        conv.append({"role": "assistant", "text": out["reply"]})
        if out["suggest_action"] == "plan_roadmap" and ask("\n[로드맵 짜기 버튼] 누를까요? (y/엔터=건너뜀) ") == "y":
            plan = api.plan_roadmap(conv, args.major, targets, args.completed)
            show("로드맵 미리보기", plan)
            targets = [c for c in targets if c not in plan["remove"]] + plan["add"]
            print(f"[적용 후 목표] {targets}")


def run_prereq(args):
    """선수과목 상담: 첫 판단을 보여 주고 이어서 대화한다."""
    conv = []
    out = api.chat("prereq", conv, args.completed, subject=args.subject, unmet=args.unmet)
    show("첫 판단", out)
    # 첫 판단 요청도 대화에 넣어야 후속 질문 때 맥락이 이어진다 (demo.py와 같은 형식)
    conv += [{"role": "user", "text": api.FIRST_PREREQ_MSG}, {"role": "assistant", "text": out["reply"]}]
    while (text := ask("\n나> ")) is not None:
        conv.append({"role": "user", "text": text})
        out = api.chat("prereq", conv, args.completed, subject=args.subject, unmet=args.unmet)
        show("선수과목 상담", out)
        conv.append({"role": "assistant", "text": out["reply"]})


def run_roadmap(args):
    """메시지 하나로 plan_roadmap을 한 번 호출한다."""
    show("로드맵", api.plan_roadmap([{"role": "user", "text": args.message}],
                                  args.major, args.targets, args.completed))


def main():
    """명령줄 인자를 읽어 해당 기능을 실행한다."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--major", default=MAJOR)
    common.add_argument("--completed", type=codes, default=COMPLETED, help="이수 과목 코드, 쉼표 구분")
    common.add_argument("--targets", type=codes, default=[], help="현재 목표 과목 코드, 쉼표 구분")

    parser = argparse.ArgumentParser(description="LLM 상담·로드맵 CLI 테스트")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("chat", parents=[common], help="일반 상담 (대화형)").set_defaults(fn=run_chat)
    p = sub.add_parser("prereq", parents=[common], help="선수과목 상담 (대화형)")
    p.add_argument("--subject", required=True, help="대상 과목 코드")
    p.add_argument("--unmet", type=codes, required=True, help="안 들은 선수과목 코드, 쉼표 구분")
    p.set_defaults(fn=run_prereq)
    p = sub.add_parser("roadmap", parents=[common], help="로드맵 짜기 (한 번 호출)")
    p.add_argument("message", help="학생 요청 문장")
    p.set_defaults(fn=run_roadmap)

    args = parser.parse_args()
    try:
        args.fn(args)
    except (ValueError, client.LLMError) as e:
        print(f"[오류] {e}")


if __name__ == "__main__":
    main()
