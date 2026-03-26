from commandlab.data.tasks import TASKS


# ─────────────────────────────────────────────────────────────
# LEVEL LOCKING
# ─────────────────────────────────────────────────────────────

# Difficulty levels in order — each locks the next
LEVEL_ORDER = ["easy", "medium", "hard", "insane"]


def get_level_tasks(domain_name, level):
    """Return all tasks in a domain at a given difficulty level."""
    try:
        from commandlab.plugins.loader import PLUGIN_TASKS
    except ImportError:
        PLUGIN_TASKS = {}
    tasks = TASKS.get(domain_name) or PLUGIN_TASKS.get(domain_name, [])
    return [t for t in tasks if t["level"] == level]


def is_level_unlocked(domain_name, level, progress):
    """
    A level is unlocked if all tasks in the PREVIOUS level are completed.
    'easy' is always unlocked.
    """
    completed_ids = set(progress.get("completed", []))
    idx = LEVEL_ORDER.index(level)
    if idx == 0:
        return True  # easy is always open
    prev_level = LEVEL_ORDER[idx - 1]
    prev_tasks = get_level_tasks(domain_name, prev_level)
    return all(t["id"] in completed_ids for t in prev_tasks)


def get_task_lock_status(task, domain_name, progress):
    """Return True if this specific task is accessible (its level is unlocked)."""
    return is_level_unlocked(domain_name, task["level"], progress)


def get_domain_tasks(domain_name):
    """Return tasks for a domain (built-in or plugin)."""
    try:
        from commandlab.plugins.loader import PLUGIN_TASKS
    except ImportError:
        PLUGIN_TASKS = {}
    if domain_name in TASKS:
        return TASKS[domain_name]
    return PLUGIN_TASKS.get(domain_name, [])
