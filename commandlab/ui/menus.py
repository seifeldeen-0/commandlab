from commandlab.ui.colors import C
from commandlab.ui.i18n import T, task_field
from commandlab.ui.display import (
    clear, hr, LOGO, DIFF_COLORS, DOMAIN_ICONS,
    progress_bar, diff_badge,
)
from commandlab.data.tasks import TASKS
from commandlab.core.locks import LEVEL_ORDER, is_level_unlocked, get_level_tasks


def _get_plugin_data():
    """Lazy import of PLUGIN_TASKS and _PLUGIN_META to avoid circular imports."""
    try:
        from commandlab.plugins.loader import PLUGIN_TASKS, _PLUGIN_META
        return PLUGIN_TASKS, _PLUGIN_META
    except ImportError:
        return {}, {}


# ─────────────────────────────────────────────────────────────
# DOMAIN STATS
# ─────────────────────────────────────────────────────────────
def domain_stats(domain_name, progress):
    PLUGIN_TASKS, _PLUGIN_META = _get_plugin_data()
    tasks = TASKS.get(domain_name) or PLUGIN_TASKS.get(domain_name, [])
    completed_ids = set(progress.get("completed", []))
    done = sum(1 for t in tasks if t["id"] in completed_ids)
    total = len(tasks)
    by_level = {}
    for t in tasks:
        lvl = t["level"]
        if lvl not in by_level:
            by_level[lvl] = {"done": 0, "total": 0, "unlocked": is_level_unlocked(domain_name, lvl, progress)}
        by_level[lvl]["total"] += 1
        if t["id"] in completed_ids:
            by_level[lvl]["done"] += 1
    return done, total, by_level


# ─────────────────────────────────────────────────────────────
# SCREENS
# ─────────────────────────────────────────────────────────────
def show_main_menu(progress):
    clear()
    print(LOGO)
    completed_ids = set(progress.get("completed", []))
    total_tasks = sum(len(v) for v in TASKS.values())
    total_done = len(completed_ids)

    print(f"  {C.BOLD}{T('total_progress')}:{C.RESET}  {progress_bar(total_done, total_tasks, width=28)}")
    print()

    hr()
    print(f"\n  {C.BOLD}{C.WHITE}{T('domains')}{C.RESET}\n")

    domain_list = list(TASKS.keys())
    for i, domain in enumerate(domain_list, 1):
        icon = DOMAIN_ICONS[domain]
        done, total, _ = domain_stats(domain, progress)
        bar = progress_bar(done, total, width=18)
        locked = done == 0 and total_done == 0 and i > 1
        status = f"{C.GRAY}[{T('locked_level')}]{C.RESET}" if locked else bar
        print(f"  {C.CYAN}{i}{C.RESET}. {icon} {C.BOLD}{domain.upper():14s}{C.RESET}  {status}")

    # Plugin domains
    PLUGIN_TASKS, _PLUGIN_META = _get_plugin_data()
    for i, (domain, tasks) in enumerate(PLUGIN_TASKS.items(), len(domain_list) + 1):
        meta = _PLUGIN_META.get(domain, {})
        done = sum(1 for t in tasks if t["id"] in completed_ids)
        total = len(tasks)
        bar = progress_bar(done, total, width=18)
        print(f"  {C.CYAN}{i}{C.RESET}. 🔌 {C.BOLD}{meta.get('name', domain).upper():14s}{C.RESET}  {bar}  {C.GRAY}[plugin]{C.RESET}")

    print()
    hr()

    # Extra menu row
    print(f"\n  {C.PURPLE}p{C.RESET}. 🔌 {T('plugins')}"
          f"    {C.CYAN}l{C.RESET}. 🌐 {T('language')}")
    print(f"\n  {C.GRAY}s{C.RESET}. {T('stats')}    {C.GRAY}r{C.RESET}. {T('reset')}    {C.GRAY}q{C.RESET}. {T('quit')}\n")

    choice = input(f"  {C.GREEN}❯{C.RESET} {T('choose_domain')}: ").strip().lower()
    return choice, domain_list

def show_domain_menu(domain_name, progress):
    clear()
    icon = DOMAIN_ICONS.get(domain_name, "🔌")
    completed_ids = set(progress.get("completed", []))
    done, total, by_level = domain_stats(domain_name, progress)

    print(f"\n  {icon} {C.BOLD}{C.WHITE}{domain_name.upper()}{C.RESET}  {progress_bar(done, total, width=24)}\n")
    hr()
    print()

    # Level summary with lock icons
    for level in LEVEL_ORDER:
        if level in by_level:
            s = by_level[level]
            col = DIFF_COLORS[level]
            unlocked = s["unlocked"]
            if unlocked:
                bar = progress_bar(s["done"], s["total"], width=12, color=col)
                lock_icon = f"{C.GREEN}🔓{C.RESET}" if s["done"] == s["total"] else f"  "
                print(f"  {lock_icon} {col}{level.upper():8s}{C.RESET}  {bar}")
            else:
                prev = LEVEL_ORDER[LEVEL_ORDER.index(level) - 1]
                prev_s = by_level.get(prev, {})
                remaining = prev_s.get("total", 0) - prev_s.get("done", 0)
                lock_msg = T("complete_first", prev=prev.upper(), n=remaining)
                print(f"  🔒 {C.GRAY}{level.upper():8s}  {T('locked_level')} — {lock_msg}{C.RESET}")

    print()
    hr()
    print(f"\n  {C.BOLD}{T('tasks')}{C.RESET}\n")

    PLUGIN_TASKS, _PLUGIN_META = _get_plugin_data()
    tasks = TASKS.get(domain_name, PLUGIN_TASKS.get(domain_name, []))
    current_level = None
    for t in tasks:
        tid = t["id"]
        lvl = t["level"]
        unlocked = is_level_unlocked(domain_name, lvl, progress)

        if lvl != current_level:
            current_level = lvl
            col = DIFF_COLORS.get(lvl, C.WHITE)
            if unlocked:
                print(f"\n  {col}── {lvl.upper()} ──────────────────────────────────────────{C.RESET}")
            else:
                print(f"\n  {C.GRAY}── {lvl.upper()} ──────────────────────────────────── 🔒 {T('locked_level')}{C.RESET}")

        local_num = tasks.index(t) + 1

        if not unlocked:
            print(f"  {C.GRAY}  {local_num:2d}. 🔒 {task_field(t, 'title')}{C.RESET}")
        else:
            done_marker = f"{C.GREEN}✓{C.RESET}" if tid in completed_ids else f"{C.GRAY}○{C.RESET}"
            attempts = progress.get("attempts", {}).get(str(tid), 0)
            att_str = f" {C.GRAY}({attempts}✗){C.RESET}" if attempts > 0 and tid not in completed_ids else ""
            print(f"  {done_marker} {C.DIM}{local_num:2d}{C.RESET}. {C.WHITE}{task_field(t, 'title')}{C.RESET}{att_str}")

    print()
    hr()
    print(f"\n  {C.GRAY}b{C.RESET}. {T('back')}    {C.GRAY}r{C.RESET}. {T('random_task')}\n")

    choice = input(f"  {C.GREEN}❯{C.RESET} {T('choose_task')}: ").strip().lower()
    return choice, tasks

def show_stats(progress):
    clear()
    print()
    print(f"  {C.BOLD}{C.WHITE}{T('your_stats')}{C.RESET}\n")
    hr()
    print()

    completed_ids = set(progress.get("completed", []))
    revealed_ids  = set(progress.get("revealed", []))
    total = sum(len(v) for v in TASKS.values())
    done = len(completed_ids)

    print(f"  {C.BOLD}{T('total')}{C.RESET}  {progress_bar(done, total, width=30)}")
    if revealed_ids:
        print(f"  {C.ORANGE}{T('revealed_count')} {len(revealed_ids)}{C.RESET}")
    print()

    for domain in TASKS:
        d, t, by_level = domain_stats(domain, progress)
        icon = DOMAIN_ICONS[domain]
        print(f"  {icon} {domain.upper():14s}  {progress_bar(d, t, width=20)}")
        for level in LEVEL_ORDER:
            if level in by_level:
                s = by_level[level]
                col = DIFF_COLORS[level]
                unlocked = s["unlocked"]
                lock_str = "" if unlocked else f"  {C.GRAY}🔒 {T('locked_level')}{C.RESET}"
                rev = sum(1 for t2 in TASKS[domain] if t2["level"] == level and t2["id"] in revealed_ids)
                rev_str = f"  {C.ORANGE}({rev} revealed){C.RESET}" if rev > 0 else ""
                print(f"       {col}{level:8s}{C.RESET}  {s['done']}/{s['total']}{rev_str}{lock_str}")
        print()

    # Plugin stats
    PLUGIN_TASKS, _PLUGIN_META = _get_plugin_data()
    for domain, tasks in PLUGIN_TASKS.items():
        meta = _PLUGIN_META.get(domain, {})
        d = sum(1 for t in tasks if t["id"] in completed_ids)
        t = len(tasks)
        print(f"  🔌 {meta.get('name', domain)[:14]:14s}  {progress_bar(d, t, width=20, color=C.PURPLE)}")
    if PLUGIN_TASKS:  # noqa: F821 — assigned above in this function
        print()

    # Attempts info
    attempts = progress.get("attempts", {})
    if attempts:
        total_wrong = sum(attempts.values())
        print(f"  {C.GRAY}{T('wrong_attempts')} {total_wrong}{C.RESET}")
        hardest = sorted(attempts.items(), key=lambda x: x[1], reverse=True)[:3]
        if hardest:
            print(f"  {C.GRAY}{T('hardest_tasks')}{C.RESET}")
            for tid, count in hardest:
                for domain_tasks in TASKS.values():
                    for t in domain_tasks:
                        if str(t["id"]) == str(tid):
                            print(f"    #{t['id']} {task_field(t, 'title')} — {count} wrong attempts")
    print()
    hr()
    print()
    input(f"  {C.GRAY}{T('press_enter')}{C.RESET}")


