"""Local agent — same-process, no WebSocket. Reads commands, acts on WorldState."""
import asyncio, json, os, sys, time
from ._shared import process_agent_command

CMD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_commands.jsonl")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_output.jsonl")

_MAX_LOG_LINES = 200   # keep only the most recent log lines
_log_write_count = 0

def log_msg(msg: dict):
    global _log_write_count
    text = json.dumps(msg, ensure_ascii=False)
    print(text, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    _log_write_count += 1
    # periodically truncate log to prevent unbounded growth
    if _log_write_count % 50 == 0:
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > _MAX_LOG_LINES:
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.writelines(lines[-_MAX_LOG_LINES // 2:])
        except Exception:
            pass

_last_seen_positions: dict = {}  # for see-event dedup

def read_commands():
    cmds = []
    try:
        if os.path.exists(CMD_FILE):
            with open(CMD_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try: cmds.append(json.loads(line))
                        except: pass
            os.remove(CMD_FILE)
    except Exception as e:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(json.dumps({"event":"read_err","error":str(e)})+"\n")
        except: pass
    return cmds

async def local_agent_loop(name, ws, texture=""):

    """Run agent locally, sharing WorldState."""
    global _last_seen_positions
    from metaverse.server import handle_message, _build_snapshot
    token = f"token_{name}"
    resp = handle_message(ws, name, {"type":"connect","token":token,"owner":"agent","texture":texture})
    # clear stale log from previous run
    if os.path.exists(LOG_FILE):
        open(LOG_FILE, "w", encoding="utf-8").close()
    if os.path.exists(CMD_FILE):
        open(CMD_FILE, "w", encoding="utf-8").close()
    log_msg({"event":"connected","pos":[resp.get("x",0), resp.get("y",0)]})
    print(f"[{name}] connected locally")

    last_chat_tick = -1
    while True:
        try:
            await asyncio.sleep(0.3)

            # check server chat_log for new messages
            for c in ws.chat_log:
                if c.get("from") != name and c.get("tick", 0) > last_chat_tick:
                    log_msg({"event":"heard","from":c["from"],"message":c["message"]})
                    print(f"[{name}] {c['from']}: {c['message']}")
                    last_chat_tick = max(last_chat_tick, c.get("tick", 0))

            # check snapshot for other avatars — only log on position change
            snap = _build_snapshot(ws)
            others = {k: [round(v["x"],1), round(v["y"],1)] for k,v in snap.get("avatars",{}).items() if k != name}
            if others and others != _last_seen_positions:
                log_msg({"event":"see","avatars":others})
                _last_seen_positions = dict(others)
            # check goto completion
            av = ws.avatars.get(name)
            if av and av.goto_done:
                av.goto_done = False
                log_msg({"event":"goto_done","x":av.x,"y":av.y,"map":av.current_map or os.path.basename(ws.map_path)})

            # poll commands
            for cmd in read_commands():
                try:
                    process_agent_command(handle_message, ws, name, cmd, log_fn=log_msg)
                except Exception as e:
                    log_msg({"event":"cmd_error","error":str(e)})
        except Exception as e:
            try:
                with open(LOG_FILE, "a", encoding="utf-8") as lf:
                    lf.write(json.dumps({"event":"loop_crash","error":str(e)})+"\n")
            except: pass
