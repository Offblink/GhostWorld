"""Channel entry points — ``ghostworld-send`` / ``ghostworld-wait``.

Both are one-shot processes an agent (omp, a Fungi clone, a bot) can call to
drive its character and to be woken by player speech:

    ghostworld-send '{"cmd":"pos"}'
    ghostworld-send '{"cmd":"say","message":"来了"}'
    ghostworld-wait --timeout 25                  # blocks, prints one line per event
    ghostworld-wait --all --follow                # long-lived watcher
    ghostworld-wait --kinds observation           # non-waking events

Exit codes (part of the contract, see docs/PROTOCOL-agent-channel.md):

    send  0 = ack received    1 = accepted but no ack    2 = no channel / bad usage
    wait  0 = events printed  2 = no channel / bad usage 3 = nothing before the deadline
"""
from __future__ import annotations

import contextlib
import json
import sys

from .channel_client import (
    DEFAULT_WAIT_TIMEOUT,
    ChannelClient,
    ChannelTimeout,
    ChannelUnavailable,
    NoAck,
)

EXIT_OK = 0
EXIT_NO_ACK = 1
EXIT_NO_CHANNEL = 2
EXIT_TIMEOUT = 3

WAKE_KINDS = {"wake"}

_USAGE = {
    "send": "usage: ghostworld-send '<json command>'   (or - to read JSON from stdin)",
    "wait": ("usage: ghostworld-wait [--timeout SECONDS] [--after SEQ] "
             "[--kinds wake,observation] [--all] [--follow]"),
}


def utf8_stdio() -> None:
    """Pin this CLI's own pipes to UTF-8 — what every consumer assumes.

    The line JSON is UTF-8 on the socket, and a watcher decodes this process's
    stdout as UTF-8 as well (`subprocess(..., text=True, encoding="utf-8")`).
    Launched by a GUI — no PYTHONUTF8/PYTHONIOENCODING — the child would instead
    use the console code page (cp936 on this box), so the player's 你好 reached
    the agent as U+FFFD mojibake and the agent's own reply came back mangled
    (2026-09-15 real-machine report).
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if (getattr(stream, "encoding", "") or "").lower().replace("-", "") == "utf8":
            continue  # already there (a harness that exports PYTHONUTF8) — no work
        with contextlib.suppress(Exception):  # in-process use, or a replaced stream
            stream.reconfigure(encoding="utf-8")


def send_main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    payload = None
    for a in args:
        if a in ("-h", "--help"):
            print(__doc__)
            return EXIT_OK
        if a == "-":
            payload = sys.stdin.read()
        elif not a.startswith("-"):
            payload = a
        else:
            print(f"ghostworld-send: unknown option {a}\n{_USAGE['send']}", file=sys.stderr)
            return EXIT_NO_CHANNEL
    if not payload:
        print(_USAGE["send"], file=sys.stderr)
        return EXIT_NO_CHANNEL
    try:
        cmd = json.loads(payload)
    except ValueError as e:
        print(f"ghostworld-send: invalid JSON: {e}", file=sys.stderr)
        return EXIT_NO_CHANNEL
    if not isinstance(cmd, dict):
        print("ghostworld-send: the command must be a JSON object", file=sys.stderr)
        return EXIT_NO_CHANNEL

    try:
        client = ChannelClient.from_file()
    except ChannelUnavailable as e:
        print(f"ghostworld-send: {e}", file=sys.stderr)
        return EXIT_NO_CHANNEL
    try:
        ack = client.send(cmd)
    except NoAck as e:
        print(f"ghostworld-send: {e}", file=sys.stderr)
        return EXIT_NO_ACK
    except ChannelUnavailable as e:
        print(f"ghostworld-send: {e}", file=sys.stderr)
        return EXIT_NO_CHANNEL
    print(json.dumps(ack, ensure_ascii=False))
    return EXIT_OK


def _emit(events: list[dict], client: ChannelClient) -> None:
    utf8_stdio()  # the printer owns its encoding, next to owning its flush
    if client.last_gap:
        print(f"[channel] events were lost (buffer holds seq >= {client.last_gap.get('oldest')})",
              file=sys.stderr)
    for evt in events:
        # A watcher reads this over a pipe (`--follow`, spawned by a harness),
        # where stdout is block-buffered: without the flush the player's line
        # sits in the child's 8 KB buffer until the game exits, and the agent is
        # never woken (2026-09-15 real-machine report).
        print(json.dumps(evt, ensure_ascii=False), flush=True)


def wait_main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = list(sys.argv[1:] if argv is None else argv)
    timeout = DEFAULT_WAIT_TIMEOUT
    after = None
    kinds: set[str] | None = set(WAKE_KINDS)
    follow = False
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-h", "--help"):
            print(__doc__)
            return EXIT_OK
        try:
            if a == "--timeout":
                i += 1
                timeout = float(args[i])
            elif a == "--after":
                i += 1
                after = int(args[i])
            elif a == "--kinds":
                i += 1
                kinds = {k.strip() for k in args[i].split(",") if k.strip()}
            elif a == "--all":
                kinds = None
            elif a == "--follow":
                follow = True
            else:
                print(f"ghostworld-wait: unknown option {a}\n{_USAGE['wait']}", file=sys.stderr)
                return EXIT_NO_CHANNEL
        except (IndexError, ValueError):
            print(_USAGE["wait"], file=sys.stderr)
            return EXIT_NO_CHANNEL
        i += 1

    try:
        client = ChannelClient.from_file()
    except ChannelUnavailable as e:
        print(f"channel not found — 游戏没在跑？({e})", file=sys.stderr)
        return EXIT_NO_CHANNEL

    if follow:
        try:
            for events in client.iter_events(timeout=timeout, kinds=kinds):
                _emit(events, client)
        except KeyboardInterrupt:
            return EXIT_OK
        print("ghostworld-wait: channel went away", file=sys.stderr)
        return EXIT_NO_CHANNEL

    try:
        events = client.wait(timeout=timeout, kinds=kinds, after=after)
    except ChannelTimeout:
        print(f"ghostworld-wait: no events within {timeout:g}s", file=sys.stderr)
        return EXIT_TIMEOUT
    except ChannelUnavailable as e:
        print(f"ghostworld-wait: {e}", file=sys.stderr)
        return EXIT_NO_CHANNEL
    _emit(events, client)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """``python -m metaverse.cli_channel send|wait ...``"""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return EXIT_OK
    verb, rest = args[0], args[1:]
    if verb == "send":
        return send_main(rest)
    if verb == "wait":
        return wait_main(rest)
    print(f"unknown verb '{verb}' — expected 'send' or 'wait'\n{__doc__}", file=sys.stderr)
    return EXIT_NO_CHANNEL


if __name__ == "__main__":
    sys.exit(main())
