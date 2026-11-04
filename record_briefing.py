"""Run the morning briefing from the command line and record every Claude response to cache/.

Usage:  py record_briefing.py          (needs ANTHROPIC_API_KEY in .env)
        py record_briefing.py --offline   (replay from cache only)
"""
import sys

from dotenv import load_dotenv

load_dotenv()

from qr import agent, store  # noqa: E402
from qr.tools import Ctx  # noqa: E402


def main() -> None:
    state = store.load_all()
    ctx = Ctx(state, offline="--offline" in sys.argv)
    out = agent.run_briefing(
        ctx, on_step=lambda s: print(f"[{s['turn']}] {s['tool']} -> {s['result']}"))
    print("\n" + out["summary"])
    print(f"\nUsage: {out['usage']}  queued: {len(state['outbox'])}")


if __name__ == "__main__":
    main()
