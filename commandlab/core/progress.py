import os
import json
import datetime


# ─────────────────────────────────────────────────────────────
# PROGRESS STORAGE
# ─────────────────────────────────────────────────────────────
def get_progress_path():
    home = os.path.expanduser("~")
    config_dir = os.path.join(home, ".config", "commandlab")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "progress.json")

def load_progress():
    path = get_progress_path()
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed": [], "attempts": {}, "streaks": {}, "started": str(datetime.date.today())}

def save_progress(progress):
    with open(get_progress_path(), "w") as f:
        json.dump(progress, f, indent=2)


# ─────────────────────────────────────────────────────────────
# ANSWER CHECKING
# ─────────────────────────────────────────────────────────────
def check_answer(task, answer):
    answer = answer.strip()
    if not answer:
        return False, "empty"

    answer_lower = answer.lower()

    # Check against accepted answers (flexible match)
    for acc in task["accepted"]:
        acc_norm = acc.strip().lower()
        if answer_lower == acc_norm:
            return True, "exact"
        # Normalize spaces and check core parts
        if acc_norm.replace("  ", " ") == answer_lower.replace("  ", " "):
            return True, "exact"

    # Keyword-based check: all keywords must appear in the answer
    keywords = [k.lower() for k in task.get("keywords", [])]
    if keywords and all(kw in answer_lower for kw in keywords):
        return True, "keyword"

    return False, "wrong"
