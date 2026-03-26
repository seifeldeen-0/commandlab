import os
import sys
import glob
import json
from pathlib import Path

from commandlab.ui.colors import C
from commandlab.ui.i18n import T, task_field
from commandlab.ui.display import (
    clear, hr, progress_bar, DIFF_COLORS,
)
from commandlab.core.progress import save_progress
from commandlab.core.locks import LEVEL_ORDER, is_level_unlocked
from commandlab.data.tasks import TASKS
from commandlab.core.sandbox import run_sandboxed_task
from commandlab.engine.task_runner import show_task


# ─────────────────────────────────────────────────────────────
# EXTERNAL PLUGIN / TASK LOADER
# ─────────────────────────────────────────────────────────────
PLUGIN_TASKS = {}   # domain_name -> [task_dicts]  (loaded from tasks/*.json or tasks/*.yaml)
_PLUGIN_META = {}   # domain_name -> {name, description, author}

def _load_plugins():
    """
    Scan tasks/ directories for JSON/YAML plugin files.
    Looks in two locations:
      1. commandlab/tasks/  — built-in plugin packs shipped with the tool
      2. tasks/             — user-added custom plugins (next to the package)
    Each file must contain:
      {
        "domain": "my_domain",
        "name": "Human Name",
        "description": "...",
        "author": "...",
        "tasks": [ { same structure as built-in tasks } ]
      }
    YAML support requires PyYAML; falls back silently if unavailable.
    This function is non-destructive: built-in TASKS are never modified.
    """
    pkg_tasks_dir  = Path(__file__).parent.parent / "tasks"       # commandlab/tasks/
    root_tasks_dir = Path(__file__).parent.parent.parent / "tasks" # tasks/ (next to package)

    dirs_to_scan = [d for d in (pkg_tasks_dir, root_tasks_dir) if d.is_dir()]
    if not dirs_to_scan:
        return

    # Attempt YAML import
    try:
        import yaml as _yaml
        _has_yaml = True
    except ImportError:
        _has_yaml = False

    all_files = []
    for d in dirs_to_scan:
        all_files.extend(sorted(glob.glob(str(d / "*.json"))))
        if _has_yaml:
            all_files.extend(sorted(glob.glob(str(d / "*.yaml"))))
            all_files.extend(sorted(glob.glob(str(d / "*.yml"))))

    for filepath in all_files:
            try:
                with open(filepath, encoding="utf-8") as f:
                    if filepath.endswith(".json"):
                        import json as _json
                        data = _json.load(f)
                    else:
                        data = _yaml.safe_load(f)

                # Support both a single plugin dict {} and an array of plugins []
                entries = data if isinstance(data, list) else [data]

                for entry in entries:
                    domain = entry.get("domain", "").strip()
                    tasks  = entry.get("tasks", [])
                    if not domain or not tasks:
                        continue

                    # Assign unique IDs to avoid collision with built-in 1-100
                    base_id = 10000 + len(PLUGIN_TASKS) * 100
                    for i, t in enumerate(tasks):
                        if "id" not in t:
                            t["id"] = base_id + i
                        # Ensure required fields have defaults
                        t.setdefault("level", "easy")
                        t.setdefault("accepted", [])
                        t.setdefault("keywords", [])
                        t.setdefault("check_type", "keyword")
                        t.setdefault("setup", "")
                        t.setdefault("verify", None)
                        t.setdefault("concept", "")
                        t.setdefault("hint", "")

                    PLUGIN_TASKS[domain] = tasks
                    _PLUGIN_META[domain] = {
                        "name":        entry.get("name", domain),
                        "description": entry.get("description", ""),
                        "author":      entry.get("author", "unknown"),
                        "file":        os.path.basename(filepath),
                    }
            except Exception as e:
                # Never crash on bad plugin — just skip
                print(f"  [plugin] Warning: failed to load {filepath}: {e}",
                      file=sys.stderr)

    # Detect duplicate task IDs across all loaded plugins
    all_plugin_ids = [t["id"] for tasks in PLUGIN_TASKS.values()
                      for t in tasks if isinstance(t.get("id"), int)]
    _seen = set()
    _duplicates = set()
    for _pid in all_plugin_ids:
        if _pid in _seen:
            _duplicates.add(_pid)
        _seen.add(_pid)
    if _duplicates:
        print(f"  [plugin] Warning: duplicate task IDs detected: {_duplicates}",
              file=sys.stderr)

def get_all_domains():
    """Return built-in domains + plugin domains."""
    return {**TASKS, **PLUGIN_TASKS}

def get_domain_tasks(domain_name):
    """Return tasks for a domain (built-in or plugin)."""
    if domain_name in TASKS:
        return TASKS[domain_name]
    return PLUGIN_TASKS.get(domain_name, [])

def is_plugin_domain(domain_name):
    return domain_name in PLUGIN_TASKS


def show_plugins(progress):
    """Show plugin domain browser."""
    clear()
    print()
    print(f"  {C.BOLD}{C.PURPLE}  {T('plugins_title')}{C.RESET}\n")
    hr()
    print()

    if not PLUGIN_TASKS:
        print(f"  {C.GRAY}{T('plugins_none')}{C.RESET}")
        print(f"  {C.DIM}  Create a tasks/ directory next to the commandlab/ package")
        print(f"  and add JSON files with the task structure.{C.RESET}\n")
        print(f"  {C.DIM}  Example: tasks/my_module.json{C.RESET}\n")
        hr()
        print()
        input(f"  {C.GRAY}{T('press_enter')}{C.RESET}")
        return

    print(f"  {C.GREEN}{T('plugins_loaded', n=len(PLUGIN_TASKS))}{C.RESET}\n")
    plugin_list = list(PLUGIN_TASKS.keys())
    for i, domain in enumerate(plugin_list, 1):
        meta = _PLUGIN_META.get(domain, {})
        name = meta.get("name", domain)
        desc = meta.get("description", "")
        author = meta.get("author", "")
        n_tasks = len(PLUGIN_TASKS[domain])
        print(f"  {C.CYAN}{i}{C.RESET}. {C.BOLD}{name}{C.RESET}  {C.GRAY}({n_tasks} tasks, by {author}){C.RESET}")
        if desc:
            print(f"       {C.DIM}{desc[:70]}{C.RESET}")

    print()
    hr()
    print(f"\n  {C.GRAY}b{C.RESET}. {T('back')}\n")

    try:
        choice = input(f"  {C.GREEN}❯{C.RESET} Choose plugin (1-{len(plugin_list)}): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return

    if choice in ("b", "back", ""):
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(plugin_list):
            domain_name = plugin_list[idx]
            # Reuse existing domain menu for plugin domains
            _run_plugin_domain(domain_name, progress)
    except ValueError:
        pass

def _run_plugin_domain(domain_name: str, progress):
    """Run a plugin domain using the same task flow as built-in domains."""
    while True:
        tasks = get_domain_tasks(domain_name)
        meta  = _PLUGIN_META.get(domain_name, {})
        clear()
        done_ids = set(progress.get("completed", []))
        done = sum(1 for t in tasks if t["id"] in done_ids)
        print(f"\n  {C.PURPLE}{T('plugin_domain')}{C.RESET} {C.BOLD}{C.WHITE}{meta.get('name', domain_name).upper()}{C.RESET}  {progress_bar(done, len(tasks), width=20)}\n")
        hr()
        print()
        for i, t in enumerate(tasks, 1):
            tid = t["id"]
            marker = f"{C.GREEN}✓{C.RESET}" if tid in done_ids else f"{C.GRAY}○{C.RESET}"
            col = DIFF_COLORS.get(t.get("level", "easy"), C.WHITE)
            badge = f"{col}[{t.get('level','easy').upper()}]{C.RESET}"
            print(f"  {marker} {C.DIM}{i:2d}{C.RESET}. {badge} {C.WHITE}{t.get('title','')}{C.RESET}")
        print()
        hr()
        print(f"\n  {C.GRAY}b{C.RESET}. {T('back')}\n")
        try:
            choice = input(f"  {C.GREEN}❯{C.RESET} {T('choose_task')}: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break
        if choice in ("b", "back", ""):
            break
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(tasks):
                result = show_task(tasks[idx], domain_name, progress)
        except ValueError:
            continue


