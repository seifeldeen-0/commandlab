# CommandLab

```
  ____ ___  __  __ __  __    _    _   _ ____  _        _    ____
 / ___/ _ \|  \/  |  \/  |  / \  | \ | |  _ \| |      / \  | __ )
| |  | | | | |\/| | |\/| | / _ \ |  \| | | | | |     / _ \ |  _ \
| |__| |_| | |  | | |  | |/ ___ \| |\  | |_| | |___ / ___ \| |_) |
 \____\___/|_|  |_|_|  |_/_/   \_\_| \_|____/|_____/_/   \_\____/
  [ command-line learning toolkit ]
```

**An interactive Linux CLI learning platform with a sandboxed execution engine, intelligent command risk classification, bilingual support, and an extensible plugin system.**

---

## Overview

CommandLab is a self-contained, terminal-based learning tool written in pure Python 3 with zero external dependencies. It teaches Linux command-line skills through hands-on practice inside an isolated sandbox environment, so learners can safely run real commands without risk to the host system.

At its core, the platform combines a structured task progression system with a multi-layer security architecture that classifies every command before execution and routes it to the appropriate handler — sandbox execution, keyword verification, or a full block.

---

## Features

### Structured Learning Domains
CommandLab organizes tasks into thematic domains — **Files**, **Viewing**, **Permissions**, **Processes**, and **Networking** — each with tasks spanning four difficulty tiers:

| Tier     | Description                              |
|----------|------------------------------------------|
| Easy     | Always unlocked, foundational commands   |
| Medium   | Unlocked after completing all Easy tasks |
| Hard     | Unlocked after completing all Medium tasks |
| Insane   | Unlocked after completing all Hard tasks |

Each task includes a question, a core concept explanation, a hint, and one or more accepted answers with automated verification.

### Sandboxed Command Execution
Every user command runs inside a fully isolated chroot jail. The sandbox lifecycle is:

1. A per-task temporary working directory is created on the host.
2. A minimal chroot root is built with read-only bind mounts of `/usr`, `/lib64`, `/proc`, `/dev`, `/etc/resolv.conf`, and `/etc/ssl/certs`.
3. The task's setup script populates `/home/user` with any required files.
4. The user's command runs inside the jail with a strict timeout.
5. A custom verify function checks whether the goal was achieved.
6. The entire chroot tree is unmounted and deleted on exit.

Three isolation modes are supported with automatic detection and graceful degradation:

| Mode             | Mechanism                          | Requires                    |
|------------------|------------------------------------|-----------------------------|
| `chroot_direct`  | Direct bind mount + `chroot(2)`    | `CAP_SYS_ADMIN` or root     |
| `chroot_unshare` | Unprivileged user + mount namespace | `kernel.unprivileged_userns_clone=1` |
| `fallback`       | cwd-only, dangerous commands blocked | Nothing (reduced security) |

### Command Risk Classification
CommandLab integrates `command_classifier.py`, a standalone risk classification engine that analyzes every command string before execution. The classifier parses chained commands (`&&`, `||`, `;`, `|`) and applies a decision hierarchy:

| Risk Level | Decision      | Action                              |
|------------|---------------|-------------------------------------|
| SAFE       | SAFE_EXECUTE  | Executed in sandbox or cwd          |
| INSPECT    | SANDBOX       | Executed inside the isolated jail   |
| MODIFY     | TEXT_ONLY     | Keyword-verified only, never run    |
| CONTROL    | BLOCK         | Hard blocked, never executed        |

The classifier accounts for obfuscation patterns (`eval`, `$(...)`, backtick substitution), sensitive path access (`/proc`, `/sys`, `/dev`, `/etc/shadow`), argument-based escalation (`sed -i`, `find -exec`, `dd of=/dev/sda`), and shell interpreter invocations with arguments.

### Challenge Mode
Beyond individual tasks, CommandLab includes a **Challenge Mode** featuring multi-step situational scenarios. Each challenge presents a real-world problem that requires the learner to chain multiple commands across sequential steps, with per-step verification.

### Bilingual Interface (English / Arabic)
The entire UI is fully localized in both English and Arabic, including task titles, questions, hints, concept explanations, menus, and status messages. The language is selected on first run and stored in the progress file.

### Plugin System
CommandLab supports **external plugin packs** that extend the platform with entirely new task domains. Plugins are loaded automatically at startup from the `tasks/` directory alongside the main script.

> See [Plugin Development](#plugin-development) below for the full specification.

### Progress Tracking
Progress is persisted to a local JSON file and tracks:

- Completed task IDs per domain
- Wrong attempt counts per task (for stats and "hardest tasks" ranking)
- Tasks where the answer was revealed (marked as not counted)
- Streak information and session start date
- Language preference

### ANSI Color UI
The terminal interface uses 256-color ANSI rendering with progress bars, bordered task boxes, difficulty badges, lock icons, and classifier decision badges shown inline on each task screen.

---

## Requirements

- Python 3.8+
- Linux (required for sandbox isolation; macOS/Windows not supported)
- No external Python packages required

For full sandbox isolation, one of the following is needed:

```bash
# Option A: run as root or with CAP_SYS_ADMIN
sudo python3 commandlab.py

# Option B: enable unprivileged user namespaces (recommended for normal users)
sudo sysctl -w kernel.unprivileged_userns_clone=1
```

If neither is available, CommandLab falls back to a reduced-security mode and blocks all dangerous commands automatically.

---

## Installation

```bash
git clone https://github.com/yourname/commandlab.git
cd commandlab
python3 commandlab.py
```

Both files must be in the same directory:

```
commandlab.py          # Main application
command_classifier.py  # Risk classification engine
tasks/                 # Optional plugin directory
```

---

## Usage

Launch the tool and navigate using the number keys and shortcut letters shown in each menu:

```bash
python3 commandlab.py
```

**Main menu shortcuts:**

| Key | Action                     |
|-----|----------------------------|
| `1–5` | Enter a learning domain  |
| `c`   | Challenge Mode           |
| `p`   | Plugin Manager           |
| `s`   | View your stats          |
| `l`   | Toggle language (EN/AR)  |
| `r`   | Reset all progress       |
| `q`   | Quit                     |

**Inside a task:**

| Input     | Action                           |
|-----------|----------------------------------|
| `hint`    | Show a hint                      |
| `concept` | Show the core concept            |
| `answer`  | Reveal the answer (not counted)  |
| `skip`    | Move to the next task            |
| `b`       | Go back to the domain menu       |

---

## Plugin Development

CommandLab's plugin system allows you to ship additional task domains as standalone Python files. Plugins are discovered automatically at startup from the `tasks/` subdirectory.

### Plugin File Structure

Create a file at `tasks/my_plugin.py`. It must define a `PLUGIN` dictionary:

```python
PLUGIN = {
    "domain": "scripting",          # Domain name shown in the main menu
    "icon": "📝",                   # Emoji icon displayed next to the domain name
    "tasks": [
        {
            "id": 1001,             # Must be globally unique across all tasks
            "level": "easy",        # "easy" | "medium" | "hard" | "insane"
            "title": "Hello World",
            "question": "Print 'Hello, World!' to standard output.",
            "concept": "echo writes its arguments to stdout followed by a newline.",
            "hint": "Think about the simplest output command.",

            # Optional Arabic translations
            "title_ar": "مرحبا بالعالم",
            "question_ar": "اطبع 'Hello, World!' على المخرج القياسي.",
            "concept_ar": "الأمر echo يكتب وسيطاته على stdout متبوعة بسطر جديد.",
            "hint_ar": "فكّر في أبسط أمر للإخراج.",

            "accepted": ["echo Hello, World!", "echo 'Hello, World!'"],
            "keywords": ["echo", "Hello"],
            "check_type": "keyword",    # "keyword" | "sandbox"

            # Optional: shell script to run before the task
            "setup": "touch sample.txt",

            # Optional: callable that verifies the goal was achieved
            # Signature: verify(sandbox_path, return_code, stdout, stderr) -> (bool, str)
            "verify": lambda sb, rc, out, err: (
                "Hello" in out,
                "Output must contain 'Hello'"
            ),
        },
    ]
}
```

### Task Fields Reference

| Field        | Required | Description                                              |
|--------------|----------|----------------------------------------------------------|
| `id`         | Yes      | Unique integer ID across all tasks and plugins           |
| `level`      | Yes      | Difficulty: `easy`, `medium`, `hard`, or `insane`        |
| `title`      | Yes      | Short task title                                         |
| `question`   | Yes      | Task prompt shown to the learner                         |
| `concept`    | Yes      | Core concept explanation, shown on request               |
| `hint`       | Yes      | Hint shown on request                                    |
| `accepted`   | Yes      | List of accepted command strings for keyword matching    |
| `keywords`   | Yes      | List of substrings that must appear in the user's answer |
| `check_type` | Yes      | `"keyword"` for text matching, `"sandbox"` for execution |
| `setup`      | No       | Shell script to initialize the sandbox environment       |
| `verify`     | No       | Python callable for sandbox result verification          |
| `*_ar`       | No       | Arabic translation of any text field                     |

### How Plugins Are Loaded

At startup, CommandLab scans `tasks/*.py`, imports each file, reads its `PLUGIN` dict, and registers the domain and task list. Plugin domains appear in the main menu after the built-in domains, tagged with `[PLUGIN]`. Progress, locking, stats, and challenge mode all work identically for plugin tasks.

---

## Command Classifier API

`command_classifier.py` can be used independently of the main application:

```python
from command_classifier import classify

result = classify("ls -la && cat /etc/passwd")
print(result)               # human-readable summary
print(result.final_decision)  # Decision.SANDBOX
print(result.to_dict())     # structured dict for JSON serialisation
```

**ClassificationResult fields:**

| Field          | Type             | Description                               |
|----------------|------------------|-------------------------------------------|
| `raw_input`    | `str`            | The original command string               |
| `commands`     | `list[CommandResult]` | Per-segment breakdown              |
| `final_decision` | `Decision`     | Highest-risk decision across all segments |
| `flagged`      | `bool`           | True if obfuscation patterns were detected|

Running `python3 command_classifier.py` executes its built-in test suite of 40+ cases.

---

## Architecture

```
commandlab.py
├── Localization (T(), STRINGS)
├── Task Database (TASKS)
├── Plugin Loader (_load_plugins)
├── Command Classifier Integration (_classifier_gate)
├── Sandbox
│   ├── _detect_sandbox_mode()
│   ├── _build_chroot_root()
│   ├── Sandbox.setup()
│   ├── Sandbox.run()
│   └── Sandbox.verify()
├── Answer Checker (check_answer)
├── UI Screens
│   ├── show_main_menu()
│   ├── show_domain_menu()
│   ├── show_task()
│   ├── show_challenges()
│   ├── show_plugins()
│   └── show_stats()
└── Main Loop (main)

command_classifier.py
├── Risk (Enum: SAFE, INSPECT, MODIFY, CONTROL)
├── Decision (Enum: SAFE_EXECUTE, SANDBOX, TEXT_ONLY, BLOCK)
├── CommandClassifier
│   ├── classify(raw_input)
│   ├── _split_commands()
│   ├── _assess_risk()
│   └── _check_path_risks()
└── classify() (module-level convenience function)
```

---

## Security Notes

- The chroot jail prevents any sandboxed process from accessing host paths that are not explicitly bind-mounted.
- All system mounts inside the jail (`/usr`, `/lib64`, `/etc/resolv.conf`, `/etc/ssl/certs`) are read-only.
- The only writable location inside the jail is `/home/user`, which maps to a per-session temporary directory that is deleted after each task.
- A pre-execution blocklist (`_is_dangerous`) catches fork bombs, disk wipe patterns, and other catastrophic constructs before they reach the jail.
- The classifier's `CONTROL`-tier decision causes a hard block with no execution path of any kind.
- Plugin task `setup` scripts are developer-controlled and bypass the classifier gate. Plugin `verify` functions run on the host side with access to the sandbox work directory path.

---

## License

MIT License. See `LICENSE` for details.
