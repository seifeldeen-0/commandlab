import textwrap
import time

from commandlab.ui.colors import C
from commandlab.ui.i18n import T, task_field
from commandlab.ui.display import (
    clear, hr, box, diff_badge, progress_bar,
    DIFF_COLORS, DOMAIN_ICONS,
)
from commandlab.core.progress import save_progress
from commandlab.core.locks import LEVEL_ORDER, is_level_unlocked
from commandlab.core.sandbox import (
    run_sandboxed_task, _CLASSIFIER_OK, _classifier_gate,
)


# ─────────────────────────────────────────────────────────────
# TASK RUNNER
# ─────────────────────────────────────────────────────────────
def show_task(task, domain_name, progress):
    completed_ids = set(progress.get("completed", []))
    already_done = task["id"] in completed_ids
    level = task["level"]
    diff_color = DIFF_COLORS.get(level, C.WHITE)
    has_sandbox = bool(task.get("setup") is not None or task.get("verify") is not None)

    # Enforce level lock
    if not is_level_unlocked(domain_name, level, progress):
        clear()
        print(f"\n  {C.RED}{T('level_locked')}{C.RESET}")
        prev_level = LEVEL_ORDER[LEVEL_ORDER.index(level)-1] if level in LEVEL_ORDER and LEVEL_ORDER.index(level) > 0 else level
        print(f"  {C.GRAY}{T('complete_prev', prev=prev_level.upper())}{C.RESET}\n")
        time.sleep(2)
        return "back"

    clear()
    print()

    icon = DOMAIN_ICONS.get(domain_name, "🔌")
    status_str = f"{C.GREEN}[COMPLETED]{C.RESET}" if already_done else ""
    mode_badge = (f"  {C.CYAN}[SANDBOX]{C.RESET}" if has_sandbox else f"  {C.GRAY}[KEYWORD]{C.RESET}")

    # ── Classifier preview badge ──────────────────────────────
    # Show what the classifier would say about the task's primary accepted answer
    # so the player knows up-front whether it's a text checker or sandbox checker.
    _clf_badge = ""
    if _CLASSIFIER_OK and task.get("accepted"):
        _sample_cmd = task["accepted"][0]
        _gate = _classifier_gate(_sample_cmd)
        _decision_label = _gate["decision"]
        _checker_label  = _gate["checker"]
        if _checker_label == "text checker":
            _clf_badge = f"  {C.YELLOW}[TEXT CHECKER · {_decision_label}]{C.RESET}"
        else:
            _clf_badge = f"  {C.CYAN}[SANDBOX CHECKER · {_decision_label}]{C.RESET}"

    print(f"  {icon} Task #{task['id']}  {diff_badge(level)}{mode_badge}{_clf_badge}  {status_str}")
    print()

    box([
        f"{C.BOLD}{C.WHITE}{task_field(task, 'title')}{C.RESET}",
        "",
        *[f"{C.WHITE}{line}{C.RESET}" for line in textwrap.wrap(task_field(task, "question"), width=78)],
    ], color=diff_color)

    if has_sandbox and task.get("setup", "").strip():
        print()
        print(f"  {C.CYAN}🔬 {T('sandbox_env')}{C.RESET}")
        setup_lines = [l.strip() for l in task["setup"].split("&&") if l.strip()]
        for sl in setup_lines[:3]:
            print(f"     {C.DIM}$ {sl}{C.RESET}")
        if len(setup_lines) > 3:
            print(f"     {C.DIM}... (+{len(setup_lines)-3} more){C.RESET}")

    print()

    hint_shown = False
    answer_revealed = False
    attempts = 0

    while True:
        if answer_revealed:
            print(f"  {C.DIM}{T('practice_prompt')}{C.RESET}")
        else:
            print(f"  {C.DIM}{T('commands_help')}{C.RESET}")
        print()

        try:
            answer = input(f"  {C.GREEN}$ {C.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return "back"

        if not answer:
            continue
        if answer.lower() in ("b", "back"):
            return "back"
        if answer.lower() == "skip":
            return "skip"

        # HINT
        if answer.lower() == "hint":
            if not hint_shown:
                print()
                print(f"  {C.YELLOW}{T('hint_label')}{C.RESET}  {C.WHITE}{task_field(task, 'hint')}{C.RESET}")
                print()
                hint_shown = True
            else:
                print()
                print(f"  {C.YELLOW}{T('hint_more')}{C.RESET}")
                print()
            continue

        # CONCEPT
        if answer.lower() == "concept":
            print()
            print(f"  {C.PURPLE}{T('concept_label')}{C.RESET}")
            for line in textwrap.wrap(task_field(task, "concept"), width=78):
                print(f"     {C.WHITE}{line}{C.RESET}")
            print()
            continue

        # ANSWER REVEAL
        if answer.lower() == "answer":
            print()
            print(f"  {C.ORANGE}{'─' * 60}{C.RESET}")
            print(f"  {C.ORANGE}{T('answer_revealed')}{C.RESET}")
            print(f"  {C.ORANGE}{'─' * 60}{C.RESET}")
            print()
            print(f"  {C.BOLD}{C.WHITE}{T('answer_label')}{C.RESET}")
            for i, acc in enumerate(task["accepted"], 1):
                marker = f"{C.CYAN}${C.RESET}" if i == 1 else f"{C.GRAY}or${C.RESET}"
                print(f"     {marker} {C.BOLD}{acc}{C.RESET}")
            print()
            print(f"  {C.PURPLE}{T('concept_label')}{C.RESET}")
            for line in textwrap.wrap(task_field(task, "concept"), width=78):
                print(f"     {C.DIM}{line}{C.RESET}")
            print()
            print(f"  {C.ORANGE}{'─' * 60}{C.RESET}")

            if "revealed" not in progress:
                progress["revealed"] = []
            if task["id"] not in progress["revealed"]:
                progress["revealed"].append(task["id"])
            if task["id"] in progress.get("completed", []):
                progress["completed"].remove(task["id"])
            save_progress(progress)

            answer_revealed = True
            print()
            try:
                next_action = input(f"  {C.GRAY}{T('next_task_prompt')}{C.RESET} ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return "back"
            if next_action in ("n", "next"):
                return "next"
            elif next_action in ("b", "back"):
                return "back"
            print()
            continue

        # SANDBOX / KEYWORD CHECK
        attempts += 1
        if has_sandbox:
            print(f"  {C.DIM}{T('running_sandbox')}{C.RESET}", end="\r")

        result = run_sandboxed_task(task, answer)

        if has_sandbox:
            print(" " * 40, end="\r")

        if "attempts" not in progress:
            progress["attempts"] = {}
        if str(task["id"]) not in progress["attempts"]:
            progress["attempts"][str(task["id"])] = 0
        if not result["passed"]:
            progress["attempts"][str(task["id"])] += 1
            save_progress(progress)

        correct = result["passed"]
        mode = result["mode"]
        checker_label = result.get("checker", "sandbox checker")
        clf_decision  = result.get("clf_decision", "")

        # BLOCKED
        if mode == "blocked":
            print()
            checker_label = result.get("checker", "text checker")
            clf_dec = result.get("clf_decision", "")
            clf_info = f"  {C.GRAY}[{checker_label.upper()} · {clf_dec}]{C.RESET}" if clf_dec else ""
            print(f"  {C.RED}{T('blocked')} {result['message']}{C.RESET}{clf_info}")
            print(f"  {C.GRAY}{T('not_permitted')}{C.RESET}")
            print()
            continue

        # CORRECT
        if correct:
            print()
            print(f"  {C.GREEN}{'─' * 60}{C.RESET}")

            if answer_revealed:
                print(f"  {C.YELLOW}{T('correct_revealed')}{C.RESET}")
                print(f"  {C.GRAY}{T('peek_note')}{C.RESET}")
            elif already_done:
                print(f"  {C.GREEN}{T('already_done')}{C.RESET}")
            else:
                if mode == "sandbox":
                    print(f"  {C.GREEN}{T('correct_sandbox')}{C.RESET}  {C.CYAN}[{checker_label.upper()}]{C.RESET}")
                else:
                    print(f"  {C.GREEN}{T('correct_keyword')}{C.RESET}  {C.YELLOW}[{checker_label.upper()}]{C.RESET}")
                progress["completed"].append(task["id"])
                if "revealed" in progress and task["id"] in progress["revealed"]:
                    progress["revealed"].remove(task["id"])
                save_progress(progress)

                for lvl in LEVEL_ORDER:
                    if not is_level_unlocked(domain_name, lvl, progress):
                        if is_level_unlocked(domain_name, lvl, progress):
                            print()
                            print(f"  {C.BOLD}{C.GREEN}{T('unlocked', level=lvl.upper())}{C.RESET}")
                        break

            if mode == "sandbox" and result["message"].strip():
                print()
                print(f"  {C.DIM}{T('cmd_output')}{C.RESET}")
                print(result["message"])

            print()
            print(f"  {C.PURPLE}{T('concept_label')}{C.RESET}")
            for line in textwrap.wrap(task_field(task, "concept"), width=78):
                print(f"     {C.DIM}{line}{C.RESET}")
            print()
            print(f"  {C.GREEN}{'─' * 60}{C.RESET}")
            print()

            try:
                next_action = input(f"  {C.GRAY}{T('next_back')}{C.RESET} ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                return "back"
            if next_action in ("n", "next"):
                return "next"
            elif next_action in ("b", "back"):
                return "back"
            return "next"

        # WRONG
        else:
            print()
            if mode == "sandbox":
                print(f"  {C.RED}{T('wrong_sandbox')}{C.RESET}  {C.GRAY}{T('attempt')}{attempts}  [{checker_label.upper()}]{C.RESET}")
                if result["stdout"].strip():
                    lines = result["stdout"].strip().splitlines()[:5]
                    print(f"  {C.DIM}stdout:{C.RESET}")
                    for l in lines:
                        print(f"    {C.DIM}{l}{C.RESET}")
                if result["stderr"].strip():
                    print(f"  {C.RED}stderr: {result['stderr'].strip()[:200]}{C.RESET}")
                if result["message"].strip():
                    print(f"  {C.GRAY}{T('verifier_says')} {result['message'].strip()[:200]}{C.RESET}")
            elif mode == "keyword":
                print(f"  {C.RED}{T('wrong_keyword')}{C.RESET}  {C.GRAY}{T('attempt')}{attempts}. {T('try_hint')}{C.RESET}")
                answer_lower = answer.lower()
                missing = [k for k in task.get("keywords", []) if k.lower() not in answer_lower]
                matched = [k for k in task.get("keywords", []) if k.lower() in answer_lower]
                if matched and missing:
                    print(f"  {C.GRAY}{T('missing_keywords')} {', '.join(missing[:3])}{C.RESET}")
                elif not matched:
                    print(f"  {C.GRAY}{T('try_hint')}{C.RESET}")
            print()


