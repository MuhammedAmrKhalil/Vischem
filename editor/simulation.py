"""
editor/simulation.py  —  Vischem v0.1
NGspice / Xyce simulation runner.

Responsibilities
----------------
- Locate ngspice (or Xyce) on the host system automatically
- Run the simulator as a subprocess against a .cir file
- Stream stdout/stderr back to the caller via a callback
- Return a SimRun dataclass with success flag, output text, timing, and paths

Nothing in this module touches the GUI directly.
The Editor class in app.py owns all Tkinter calls.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field


# ── Platform-specific search paths ────────────────────────────────────────────
_NGSPICE_WIN_PATHS = [
    r"C:\ngspice\bin\ngspice.exe",
    r"C:\Program Files\ngspice\bin\ngspice.exe",
    r"C:\Program Files (x86)\ngspice\bin\ngspice.exe",
    r"C:\Users\Public\ngspice\bin\ngspice.exe",
]

_NGSPICE_LINUX_PATHS = [
    "/usr/bin/ngspice",
    "/usr/local/bin/ngspice",
    "/opt/ngspice/bin/ngspice",
    "/snap/bin/ngspice",
]

_XYCE_WIN_PATHS = [
    r"C:\Xyce\bin\Xyce.exe",
    r"C:\Program Files\Xyce\bin\Xyce.exe",
]

_XYCE_LINUX_PATHS = [
    "/usr/local/bin/Xyce",
    "/usr/bin/Xyce",
    "/opt/Xyce/bin/Xyce",
]


# ── Simulator location ─────────────────────────────────────────────────────────
def find_ngspice() -> str | None:
    """
    Return the path to the ngspice executable or None if not found.
    Search order:
      1. PATH (handles system installs and conda environments)
      2. Common platform-specific install locations
    """
    # 1 — PATH
    found = shutil.which("ngspice")
    if found:
        return found

    # 2 — Known locations
    candidates = (_NGSPICE_WIN_PATHS
                  if sys.platform == "win32"
                  else _NGSPICE_LINUX_PATHS)
    for p in candidates:
        if os.path.isfile(p):
            return p

    return None


def find_xyce() -> str | None:
    """
    Return the path to the Xyce executable or None if not found.
    Xyce is used when Verilog-A components are present in the schematic.
    """
    found = shutil.which("Xyce") or shutil.which("xyce")
    if found:
        return found

    candidates = (_XYCE_WIN_PATHS
                  if sys.platform == "win32"
                  else _XYCE_LINUX_PATHS)
    for p in candidates:
        if os.path.isfile(p):
            return p

    return None


def simulator_version(exe_path: str) -> str:
    """
    Return a short version string for display, e.g. "ngspice-42".
    Returns the path basename on failure.
    """
    try:
        result = subprocess.run(
            [exe_path, "--version"],
            capture_output=True, text=True, timeout=5)
        # ngspice prints version on stdout or stderr depending on build
        text = (result.stdout + result.stderr).strip()
        # Extract "ngspice-42" or "Xyce 7.6" style strings
        m = re.search(r"(ngspice|xyce)\s*[-v]?\s*(\d+[\d.]*)",
                      text, re.I)
        if m:
            return f"{m.group(1).lower()}-{m.group(2)}"
        return os.path.basename(exe_path)
    except Exception:
        return os.path.basename(exe_path)


# ── Result dataclass ──────────────────────────────────────────────────────────
@dataclass
class SimRun:
    """
    Holds every artefact produced by one simulation run.

    Attributes
    ----------
    success     : True if ngspice exited with code 0
    cir_path    : path to the .cir file that was simulated
    raw_path    : path where the .raw file was (or should have been) written
    stdout      : captured ngspice standard output
    stderr      : captured ngspice standard error
    duration_s  : wall-clock seconds the simulator ran
    exit_code   : raw process exit code
    errors      : list of error lines extracted from stdout/stderr
    warnings    : list of warning lines extracted from stdout/stderr
    """
    success    : bool       = False
    cir_path   : str        = ""
    raw_path   : str        = ""
    stdout     : str        = ""
    stderr     : str        = ""
    duration_s : float      = 0.0
    exit_code  : int        = -1
    errors     : list[str]  = field(default_factory=list)
    warnings   : list[str]  = field(default_factory=list)

    @property
    def raw_exists(self) -> bool:
        return bool(self.raw_path) and os.path.isfile(self.raw_path)

    @property
    def combined_output(self) -> str:
        """stdout + stderr merged, useful for log display."""
        parts = []
        if self.stdout.strip():
            parts.append(self.stdout)
        if self.stderr.strip():
            parts.append(self.stderr)
        return "\n".join(parts)


# ── Parser helpers ─────────────────────────────────────────────────────────────
def _classify_output(stdout: str, stderr: str) -> tuple[list[str], list[str]]:
    """
    Scan ngspice output for error and warning lines.
    Returns (errors, warnings).
    """
    errors:   list[str] = []
    warnings: list[str] = []
    text = stdout + "\n" + stderr
    for line in text.splitlines():
        ll = line.lower()
        if any(kw in ll for kw in ("error", "fatal", "abort", "failed")):
            errors.append(line.strip())
        elif any(kw in ll for kw in ("warning", "note:", "caution")):
            warnings.append(line.strip())
    return errors, warnings


# ── Main run function ─────────────────────────────────────────────────────────
def run(
    cir_path:    str,
    raw_path:    str,
    ngspice_exe: str,
    on_line:     "callable | None" = None,
    timeout_s:   int = 120,
) -> SimRun:
    """
    Run ngspice in batch mode against *cir_path* and write results to *raw_path*.

    Parameters
    ----------
    cir_path    : absolute path to the .cir netlist file
    raw_path    : absolute path where ngspice should write the .raw file
    ngspice_exe : path to the ngspice executable (from find_ngspice())
    on_line     : optional callback(line: str, is_stderr: bool) called for
                  each line of output as it arrives — use for live log streaming
    timeout_s   : kill the process after this many seconds (default 120)

    Returns
    -------
    SimRun dataclass with all results.
    """
    result = SimRun(cir_path=cir_path, raw_path=raw_path)

    if not os.path.isfile(cir_path):
        result.errors.append(f"Netlist file not found: {cir_path}")
        return result

    if not os.path.isfile(ngspice_exe):
        result.errors.append(f"ngspice not found at: {ngspice_exe}")
        return result

    # ngspice batch flags:
    #   -b          batch mode (no interactive prompt)
    #
    # Note: we do NOT pass -r here. The netlist's .control block contains
    # a "write filename.raw" command that handles output. ngspice resolves
    # the write path relative to cwd, which we set to the netlist directory.
    cmd = [ngspice_exe, "-b", cir_path]

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    t0 = time.perf_counter()
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(cir_path),
        )

        # Stream stdout in real time
        for line in proc.stdout:
            line = line.rstrip()
            stdout_lines.append(line)
            if on_line:
                try:
                    on_line(line, False)
                except Exception:
                    pass

        # Capture stderr after stdout closes
        stderr_text = proc.stderr.read()
        for line in stderr_text.splitlines():
            line = line.rstrip()
            stderr_lines.append(line)
            if on_line:
                try:
                    on_line(line, True)
                except Exception:
                    pass

        proc.wait(timeout=timeout_s)
        result.exit_code = proc.returncode

    except subprocess.TimeoutExpired:
        proc.kill()
        stderr_lines.append(
            f"[!] ngspice timed out after {timeout_s}s — killed")
        result.exit_code = -1

    except FileNotFoundError:
        result.errors.append(
            f"Cannot execute ngspice: {ngspice_exe}\n"
            "Check that ngspice is installed and the path is correct.")
        return result

    except Exception as exc:
        result.errors.append(f"Simulation error: {exc}")
        return result

    finally:
        result.duration_s = time.perf_counter() - t0

    result.stdout = "\n".join(stdout_lines)
    result.stderr = "\n".join(stderr_lines)
    result.errors, result.warnings = _classify_output(
        result.stdout, result.stderr)

    # ngspice returns 0 on success; non-zero or missing .raw = failure
    result.success = (result.exit_code == 0 and result.raw_exists)

    return result


# ── CLI smoke-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    exe = find_ngspice()
    if not exe:
        print("[!] ngspice not found — install it first")
        sys.exit(1)

    print(f"Found: {exe}  ({simulator_version(exe)})")

    # Write a minimal test netlist
    import tempfile
    cir = tempfile.NamedTemporaryFile(suffix=".cir", delete=False, mode="w")
    cir.write("* Vischem simulation.py smoke test\n")
    cir.write("V1 vdd 0 DC 1\n")
    cir.write("R1 vdd out 1k\n")
    cir.write("R2 out 0 1k\n")
    cir.write(".op\n")
    cir.write(".end\n")
    cir.flush()
    raw_path = cir.name.replace(".cir", ".raw")
    cir.close()

    print(f"Running: {cir.name}")
    sim = run(cir.name, raw_path, exe,
              on_line=lambda l, err: print(f"{'ERR' if err else 'OUT'}: {l}"))

    print(f"\nSuccess:  {sim.success}")
    print(f"Duration: {sim.duration_s:.2f}s")
    print(f"Raw file: {sim.raw_path}  (exists={sim.raw_exists})")
    if sim.errors:
        print("Errors:", sim.errors)
    if sim.warnings:
        print("Warnings:", sim.warnings)

    os.unlink(cir.name)
    if sim.raw_exists:
        os.unlink(raw_path)
