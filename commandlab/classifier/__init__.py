"""
command_classifier.py
─────────────────────
Command risk classification and execution control system for a Linux CLI
learning platform.  Assumes the user may be adversarial.

Public API
──────────
    result = classify(raw_input: str) -> ClassificationResult
    print(result)                        # human-readable summary
    result.to_dict()                     # structured dict for JSON serialisation

Decision hierarchy (highest risk wins across all chained commands):
    CONTROL  → BLOCK          (kernel / network / hardware)
    MODIFY   → TEXT_ONLY      (filesystem / package / user state changes)
    INSPECT  → SANDBOX        (process / system-level reads)
    SAFE     → SAFE_EXECUTE   (read-only, no side effects)
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class Risk(str, Enum):
    SAFE    = "SAFE"
    INSPECT = "INSPECT"
    MODIFY  = "MODIFY"
    CONTROL = "CONTROL"

    # Ordered so that max() works correctly
    def __lt__(self, other: "Risk") -> bool:
        return _RISK_ORDER[self] < _RISK_ORDER[other]

    def __gt__(self, other: "Risk") -> bool:
        return _RISK_ORDER[self] > _RISK_ORDER[other]

    def __le__(self, other: "Risk") -> bool:
        return _RISK_ORDER[self] <= _RISK_ORDER[other]

    def __ge__(self, other: "Risk") -> bool:
        return _RISK_ORDER[self] >= _RISK_ORDER[other]

_RISK_ORDER = {
    Risk.SAFE:    0,
    Risk.INSPECT: 1,
    Risk.MODIFY:  2,
    Risk.CONTROL: 3,
}

class Decision(str, Enum):
    SAFE_EXECUTE = "SAFE_EXECUTE"
    SANDBOX      = "SANDBOX"
    TEXT_ONLY    = "TEXT_ONLY"
    BLOCK        = "BLOCK"


_RISK_TO_DECISION: dict[Risk, Decision] = {
    Risk.SAFE:    Decision.SAFE_EXECUTE,
    Risk.INSPECT: Decision.SANDBOX,
    Risk.MODIFY:  Decision.TEXT_ONLY,
    Risk.CONTROL: Decision.BLOCK,
}


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge bases
# ─────────────────────────────────────────────────────────────────────────────

# Each set contains base command names OR absolute-path suffixes that map to
# a risk level.  Checked after stripping leading path components.
_SAFE_COMMANDS: frozenset[str] = frozenset({
    "ls", "ll", "la", "dir",
    "cat", "tac", "bat",
    "echo", "printf", "print",
    "grep", "egrep", "fgrep", "rg", "ag",
    "awk", "gawk", "mawk", "nawk",   # write redirects escalated in _assess_risk
    "sed",          # sed without -i is read-only
    "cut", "sort", "uniq", "tr", "paste", "join", "comm",
    "head", "tail", "wc", "nl", "od", "xxd", "hexdump",
    "diff", "cmp", "vimdiff",
    "find",         # classified higher if -exec or -delete present
    "locate", "which", "whereis", "type",
    "pwd", "cd",
    "date", "cal", "uptime", "hostname",
    "env", "printenv", "set", "export",
    "true", "false", "test", "[", "[[",
    "read",
    "less", "more",
    "file", "stat",
    "strings", "nm", "objdump", "readelf",
    "base64", "md5sum", "sha1sum", "sha256sum",
    "zip", "unzip", "tar", "gzip", "gunzip", "bzip2", "xz",  # extraction; not writing to /
    "jq", "yq",
    "man", "info", "help",
    "history",
    "alias", "unalias",
    "bc", "expr",
    "sleep",
    "xargs",        # escalated based on downstream command
    "time",
    "nohup",        # escalated based on downstream command
    "pstree", "pidof",
    "du", "df",
    "lsblk", "blkid",   # read-only disk info
})

_INSPECT_COMMANDS: frozenset[str] = frozenset({
    "ps", "pgrep", "pstree", "pidof",
    "top", "htop", "atop", "btop", "glances",
    "lsof",
    "vmstat", "iostat", "mpstat", "sar",
    "free",
    "ss", "netstat",
    "ip",           # escalated to CONTROL if modifying interfaces/routes
    "ifconfig",     # read-only usage
    "dig", "nslookup", "host", "resolvectl",
    "traceroute", "tracepath", "mtr",
    "ping",
    "arp",
    "route",        # read-only
    "strace", "ltrace",
    "ldd",
    "service",               # systemctl moved to _MODIFY_COMMANDS
    "journalctl", "dmesg",
    "uname", "lscpu", "lshw", "lspci", "lsusb",
    "sensors", "dmidecode",
    "id", "whoami", "groups", "w", "who", "last", "lastlog", "finger",
    "getfacl",
    "lsattr",
    "getent",
    "capsh",         # --print is inspect; --drop changes caps → CONTROL
    "bpftool",
    "perf",
    "ftrace",
    "auditctl", "ausearch", "aureport",
    "criu",          # dump/restore is CONTROL; inspect = INSPECT
    "nsenter",
    "unshare",
})

_MODIFY_COMMANDS: frozenset[str] = frozenset({
    # File operations
    "rm", "rmdir", "shred", "wipe",
    "mv", "rename",
    "cp",           # safe read; escalated to MODIFY because it writes
    "touch",
    "mkdir",
    "ln",
    "chmod", "chown", "chgrp",
    "chattr", "setfacl",
    "truncate",
    "tee",
    "install",
    "rsync",
    "dd",           # escalated to CONTROL if targeting /dev block device
    "split",
    # Editors (write to disk)
    "nano", "vim", "vi", "emacs", "gedit", "code", "subl",
    # Package management
    "apt", "apt-get", "apt-cache",
    "dpkg",
    "yum", "dnf", "rpm",
    "pacman", "yay", "paru",
    "snap", "flatpak",
    "pip", "pip3",
    "npm", "yarn", "pnpm",
    "cargo", "gem", "go",
    # User / group management
    "useradd", "adduser", "usermod", "userdel", "deluser",
    "groupadd", "groupmod", "groupdel",
    "passwd", "chpasswd",
    "gpasswd",
    # Service / process control
    "systemctl",
    "kill", "killall", "pkill",
    "renice",
    "nice",
    # Cron / scheduling
    "crontab",
    "at",
    # Archive / compression (write)
    "tar",          # already in SAFE for extraction; contextual check below
    "zip",
    # Misc write operations
    "tee",
    "sed",          # sed -i → MODIFY
    "logger",
    "wall", "write",
    "newgrp",
    "setcap",
    "update-alternatives",
    "ldconfig",
    "depmod", "modprobe", "rmmod", "insmod",   # → CONTROL below
    "sysctl",       # → CONTROL
    "env",          # env VAR=.. cmd → escalated contextually
    "sudo",         # always escalates downstream command
    "su",
})

_CONTROL_COMMANDS: frozenset[str] = frozenset({
    # Kernel modules
    "modprobe", "insmod", "rmmod", "depmod",
    # Block devices & filesystems
    "mount", "umount", "findmnt",
    "mkfs", "mke2fs", "mkswap", "swapon", "swapoff",
    "mkfs.ext4", "mkfs.ext3", "mkfs.xfs", "mkfs.btrfs",
    "fdisk", "gdisk", "parted", "gparted", "cfdisk",
    "losetup",
    "cryptsetup",
    # Networking – modification
    "iptables", "ip6tables", "nftables", "nft",
    "ufw", "firewall-cmd",
    "tc",                    # traffic control
    "brctl",
    "ovs-vsctl",
    "wg", "openvpn",         # VPN
    "arp",                   # -s/-d modifies ARP cache
    # Network sniffing / injection
    "tcpdump", "tshark", "wireshark", "dumpcap",
    "nc", "ncat", "netcat",
    "nmap",
    "socat",
    "hping3",
    # Kernel parameters
    "sysctl",
    # Shutdown / reboot
    "shutdown", "reboot", "poweroff", "halt", "init", "telinit",
    # chroot / namespace
    "chroot",
    "unshare",               # already in INSPECT; contextual check below
    # cgroup manipulation
    "cgcreate", "cgset", "cgexec",
    # Hardware / firmware
    "flashrom", "efibootmgr",
    # Disk wiping
    "shred",                 # already in MODIFY; block device → CONTROL
    # selinux / apparmor
    "setenforce", "aa-enforce", "aa-disable",
    # Privilege escalation wrappers
    "sudo", "su", "pkexec", "doas",
    # CRIU checkpoint/restore
    "criu",
    # Capabilities
    "setcap",                # granting caps → CONTROL
    # BPF program loading
    "bpftool",               # load/attach → CONTROL
})

# ─────────────────────────────────────────────────────────────────────────────
# Sensitive path patterns
# ─────────────────────────────────────────────────────────────────────────────

# Paths that immediately elevate risk regardless of the base command.
_PATH_RISK_RULES: list[tuple[re.Pattern, Risk, str]] = [
    # Writing to /proc/sys → kernel parameter change
    (re.compile(r"/proc/sys/"), Risk.CONTROL, "/proc/sys/ write"),
    # /proc references → at least INSPECT
    (re.compile(r"/proc/"),     Risk.INSPECT, "/proc/ access"),
    # /sys → kernel sysfs, often CONTROL
    (re.compile(r"/sys/"),      Risk.CONTROL, "/sys/ access"),
    # /dev block devices → CONTROL
    (re.compile(r"/dev/[sh]d[a-z]|/dev/nvme|/dev/vd[a-z]|/dev/xvd"),
                                Risk.CONTROL, "block device access"),
    # /dev/null, /dev/zero, /dev/urandom → safe
    (re.compile(r"/dev/(null|zero|urandom|random)$"),
                                Risk.SAFE,    "/dev special file"),
    # /etc → at least INSPECT (reading config), MODIFY if writing
    (re.compile(r"/etc/"),      Risk.INSPECT, "/etc/ access"),
    # /boot, /lib/modules → CONTROL
    (re.compile(r"(/boot/|/lib/modules/)"),
                                Risk.CONTROL, "boot/modules path"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Obfuscation / injection patterns (pre-normalisation flags)
# ─────────────────────────────────────────────────────────────────────────────

_OBFUSCATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\$\("),         "command substitution $()"),
    (re.compile(r"`"),            "backtick command substitution"),
    (re.compile(r"<\("),          "process substitution <()"),
    (re.compile(r">\("),          "process substitution >()"),
    (re.compile(r"\beval\b"),     "eval usage"),
    (re.compile(r"\bexec\b"),     "exec usage"),
    (re.compile(r"\\x[0-9a-f]{2}",re.I), "hex escape sequence"),
    (re.compile(r"\$'\\.+'"),     "ANSI-C quoting obfuscation"),
    (re.compile(r":\(\)\s*\{.*?\|.*?:\s*&"),  "fork bomb pattern"),
]

# Matches shell environment-variable assignments like FOO=bar or PATH=/usr/local/bin
_ENV_VAR_RE = re.compile(r'^[A-Z_][A-Z_0-9]*=\S*$', re.IGNORECASE)

# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CommandResult:
    """Classification result for a single parsed command token."""
    raw:            str
    normalized:     str
    base:           str
    args:           list[str]
    classification: Risk
    reason:         str = ""

    def to_dict(self) -> dict:
        return {
            "raw":            self.raw,
            "normalized":     self.normalized,
            "base":           self.base,
            "args":           self.args,
            "classification": self.classification.value,
            "reason":         self.reason,
        }


@dataclass
class ClassificationResult:
    """Aggregated result for the full user input."""
    raw_input:        str
    obfuscation_flags: list[str]
    commands:          list[CommandResult]
    highest_risk:      Risk
    final_decision:    Decision

    def to_dict(self) -> dict:
        return {
            "raw_input":         self.raw_input,
            "obfuscation_flags": self.obfuscation_flags,
            "commands":          [c.to_dict() for c in self.commands],
            "highest_risk":      self.highest_risk.value,
            "final_decision":    self.final_decision.value,
        }

    def __str__(self) -> str:
        lines = [
            f"Input       : {self.raw_input!r}",
            f"Decision    : {self.final_decision.value}",
            f"Highest risk: {self.highest_risk.value}",
        ]
        if self.obfuscation_flags:
            lines.append(f"⚠ Obfuscation: {', '.join(self.obfuscation_flags)}")
        for i, cmd in enumerate(self.commands, 1):
            lines.append(
                f"  [{i}] base={cmd.base!r:20s} risk={cmd.classification.value:8s}"
                f"  reason={cmd.reason!r}"
            )
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Core classifier
# ─────────────────────────────────────────────────────────────────────────────

class CommandClassifier:
    """
    Classifies shell command strings into risk categories and produces an
    execution decision.

    Usage
    ─────
        clf = CommandClassifier()
        result = clf.classify("ls -la /etc && cat /proc/self/maps")
        print(result)
        import json; print(json.dumps(result.to_dict(), indent=2))
    """

    # Chain-splitting pattern: &&, ||, ;, and pipe |
    _CHAIN_SPLIT = re.compile(r"&&|\|\|?|;")

    def classify(self, raw_input: str) -> ClassificationResult:
        """Main entry point. Returns a ClassificationResult."""
        obfuscation_flags = self._detect_obfuscation(raw_input)
        normalized_input  = self._normalize(raw_input)

        # ── Pipe-to-shell detection ────────────────────────────────────────
        # If any non-first segment of a bare pipe chain is a shell interpreter,
        # escalate the entire input to CONTROL immediately.
        _SHELL_INTERPRETERS = frozenset({
            "bash", "sh", "zsh", "dash", "fish",
            "python", "python3", "perl", "ruby", "node",
        })
        _pipe_parts = [p.strip() for p in re.split(r'(?<!\|)\|(?!\|)', normalized_input) if p.strip()]
        if len(_pipe_parts) > 1:
            for _part in _pipe_parts[1:]:
                _seg_base = _part.strip().split()[0].split("/")[-1].lower() if _part.strip() else ""
                if _seg_base in _SHELL_INTERPRETERS:
                    return ClassificationResult(
                        raw_input=raw_input,
                        obfuscation_flags=obfuscation_flags,
                        commands=[CommandResult(
                            raw=_part, normalized=_part, base=_seg_base,
                            args=[], classification=Risk.CONTROL,
                            reason=f"pipe-to-shell interpreter: {_seg_base}",
                        )],
                        highest_risk=Risk.CONTROL,
                        final_decision=Decision.BLOCK,
                    )

        segments          = self._split_chained(normalized_input)

        command_results: list[CommandResult] = []
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            cr = self._classify_segment(seg)
            command_results.append(cr)

        # If no commands parsed, treat as SAFE
        if not command_results:
            highest = Risk.SAFE
        else:
            highest = max(cr.classification for cr in command_results)

        # Obfuscation detected → escalate to at least INSPECT
        if obfuscation_flags and highest < Risk.INSPECT:
            highest = Risk.INSPECT

        decision = _RISK_TO_DECISION[highest]

        return ClassificationResult(
            raw_input=raw_input,
            obfuscation_flags=obfuscation_flags,
            commands=command_results,
            highest_risk=highest,
            final_decision=decision,
        )

    # ── normalisation ─────────────────────────────────────────

    @staticmethod
    def _normalize(cmd: str) -> str:
        """
        Produce a cleaned version of the input for parsing.
        - Strips leading/trailing whitespace
        - Removes $() and backtick substitutions (keeps inner content for
          downstream analysis — we do NOT want to lose path references)
        - Collapses multiple spaces
        """
        # Unwrap $(...) → keep inner text for path inspection
        cmd = re.sub(r"\$\(([^)]*)\)", r" \1 ", cmd)
        # Unwrap backticks
        cmd = re.sub(r"`([^`]*)`", r" \1 ", cmd)
        # Process substitution <(cmd) >( cmd)
        cmd = re.sub(r"[<>]\(([^)]*)\)", r" \1 ", cmd)
        # Collapse whitespace
        cmd = re.sub(r"\s+", " ", cmd).strip()
        return cmd

    # ── obfuscation detection ─────────────────────────────────

    @staticmethod
    def _detect_obfuscation(raw: str) -> list[str]:
        """Return a list of detected obfuscation technique descriptions."""
        flags: list[str] = []
        for pattern, description in _OBFUSCATION_PATTERNS:
            if pattern.search(raw):
                flags.append(description)
        return flags

    # ── chain splitting ───────────────────────────────────────

    @classmethod
    def _split_chained(cls, cmd: str) -> list[str]:
        """Split on &&, ||, ;, and |  (but keep each segment for individual analysis)."""
        return [seg.strip() for seg in cls._CHAIN_SPLIT.split(cmd) if seg.strip()]

    # ── single-segment classification ─────────────────────────

    def _classify_segment(self, segment: str) -> CommandResult:
        """Classify one command segment (no chain operators present)."""
        base, args = self._parse_segment(segment)
        risk, reason = self._assess_risk(base, args, segment)
        return CommandResult(
            raw=segment,
            normalized=segment,
            base=base,
            args=args,
            classification=risk,
            reason=reason,
        )

    # ── parsing ───────────────────────────────────────────────

    @staticmethod
    def _parse_segment(segment: str) -> tuple[str, list[str]]:
        """
        Extract the base command name and argument list.
        Handles absolute/relative paths (e.g. /bin/rm → rm).
        Falls back to simple split on shlex failure.
        """
        try:
            tokens = shlex.split(segment)
        except ValueError:
            tokens = segment.split()

        if not tokens:
            return "", []

        # Strip leading VAR=value prefix tokens (e.g. PATH=/evil ls → ls)
        while len(tokens) > 1 and _ENV_VAR_RE.match(tokens[0]):
            tokens = tokens[1:]

        # Strip leading path components: /usr/bin/cat → cat
        raw_base = tokens[0]
        base = raw_base.split("/")[-1].lower()

        # Handle "sudo command" → treat 'command' as the effective base for
        # risk, but mark the whole thing as CONTROL (handled in _assess_risk)
        return base, tokens[1:]

    # ── risk assessment ───────────────────────────────────────

    def _assess_risk(
        self, base: str, args: list[str], full_segment: str
    ) -> tuple[Risk, str]:
        """
        Determine the Risk level for a single command.
        Returns (Risk, human-readable reason string).
        """
        # ── 1. Absolute highest-priority: sudo / su / pkexec ─
        if base in ("sudo", "su", "pkexec", "doas"):
            # Escalate the *downstream* command too, but the wrapper itself
            # is CONTROL because it grants root.
            return Risk.CONTROL, f"privilege escalation wrapper: {base}"

        # ── 2. CONTROL command list check ─────────────────────
        if base in _CONTROL_COMMANDS:
            # Special case: 'ip' in read-only mode
            if base == "ip" and args and args[0] in ("addr", "a", "route", "r", "link", "neigh"):
                if not any(a in args for a in ("add", "del", "set", "flush", "change")):
                    return Risk.INSPECT, "ip read-only subcommand"
            # Special case: 'arp' without -s/-d
            if base == "arp" and not any(a in ("-s", "-d", "--set", "--delete") for a in args):
                return Risk.INSPECT, "arp table read"
            # Special case: 'bpftool' prog list → INSPECT
            if base == "bpftool" and args and args[0] in ("prog",) and (len(args) < 2 or args[1] in ("list", "show")):
                return Risk.INSPECT, "bpftool read-only"
            return Risk.CONTROL, f"control-tier command: {base}"

        # ── 3. MODIFY command list check ──────────────────────
        if base in _MODIFY_COMMANDS:
            # sed without -i is safe
            if base == "sed" and not any(a.startswith("-i") for a in args):
                return Risk.SAFE, "sed without -i (read-only)"
            # cp is a write operation
            if base == "cp":
                return Risk.MODIFY, "cp writes to destination"
            # tar: read (x/t) vs write (c/r/u)
            if base == "tar":
                mode_flags = "".join(a.lstrip("-") for a in args if a.startswith("-") or (args and a == args[0]))
                if any(f in mode_flags for f in ("c", "r", "u")):
                    return Risk.MODIFY, "tar create/update mode"
                return Risk.SAFE, "tar extract/list mode"
            # systemctl start/stop/enable/disable/restart → MODIFY
            if base == "systemctl":
                modify_verbs = {"start","stop","restart","reload","enable","disable","mask","unmask","daemon-reload"}
                if args and args[0].lower() in modify_verbs:
                    return Risk.MODIFY, f"systemctl {args[0]} modifies service state"
                return Risk.INSPECT, "systemctl read-only subcommand"
            # kill / pkill → MODIFY (changes process state)
            if base in ("kill", "killall", "pkill"):
                return Risk.MODIFY, "sends signal to process"
            # dd: if targeting block device → CONTROL (handled below via path)
            if base == "dd":
                for a in args:
                    if a.startswith("of=") and re.search(r"/dev/[sh]d[a-z]|/dev/nvme|/dev/vd", a):
                        return Risk.CONTROL, "dd to block device"
                return Risk.MODIFY, "dd write operation"
            # rm with recursive flag targeting root or core system paths → CONTROL
            if base == "rm":
                _has_recursive = any(
                    a in ("-r", "-rf", "-fr", "--recursive")
                    or (a.startswith("-") and not a.startswith("--") and "r" in a)
                    for a in args
                )
                _system_paths = {"/", "/*", "/bin", "/usr", "/etc", "/lib", "/lib64", "/sbin", "/boot"}
                _targets_system = any(a in _system_paths for a in args)
                if _has_recursive and _targets_system:
                    return Risk.CONTROL, "recursive delete of system path"
            return Risk.MODIFY, f"modify-tier command: {base}"

        # ── 4. INSPECT command list check ─────────────────────
        if base in _INSPECT_COMMANDS:
            # ip: escalate mutating subcommands to CONTROL
            if base == "ip" and len(args) >= 1:
                subcmd = args[0].lower()
                verb = args[1].lower() if len(args) >= 2 else ""
                if subcmd == "netns" and verb in ("add", "del"):
                    return Risk.CONTROL, f"ip netns {verb} modifies network namespace"
                if subcmd == "link" and verb in ("add", "del", "set"):
                    return Risk.CONTROL, f"ip link {verb} modifies network interface"
            return Risk.INSPECT, f"inspect-tier command: {base}"

        # ── 5. SAFE command list check ────────────────────────
        if base in _SAFE_COMMANDS:
            # find with dangerous flags → elevate
            if base == "find":
                danger_flags = {"-exec", "-execdir", "-delete", "-ok"}
                if any(f in args for f in danger_flags):
                    return Risk.MODIFY, "find with -exec/-delete"
            # For safe commands that accept file/path arguments, still check
            # whether those paths are sensitive — cat /proc/self/maps is INSPECT
            path_risk, path_reason = self._check_path_risks(full_segment)
            if path_risk and path_risk > Risk.SAFE:
                return path_risk, path_reason
            return Risk.SAFE, f"safe read-only command: {base}"

        # ── 6. Sensitive path analysis ────────────────────────
        # Even if the base command is unknown, arguments referencing sensitive
        # paths escalate the risk.
        path_risk, path_reason = self._check_path_risks(full_segment)
        if path_risk:
            return path_risk, path_reason

        # ── 7. Unknown command — treat conservatively ─────────
        # Redirect to a sensitive path (e.g. echo 1 > /proc/sys/...)
        # The path risk check covers the destination of the redirect.
        path_risk, path_reason = self._check_path_risks(full_segment)
        if path_risk and path_risk > Risk.SAFE:
            return path_risk, path_reason

        # Redirect-to-file (> or >>) implies writing
        if re.search(r"(?<![<>])>{1,2}(?![>])\s*\S", full_segment):
            return Risk.MODIFY, "output redirection (writes to file)"

        # Shell interpreters (python, node, bash) are INSPECT by default
        # because they can do anything; promote to CONTROL to be safe when
        # there's a script argument.
        if base in ("python", "python3", "python2", "perl", "ruby", "node",
                    "bash", "sh", "zsh", "dash", "fish"):
            if args:
                return Risk.CONTROL, f"script interpreter {base} with arguments"
            return Risk.INSPECT, f"interactive interpreter: {base}"

        # Default for completely unknown commands
        return Risk.INSPECT, f"unknown command '{base}' — treated as INSPECT"

    # ── path risk checker ──────────────────────────────────────

    @staticmethod
    def _check_path_risks(segment: str) -> tuple[Optional[Risk], str]:
        """
        Scan the full segment for sensitive path patterns.
        Returns (Risk, reason) or (None, "") if no sensitive paths found.
        """
        highest_risk: Optional[Risk] = None
        reason = ""

        for pattern, risk, desc in _PATH_RISK_RULES:
            if pattern.search(segment):
                if highest_risk is None or risk > highest_risk:
                    highest_risk = risk
                    reason = f"sensitive path: {desc}"

        return highest_risk, reason


# ─────────────────────────────────────────────────────────────────────────────
# Module-level convenience function
# ─────────────────────────────────────────────────────────────────────────────

_default_classifier = CommandClassifier()

def classify(raw_input: str) -> ClassificationResult:
    """
    Classify a raw user command string.

    Parameters
    ──────────
    raw_input : str
        The command as typed by the user.

    Returns
    ───────
    ClassificationResult
        Contains per-command breakdown and the overall final_decision.
    """
    return _default_classifier.classify(raw_input)


# ─────────────────────────────────────────────────────────────────────────────
# Self-contained test suite  (run with: python command_classifier.py)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    TEST_CASES: list[tuple[str, Decision]] = [
        # ── SAFE_EXECUTE ──────────────────────────────────────
        ("ls -la",                          Decision.SAFE_EXECUTE),
        ("grep -i error system.log",        Decision.SAFE_EXECUTE),
        ("cat readme.txt",                  Decision.SAFE_EXECUTE),
        ("echo hello world",                Decision.SAFE_EXECUTE),
        ("wc -l data.csv",                  Decision.SAFE_EXECUTE),
        ("awk '{print $3}' stats.txt",      Decision.SAFE_EXECUTE),
        ("head -n 5 access.log",            Decision.SAFE_EXECUTE),
        ("sed 's/foo/bar/g' config.txt",    Decision.SAFE_EXECUTE),   # no -i
        ("diff <(ls /etc) <(ls /usr/lib)",  Decision.SANDBOX),    # /etc in substitution → INSPECT
        # ── SANDBOX ───────────────────────────────────────────
        ("ps aux",                          Decision.SANDBOX),
        ("lsof -p $$",                      Decision.SANDBOX),
        ("ss -tulpn",                       Decision.SANDBOX),
        ("cat /proc/self/maps",             Decision.SANDBOX),
        ("cat /etc/passwd",                 Decision.SANDBOX),
        ("dig github.com",                  Decision.SANDBOX),
        ("strace ls",                       Decision.SANDBOX),
        ("ip addr",                         Decision.SANDBOX),
        ("ping -c 4 google.com",            Decision.SANDBOX),
        # ── TEXT_ONLY ─────────────────────────────────────────
        ("chmod 640 secret.key",            Decision.TEXT_ONLY),
        ("chown alice:finance report.pdf",  Decision.TEXT_ONLY),
        ("rm -rf /tmp/testdir",             Decision.TEXT_ONLY),
        ("mv new.conf app.conf",            Decision.TEXT_ONLY),
        ("touch notes.txt",                 Decision.TEXT_ONLY),
        ("ln -s v2.1 current",              Decision.TEXT_ONLY),
        ("sed -i 's/localhost/127.0.0.1/g' config.txt",  Decision.TEXT_ONLY),
        ("kill 4567",                       Decision.TEXT_ONLY),
        ("apt-get update",                  Decision.TEXT_ONLY),
        ("cp report.txt backup/",           Decision.TEXT_ONLY),
        # ── BLOCK ─────────────────────────────────────────────
        ("sudo apt update",                 Decision.BLOCK),
        ("iptables -A INPUT -p tcp --dport 8080 -j DROP", Decision.BLOCK),
        ("echo 1 > /proc/sys/net/ipv4/ip_forward",        Decision.BLOCK),
        ("mount /dev/sda1 /mnt",            Decision.BLOCK),
        ("tcpdump -i eth0 tcp port 443",    Decision.BLOCK),
        ("nc -zv 192.168.1.100 22",         Decision.BLOCK),
        ("shutdown -h now",                 Decision.BLOCK),
        ("dd if=/dev/zero of=/dev/sda",     Decision.BLOCK),
        ("chroot /mnt/newroot bash",        Decision.BLOCK),
        ("python3 server.py",               Decision.BLOCK),   # interpreter + args
        # ── chained commands ──────────────────────────────────
        ("ls && cat /etc/passwd",           Decision.SANDBOX),     # highest = INSPECT
        ("touch x && chmod 600 x",         Decision.TEXT_ONLY),   # highest = MODIFY
        ("ls | grep foo",                  Decision.SAFE_EXECUTE),
        ("ls && sudo rm -rf /",            Decision.BLOCK),        # sudo → CONTROL
        # ── obfuscation ───────────────────────────────────────
        ("$(ls)",                           Decision.SANDBOX),     # obfuscation → INSPECT
        ("`cat /etc/shadow`",               Decision.SANDBOX),
        ("eval 'rm -rf /'",                Decision.SANDBOX),     # obfuscation flag
    ]

    clf = CommandClassifier()
    passed = 0
    failed = 0

    print("=" * 72)
    print(f"  CommandClassifier — test suite ({len(TEST_CASES)} cases)")
    print("=" * 72)

    for cmd, expected in TEST_CASES:
        result = clf.classify(cmd)
        ok = result.final_decision == expected
        symbol = "✓" if ok else "✗"
        if ok:
            passed += 1
        else:
            failed += 1
        status = f"got {result.final_decision.value}" if not ok else result.final_decision.value
        print(f"  {symbol} [{status:14s}]  {cmd!r}")
        if not ok:
            print(f"      expected: {expected.value}")
            for c in result.commands:
                print(f"      └─ base={c.base!r} risk={c.classification.value} reason={c.reason!r}")

    print("=" * 72)
    print(f"  Results: {passed} passed, {failed} failed out of {len(TEST_CASES)}")
    print("=" * 72)

    # Pretty-print one example
    print()
    print("── Example structured output ────────────────────────────────────────")
    example = clf.classify("ls -la && cat /proc/self/maps | grep heap")
    print(json.dumps(example.to_dict(), indent=2))
