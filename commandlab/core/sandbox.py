import os
import sys
import re
import json
import subprocess
import shutil
import tempfile
import signal

from commandlab.core.progress import check_answer
from commandlab.ui.colors import C

# ── Command Classifier integration ───────────────────────────
try:
    from commandlab.classifier import classify as _classify, Decision as _Decision
    _CLASSIFIER_OK = True
except Exception:
    _CLASSIFIER_OK = False
    _classify = None
    _Decision = None

# ─────────────────────────────────────────────────────────────
# SANDBOX ENGINE
# ─────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
# SANDBOX ENGINE
# ─────────────────────────────────────────────────────────────

# Thin last-resort blocklist kept only as a UI-level guard so that
# obviously destructive commands are rejected with a clear message
# *before* we even attempt to enter the sandbox.  The actual security
# boundary is the chroot/namespace isolation in Sandbox._exec — this
# list is NOT relied upon for containment.
_BLOCKED_PATTERNS = [
    (r'\bshutdown\b|\breboot\b|\bpoweroff\b|\bhalt\b', "system shutdown/reboot"),
    (r':\(\)\s*\{.*\|.*:.*&.*\}',                      "fork bomb"),
    (r'\bmkfs\b',                                       "disk formatting"),
    (r'\bdd\b.*of=/dev/(sd[a-z]|hd[a-z]|nvme[0-9]|vd[a-z]|xvd[a-z])', "dd to block device"),
]

def _is_dangerous(cmd: str):
    """Return (True, reason) if the command matches a blocked pattern."""
    for pattern, reason in _BLOCKED_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE | re.DOTALL):
            return True, reason
    return False, None


def _classifier_gate(cmd: str):
    """
    Run the command classifier and return an action dict:

      {
        "action":   "block" | "text_only" | "allow",
        "checker":  "text checker" | "sandbox checker",
        "decision": str,            # classifier's final_decision value
        "reason":   str,            # human-readable explanation
        "details":  str,            # optional obfuscation / per-command detail
      }

    If the classifier module is unavailable the function returns
    action="allow" so the rest of the pipeline is unaffected.

    Mapping (highest risk wins across all chained commands):
      BLOCK        -> action="text_only"  checker="text checker"   (kernel/network/hardware — text compare only, never executed)
      TEXT_ONLY    -> action="text_only"  checker="text checker"   (filesystem/package writes — text compare only)
      SANDBOX      -> action="allow"      checker="sandbox checker"
      SAFE_EXECUTE -> action="allow"      checker="sandbox checker"

    Note: hard blocks (_is_dangerous) for fork-bombs / disk-wipes remain in
    run_sandboxed_task() and are never overridden by this function.
    """
    if not _CLASSIFIER_OK:
        return {
            "action":   "allow",
            "checker":  "sandbox checker",
            "decision": "UNKNOWN",
            "reason":   "classifier unavailable",
            "details":  "",
        }

    result = _classify(cmd)
    decision = result.final_decision.value   # str: SAFE_EXECUTE | SANDBOX | TEXT_ONLY | BLOCK

    # Build a brief per-command detail string
    details_parts = []
    if result.obfuscation_flags:
        details_parts.append("⚠ obfuscation: " + ", ".join(result.obfuscation_flags[:2]))
    for cr in result.commands:
        details_parts.append(f"{cr.base}→{cr.classification.value}")
    details = "  ".join(details_parts)

    if decision == "BLOCK":
        # Risky/control commands are NOT hard-blocked.
        # They are checked by text comparison only — never executed in the sandbox.
        return {
            "action":   "text_only",
            "checker":  "text checker",
            "decision": decision,
            "reason":   "high-risk command — answer checked by text comparison only",
            "details":  details,
        }

    if decision == "TEXT_ONLY":
        return {
            "action":   "text_only",
            "checker":  "text checker",
            "decision": decision,
            "reason":   "command modifies filesystem/packages — text-only feedback",
            "details":  details,
        }

    # SANDBOX or SAFE_EXECUTE → run normally
    checker = "sandbox checker" if decision == "SANDBOX" else "sandbox checker"
    return {
        "action":   "allow",
        "checker":  checker,
        "decision": decision,
        "reason":   "",
        "details":  details,
    }


# ── Sandbox isolation strategy ─────────────────────────────────────────────
#
# Goal: give the subprocess access to standard Linux binaries (ls, grep, awk,
# find, …) while preventing it from reading or writing *anything* on the real
# host filesystem outside the per-task temp directory.
#
# Approach — "chroot jail with read-only bind mounts":
#
#   chroot_root/          ← ephemeral directory, torn down after every command
#     usr/  (ro bind)     ← /usr from host (provides /bin, /sbin, /lib via symlinks)
#     lib64/ (ro bind)    ← ELF interpreter on merged-usr systems
#     tmp/  (tmpfs)       ← scratch space, lives only for the command duration
#     proc/ (procfs)      ← needed by some tools (ps, top, etc.)
#     dev/  (devtmpfs)    ← /dev/null, /dev/zero, /dev/urandom
#     etc/  (empty dir)   ← prevents "no such file" crashes; no host files
#     home/user/ (rw bind)← the task's writable sandbox directory (self.path)
#
#   The subprocess is launched as:
#       chroot <chroot_root> /bin/bash -c "<cmd>"
#   with HOME=/home/user and cwd=/home/user.
#
# Two execution paths are tried, in order:
#
#   1. Direct mount + chroot (requires CAP_SYS_ADMIN or root).
#      Works when the tool is run as root or with the right capabilities.
#
#   2. unshare(1) —user —map-root-user —mount + chroot inside the new
#      mount namespace.  This works for unprivileged users on kernels that
#      allow unprivileged user namespaces (most modern distros; controlled by
#      /proc/sys/kernel/unprivileged_userns_clone on older kernels).
#
#   3. Graceful degradation: if both fail (e.g. unshare is absent, or the
#      kernel disables unprivileged namespaces), _exec falls back to the old
#      cwd-only execution and emits a one-time warning so the operator knows
#      the sandbox is running in reduced-security mode.

def _find_bin(name: str, candidates: tuple) -> str:
    """Return the first existing path from candidates, or just name as fallback."""
    for path in candidates:
        if os.path.isfile(path):
            return path
    return name

# Absolute paths to privileged binaries — resolved once at import time.
_MOUNT_BIN   = _find_bin("mount",   ("/bin/mount",  "/usr/bin/mount",  "/sbin/mount",  "/usr/sbin/mount"))
_UMOUNT_BIN  = _find_bin("umount",  ("/bin/umount", "/usr/bin/umount", "/sbin/umount", "/usr/sbin/umount"))
_CHROOT_BIN  = _find_bin("chroot",  ("/usr/sbin/chroot", "/sbin/chroot", "/bin/chroot", "/usr/bin/chroot"))
_UNSHARE_BIN = _find_bin("unshare", ("/usr/bin/unshare", "/bin/unshare"))


def _mount(*args):
    """Run mount(8) with the given args; raise RuntimeError on failure."""
    r = subprocess.run([_MOUNT_BIN] + list(args),
                       capture_output=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(
            "mount " + " ".join(args) + " failed: " + r.stderr.decode(errors="replace").strip()
        )


def _build_chroot_root_unshare(workdir: str) -> str:
    """
    Like _build_chroot_root() but uses 'unshare --user --mount' to create a
    private mount namespace so bind mounts succeed without root privileges.

    We do this by launching a tiny Python helper inside the new namespace that:
      1. Builds the chroot root with bind mounts (now possible as namespace-root).
      2. Writes the chroot root path to stdout and then BLOCKS until stdin closes.
      3. The parent reads the path and returns it.
      4. When the Sandbox is cleaned up, the helper's stdin is closed (EOF),
         it wakes up, runs teardown, and exits.

    This keeps the mount namespace alive for the duration of the Sandbox session.
    """
    helper_code = r"""
import os, sys, subprocess, tempfile, shutil, json

MOUNT_BIN  = sys.argv[1]
UMOUNT_BIN = sys.argv[2]
CHROOT_BIN = sys.argv[3]
workdir    = sys.argv[4]

def do_mount(*args):
    r = subprocess.run([MOUNT_BIN] + list(args), capture_output=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace").strip())

def teardown(root):
    for sub in ("home/user", "etc/resolv.conf", "etc/ssl/certs",
                "etc/alternatives", "dev", "proc", "tmp", "lib64", "usr"):
        mnt = os.path.join(root, sub)
        # resolv.conf is a file mount; isfile covers that case too
        if os.path.exists(mnt):
            subprocess.run([UMOUNT_BIN, mnt], capture_output=True, timeout=10)
    shutil.rmtree(root, ignore_errors=True)

root = tempfile.mkdtemp(prefix="cmdlab_chr_")
try:
    for d in ("usr", "lib64", "etc", "tmp", "proc", "dev", "home", "home/user"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    for lnk, tgt in (("bin","usr/bin"),("sbin","usr/sbin"),("lib","usr/lib")):
        lp = os.path.join(root, lnk)
        if not os.path.exists(lp):
            os.symlink(tgt, lp)
    do_mount("--bind", "-o", "ro", "/usr",  os.path.join(root, "usr"))
    if os.path.isdir("/lib64"):
        do_mount("--bind", "-o", "ro", "/lib64", os.path.join(root, "lib64"))
    do_mount("-t", "tmpfs",    "tmpfs",    os.path.join(root, "tmp"))
    do_mount("-t", "proc",     "proc",     os.path.join(root, "proc"))
    do_mount("-t", "devtmpfs", "devtmpfs", os.path.join(root, "dev"))
    if os.path.isdir("/etc/alternatives"):
        os.makedirs(os.path.join(root, "etc", "alternatives"), exist_ok=True)
        do_mount("--bind", "-o", "ro", "/etc/alternatives",
                 os.path.join(root, "etc", "alternatives"))
    if os.path.isfile("/etc/resolv.conf"):
        dest = os.path.join(root, "etc", "resolv.conf")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "w").close()          # file mount-point
        do_mount("--bind", "-o", "ro", "/etc/resolv.conf", dest)
    if os.path.isdir("/etc/ssl/certs"):
        dest = os.path.join(root, "etc", "ssl", "certs")
        os.makedirs(dest, exist_ok=True) # directory mount-point
        do_mount("--bind", "-o", "ro", "/etc/ssl/certs", dest)
    do_mount("--bind", workdir, os.path.join(root, "home", "user"))

    # Signal readiness: write the root path + a sentinel JSON to stdout
    sys.stdout.write(json.dumps({"root": root, "ok": True}) + "\n")
    sys.stdout.flush()

    # Block until parent closes our stdin (= Sandbox.cleanup() called)
    sys.stdin.read()

except Exception as exc:
    sys.stdout.write(json.dumps({"root": root, "ok": False, "err": str(exc)}) + "\n")
    sys.stdout.flush()
    sys.stdin.read()
finally:
    teardown(root)
"""

    import subprocess as _sp
    proc = _sp.Popen(
        [_UNSHARE_BIN, "--user", "--map-root-user", "--mount",
         "python3", "-c", helper_code,
         _MOUNT_BIN, _UMOUNT_BIN, _CHROOT_BIN, workdir],
        stdin=_sp.PIPE,
        stdout=_sp.PIPE,
        stderr=_sp.PIPE,
    )
    try:
        # Read the JSON handshake (blocks until helper writes it)
        line = proc.stdout.readline().decode(errors="replace").strip()
        import json as _json
        info = _json.loads(line)
        if not info.get("ok"):
            proc.stdin.close()
            proc.wait(timeout=5)
            raise RuntimeError(info.get("err", "unshare helper failed"))
        chroot_root = info["root"]
        # Attach proc to the chroot_root path so cleanup can kill it
        _UNSHARE_PROCS[chroot_root] = proc
        return chroot_root
    except Exception:
        proc.stdin.close()
        proc.wait(timeout=5)
        raise


# Registry of live unshare helper processes keyed by chroot_root path.
# _teardown_chroot_root() checks here and kills the helper when done.
_UNSHARE_PROCS: dict = {}


def _detect_sandbox_mode() -> str:

    """
    Probe which isolation mode is available.
    Returns one of: "chroot_direct" | "chroot_unshare" | "fallback"
    Result is cached in _SANDBOX_MODE after the first call.
    """
    # Can we mount directly? (root / CAP_SYS_ADMIN)
    probe = tempfile.mkdtemp(prefix="cmdlab_probe_")
    try:
        r = subprocess.run(
            [_MOUNT_BIN, "--bind", "-o", "ro", "/usr", probe],
            capture_output=True, timeout=5,
        )
        if r.returncode == 0:
            subprocess.run([_UMOUNT_BIN, probe], capture_output=True, timeout=5)
            return "chroot_direct"
    except Exception:
        pass
    finally:
        shutil.rmtree(probe, ignore_errors=True)

    # Can we use unshare --user --mount?
    try:
        r = subprocess.run(
            [_UNSHARE_BIN, "--user", "--map-root-user", "--mount",
             "echo", "ok"],
            capture_output=True, timeout=5,
        )
        if r.returncode == 0:
            return "chroot_unshare"
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return "fallback"


_SANDBOX_MODE: str = ""          # filled lazily on first Sandbox._exec call
_SANDBOX_MODE_WARNED: bool = False


def _get_sandbox_mode() -> str:
    global _SANDBOX_MODE
    if not _SANDBOX_MODE:
        _SANDBOX_MODE = _detect_sandbox_mode()
    return _SANDBOX_MODE


# ── chroot root builder / teardown ──────────────────────────────────────────

def _build_chroot_root(workdir: str) -> str:
    """
    Create a minimal chroot root directory tree with bind mounts already
    applied.  The caller is responsible for calling _teardown_chroot_root()
    afterwards (even on error).

    workdir is bind-mounted read-write at <root>/home/user inside the chroot.

    Returns the path to the chroot root.
    Raises RuntimeError if any critical mount step fails.
    """
    root = tempfile.mkdtemp(prefix="cmdlab_chr_")
    try:
        # Directories that will exist inside the chroot
        for d in ("usr", "lib64", "etc", "tmp", "proc", "dev",
                  "home", os.path.join("home", "user")):
            os.makedirs(os.path.join(root, d), exist_ok=True)

        # /bin /sbin /lib are symlinks on merged-usr systems (Debian ≥ 12,
        # Ubuntu ≥ 22.04).  Recreate those symlinks inside the chroot so that
        # paths like /bin/bash resolve correctly after the chroot(2) call.
        for link, target in (("bin", "usr/bin"), ("sbin", "usr/sbin"), ("lib", "usr/lib")):
            lpath = os.path.join(root, link)
            if not os.path.exists(lpath):
                os.symlink(target, lpath)

        # Bind-mount /usr read-only (gives us all standard binaries + libs)
        _mount("--bind", "-o", "ro", "/usr", os.path.join(root, "usr"))

        # /lib64 holds the ELF interpreter (ld-linux-x86-64.so.2) on x86_64.
        # It may not exist on all architectures; skip silently if absent.
        if os.path.isdir("/lib64"):
            _mount("--bind", "-o", "ro", "/lib64", os.path.join(root, "lib64"))

        # Fresh tmpfs for /tmp — writes go to memory, not the host /tmp.
        _mount("-t", "tmpfs", "tmpfs", os.path.join(root, "tmp"))

        # /proc — needed by ps, top, /proc/self/fd, etc.
        _mount("-t", "proc", "proc", os.path.join(root, "proc"))

        # /dev — needed for /dev/null, /dev/urandom redirection, etc.
        _mount("-t", "devtmpfs", "devtmpfs", os.path.join(root, "dev"))

        # /etc/alternatives — Debian/Ubuntu distros symlink many /usr/bin tools
        # (awk, cc, python3, etc.) through this directory.  Bind-mounting it
        # read-only ensures those symlink chains resolve correctly inside the jail.
        if os.path.isdir("/etc/alternatives"):
            os.makedirs(os.path.join(root, "etc", "alternatives"), exist_ok=True)
            _mount("--bind", "-o", "ro", "/etc/alternatives",
                   os.path.join(root, "etc", "alternatives"))

        # /etc/resolv.conf — DNS resolver configuration.
        # Bind-mount the host file read-only so tools like curl, wget, ping,
        # and dig can resolve hostnames inside the sandbox.
        if os.path.isfile("/etc/resolv.conf"):
            dest = os.path.join(root, "etc", "resolv.conf")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "w").close()          # create file mount-point
            _mount("--bind", "-o", "ro", "/etc/resolv.conf", dest)

        # /etc/ssl/certs — CA certificate bundle.
        # Required for SSL/TLS verification by curl, wget, Python's ssl module,
        # etc.  Bind-mounted read-only; the sandbox cannot modify host certs.
        if os.path.isdir("/etc/ssl/certs"):
            dest = os.path.join(root, "etc", "ssl", "certs")
            os.makedirs(dest, exist_ok=True) # create directory mount-point
            _mount("--bind", "-o", "ro", "/etc/ssl/certs", dest)

        # The task's writable work directory, visible as /home/user
        _mount("--bind", workdir, os.path.join(root, "home", "user"))

        return root

    except Exception:
        # Best-effort teardown before re-raising
        _teardown_chroot_root(root)
        raise


def _teardown_chroot_root(root: str) -> None:
    """
    Tear down the chroot root.

    For unshare-backed sessions the mount namespace lives in the helper
    process; we just close its stdin (EOF = signal to stop blocking) and
    wait for it to umount + delete the tree itself.

    For direct-mount sessions we umount each sub-mount in reverse order
    then delete the tree ourselves.
    """
    if root in _UNSHARE_PROCS:
        proc = _UNSHARE_PROCS.pop(root)
        try:
            proc.stdin.close()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        return   # helper already deleted the tree

    # Direct-mount session: unmount and clean up here.
    # Unmount in reverse dependency order.  resolv.conf and ssl/certs must
    # come before etc/alternatives (all under etc/) to avoid EBUSY.
    for subdir in ("home/user", "etc/resolv.conf", "etc/ssl/certs",
                   "etc/alternatives", "dev", "proc", "tmp", "lib64", "usr"):
        mnt = os.path.join(root, subdir)
        if os.path.isdir(mnt):
            subprocess.run([_UMOUNT_BIN, mnt],
                           capture_output=True, timeout=10)
    shutil.rmtree(root, ignore_errors=True)



class Sandbox:
    """
    Isolated execution environment for a single task session.

    Lifecycle:
      with Sandbox(task) as sb:
          sb.setup()              # runs task["setup"] script if present
          ok, out, err = sb.run(user_cmd)
          passed = sb.verify()   # runs task["verify"] function
      # __exit__ calls sb.cleanup() automatically

    Directory layout (from the subprocess's point of view):
      /home/user/    <- cwd and $HOME; the ONLY writable location
      /usr/          <- host /usr, read-only bind mount (all standard binaries)
      /bin /sbin /lib <- symlinks -> usr/...  (merged-usr compatibility)
      /lib64/        <- host /lib64, read-only (ELF interpreter)
      /tmp/          <- fresh tmpfs; discarded on cleanup
      /proc/         <- procfs
      /dev/          <- devtmpfs
      /etc/resolv.conf (ro bind) <- host DNS config; enables curl/wget/ping/dig
      /etc/ssl/certs/  (ro bind) <- host CA bundle; enables HTTPS verification

    Security model:
      * chroot(2) prevents the subprocess from accessing ANY host path that
        is not explicitly bind-mounted inside the jail.  /etc/passwd, /root,
        /home/otheruser, /var, etc. do not exist inside the sandbox.
      * All system bind mounts (/usr, /lib64) are read-only — the process
        can use every standard binary but cannot modify them.
      * The ONLY writable mount is /home/user (== self.path on the host).
        /tmp is a fresh tmpfs discarded when the sandbox is torn down.
      * A hard per-command timeout kills the subprocess on expiry.
      * A thin UI-level blocklist (_is_dangerous) rejects obviously
        destructive shell constructs before the command reaches the jail.

    The chroot root is built once in __enter__ / setup and torn down in
    cleanup / __exit__, so files created by setup() persist across run()
    calls within the same session.

    Graceful degradation:
      If neither direct-mount nor unshare-based chroot is available _exec
      falls back to legacy cwd-only mode and prints a one-time warning.
    """

    TIMEOUT = 15
    ENV_BASE = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "TERM":  "xterm-256color",
        "SHELL": "/bin/bash",
        "LANG":  "C.UTF-8",
    }

    def __init__(self, task: dict):
        self.task          = task
        self.path: str     = ""   # host-side writable work dir (self.path == /home/user inside)
        self._chroot_root  = ""   # host-side chroot root; "" when not yet built
        self._last_stdout  = ""
        self._last_stderr  = ""
        self._last_rc      = -1

    # ── context manager ────────────────────────────────────────
    def __enter__(self):
        self.path = tempfile.mkdtemp(prefix="cmdlab_")
        self._build_jail()
        return self

    def __exit__(self, *_):
        self.cleanup()

    # ── public API ─────────────────────────────────────────────
    def setup(self) -> bool:
        """Run the task's setup script inside the sandbox. Returns True on success."""
        script = self.task.get("setup", "").strip()
        if not script:
            return True
        script = script.replace("$SANDBOX", "/home/user")
        # Mark as setup so _run_fallback bypasses the classifier gate —
        # setup scripts are developer-controlled, not user input.
        self._in_setup = True
        try:
            rc, _, err = self._exec(script)
        finally:
            self._in_setup = False
        if rc != 0:
            self._last_stderr = f"[setup error rc={rc}] {err}"
        return rc == 0

    def run(self, user_cmd: str):
        """
        Execute the user's command in the sandbox.
        Returns (returncode, stdout, stderr).
        """
        dangerous, reason = _is_dangerous(user_cmd)
        if dangerous:
            return -99, "", f"BLOCKED: {reason}"

        mode = _get_sandbox_mode()
        if mode in ("chroot_direct", "chroot_unshare"):
            cmd = user_cmd.replace("$SANDBOX", "/home/user")
        else:
            cmd = user_cmd.replace("$SANDBOX", self.path)

        rc, out, err = self._exec(cmd)
        self._last_rc     = rc
        self._last_stdout = out
        self._last_stderr = err
        return rc, out, err

    def verify(self) -> tuple:
        """
        Run the task's verify function/script to check if the goal was met.
        Returns (passed: bool, message: str).

        Verify callables receive the host-side self.path so they can use
        os.path.isfile / os.listdir without needing to know about the chroot.
        """
        verify = self.task.get("verify")
        if verify is None:
            return None, "fallback"

        if callable(verify):
            try:
                result = verify(
                    self.path,
                    self._last_rc,
                    self._last_stdout,
                    self._last_stderr,
                )
                if isinstance(result, tuple):
                    return result[0], result[1] if len(result) > 1 else ""
                return bool(result), ""
            except Exception as e:
                return False, f"verify error: {e}"

        if isinstance(verify, str):
            script = verify.replace("$SANDBOX", self.path)
            rc, out, err = self._exec(script)
            return rc == 0, out.strip() or err.strip()

        return False, "unknown verify type"

    def cleanup(self):
        """Tear down the chroot jail and remove the work directory."""
        self._teardown_jail()
        if self.path and os.path.isdir(self.path):
            shutil.rmtree(self.path, ignore_errors=True)
        self.path = ""

    # ── jail lifecycle ─────────────────────────────────────────
    def _build_jail(self):
        """
        Create the chroot root with bind mounts.  Called once from __enter__.
        On failure we fall back to cwd-only mode (self._chroot_root stays "").
        """
        mode = _get_sandbox_mode()
        if mode == "chroot_direct":
            try:
                self._chroot_root = _build_chroot_root(self.path)
            except RuntimeError:
                self._chroot_root = ""  # graceful degradation
        # For chroot_unshare mode the jail is built inside each _exec call
        # (the unshare child handles setup+exec+teardown atomically).

    def _teardown_jail(self):
        """Unmount and remove the chroot root if it was built directly."""
        if self._chroot_root:
            _teardown_chroot_root(self._chroot_root)
            self._chroot_root = ""

    # ── internal executor ──────────────────────────────────────
    def _exec(self, cmd: str):
        """
        Run cmd via bash inside the appropriate isolation level.

          chroot_direct  -> already-mounted chroot root in self._chroot_root
          chroot_unshare -> new unshare child builds+runs+tears-down its own jail
          fallback       -> legacy cwd-only (warns once)
        """
        mode = _get_sandbox_mode()

        if mode == "chroot_direct":
            if self._chroot_root:
                return self._run_in_chroot(self._chroot_root, cmd)
            # Jail failed to build; fall through to fallback
        elif mode == "chroot_unshare":
            rc, out, err = self._exec_via_unshare(cmd)
            if rc != -3:   # -3 means infrastructure failure (mount/chroot failed), not a command result
                return rc, out, err
            # unshare sandbox failed to initialize (e.g. proc/devtmpfs mount denied)
            # fall through to fallback below

        # ── fallback ──────────────────────────────────────────
        global _SANDBOX_MODE_WARNED
        if not _SANDBOX_MODE_WARNED:
            _SANDBOX_MODE_WARNED = True
            sys.stderr.write(
                "\n[CommandLab] WARNING: chroot isolation is unavailable on this system.\n"
                "  Sandbox is running in reduced-security mode (cwd-only).\n"
                "  For full isolation run as root, grant CAP_SYS_ADMIN,\n"
                "  or enable unprivileged user namespaces:\n"
                "    sudo sysctl -w kernel.unprivileged_userns_clone=1\n\n"
            )
        return self._run_fallback(cmd)

    def _run_in_chroot(self, chroot_root: str, cmd: str):
        """Execute bash inside the pre-mounted chroot root."""
        env = {**self.ENV_BASE, "HOME": "/home/user", "SANDBOX": "/home/user"}
        # chroot resets the process root to /, so relative paths would resolve
        # from / rather than /home/user.  Prefix every command with a cd so
        # the working directory is the writable sandbox dir inside the jail.
        wrapped = "cd /home/user && " + cmd
        try:
            result = subprocess.run(
                [_CHROOT_BIN, chroot_root, "/bin/bash", "-c", wrapped],
                cwd=os.path.join(chroot_root, "home", "user"),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {self.TIMEOUT}s"
        except FileNotFoundError as exc:
            return -2, "", f"Executor not found: {exc}"
        except Exception as exc:
            return -3, "", str(exc)

    def _exec_via_unshare(self, cmd: str):
        """
        For unprivileged users: spawn a new user+mount namespace, build the
        chroot root inside it, run the command, and tear down — all in one
        child process.  stdout/stderr are returned via a JSON envelope on the
        last line of the child's stdout.
        """
        work    = self.path
        timeout = self.TIMEOUT
        env_json = json.dumps({**self.ENV_BASE, "HOME": "/home/user", "SANDBOX": "/home/user"})

        inner = r"""
import os, sys, json, subprocess, tempfile, shutil

work        = sys.argv[1]
cmd         = sys.argv[2]
env         = json.loads(sys.argv[3])
timeout     = int(sys.argv[4])
MOUNT_BIN   = sys.argv[5] if len(sys.argv) > 5 else "mount"
UMOUNT_BIN  = sys.argv[6] if len(sys.argv) > 6 else "umount"
CHROOT_BIN  = sys.argv[7] if len(sys.argv) > 7 else "chroot"

def mount(*args):
    r = subprocess.run([MOUNT_BIN] + list(args), capture_output=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace").strip())

def teardown(root):
    for sub in ("home/user", "etc/resolv.conf", "etc/ssl/certs",
                "etc/alternatives", "dev", "proc", "tmp", "lib64", "usr"):
        mnt = os.path.join(root, sub)
        if os.path.exists(mnt):  # covers both file and dir mounts
            subprocess.run([UMOUNT_BIN, "-l", mnt], capture_output=True, timeout=10)
    shutil.rmtree(root, ignore_errors=True)

root = tempfile.mkdtemp(prefix="cmdlab_chr_")
try:
    for d in ("usr", "lib64", "etc", "tmp", "proc", "dev", "home", "home/user"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    for lnk, tgt in (("bin","usr/bin"),("sbin","usr/sbin"),("lib","usr/lib")):
        lp = os.path.join(root, lnk)
        if not os.path.exists(lp):
            os.symlink(tgt, lp)
    mount("--bind", "-o", "ro", "/usr",  os.path.join(root, "usr"))
    if os.path.isdir("/lib64"):
        mount("--bind", "-o", "ro", "/lib64", os.path.join(root, "lib64"))
    mount("-t", "tmpfs",    "tmpfs",    os.path.join(root, "tmp"))
    mount("-t", "proc",     "proc",     os.path.join(root, "proc"))
    mount("-t", "devtmpfs", "devtmpfs", os.path.join(root, "dev"))
    etc_alt = "/etc/alternatives"
    if os.path.isdir(etc_alt):
        os.makedirs(os.path.join(root, "etc", "alternatives"), exist_ok=True)
        mount("--bind", "-o", "ro", etc_alt, os.path.join(root, "etc", "alternatives"))
    if os.path.isfile("/etc/resolv.conf"):
        dest = os.path.join(root, "etc", "resolv.conf")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "w").close()          # file mount-point
        mount("--bind", "-o", "ro", "/etc/resolv.conf", dest)
    if os.path.isdir("/etc/ssl/certs"):
        dest = os.path.join(root, "etc", "ssl", "certs")
        os.makedirs(dest, exist_ok=True) # directory mount-point
        mount("--bind", "-o", "ro", "/etc/ssl/certs", dest)
    mount("--bind", work, os.path.join(root, "home", "user"))
    try:
        wrapped = "cd /home/user && " + cmd
        r = subprocess.run(
            [CHROOT_BIN, root, "/bin/bash", "-c", wrapped],
            cwd=os.path.join(root, "home", "user"),
            env=env, capture_output=True, text=True, timeout=timeout,
        )
        result = {"rc": r.returncode, "out": r.stdout, "err": r.stderr}
    except subprocess.TimeoutExpired:
        result = {"rc": -1, "out": "", "err": f"Command timed out after {timeout}s"}
    except Exception as exc:
        result = {"rc": -3, "out": "", "err": str(exc)}
finally:
    teardown(root)

print(json.dumps(result))
"""
        try:
            r = subprocess.run(
                [
                    _UNSHARE_BIN, "--user", "--map-root-user", "--mount",
                    "python3", "-c", inner,
                    work, cmd, env_json, str(timeout),
                    _MOUNT_BIN, _UMOUNT_BIN, _CHROOT_BIN,
                ],
                capture_output=True, text=True,
                timeout=timeout + 10,
            )
            lines = r.stdout.strip().splitlines()
            for line in reversed(lines):
                try:
                    d = json.loads(line)
                    prefix = lines[:lines.index(line)]
                    extra  = "\n".join(prefix)
                    return (
                        d["rc"],
                        (extra + "\n" + d["out"]).lstrip("\n") if extra else d["out"],
                        d["err"],
                    )
                except (json.JSONDecodeError, ValueError):
                    continue
            return -3, "", r.stderr or r.stdout or "unshare execution failed"
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {self.TIMEOUT}s"
        except Exception as exc:
            return -3, "", str(exc)

    def _run_fallback(self, cmd: str):
        """Legacy cwd-only executor used when chroot is unavailable.

        SAFE/INSPECT commands execute in self.path (the session work directory)
        so that files created by setup() are visible when run() executes.
        MODIFY/CONTROL commands are blocked — no isolation is available.
        """
        # Show isolation warning once per session
        if not getattr(self, '_fallback_warning_shown', False):
            self._fallback_warning_shown = True
            print("\n[WARNING] Running without full sandbox isolation."
                  " Dangerous commands are blocked.\n")

        # Use the classifier to decide whether to execute or block.
        # Setup scripts are developer-controlled (not user input) — skip the gate.
        if not getattr(self, '_in_setup', False):
            gate = _classifier_gate(cmd)
            if gate["action"] != "allow":
                return 1, "", "Blocked in fallback mode: command modifies system state."

        # FIX C: Execute in self.path so setup() files are visible to run() commands.
        cwd = self.path if self.path and os.path.isdir(self.path) else None

        # FIX D: Background commands (&) cause the shell to return immediately, but
        # the spawned process inherits the stdout/stderr PIPE and keeps it open until
        # it exits — making communicate() wait the full lifetime of the process.
        # Fix: route background I/O to DEVNULL so there is no pipe to wait on.
        is_background = cmd.strip().endswith('&') or ' & ' in cmd
        if is_background:
            try:
                result = subprocess.run(
                    cmd, shell=True, cwd=cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                )
                return result.returncode, "", ""
            except subprocess.TimeoutExpired:
                return 0, "", ""   # shell launched the background job — treat as success
            except Exception as exc:
                return -3, "", str(exc)

        try:
            result = subprocess.run(
                cmd, shell=True, cwd=cwd,
                capture_output=True, text=True,
                timeout=self.TIMEOUT,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {self.TIMEOUT}s"
        except Exception as exc:
            return -3, "", str(exc)


def run_sandboxed_task(task: dict, user_cmd: str):
    """
    High-level entry point used by show_task().

    Returns a dict:
      {
        "mode":    "sandbox" | "keyword" | "blocked",
        "passed":  bool,
        "rc":      int,
        "stdout":  str,
        "stderr":  str,
        "message": str,   # human-readable feedback
        "checker": str,   # "text checker" | "sandbox checker"
        "clf_decision": str,  # classifier's final_decision value
      }
    """
    # ── 1. _is_dangerous pre-screen (fork bombs, disk wipes, etc.) ──
    # These are routed to text-only checking — never executed in the sandbox.
    dangerous, reason = _is_dangerous(user_cmd)
    if dangerous:
        passed, match_type = check_answer(task, user_cmd)
        return {
            "mode": "keyword", "passed": passed,
            "rc": 0, "stdout": "", "stderr": "",
            "message": match_type,
            "checker": "text checker",
            "clf_decision": "BLOCK",
        }

    # ── 2. Classifier gate ─────────────────────────────────────────
    gate = _classifier_gate(user_cmd)

    if gate["action"] == "text_only":
        # BLOCK or TEXT_ONLY decision: check by text comparison only, never run in sandbox
        passed, match_type = check_answer(task, user_cmd)
        msg = match_type
        if gate["details"]:
            msg += f"  [{gate['details']}]"
        return {
            "mode": "keyword", "passed": passed,
            "rc": 0, "stdout": "", "stderr": "",
            "message": msg,
            "checker": gate["checker"],
            "clf_decision": gate["decision"],
        }

    # ── 3. Normal execution path (SAFE_EXECUTE or SANDBOX) ─────────
    has_sandbox = bool(task.get("setup") or task.get("verify"))

    if not has_sandbox:
        # Pure keyword fallback — no sandbox needed
        passed, match_type = check_answer(task, user_cmd)
        return {
            "mode": "keyword", "passed": passed,
            "rc": 0, "stdout": "", "stderr": "",
            "message": match_type,
            "checker": gate["checker"],
            "clf_decision": gate["decision"],
        }

    with Sandbox(task) as sb:
        sb.setup()
        rc, stdout, stderr = sb.run(user_cmd)

        if rc == -99:
            # Sandbox refused to execute — fall back to text comparison
            passed, match_type = check_answer(task, user_cmd)
            return {
                "mode": "keyword", "passed": passed,
                "rc": 0, "stdout": "", "stderr": "",
                "message": match_type,
                "checker": "text checker",
                "clf_decision": "BLOCK",
            }

        passed, vmsg = sb.verify()

        if passed is None:
            # verify returned fallback signal — use keyword matching
            passed, match_type = check_answer(task, user_cmd)
            return {
                "mode": "keyword", "passed": passed,
                "rc": rc, "stdout": stdout, "stderr": stderr,
                "message": match_type,
                "checker": gate["checker"],
                "clf_decision": gate["decision"],
            }

        # Build a human-readable message from command output
        msg = ""
        if stdout.strip():
            lines = stdout.strip().splitlines()
            msg = "\n".join(f"  {C.DIM}{l}{C.RESET}" for l in lines[:8])
            if len(lines) > 8:
                msg += f"\n  {C.GRAY}... ({len(lines)-8} more lines){C.RESET}"
        if stderr.strip() and not passed:
            msg += f"\n  {C.RED}stderr: {stderr.strip()[:200]}{C.RESET}"
        if vmsg and not passed:
            msg += f"\n  {C.GRAY}{vmsg}{C.RESET}"

        return {
            "mode": "sandbox", "passed": passed,
            "rc": rc, "stdout": stdout, "stderr": stderr,
            "message": msg,
            "checker": gate["checker"],
            "clf_decision": gate["decision"],
        }

