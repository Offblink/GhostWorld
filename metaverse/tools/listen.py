"""Listen to player chat in GhostEngine Metaverse.

Usage:
    python metaverse/tools/listen.py [--once] [--interval 5]

Reads ``agent_output.jsonl`` and prints player messages.  Progress is kept as an
event **seq** (the file is a projection of the channel bus), not as a line
number: a rotated or restarted log can never renumber the reader's position.
Rotated-away events are reported as a gap, and nothing is ever replayed.

The channel CLI (``ghostworld-wait``) is the primary way to be woken by player
speech; this tool stays for grep-style use of the log file.
"""
import json
import os
import sys
import time

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_META_DIR = os.path.dirname(_TOOLS_DIR)
OUTPUT_FILE = os.path.join(_META_DIR, "agent_output.jsonl")
CURSOR_FILE = os.path.join(_TOOLS_DIR, "listen_cursor.json")
LEGACY_STATE_FILE = os.path.join(_TOOLS_DIR, "listen_state.txt")  # held line numbers


def load_cursor() -> int:
    """Last seq this reader has seen (0 = nothing yet)."""
    try:
        with open(CURSOR_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        return 0
    seq = state.get("seq") if isinstance(state, dict) else None
    return seq if isinstance(seq, int) and seq >= 0 else 0


def save_cursor(seq: int) -> None:
    tmp = CURSOR_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"seq": int(seq)}, f)
    os.replace(tmp, CURSOR_FILE)


def read_events() -> list[dict]:
    """Every parsed event in the log, in file order."""
    if not os.path.exists(OUTPUT_FILE):
        return []
    events = []
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if isinstance(data, dict) and isinstance(data.get("seq"), int):
                events.append(data)
    return events


def poll() -> list[str]:
    """Player messages published since the stored seq."""
    events = read_events()
    if not events:
        return []
    cursor = load_cursor()
    first_seq, last_seq = events[0]["seq"], events[-1]["seq"]
    if cursor > last_seq:
        # A different game process wrote this log: every line in it is new.
        print(f"[listen] log belongs to a newer run (cursor {cursor} > seq {last_seq}) — reading it all",
              file=sys.stderr)
        fresh = events
    else:
        if cursor + 1 < first_seq:
            print(f"[listen] {first_seq - cursor - 1} event(s) rotated away (seq {cursor + 1}..{first_seq - 1})",
                  file=sys.stderr)
        fresh = [e for e in events if e["seq"] > cursor]
    if fresh:
        save_cursor(fresh[-1]["seq"])
    return [e["message"] for e in fresh if e.get("event") == "heard" and e.get("from") == "player"]


def main():
    from .._paths import utf8_stdio

    utf8_stdio()  # player lines are Chinese: never encode them with the code page
    if os.path.exists(LEGACY_STATE_FILE):
        try:
            os.remove(LEGACY_STATE_FILE)  # line numbers are meaningless now
        except OSError:
            pass
    once = "--once" in sys.argv
    interval = 5
    for i, a in enumerate(sys.argv):
        if a == "--interval" and i + 1 < len(sys.argv):
            interval = float(sys.argv[i + 1])

    print(f"[listen] tailing agent_output.jsonl by seq (every {interval}s)", flush=True)
    while True:
        time.sleep(interval)
        for m in poll():
            # Same pipe rule as the channel CLI: a tailer's consumer reads lines
            # as they happen, not when an 8 KB buffer happens to fill.
            print(f"[player] {m}", flush=True)
        if once:
            break


if __name__ == "__main__":
    main()
