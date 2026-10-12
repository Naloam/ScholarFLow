#!/usr/bin/env python3
"""P4.4 — idea pool CLI (journal production line intake).

    cd backend && ../.venv/bin/python ../scripts/idea_pool.py add "想法..." [--domain tabular]
                                    idea_pool.py list [--status queued]
                                    idea_pool.py next
                                    idea_pool.py status <idea_id> done
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from services.research_harness import idea_pool  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="add an idea (dedup + offline novelty pre-check)")
    p_add.add_argument("idea")
    p_add.add_argument("--domain", default=None, help="optional domain tag (claim/tabular/structured/code)")

    p_list = sub.add_parser("list", help="list pool entries")
    p_list.add_argument("--status", default=None, choices=list(idea_pool.STATUSES))

    sub.add_parser("next", help="print the oldest queued idea (FIFO)")

    p_status = sub.add_parser("status", help="set an idea's status")
    p_status.add_argument("idea_id")
    p_status.add_argument("new_status", choices=list(idea_pool.STATUSES))

    args = ap.parse_args()
    try:
        if args.cmd == "add":
            entry = idea_pool.add_idea(args.idea, domain=args.domain)
            print(json.dumps(entry, ensure_ascii=False, indent=2))
        elif args.cmd == "list":
            for e in idea_pool.list_ideas(status=args.status):
                overlap = (e.get("novelty_precheck") or {}).get("overlap_score", 0.0)
                print(f"{e['id']}  {e['status']:8}  overlap={overlap:.2f}  {e['idea'][:60]}")
        elif args.cmd == "next":
            entry = idea_pool.next_idea()
            print(json.dumps(entry, ensure_ascii=False, indent=2) if entry else "(queue empty)")
        elif args.cmd == "status":
            print(json.dumps(idea_pool.set_status(args.idea_id, args.new_status), ensure_ascii=False, indent=2))
    except (ValueError, KeyError) as exc:
        raise SystemExit(f"error: {exc}")


if __name__ == "__main__":
    main()
