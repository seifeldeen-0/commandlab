import sys
import datetime
import time
import random

from commandlab.ui.colors import C
from commandlab.ui import i18n as _i18n_module
from commandlab.ui.i18n import T, set_language, select_language
from commandlab.ui.display import clear, LOGO
from commandlab.ui.menus import show_main_menu, show_domain_menu, show_stats
from commandlab.data.tasks import TASKS
from commandlab.core.progress import load_progress, save_progress
from commandlab.core.locks import (
    LEVEL_ORDER, is_level_unlocked, get_level_tasks, get_domain_tasks,
)
from commandlab.plugins.loader import (
    PLUGIN_TASKS, _load_plugins, show_plugins,
)
from commandlab.engine.task_runner import show_task


# ─────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────
def main():
    # Check terminal supports ANSI
    if not sys.stdout.isatty():
        for attr in vars(C):
            if not attr.startswith("_"):
                setattr(C, attr, "")

    # ── Language selection on first run ──────────────────────
    progress = load_progress()
    if "language" not in progress:
        lang = select_language()
        progress["language"] = lang
        save_progress(progress)
    else:
        set_language(progress.get("language", "en"))

    # ── Load external plugins ────────────────────────────────
    _load_plugins()

    while True:
        choice, domain_list = show_main_menu(progress)

        # ── Quit ────────────────────────────────────────────
        if choice in ("q", "quit", "exit"):
            clear()
            print(f"\n  {C.GREEN}{T('goodbye')}{C.RESET}\n")
            sys.exit(0)

        # ── Reset progress ──────────────────────────────────
        if choice == "r":
            lang = progress.get("language", "en")
            progress = {"completed": [], "attempts": {}, "streaks": {}, "started": str(datetime.date.today()), "language": lang}
            save_progress(progress)
            print(f"\n  {C.YELLOW}{T('progress_reset')}{C.RESET}")
            time.sleep(1)
            continue

        # ── Stats ────────────────────────────────────────────
        if choice == "s":
            show_stats(progress)
            continue

        # ── Plugins ──────────────────────────────────────────
        if choice == "p":
            show_plugins(progress)
            continue

        # ── Language switch ───────────────────────────────────
        if choice == "l":
            new_lang = "ar" if _i18n_module._LANG == "en" else "en"
            set_language(new_lang)
            progress["language"] = new_lang
            save_progress(progress)
            continue

        # ── Plugin domain by number ───────────────────────────
        all_domains = list(TASKS.keys()) + list(PLUGIN_TASKS.keys())
        try:
            domain_idx = int(choice) - 1
            if domain_idx < 0 or domain_idx >= len(all_domains):
                continue
        except ValueError:
            continue

        domain_name = all_domains[domain_idx]
        tasks_for_domain = get_domain_tasks(domain_name)

        # Domain loop
        while True:
            task_choice, tasks = show_domain_menu(domain_name, progress)

            if task_choice in ("b", "back"):
                break

            if task_choice == "r":
                completed_ids = set(progress.get("completed", []))
                unlocked_undone = [
                    t for t in tasks
                    if t["id"] not in completed_ids
                    and is_level_unlocked(domain_name, t["level"], progress)
                ]
                if not unlocked_undone:
                    unlocked_undone = [
                        t for t in tasks
                        if is_level_unlocked(domain_name, t["level"], progress)
                    ]
                if unlocked_undone:
                    task = random.choice(unlocked_undone)
                else:
                    task = random.choice(tasks)
                result = show_task(task, domain_name, progress)
                continue

            try:
                task_idx = int(task_choice) - 1
                if task_idx < 0 or task_idx >= len(tasks):
                    continue
            except ValueError:
                continue

            # Enforce lock
            selected_task = tasks[task_idx]
            if not is_level_unlocked(domain_name, selected_task["level"], progress):
                clear()
                prev_level = LEVEL_ORDER[LEVEL_ORDER.index(selected_task["level"]) - 1]
                prev_tasks = get_level_tasks(domain_name, prev_level)
                completed_ids = set(progress.get("completed", []))
                remaining = [t for t in prev_tasks if t["id"] not in completed_ids]
                print(f"\n  {C.RED}{T('level_locked')}{C.RESET}")
                print(f"  {C.GRAY}{T('complete_prev', prev=prev_level.upper())}{C.RESET}")
                print(f"  {C.GRAY}{T('need_tasks', n=len(remaining), prev=prev_level.upper())}{C.RESET}\n")
                time.sleep(2)
                continue

            # Task navigation loop
            current_idx = task_idx
            while True:
                task = tasks[current_idx]
                if not is_level_unlocked(domain_name, task["level"], progress):
                    clear()
                    prev_level = LEVEL_ORDER[LEVEL_ORDER.index(task["level"]) - 1]
                    print(f"\n  {C.YELLOW}{T('next_locked', prev=prev_level.upper())}{C.RESET}\n")
                    time.sleep(2)
                    break
                result = show_task(task, domain_name, progress)

                if result == "back":
                    break
                elif result in ("next", "skip"):
                    current_idx += 1
                    if current_idx >= len(tasks):
                        clear()
                        completed_ids = set(progress.get("completed", []))
                        done = sum(1 for t in tasks if t["id"] in completed_ids)
                        if done == len(tasks):
                            print(f"\n  {C.GREEN}{T('domain_complete', domain=domain_name.upper())}{C.RESET}\n")
                        else:
                            print(f"\n  {C.CYAN}{T('domain_progress', done=done, total=len(tasks))}{C.RESET}\n")
                        time.sleep(2)
                        break
                else:
                    break


