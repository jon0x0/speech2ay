#!/usr/bin/env python3
"""Run Fuse with an unattended debugger-command script and capture output.

Adapted directly from the sibling `elite` project's
scripts/run_fuse_debug.py (same technique, same Fuse debugger-command
flag), which the user already uses for scripted emulator testing,
debugging, and timing measurement. Reused here rather than reinvented so
Berzerk's Fuse automation follows the exact same convention.

NOTE: this must be run somewhere that can execute the real fuse.exe (the
user's Windows machine / WSL with X or the JLO test build referenced in
the project instructions) — it is not runnable from this cloud sandbox
(no GUI/Fuse binary here, and no network to install one). Written here so
it's ready to use on-device.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path


DEFAULT_FUSE = Path(r"C:\apps\emulation\Fuse\fuse.exe")
# ^ Confirmed installed here. NOTE: this build's roms/ folder ships
# tc2068-0.rom/tc2068-1.rom (the PAL/export "TC2068" ROM set), not
# ts2068-0.rom/ts2068-1.rom (NTSC "TS2068") — checked by directory
# listing only, not run (see script header: not executable from the
# cloud sandbox). If "--machine ts2068" fails to start because it can't
# find its expected ROM filenames, try "--machine tc2068" instead, or
# copy/rename the tc2068 ROMs to ts2068-0.rom/ts2068-1.rom in this
# folder if Fuse's ts2068 support specifically needs those names.

# ----------------------------------------------------------------
# WSL path translation.
#
# This project's own instructions say pasmo is "runnable via WSL" — and
# in practice the user runs these Python scripts from inside a WSL bash
# shell too (python3, /mnt/d/... cwd), not from native Windows Python.
# fuse.exe is a native Windows PE binary. Two translations are needed
# for that combination to work at all:
#
#   1. The fuse.exe path itself: WSL's own interop can execve a Windows
#      binary directly, but only via its WSL-mount path (/mnt/c/...) —
#      a literal "C:\..." string handed to Python's subprocess.run() is
#      just an invalid Linux filename (confirmed: this is exactly the
#      FileNotFoundError the user hit).
#   2. The --dock media path: once fuse.exe *is* running (as a genuine
#      Windows process, just reached via /mnt/c/...), it does NOT
#      understand WSL's /mnt/d/... POSIX paths for its own arguments —
#      those need to go back to Windows form (D:\...).
#
# Both translations are no-ops when this script runs under native
# Windows Python (os.name == "nt"), so nothing changes for that case.
# ----------------------------------------------------------------

_WINDOWS_DRIVE_RE = re.compile(r"^([A-Za-z]):[\\/](.*)$")
_WSL_MOUNT_RE = re.compile(r"^/mnt/([A-Za-z])/(.*)$")


def _is_wsl() -> bool:
    if os.name != "posix":
        return False
    try:
        with open("/proc/version", encoding="utf-8", errors="ignore") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def _to_wsl_path(path_str: str) -> str:
    """C:\\foo\\bar -> /mnt/c/foo/bar. No-op if not a drive-letter path."""
    match = _WINDOWS_DRIVE_RE.match(path_str)
    if not match:
        return path_str
    drive, rest = match.groups()
    return f"/mnt/{drive.lower()}/{rest.replace(chr(92), '/')}"


def _to_windows_path(path_str: str) -> str:
    """/mnt/d/foo/bar -> D:\\foo\\bar. No-op if not a /mnt/<drive>/ path."""
    match = _WSL_MOUNT_RE.match(path_str)
    if not match:
        return path_str
    drive, rest = match.groups()
    return f"{drive.upper()}:\\{rest.replace('/', chr(92))}"


def _running_fuse_pids() -> set[str]:
    """PIDs of every currently-running fuse.exe, via tasklist.exe's CSV
    output. WSL-only helper — see the PID-diff explanation in run_fuse()
    for why this exists instead of trusting subprocess's own child PID."""
    try:
        r = subprocess.run(
            ["tasklist.exe", "/FI", "IMAGENAME eq fuse.exe", "/FO", "CSV", "/NH"],
            check=False, capture_output=True, text=True, timeout=5.0,
        )
    except (subprocess.TimeoutExpired, OSError):
        return set()
    pids = set()
    for line in r.stdout.splitlines():
        fields = [f.strip('"') for f in line.strip().split('","')]
        if len(fields) >= 2 and fields[0].lower() == "fuse.exe":
            pids.add(fields[1])
    return pids


def run_fuse(
    *,
    machine: str,
    media: Path,
    debugger_command: str,
    fuse: Path = DEFAULT_FUSE,
    tape: bool = False,
    speed: int = 5000,
    timeout: float = 10.0,
) -> subprocess.CompletedProcess[str]:
    fuse_arg = str(fuse)
    media_arg = str(media)
    is_wsl = _is_wsl()
    if is_wsl:
        fuse_arg = _to_wsl_path(fuse_arg)      # so WSL's execve can find it
        media_arg = _to_windows_path(media_arg) # so the Windows process
                                                 # spawned via that path
                                                 # can understand its own
                                                 # --dock/--tape argument

    args = [
        fuse_arg,
        "--machine",
        machine,
        "--speed",
        str(speed),
        "--no-sound",
        "--no-loading-sound",
        "--debugger-command",
        debugger_command.rstrip(),
    ]
    if tape:
        args.extend(["--tape", media_arg, "--auto-load"])
    else:
        args.extend(["--dock", media_arg])

    startupinfo = None
    creationflags = 0
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW

    # Under WSL, launching a native fuse.exe via its /mnt/c/... interop
    # path detaches the real Windows window process from the child
    # subprocess.run() tracks — confirmed this session: even a *timeout*
    # kill (which subprocess.run does attempt on its own tracked child)
    # never reached the real window, leaving it orphaned for the user to
    # kill by hand. The fix must NOT be "kill every fuse.exe by image
    # name" — the user runs their own independent Fuse sessions
    # alongside these scripts, and a blunt sweep killed one (confirmed
    # this session too). Instead: snapshot fuse.exe PIDs before
    # launching, and after a timeout, kill only whichever PIDs are new —
    # i.e. only ones this call itself spawned, never a pre-existing
    # session.
    before_pids = _running_fuse_pids() if is_wsl else set()

    try:
        return subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired:
        if is_wsl:
            new_pids = _running_fuse_pids() - before_pids
            for pid in new_pids:
                subprocess.run(["taskkill.exe", "/F", "/PID", pid],
                                check=False, capture_output=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("media", type=Path)
    parser.add_argument("command_file", type=Path)
    parser.add_argument("--machine", default="ts2068")
    parser.add_argument("--fuse", type=Path, default=DEFAULT_FUSE)
    parser.add_argument("--tape", action="store_true")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--speed", type=int, default=5000)
    parser.add_argument("--stdout", type=Path)
    parser.add_argument("--stderr", type=Path)
    args = parser.parse_args()

    result = run_fuse(
        machine=args.machine,
        media=args.media.resolve(),
        debugger_command=args.command_file.read_text(encoding="utf-8"),
        fuse=args.fuse,
        tape=args.tape,
        speed=args.speed,
        timeout=args.timeout,
    )
    if args.stdout:
        args.stdout.write_text(result.stdout, encoding="utf-8")
    else:
        print(result.stdout, end="")
    if args.stderr:
        args.stderr.write_text(result.stderr, encoding="utf-8")
    elif result.stderr:
        print(result.stderr, end="")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
