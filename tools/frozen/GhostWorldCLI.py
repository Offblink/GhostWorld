"""Frozen entry — the console companion, same package, a real stdout.

    GhostWorldCLI.exe send '<json>'        drive the character (Fungi's path)
    GhostWorldCLI.exe wait [--timeout N]   block until the game pushes an event
    GhostWorldCLI.exe where                where this copy lives and what it writes
    GhostWorldCLI.exe play [map.json]      the game with a console, for debugging

Exit codes are the channel contract (see `metaverse/cli_channel.py`): 0 ok,
1 accepted-but-no-ack, 2 no channel / bad usage, 3 nothing before the deadline.
"""
import sys

USAGE = (
    "GhostWorldCLI.exe send '<json command>'\n"
    "GhostWorldCLI.exe wait [--timeout SECONDS] [--after SEQ] [--kinds wake,observation] [--all] [--follow]\n"
    "GhostWorldCLI.exe where\n"
    "GhostWorldCLI.exe play [map.json]\n"
)


def main() -> int:
    args = sys.argv[1:]
    verb = args[0] if args else ""
    rest = args[1:]
    if verb in ("send", "wait"):
        from metaverse import cli_channel

        return cli_channel.main([verb] + rest)
    if verb == "where":
        from metaverse._paths import main as where_main

        return where_main()
    if verb == "play":
        sys.argv = [sys.argv[0]] + rest
        from metaverse.launch import main as play_main

        play_main()
        return 0
    print(USAGE if verb in ("", "-h", "--help") else f"unknown command {verb!r}\n{USAGE}")
    return 0 if verb in ("", "-h", "--help") else 2


if __name__ == "__main__":
    sys.exit(main())
