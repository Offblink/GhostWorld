"""Listen to player chat in GhostEngine Metaverse.

Usage:
    python listen.py [--once] [--interval 5]

Reads agent_output.jsonl, prints new "heard" messages from player.
With --once, runs one poll cycle and exits.
Without --once, polls continuously (Ctrl+C to stop).
"""
import time, os, json, sys

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_META_DIR = os.path.dirname(_TOOLS_DIR)
OUTPUT_FILE = os.path.join(_META_DIR, "agent_output.jsonl")
STATE_FILE = os.path.join(_TOOLS_DIR, "listen_state.txt")


def get_last_line_index():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return int(f.read().strip())
    return 0


def save_last_line_index(idx):
    with open(STATE_FILE, "w") as f:
        f.write(str(idx))


def poll():
    if not os.path.exists(OUTPUT_FILE):
        return []
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    last_idx = get_last_line_index()
    new_msgs = []
    for i in range(last_idx, len(lines)):
        try:
            d = json.loads(lines[i])
        except Exception:
            continue
        if d.get("event") == "heard" and d.get("from") == "player":
            new_msgs.append(d["message"])
    save_last_line_index(len(lines))
    return new_msgs


def main():
    once = "--once" in sys.argv
    interval = 5
    for i, a in enumerate(sys.argv):
        if a == "--interval" and i + 1 < len(sys.argv):
            interval = float(sys.argv[i + 1])

    print(f"[listen] polling agent_output.jsonl every {interval}s")
    while True:
        time.sleep(interval)
        msgs = poll()
        for m in msgs:
            print(f"[player] {m}")
        if once:
            break


if __name__ == "__main__":
    main()
