"""Build the Windows release folder: `GhostWorld.exe` + `GhostWorldCLI.exe`.

    python tools/build_exe.py [--zip]

Runs `GhostWorld.spec` (see it for why there are two exes) and then *proves* the
build rather than trusting the exit code:

* both binaries exist and carry the icon (PyInstaller logs `Copying icon to EXE`
  only when `--icon` reached the build — a silently dropped icon is exactly the
  failure this check exists for);
* `GhostWorldCLI.exe where` runs and reports the packaged version and a writable
  runtime directory — a frozen build that cannot find its own assets is broken
  even though it "built fine".

The zip is what goes on a release; the folder is what you test with.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "GhostWorld.spec"
DIST = ROOT / "dist" / "GhostWorld"
BUILD = ROOT / "build"


def _run_pyinstaller(clean: bool) -> str:
    if clean:
        for path in (BUILD, ROOT / "dist" / "GhostWorld"):
            shutil.rmtree(path, ignore_errors=True)
    cmd = [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm",
           "--distpath", str(ROOT / "dist"), "--workpath", str(BUILD)]
    print("$", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        print(log[-4000:])
        raise SystemExit(f"PyInstaller failed with {proc.returncode}")
    return log


def _check_icons(log: str) -> None:
    """`Copying icon to EXE` appears once per exe that got `--icon`."""
    hits = len(re.findall(r"Copying icon to EXE", log))
    print(f"icon embedded in {hits} exe(s)")
    if hits < 2:
        raise SystemExit("the icon did not reach every exe — see the build log")


def _check_cli(exe: Path) -> None:
    proc = subprocess.run([str(exe), "where"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out)
    if proc.returncode != 0:
        raise SystemExit(f"{exe.name} where exited {proc.returncode}")
    for needle in ("打包 exe", "运行时写入", "运行时目录"):
        if needle not in out:
            raise SystemExit(f"{exe.name} where does not mention {needle!r} — wrong layout")
    if "✗" in out:
        raise SystemExit(f"{exe.name} reports an unwritable runtime path:\n{out}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zip", action="store_true", help="also write dist/GhostWorld-<version>-win64.zip")
    ap.add_argument("--no-clean", action="store_true", help="reuse the previous build directory")
    args = ap.parse_args(argv)

    log = _run_pyinstaller(clean=not args.no_clean)
    _check_icons(log)
    _check_cli(DIST / "GhostWorldCLI.exe")
    print(f"\n{DIST}")

    if args.zip:
        version = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
        archive = ROOT / "dist" / f"GhostWorld-{version.group(1)}-win64"
        made = shutil.make_archive(str(archive), "zip", root_dir=str(DIST.parent), base_dir=DIST.name)
        print(f"{made}  ({Path(made).stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
