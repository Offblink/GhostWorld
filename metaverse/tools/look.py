"""Look around in GhostEngine Metaverse — reads perception from agent_output.jsonl.

Usage:
    python metaverse/look.py

Prints the latest perception: inventory, all items on map, nearby items.
Use together with listen.py for full agent awareness.
"""
import os, json, time

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent_output.jsonl')


def latest_perception():
    if not os.path.exists(LOG_FILE):
        return None
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("event") == "perception":
            return d
    return None


def main():
    p = latest_perception()
    if not p:
        print("[look] no perception data yet — send a 'look' command first")
        return
    inv = p.get("inventory", [])
    if inv:
        counts = {}
        for i in inv:
            label = i.get("label", i.get("id", "?"))
            counts[label] = counts.get(label, 0) + 1
        print("Inventory:")
        for label, count in counts.items():
            print(f"  {label}: {count}")
    else:
        print("Inventory: (empty)")
    print(f"Position: ({p['position'][0]:.1f}, {p['position'][1]:.1f})")
    all_items = p.get("all_items", [])
    if all_items:
        print("All items on map:")
        for i in all_items:
            print(f"  {i['name']} ({i['kind']}) at ({i['x']:.1f},{i['y']:.1f}) dist={i['distance']:.1f}")
    nearby = p.get("nearby_items", [])
    if nearby:
        print("Nearby (<=5):")
        for i in nearby:
            print(f"  {i['name']} at ({i['x']:.1f},{i['y']:.1f})")


if __name__ == "__main__":
    main()
