from commandlab.ui.colors import C
from commandlab.ui.display import clear, LOGO


# ─────────────────────────────────────────────────────────────
# LOCALIZATION — Arabic / English
# ─────────────────────────────────────────────────────────────
_LANG = "en"   # runtime language: "en" | "ar"

STRINGS = {
    # ── Main menu ──────────────────────────────────────────────
    "total_progress":       {"en": "Total Progress",        "ar": "التقدم الكلي"},
    "domains":              {"en": "DOMAINS",               "ar": "المجالات"},
    "stats":                {"en": "Stats",                 "ar": "الإحصائيات"},
    "reset":                {"en": "Reset progress",        "ar": "إعادة التعيين"},
    "quit":                 {"en": "Quit",                  "ar": "خروج"},
    "challenges":           {"en": "Challenges",            "ar": "التحديات"},
    "choose_domain":        {"en": "Choose domain (1-5)",   "ar": "اختر المجال (1-5)"},
    "plugins":              {"en": "Plugins",               "ar": "الإضافات"},
    "language":             {"en": "Language",              "ar": "اللغة"},
    # ── Domain menu ────────────────────────────────────────────
    "tasks":                {"en": "TASKS",                 "ar": "المهام"},
    "back":                 {"en": "Back",                  "ar": "رجوع"},
    "random_task":          {"en": "Random unlocked task",  "ar": "مهمة عشوائية"},
    "choose_task":          {"en": "Choose task number (1-20)", "ar": "اختر رقم المهمة (1-20)"},
    "locked_level":         {"en": "LOCKED",                "ar": "مقفل"},
    "complete_first":       {"en": "complete {prev} first ({n} left)", "ar": "أكمل {prev} أولاً ({n} متبقية)"},
    # ── Task screen ────────────────────────────────────────────
    "sandbox_env":          {"en": "Sandbox environment prepared:", "ar": "بيئة الاختبار جاهزة:"},
    "commands_help":        {"en": "Commands: hint, answer, concept, skip  b(back)", "ar": "الأوامر: hint, answer, concept, skip  b(رجوع)"},
    "hint_label":           {"en": "💡 Hint:",              "ar": "💡 تلميح:"},
    "hint_more":            {"en": "Still stuck? Type answer to reveal the full answer.", "ar": "ما زلت عالقاً؟ اكتب answer لرؤية الإجابة."},
    "concept_label":        {"en": "📖 Core Concept:",      "ar": "📖 المفهوم الأساسي:"},
    "answer_revealed":      {"en": "⚠  ANSWER REVEALED — task will NOT be marked as completed", "ar": "⚠  تم كشف الإجابة — لن تُحتسب هذه المهمة"},
    "answer_label":         {"en": "Answer:",               "ar": "الإجابة:"},
    "running_sandbox":      {"en": "⏳ Running in sandbox...", "ar": "⏳ التنفيذ في البيئة المعزولة..."},
    "blocked":              {"en": "🚫 BLOCKED:",           "ar": "🚫 محظور:"},
    "not_permitted":        {"en": "That command is not permitted in the lab environment.", "ar": "هذا الأمر غير مسموح به في بيئة المختبر."},
    "correct_sandbox":      {"en": "✓ CORRECT!  State verified in sandbox.  +1 completed", "ar": "✓ صحيح!  تم التحقق من الحالة.  +1 مكتملة"},
    "correct_keyword":      {"en": "✓ CORRECT!  +1 completed",   "ar": "✓ صحيح!  +1 مكتملة"},
    "correct_revealed":     {"en": "✓ Correct — but answer was revealed, so not counted.", "ar": "✓ صحيح — لكن الإجابة كانت مكشوفة، لا تُحتسب."},
    "peek_note":            {"en": "  Come back without peeking to mark it done.", "ar": "  عد دون النظر للإجابة لتسجيلها."},
    "already_done":         {"en": "✓ Correct! (Already completed)", "ar": "✓ صحيح! (مكتملة سابقاً)"},
    "unlocked":             {"en": "🔓 UNLOCKED: {level} level!", "ar": "🔓 مفتوح: مستوى {level}!"},
    "cmd_output":           {"en": "Command output:",       "ar": "مخرجات الأمر:"},
    "next_back":            {"en": "[n]ext task  [b]ack  [Enter] continue:", "ar": "[n] التالية  [b] رجوع  [Enter] استمر:"},
    "wrong_sandbox":        {"en": "✗ Command ran but the goal was not achieved.", "ar": "✗ نُفِّذ الأمر لكن الهدف لم يتحقق."},
    "wrong_keyword":        {"en": "✗ Not quite.",          "ar": "✗ ليس صحيحاً تماماً."},
    "attempt":              {"en": "Attempt #",             "ar": "المحاولة رقم "},
    "missing_keywords":     {"en": "You have some right parts. Still missing:", "ar": "لديك بعض الأجزاء الصحيحة. ما زال ناقصاً:"},
    "try_hint":             {"en": "Doesn't look right. Try 'hint' if you're stuck.", "ar": "لا يبدو صحيحاً. جرب 'hint' إذا كنت عالقاً."},
    "verifier_says":        {"en": "Verifier says:",        "ar": "الفاحص يقول:"},
    "practice_prompt":      {"en": "Type the answer above to practice, or 'n' for next, 'b' to go back.", "ar": "اكتب الإجابة أعلاه للتدريب، أو 'n' للتالية، 'b' للرجوع."},
    "next_task_prompt":     {"en": "[n]ext task  [b]ack  [Enter] practice anyway:", "ar": "[n] التالية  [b] رجوع  [Enter] تدرب على أي حال:"},
    # ── Stats ──────────────────────────────────────────────────
    "your_stats":           {"en": "YOUR STATS",            "ar": "إحصائياتك"},
    "total":                {"en": "Total:",                "ar": "الإجمالي:"},
    "revealed_count":       {"en": "Answers revealed (not counted):", "ar": "إجابات مكشوفة (لا تُحتسب):"},
    "wrong_attempts":       {"en": "Total wrong attempts:", "ar": "مجموع المحاولات الخاطئة:"},
    "hardest_tasks":        {"en": "Hardest tasks (most attempts):", "ar": "أصعب المهام (أكثر محاولات):"},
    "press_enter":          {"en": "Press Enter to go back...", "ar": "اضغط Enter للرجوع..."},
    # ── Locks ──────────────────────────────────────────────────
    "level_locked":         {"en": "🔒 This level is locked.", "ar": "🔒 هذا المستوى مقفل."},
    "complete_prev":        {"en": "Complete all {prev} tasks first.", "ar": "أكمل جميع مهام {prev} أولاً."},
    "need_tasks":           {"en": "Still need: {n} task(s) in {prev}.", "ar": "ما زال ناقصاً: {n} مهمة في {prev}."},
    "next_locked":          {"en": "Next level is locked. Complete {prev} tasks first.", "ar": "المستوى التالي مقفل. أكمل مهام {prev} أولاً."},
    # ── Reset / session ────────────────────────────────────────
    "progress_reset":       {"en": "Progress reset.",       "ar": "تم إعادة التعيين."},
    "goodbye":              {"en": "See you next time. Keep learning!", "ar": "إلى اللقاء. استمر في التعلم!"},
    "domain_complete":      {"en": "🎉 You completed the entire {domain} domain!", "ar": "🎉 أكملت مجال {domain} بالكامل!"},
    "domain_progress":      {"en": "End of domain. {done}/{total} completed.", "ar": "نهاية المجال. {done}/{total} مكتمل."},
    # ── Challenges ─────────────────────────────────────────────
    "challenges_title":     {"en": "CHALLENGE MODE",        "ar": "وضع التحديات"},
    "challenges_sub":       {"en": "Multi-step situational scenarios", "ar": "سيناريوهات متعددة الخطوات"},
    "challenge_step":       {"en": "Step {n} of {total}:",  "ar": "الخطوة {n} من {total}:"},
    "challenge_pass":       {"en": "✓ Step passed! Moving to next...", "ar": "✓ اجتزت هذه الخطوة! الانتقال للتالية..."},
    "challenge_fail":       {"en": "✗ Step failed.",        "ar": "✗ فشلت هذه الخطوة."},
    "challenge_complete":   {"en": "🏆 CHALLENGE COMPLETE!", "ar": "🏆 اكتمل التحدي!"},
    "choose_challenge":     {"en": "Choose challenge (1-{n}) or b to go back:", "ar": "اختر التحدي (1-{n}) أو b للرجوع:"},
    # ── Plugins ────────────────────────────────────────────────
    "plugins_title":        {"en": "EXTERNAL PLUGINS",      "ar": "الإضافات الخارجية"},
    "plugins_none":         {"en": "No plugins found in tasks/ directory.", "ar": "لا توجد إضافات في مجلد tasks/."},
    "plugins_loaded":       {"en": "{n} plugin(s) loaded.",  "ar": "تم تحميل {n} إضافة."},
    "plugin_domain":        {"en": "[PLUGIN]",              "ar": "[إضافة]"},
    # ── Language ───────────────────────────────────────────────
    "lang_select":          {"en": "Select language / اختر اللغة:", "ar": "Select language / اختر اللغة:"},
    "lang_en":              {"en": "1. English",             "ar": "1. English"},
    "lang_ar":              {"en": "2. العربية",             "ar": "2. العربية"},
}

def T(key, **kwargs):
    """Translate a string key to the current language, with optional format vars."""
    entry = STRINGS.get(key, {})
    text = entry.get(_LANG, entry.get("en", key))
    if kwargs:
        text = text.format(**kwargs)
    return text

def set_language(lang: str):
    global _LANG
    _LANG = lang if lang in ("en", "ar") else "en"

def select_language():
    """Show language picker on first run. Returns chosen lang code."""
    clear()
    print(LOGO)
    print(f"\n  {C.CYAN}{T('lang_select')}{C.RESET}\n")
    print(f"  {C.GREEN}1{C.RESET}. English")
    print(f"  {C.GREEN}2{C.RESET}. العربية (Arabic)\n")
    try:
        ch = input(f"  {C.GREEN}❯{C.RESET} ").strip()
    except (KeyboardInterrupt, EOFError):
        ch = "1"
    if ch == "2":
        set_language("ar")
        return "ar"
    set_language("en")
    return "en"

def task_field(task, field):
    """Return the Arabic version of a task field when AR mode is active."""
    if _LANG == "ar":
        ar_val = task.get(f"{field}_ar", "").strip()
        if ar_val:
            return ar_val
    return task.get(field, "")
