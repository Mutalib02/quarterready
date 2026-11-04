"""Dev tool: record Claude's answers to the agent's requests, written by Claude via Claude Code.

There is no API credit, so instead of calling the API, each request the app would send is dumped
to a pending file; Claude (running in Claude Code) reads it, writes the response it would give,
and `apply` stores it in recorded/ in the same hash-keyed format as cache/. The app then replays
it with the "Recorded by Claude (via Claude Code)" engine.

    py scripts/claude_code_recorder.py run   <pending_dir>   # run until a request needs an answer
    py scripts/claude_code_recorder.py apply <answers.json>  # store {key: response} in recorded/

Requests that can be answered in the same layer (e.g. 12 independent assess_lead calls) are
collected together; the run stops at the next main-agent turn.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qr import agent, cache, store  # noqa: E402
from qr.local_model import local_api  # noqa: E402
from qr.tools import Ctx  # noqa: E402

BY = "Claude (claude-sonnet-5-5) via Claude Code, 2026-11-04"


class NeedAnswer(Exception):
    pass


def run(pending_dir: Path) -> None:
    pending_dir.mkdir(parents=True, exist_ok=True)
    pending: list[dict] = []
    ctx = Ctx(store.load_all())

    def complete(system, messages, tools, max_tokens=1500, tool_choice=None):
        payload = {"system": system, "messages": messages, "tools": tools,
                   "max_tokens": max_tokens}
        if tool_choice:
            payload["tool_choice"] = tool_choice
        key = cache.make_key(agent.MODEL, payload)
        hit = cache.get(key, cache.RECORDED_DIR)
        if hit is not None:
            return hit
        main = bool(tools) and len(tools) > 1
        if main and pending:  # depends on unanswered inner calls: stop at the layer boundary
            raise NeedAnswer
        last = messages[-1]["content"]
        text = last if isinstance(last, str) else json.dumps(last, ensure_ascii=False, indent=1)
        pending.append({"key": key, "kind": "main" if main else
                        ("categorise" if tool_choice else "inner"), "system": system,
                        "request": text})
        if main:
            raise NeedAnswer
        return local_api(agent.MODEL, system, messages, tools, max_tokens, tool_choice)  # dummy

    try:
        agent.run_briefing(ctx, complete=complete)
    except NeedAnswer:
        pass
    if not pending:
        print("COMPLETE: every request is answered. Briefing replays from recorded/.")
        return
    lines, seen = [], set()
    for p in pending:
        lines.append(f"\n===== KEY {p['key']}  KIND {p['kind']} =====")
        if p["system"] not in seen:
            seen.add(p["system"])
            lines.append("--- SYSTEM ---\n" + p["system"])
        lines.append("--- REQUEST ---\n" + p["request"])
    (pending_dir / "pending.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(pending)} requests pending -> {pending_dir / 'pending.md'}")
    print("keys:", " ".join(p["key"] for p in pending))


def apply(answers_path: Path) -> None:
    answers = json.loads(answers_path.read_text(encoding="utf-8"))
    cache.RECORDED_DIR.mkdir(exist_ok=True)
    for key, resp in answers.items():
        resp = {**resp, "recorded_by": BY}
        resp.setdefault("usage", {"input_tokens": 0, "output_tokens": 0})
        (cache.RECORDED_DIR / f"{key}.json").write_text(
            json.dumps(resp, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"stored {len(answers)} responses in {cache.RECORDED_DIR}")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(Path(sys.argv[2]))
    else:
        apply(Path(sys.argv[2]))
