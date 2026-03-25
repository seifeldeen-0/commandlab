#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════╗
║   ██████╗ ██████╗ ███╗   ███╗███╗   ███╗ ║
║  ██╔════╝██╔═══██╗████╗ ████║████╗ ████║ ║
║  ██║     ██║   ██║██╔████╔██║██╔████╔██║ ║
║  ██║     ██║   ██║██║╚██╔╝██║██║╚██╔╝██║ ║
║  ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║ ╚═╝ ██║ ║
║   ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝ ║
║      ▄▀▄ █   ▄▀▄ █▄▄                     ║
║      █▀█ █▄▄ █▀█ █▄█                     ║
║   [ command-line learning toolkit ]       ║
╚═══════════════════════════════════════════╝

CommandLab — Interactive Linux CLI Learning Tool
Pure Python 3, zero dependencies.
"""

import os
import sys
import json
import subprocess
import hashlib
import datetime
import time
import shutil
import textwrap
import re
import tempfile
import stat
import signal

# ── Command Classifier integration ───────────────────────────
# Import the classifier from the same directory as this script.
# If it's not found (e.g. running from a different cwd), fall back
# gracefully so the rest of the tool still works.
try:
    import importlib.util as _ilu
    _clf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "command_classifier.py")
    _clf_spec = _ilu.spec_from_file_location("command_classifier", _clf_path)
    _clf_mod  = _ilu.module_from_spec(_clf_spec)
    import sys as _sys
    _sys.modules["command_classifier"] = _clf_mod   # register so dataclass __module__ resolves
    _clf_spec.loader.exec_module(_clf_mod)
    _classify         = _clf_mod.classify           # classify(raw_input) -> ClassificationResult
    _Decision         = _clf_mod.Decision
    _CLASSIFIER_OK    = True
except Exception:
    _CLASSIFIER_OK    = False
    _classify         = None
    _Decision         = None

# ─────────────────────────────────────────────────────────────
# ANSI COLORS
# ─────────────────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    GREEN   = "\033[38;5;114m"
    YELLOW  = "\033[38;5;221m"
    ORANGE  = "\033[38;5;208m"
    RED     = "\033[38;5;203m"
    BLUE    = "\033[38;5;111m"
    CYAN    = "\033[38;5;87m"
    PURPLE  = "\033[38;5;141m"
    GRAY    = "\033[38;5;240m"
    WHITE   = "\033[38;5;252m"
    BG_DARK = "\033[48;5;235m"
    BG_BOX  = "\033[48;5;233m"

    @staticmethod
    def strip(text):
        return re.sub(r'\033\[[0-9;]*m', '', text)

def clen(text):
    """Visible length of a string (strips ANSI codes)."""
    return len(C.strip(text))

def cprint(text=""):
    print(text + C.RESET)

def term_width():
    return shutil.get_terminal_size((100, 30)).columns

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

# ─────────────────────────────────────────────────────────────
# TASK DATABASE
# ─────────────────────────────────────────────────────────────
TASKS = {
    "files": [
        {
            "id": 1, "level": "easy",
            "title": "List files in current directory",
            "question": "List all files and directories in your current working directory.",
            "concept": "The ls command reads directory entries from the kernel via getdents(). Every file system object in Linux is listed this way.",
            "hint": "Think about the most basic command for listing directory contents.",
            "title_ar": 'عرض محتويات المجلد الحالي',
            "question_ar": 'اعرض جميع الملفات والمجلدات الموجودة في مجلد العمل الحالي.',
            "concept_ar": 'الأمر ls يقرأ مدخلات المجلد من النواة عبر استدعاء getdents(). كل كائن في نظام الملفات يُعرض بهذه الطريقة.',
            "hint_ar": 'فكّر في أبسط أمر لعرض محتويات المجلد.',

            "accepted": ["ls"],
            "keywords": ["ls"],
            "check_type": "keyword",
            "setup": "touch alpha.txt beta.txt gamma.conf && mkdir logs",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and bool(out.strip()),
                "ls must exit 0 and produce output"
            ),
        },
        {
            "id": 2, "level": "easy",
            "title": "Show hidden files",
            "question": "List ALL files including hidden ones (files starting with a dot) in the current directory.",
            "concept": "Hidden files in Linux are simply files whose name begins with '.'. The kernel does not treat them specially — only ls hides them by default.",
            "hint": "ls has a flag to show 'all' files.",
            "title_ar": 'عرض الملفات المخفية',
            "question_ar": 'اعرض جميع الملفات بما فيها المخفية (التي تبدأ بنقطة) في المجلد الحالي.',
            "concept_ar": 'الملفات المخفية في Linux هي ببساطة ملفات تبدأ أسماؤها بنقطة. النواة لا تتعامل معها بشكل خاص — فقط ls يخفيها افتراضياً.',
            "hint_ar": "أمر ls يمتلك خياراً لعرض 'جميع' الملفات.",

            "accepted": ["ls -a", "ls -la", "ls -al", "ls -A"],
            "keywords": ["ls", "-a"],
            "check_type": "keyword",
            "setup": "touch visible.txt .hidden_config .env",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and ".hidden_config" in out and ".env" in out,
                "Output must contain hidden files (.hidden_config, .env)"
            ),
        },
        {
            "id": 3, "level": "easy",
            "title": "Create an empty file",
            "question": "Create an empty file called 'notes.txt' in the current directory without opening any editor.",
            "concept": "touch calls the utime() syscall to update timestamps. If the file doesn't exist, it creates one via open() with O_CREAT. No editor needed.",
            "hint": "There's a command designed specifically for updating file timestamps.",
            "title_ar": 'إنشاء ملف فارغ',
            "question_ar": "أنشئ ملفاً فارغاً اسمه 'notes.txt' في المجلد الحالي دون فتح أي محرر نصوص.",
            "concept_ar": 'الأمر touch يستدعي utime() لتحديث الطوابع الزمنية. إذا لم يكن الملف موجوداً يُنشئه عبر open() مع O_CREAT. لا حاجة لمحرر نصوص.',
            "hint_ar": 'هناك أمر مُصمَّم خصيصاً لتحديث الطوابع الزمنية للملفات.',

            "accepted": ["touch notes.txt"],
            "keywords": ["touch", "notes.txt"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                os.path.isfile(os.path.join(sb, "notes.txt")),
                "notes.txt must exist as a regular file in the current directory"
            ),
        },
        {
            "id": 4, "level": "easy",
            "title": "Create a directory",
            "question": "Create a new directory called 'projects' inside the current directory.",
            "concept": "mkdir calls the mkdir() syscall which allocates a new directory inode. The parent directory's data block gets a new entry pointing to this inode.",
            "hint": "The command name literally means 'make directory'.",
            "title_ar": 'إنشاء مجلد',
            "question_ar": "أنشئ مجلداً جديداً اسمه 'projects' داخل المجلد الحالي.",
            "concept_ar": 'الأمر mkdir يستدعي mkdir() الذي يخصص inode جديداً للمجلد. كتلة بيانات المجلد الأصل تحصل على مدخل جديد يشير إلى هذا الـ inode.',
            "hint_ar": "اسم الأمر يعني حرفياً 'اصنع مجلداً'.",

            "accepted": ["mkdir projects", "mkdir ~/projects", "mkdir $HOME/projects"],
            "keywords": ["mkdir"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                os.path.isdir(os.path.join(sb, "projects")),
                "A directory named 'projects' must exist"
            ),
        },
        {
            "id": 5, "level": "easy",
            "title": "Copy a file",
            "question": "Copy a file called 'report.txt' to a directory called 'backup/'.",
            "concept": "cp reads the source with read() and writes to destination with write(). It creates a new inode — unlike a hard link, it's a full independent copy.",
            "hint": "The command means 'copy'. Source comes before destination.",
            "title_ar": 'نسخ ملف',
            "question_ar": "انسخ الملف 'report.txt' إلى المجلد 'backup/'.",
            "concept_ar": 'الأمر cp يقرأ المصدر بـ read() ويكتب إلى الوجهة بـ write(). يُنشئ inode جديداً — خلافاً للرابط الصلب، هذه نسخة مستقلة تماماً.',
            "hint_ar": "الأمر يعني 'نسخ'. المصدر يأتي قبل الوجهة.",

            "accepted": ["cp report.txt backup/", "cp report.txt backup"],
            "keywords": ["cp", "report.txt", "backup"],
            "check_type": "keyword",
            "setup": "echo 'quarterly data' > report.txt && mkdir backup",
            "verify": lambda sb, rc, out, err: (
                os.path.isfile(os.path.join(sb, "report.txt")) and
                os.path.isfile(os.path.join(sb, "backup", "report.txt")),
                "report.txt must exist in both . and backup/ — the original must not be deleted"
            ),
        },
        {
            "id": 6, "level": "medium",
            "title": "Find a file by name",
            "question": "Find all files named 'config.yml' anywhere on the system. Suppress permission error messages.",
            "concept": "find traverses the directory tree using opendir()/readdir() recursively. Redirecting stderr to /dev/null hides EACCES errors from restricted directories.",
            "hint": "Use find with a name flag, search from root /, and redirect stderr somewhere.",
            "title_ar": 'البحث عن ملف بالاسم',
            "question_ar": "ابحث عن جميع الملفات المسماة 'config.yml' في أي مكان على النظام. أخفِ رسائل خطأ الصلاحيات.",
            "concept_ar": 'الأمر find يتجول في شجرة المجلدات عبر opendir()/readdir() بشكل متكرر. إعادة توجيه stderr إلى /dev/null يخفي أخطاء EACCES من المجلدات المحظورة.',
            "hint_ar": 'استخدم find مع خيار الاسم، وابحث من المجلد الجذر /، وأعِد توجيه stderr.',

            "accepted": ["find / -name config.yml 2>/dev/null", "find / -name 'config.yml' 2>/dev/null"],
            "keywords": ["find", "-name", "config.yml", "2>/dev/null"],
            "check_type": "keyword",
            "setup": "mkdir -p apps/web apps/api && echo 'host: localhost' > apps/web/config.yml && echo 'port: 8080' > apps/api/config.yml",
            "verify": lambda sb, rc, out, err: (
                "config.yml" in out and out.count("config.yml") >= 2,
                "Must find at least 2 config.yml files in the output"
            ),
        },
        {
            "id": 7, "level": "medium",
            "title": "View inode number",
            "question": "Show the inode number of every file in the current directory.",
            "concept": "The inode is the kernel data structure storing all file metadata except the filename. ls -i reads the inode number from the directory entry via stat().",
            "hint": "ls has a flag specifically for displaying inode numbers.",
            "title_ar": 'عرض رقم الـ inode',
            "question_ar": 'اعرض رقم الـ inode لكل ملف في المجلد الحالي.',
            "concept_ar": 'الـ inode هو بنية بيانات النواة التي تخزن كل بيانات الملف ما عدا اسمه. ls -i يقرأ رقم الـ inode من مدخل المجلد عبر stat().',
            "hint_ar": 'الأمر ls يمتلك خياراً مخصصاً لعرض أرقام الـ inodes.',

            "accepted": ["ls -i", "ls -li", "ls -ia"],
            "keywords": ["ls", "-i"],
            "check_type": "keyword",
            "setup": "touch file_a.txt file_b.txt file_c.txt",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and bool(re.search(r'^\s*\d+', out, re.MULTILINE)),
                "Output must contain inode numbers (digits at line start)"
            ),
        },
        {
            "id": 8, "level": "medium",
            "title": "Create a symbolic link",
            "question": "Create a symbolic link called 'current' that points to a directory called 'v2.1/'.",
            "concept": "A symlink is a special file whose content is a path string. ln -s calls symlink() syscall. If the target is deleted, the symlink becomes dangling.",
            "hint": "ln creates links. The -s flag makes it symbolic. Target comes before link name.",
            "title_ar": 'إنشاء رابط رمزي',
            "question_ar": "أنشئ رابطاً رمزياً اسمه 'current' يشير إلى مجلد اسمه 'v2.1/'.",
            "concept_ar": 'الرابط الرمزي هو ملف خاص محتواه مسار نصي. ln -s يستدعي symlink(). إذا حُذف الهدف يصبح الرابط معطلاً.',
            "hint_ar": 'الأمر ln يُنشئ الروابط. الخيار -s يجعله رمزياً. الهدف يأتي قبل اسم الرابط.',

            "accepted": ["ln -s v2.1 current", "ln -s v2.1/ current"],
            "keywords": ["ln", "-s"],
            "check_type": "keyword",
            "setup": "mkdir v2.1 && touch v2.1/app.py v2.1/config.yml",
            "verify": lambda sb, rc, out, err: (
                os.path.islink(os.path.join(sb, "current")) and
                os.readlink(os.path.join(sb, "current")).rstrip("/") == "v2.1",
                "'current' must be a symlink pointing to v2.1"
            ),
        },
        {
            "id": 9, "level": "medium",
            "title": "Find files modified recently",
            "question": "Find all files in the 'logs/' directory that were modified in the last 24 hours.",
            "concept": "-mtime -1 means 'modified less than 1×24 hours ago'. The minus prefix means 'less than'. find compares file mtime from stat() with current time.",
            "hint": "Use find with -mtime and a value meaning 'less than 1 day'.",
            "title_ar": 'البحث عن الملفات المعدَّلة مؤخراً',
            "question_ar": "ابحث عن جميع الملفات في مجلد 'logs/' التي عُدِّلت خلال الـ 24 ساعة الماضية.",
            "concept_ar": "الخيار -mtime -1 يعني 'عُدِّل منذ أقل من 1×24 ساعة'. علامة الطرح تعني 'أقل من'. find يقارن mtime الملف من stat() مع الوقت الحالي.",
            "hint_ar": "استخدم find مع -mtime وقيمة تعني 'أقل من يوم واحد'.",

            "accepted": ["find /var/log -mtime -1", "find /var/log/ -mtime -1", "find /var/log -mtime -1 -type f",
                         "find logs -mtime -1", "find logs/ -mtime -1", "find . -mtime -1"],
            "keywords": ["-mtime", "-1"],
            "check_type": "keyword",
            "setup": "mkdir logs && touch logs/access.log logs/error.log logs/debug.log",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and ".log" in out,
                "Must find .log files modified recently in the logs/ directory"
            ),
        },
        {
            "id": 10, "level": "medium",
            "title": "Copy directory preserving metadata",
            "question": "Copy the entire directory 'project/' to 'project_backup/' preserving all permissions, timestamps, and symlinks.",
            "concept": "cp -a is equivalent to -dR --preserve=all. It preserves symlinks, permissions, timestamps, and extended attributes. Plain -r skips metadata.",
            "hint": "cp has an 'archive' flag that preserves everything. One letter flag.",
            "title_ar": 'نسخ مجلد مع الحفاظ على البيانات الوصفية',
            "question_ar": "انسخ المجلد 'project/' كاملاً إلى 'project_backup/' مع الحفاظ على الصلاحيات والطوابع الزمنية والروابط الرمزية.",
            "concept_ar": 'الخيار -a يعادل -dR --preserve=all. يحفظ الروابط الرمزية والصلاحيات والطوابع الزمنية والسمات الموسعة. الخيار -r وحده يتخطى البيانات الوصفية.',
            "hint_ar": "الأمر cp يمتلك خيار 'archive' يحفظ كل شيء. خيار حرف واحد.",

            "accepted": ["cp -a project project_backup", "cp -a project/ project_backup/", "cp -a project/ project_backup"],
            "keywords": ["cp", "-a"],
            "check_type": "keyword",
            "setup": "mkdir project && touch project/main.py && chmod 750 project/main.py && ln -s main.py project/run",
            "verify": lambda sb, rc, out, err: (
                os.path.isdir(os.path.join(sb, "project_backup")) and
                os.path.isfile(os.path.join(sb, "project_backup", "main.py")) and
                os.path.islink(os.path.join(sb, "project_backup", "run")),
                "project_backup/ must exist with main.py AND the symlink 'run' preserved"
            ),
        },
        {
            "id": 11, "level": "medium",
            "title": "Find large files",
            "question": "Find all files larger than 1KB in the current directory. Show only regular files.",
            "concept": "find -size uses stat() to check st_size. The + prefix means 'greater than'. 'M' suffix means megabytes, 'k' kilobytes. -type f excludes directories and special files.",
            "hint": "Combine find with -size and -type flags. +1k means greater than 1 kilobyte.",
            "title_ar": 'البحث عن الملفات الكبيرة',
            "question_ar": 'ابحث عن جميع الملفات الأكبر من 1 كيلوبايت في المجلد الحالي. اعرض الملفات العادية فقط.',
            "concept_ar": "الخيار -size يستخدم stat() للتحقق من st_size. البادئة + تعني 'أكبر من'. اللاحقة k تعني كيلوبايت. الخيار -type f يستثني المجلدات.",
            "hint_ar": 'ادمج find مع -size و-type. الصياغة +1k تعني أكبر من كيلوبايت.',

            "accepted": ["find / -size +100M -type f", "find / -type f -size +100M",
                         "find . -size +1k -type f", "find . -type f -size +1k"],
            "keywords": ["-size", "-type", "f"],
            "check_type": "keyword",
            "setup": "python3 -c \"open('small.txt','w').write('hi')\" && python3 -c \"open('large.dat','w').write('x'*2000)\" && mkdir subdir && python3 -c \"open('subdir/big.log','w').write('y'*5000)\"",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "large.dat" in out and "small.txt" not in out,
                "Must find large.dat but NOT small.txt (small.txt is under 1KB)"
            ),
        },
        {
            "id": 12, "level": "medium",
            "title": "Create a hard link",
            "question": "Create a hard link called 'data.bak' pointing to an existing file called 'data.csv'.",
            "concept": "A hard link is another directory entry pointing to the same inode. ln calls link() syscall which increments the inode's link count. Both names are equal — there is no 'original'.",
            "hint": "ln without -s creates a hard link. Existing file first, new link name second.",
            "title_ar": 'إنشاء رابط صلب',
            "question_ar": "أنشئ رابطاً صلباً اسمه 'data.bak' يشير إلى ملف موجود اسمه 'data.csv'.",
            "concept_ar": "الرابط الصلب هو مدخل مجلد آخر يشير إلى نفس الـ inode. ln يستدعي link() ويزيد عداد الروابط. كلا الاسمين متساويان — لا يوجد 'أصل'.",
            "hint_ar": 'الأمر ln بدون -s يُنشئ رابطاً صلباً. الملف الموجود أولاً ثم اسم الرابط.',

            "accepted": ["ln data.csv data.bak"],
            "keywords": ["ln", "data.csv", "data.bak"],
            "check_type": "keyword",
            "setup": "echo 'id,value\n1,100\n2,200' > data.csv",
            "verify": lambda sb, rc, out, err: (
                os.path.isfile(os.path.join(sb, "data.bak")) and
                not os.path.islink(os.path.join(sb, "data.bak")) and
                os.stat(os.path.join(sb, "data.csv")).st_ino == os.stat(os.path.join(sb, "data.bak")).st_ino,
                "data.bak must exist, must NOT be a symlink, and must share the same inode as data.csv"
            ),
        },
        {
            "id": 13, "level": "hard",
            "title": "Atomic file replacement",
            "question": "Replace 'app.conf' with a new version 'new.conf' atomically so no process ever reads a half-written file.",
            "concept": "mv on the same filesystem calls rename() syscall which is atomic — the directory entry is swapped instantly. cp is NOT atomic: it creates a partial file visible to other processes mid-write.",
            "hint": "One specific command guarantees atomicity via the rename() syscall.",
            "title_ar": 'استبدال ملف بشكل ذري',
            "question_ar": "استبدل 'app.conf' بنسخة جديدة 'new.conf' بشكل ذري لضمان عدم قراءة أي عملية لملف نصف مكتوب.",
            "concept_ar": 'الأمر mv على نفس نظام الملفات يستدعي rename() الذي ذري — تُبدَّل مدخلة المجلد فورياً. cp ليس ذرياً: يُنشئ ملفاً جزئياً مرئياً للعمليات الأخرى.',
            "hint_ar": 'أمر واحد فقط يضمن الذرية عبر استدعاء rename().',

            "accepted": ["mv new.conf app.conf", "mv new.conf /etc/app.conf", "sudo mv new.conf /etc/app.conf"],
            "keywords": ["mv", "new.conf"],
            "check_type": "keyword",
            "setup": "echo 'version: 1' > app.conf && echo 'version: 2' > new.conf",
            "verify": lambda sb, rc, out, err: (
                os.path.isfile(os.path.join(sb, "app.conf")) and
                open(os.path.join(sb, "app.conf")).read().strip() == "version: 2" and
                not os.path.exists(os.path.join(sb, "new.conf")),
                "app.conf must contain 'version: 2' and new.conf must no longer exist"
            ),
        },
        {
            "id": 14, "level": "hard",
            "title": "Recover deleted open file",
            "question": "A process with PID 1234 has a deleted log file still open on file descriptor 3. Print its current content.",
            "concept": "When a file is deleted but still open, the inode stays alive. The kernel exposes open fds via /proc/<pid>/fd/. Reading /proc/1234/fd/3 gives the file content even after unlink().",
            "hint": "Linux exposes every open file descriptor under /proc/<pid>/fd/. Use cat on that path.",
            "title_ar": 'استرجاع ملف محذوف ما زال مفتوحاً',
            "question_ar": 'عملية بـ PID 1234 لديها ملف سجل محذوف ما زال مفتوحاً على واصف الملف 3. اطبع محتواه الحالي.',
            "concept_ar": 'عند حذف ملف لكنه لا يزال مفتوحاً، يبقى الـ inode حياً. النواة تكشف واصفات الملفات عبر /proc/<pid>/fd/. قراءة /proc/1234/fd/3 تعطي المحتوى حتى بعد unlink().',
            "hint_ar": 'Linux يكشف كل واصف ملف مفتوح تحت /proc/<pid>/fd/. استخدم cat على ذلك المسار.',

            "accepted": ["cat /proc/1234/fd/3", "sudo cat /proc/1234/fd/3"],
            "keywords": ["/proc", "1234", "fd", "3"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("/proc" in err + out and "fd" in err + out, "Must reference /proc/<pid>/fd/ path to access deleted-but-open file"),
        },
        {
            "id": 15, "level": "hard",
            "title": "Create a sparse file",
            "question": "Create a sparse file called 'sparse.img' with an apparent size of 10MB but using almost no real disk space.",
            "concept": "Sparse files have holes — unmapped blocks that read as zeros without disk allocation. truncate creates sparse files instantly. dd with seek creates holes by jumping without writing.",
            "hint": "truncate -s sets the file size without allocating all the blocks. Or use dd with seek.",
            "title_ar": 'إنشاء ملف متفرق',
            "question_ar": "أنشئ ملفاً متفرقاً اسمه 'sparse.img' بحجم ظاهري 10 ميجابايت لكنه يستخدم مساحة قرص ضئيلة جداً.",
            "concept_ar": 'الملفات المتفرقة تمتلك ثغرات — كتل غير مخصصة تُقرأ كأصفار دون استهلاك مساحة. truncate يُنشئ الملفات المتفرقة فوراً.',
            "hint_ar": 'الأمر truncate -s يضبط حجم الملف دون تخصيص جميع الكتل.',

            "accepted": ["dd if=/dev/zero bs=1 count=1 seek=1G of=sparse.img", "dd if=/dev/zero of=sparse.img bs=1 count=0 seek=1G", "truncate -s 1G sparse.img",
                         "truncate -s 10M sparse.img", "dd if=/dev/zero of=sparse.img bs=1 count=0 seek=10M"],
            "keywords": ["sparse.img"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                os.path.isfile(os.path.join(sb, "sparse.img")) and
                os.path.getsize(os.path.join(sb, "sparse.img")) >= 1024 * 1024,
                "sparse.img must exist with apparent size > 1MB"
            ),
        },
        {
            "id": 16, "level": "hard",
            "title": "Find files by inode number",
            "question": "Find all filenames (hard links) that share the same inode as 'original.txt' anywhere under the current directory.",
            "concept": "Hard links share an inode. find -inum searches by inode number, revealing all directory entries pointing to that inode. This is how you discover all hard links to a file.",
            "hint": "First get the inode number of original.txt with ls -i, then use find -inum.",
            "title_ar": 'البحث عن الملفات بواسطة رقم الـ inode',
            "question_ar": "ابحث عن جميع الملفات (الروابط الصلبة) التي تشترك في نفس الـ inode مع 'original.txt' في المجلد الحالي.",
            "concept_ar": 'الروابط الصلبة تتشارك نفس الـ inode. الخيار find -inum يبحث برقم الـ inode كاشفاً جميع المدخلات التي تشير إليه.',
            "hint_ar": 'أولاً احصل على رقم الـ inode من ls -i، ثم استخدم find -inum.',

            "accepted": ["find /home -inum 524312", "find /home/ -inum 524312",
                         "find . -inum $(ls -i original.txt | awk '{print $1}')",
                         "ls -i original.txt"],
            "keywords": ["-inum"],
            "check_type": "keyword",
            "setup": "echo 'shared content' > original.txt && ln original.txt hardlink_a.txt && ln original.txt hardlink_b.txt",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and (
                    "hardlink_a.txt" in out or "hardlink_b.txt" in out or "original.txt" in out
                ) and "-inum" in err + out or
                (rc == 0 and re.search(r'\d+', out)),
                "Must use -inum to find related hard links OR show the inode number"
            ),
        },
        {
            "id": 17, "level": "hard",
            "title": "Check real vs apparent file size",
            "question": "Show the actual disk space used by 'sparse.img' (not its apparent size).",
            "concept": "du reports actual allocated disk blocks (from stat().st_blocks), not the apparent file size. A 1GB sparse file may use only 4KB of real disk space. ls -lh shows apparent size.",
            "hint": "du shows actual disk usage. Use it with -h for human-readable output.",
            "title_ar": 'مقارنة الحجم الحقيقي والظاهري',
            "question_ar": "اعرض مساحة القرص الفعلية المستخدمة بواسطة 'sparse.img' (ليس حجمه الظاهري).",
            "concept_ar": 'الأمر du يُبلِّغ عن الكتل الفعلية المخصصة من stat().st_blocks، وليس الحجم الظاهري. ملف متفرق بحجم 1 جيجابايت قد يستخدم 4 كيلوبايت فقط.',
            "hint_ar": 'الأمر du يُظهر الاستخدام الفعلي للقرص. استخدمه مع -h لنتائج مقروءة.',

            "accepted": ["du -h sparse.img", "du sparse.img", "du -sh sparse.img"],
            "keywords": ["du", "sparse.img"],
            "check_type": "keyword",
            "setup": "truncate -s 50M sparse.img",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "sparse.img" in out,
                "du must run successfully and show sparse.img in its output"
            ),
        },
        {
            "id": 18, "level": "insane",
            "title": "Diagnose full filesystem with free space",
            "question": "df shows 40% free but you get ENOSPC writing to /data. Show the command to check if inode exhaustion is the cause.",
            "concept": "ENOSPC can occur even with free blocks if all inodes are consumed. df -i shows inode usage per filesystem. Each file consumes one inode regardless of file size.",
            "hint": "df has a flag for showing inode counts instead of block counts.",
            "title_ar": 'تشخيص نظام ملفات ممتلئ مع وجود مساحة حرة',
            "question_ar": 'df يُظهر 40% مساحة حرة لكنك تحصل على خطأ ENOSPC. اعرض الأمر للتحقق من نفاد الـ inodes.',
            "concept_ar": 'يمكن أن يحدث ENOSPC حتى مع وجود كتل حرة إذا استُنفدت الـ inodes. df -i يُظهر استخدام الـ inodes لكل نظام ملفات.',
            "hint_ar": 'الأمر df يمتلك خياراً لعرض أعداد الـ inodes بدلاً من الكتل.',

            "accepted": ["df -i", "df -i /data", "df --inodes", "df --inodes /data"],
            "keywords": ["df", "-i"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and ("Inode" in out or "IFree" in out or "IUsed" in out),
                "Output must show inode statistics columns (Inode, IFree, IUsed, or similar)"
            ),
        },
        {
            "id": 19, "level": "insane",
            "title": "Watch filesystem events in real time",
            "question": "Monitor the current directory in real time and print a line every time any file inside it is modified.",
            "concept": "inotifywait uses the kernel's inotify subsystem — a character device that delivers filesystem events. Unlike polling, it uses zero CPU while waiting. The kernel calls your process via epoll when an event fires.",
            "hint": "inotifywait is the tool. Use -m for monitor mode, -r to recurse, -e to specify the event type.",
            "title_ar": 'مراقبة أحداث نظام الملفات في الوقت الفعلي',
            "question_ar": 'راقب المجلد الحالي في الوقت الفعلي واطبع سطراً في كل مرة يُعدَّل فيه أي ملف.',
            "concept_ar": 'الأداة inotifywait تستخدم نظام inotify في النواة — جهاز يُسلّم أحداث نظام الملفات. خلافاً للاستطلاع الدوري، لا تستهلك CPU أثناء الانتظار.',
            "hint_ar": 'استخدم inotifywait مع -m لوضع المراقبة، -r للتكرار، -e لتحديد نوع الحدث.',

            "accepted": ["inotifywait -mr -e modify /etc", "inotifywait -m -r -e modify /etc", "inotifywait -rme modify /etc",
                         "inotifywait -mr -e modify .", "inotifywait -m -e modify ."],
            "keywords": ["inotifywait", "-m", "-e", "modify"],
            "check_type": "keyword",
        "setup": 'touch watch_target.txt',
        "verify": lambda sb, rc, out, err: ("inotifywait" in err + out or rc == 127, "Must use inotifywait. rc=127 means not installed — that's acceptable in keyword mode"),
        },
        {
            "id": 20, "level": "insane",
            "title": "Flush page cache to disk",
            "question": "Force the kernel to flush all dirty page cache entries to disk immediately without unmounting the filesystem.",
            "concept": "Writing 3 to /proc/sys/vm/drop_caches first syncs then drops the page cache. sync() forces all dirty pages through pdflush to disk. The kernel's writeback mechanism normally does this lazily.",
            "hint": "There are two steps: sync to flush dirty pages, then interact with /proc/sys/vm/drop_caches.",
            "title_ar": 'تفريغ ذاكرة التخزين المؤقت للصفحات إلى القرص',
            "question_ar": 'أجبر النواة على تفريغ جميع مدخلات ذاكرة التخزين المؤقت للصفحات إلى القرص فوراً دون إلغاء تحميل نظام الملفات.',
            "concept_ar": 'كتابة 3 إلى /proc/sys/vm/drop_caches يُزامن ثم يُسقط ذاكرة التخزين المؤقت. sync() يُجبر الصفحات المتسخة على المرور عبر pdflush إلى القرص.',
            "hint_ar": 'خطوتان: sync لتفريغ الصفحات المتسخة، ثم التعامل مع /proc/sys/vm/drop_caches.',

            "accepted": ["sync && echo 3 > /proc/sys/vm/drop_caches", "sync; echo 3 > /proc/sys/vm/drop_caches", "sudo sync && sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'"],
            "keywords": ["sync", "drop_caches"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0,
                "sync must complete successfully (exit code 0). drop_caches write may require root."
            ),
        },
    ],

    "viewing": [
        {
            "id": 21, "level": "easy",
            "title": "View file content",
            "question": "Print the entire content of a file called 'readme.txt' to the terminal.",
            "concept": "cat calls read() in a loop and writes to stdout. For large files this dumps everything at once — use less for navigation. cat means 'concatenate'.",
            "hint": "The most basic file viewing command. Its name means concatenate.",
            "title_ar": 'عرض محتوى ملف',
            "question_ar": "اطبع محتوى الملف 'readme.txt' كاملاً في الطرفية.",
            "concept_ar": 'الأمر cat يستدعي read() في حلقة ويكتب إلى stdout. للملفات الكبيرة هذا يُلقي كل شيء دفعة واحدة — استخدم less للتنقل.',
            "hint_ar": "أبسط أمر لعرض الملفات. اسمه يعني 'دمج'.",

            "accepted": ["cat readme.txt"],
            "keywords": ["cat", "readme.txt"],
            "check_type": "keyword",
            "setup": "echo 'Welcome to CommandLab\nThis is a test file.\nLine 3.' > readme.txt",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "Welcome to CommandLab" in out,
                "Output must contain the file's content (e.g. 'Welcome to CommandLab')"
            ),
        },
        {
            "id": 22, "level": "easy",
            "title": "View first lines of file",
            "question": "Show only the first 5 lines of a file called 'access.log'.",
            "concept": "head reads only as many bytes as needed to print N lines, then closes the file. It does not read the whole file — efficient for huge logs.",
            "hint": "The head command with a flag to specify line count.",
            "title_ar": 'عرض الأسطر الأولى من ملف',
            "question_ar": "اعرض الأسطر الخمسة الأولى فقط من الملف 'access.log'.",
            "concept_ar": 'الأمر head يقرأ فقط البايتات الكافية لطباعة N سطر ثم يغلق الملف. لا يقرأ الملف كاملاً — فعّال للسجلات الضخمة.',
            "hint_ar": 'الأمر head مع خيار لتحديد عدد الأسطر.',

            "accepted": ["head -n 5 access.log", "head -5 access.log"],
            "keywords": ["head", "access.log"],
            "check_type": "keyword",
            "setup": "printf 'line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\nline10\n' > access.log",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and out.strip().count("\n") == 4 and "line5" in out and "line6" not in out,
                "Output must be exactly 5 lines: line1..line5. line6 must NOT appear."
            ),
        },
        {
            "id": 23, "level": "easy",
            "title": "Follow a live log",
            "question": "Display the last 10 lines of 'app.log' and keep watching for new lines as they are written.",
            "concept": "tail -f uses inotify_add_watch() to get kernel notifications when the file grows. It wakes up only when new data arrives — zero CPU polling.",
            "hint": "tail with a specific flag to 'follow' new output.",
            "title_ar": 'متابعة سجل مباشر',
            "question_ar": "اعرض آخر 10 أسطر من 'app.log' واستمر في مشاهدة الأسطر الجديدة عند كتابتها.",
            "concept_ar": 'الأمر tail -f يستخدم inotify_add_watch() للحصول على إشعارات النواة عند نمو الملف. يستيقظ فقط عند وصول بيانات جديدة — بدون استطلاع.',
            "hint_ar": "الأمر tail مع خيار لـ'متابعة' الإخراج الجديد.",

            "accepted": ["tail -f app.log", "tail -f -n 10 app.log"],
            "keywords": ["tail", "-f", "app.log"],
            "check_type": "keyword",
        "setup": 'printf "line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\nline10\n" > app.log',
        "verify": None,
        },
        {
            "id": 24, "level": "easy",
            "title": "Search inside a file",
            "question": "Find all lines containing the word 'ERROR' in a file called 'system.log'. Make it case-insensitive.",
            "concept": "grep reads line by line and applies a regex engine. -i lowercases both pattern and input before comparison. It exits 0 if any match found — useful in shell conditionals.",
            "hint": "grep with the case-insensitive flag.",
            "title_ar": 'البحث داخل ملف',
            "question_ar": "ابحث عن جميع الأسطر التي تحتوي كلمة 'ERROR' في الملف 'system.log'. اجعل البحث غير حساس لحالة الأحرف.",
            "concept_ar": 'الأمر grep يقرأ سطراً بسطر ويطبق محرك regex. الخيار -i يُصغّر كلاً من النمط والإدخال قبل المقارنة.',
            "hint_ar": 'الأمر grep مع خيار عدم حساسية حالة الأحرف.',

            "accepted": ["grep -i error system.log", "grep -i 'ERROR' system.log", "grep -i 'error' system.log"],
            "keywords": ["grep", "-i", "system.log"],
            "check_type": "keyword",
            "setup": "printf 'INFO started\nERROR disk full\ninfo checkpoint\nerror timeout\nINFO done\n' > system.log",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "ERROR disk full" in out and "error timeout" in out and "INFO started" not in out,
                "Must find both 'ERROR disk full' and 'error timeout' but not INFO lines"
            ),
        },
        {
            "id": 25, "level": "easy",
            "title": "Count lines in a file",
            "question": "Count the total number of lines in a file called 'data.csv'.",
            "concept": "wc -l counts newline characters via sequential reads. It uses O(1) memory regardless of file size. The result equals line count only if the last line ends with a newline.",
            "hint": "wc means 'word count' but it can count lines too with a specific flag.",
            "title_ar": 'عد الأسطر في ملف',
            "question_ar": "عُدَّ إجمالي عدد الأسطر في الملف 'data.csv'.",
            "concept_ar": 'الأمر wc -l يعد محارف السطر الجديد عبر قراءات متسلسلة. يستخدم ذاكرة O(1) بغض النظر عن حجم الملف.',
            "hint_ar": "wc تعني 'عد الكلمات' لكنها تعد الأسطر أيضاً بخيار محدد.",

            "accepted": ["wc -l data.csv"],
            "keywords": ["wc", "-l", "data.csv"],
            "check_type": "keyword",
            "setup": "printf 'id,name\n1,alice\n2,bob\n3,carol\n4,dave\n' > data.csv",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "5" in out,
                "Output must contain '5' (the file has 5 lines)"
            ),
        },
        {
            "id": 26, "level": "medium",
            "title": "Redirect stderr to a file",
            "question": "Run 'ls /nonexistent_dir_xyz' and redirect ALL output (both stdout and stderr) to a file called 'output.txt'.",
            "concept": "fd 1=stdout, fd 2=stderr. >file redirects stdout. 2>&1 duplicates fd2 to fd1's current destination. Order matters: >file 2>&1 works, but 2>&1 >file does not.",
            "hint": "You need to redirect fd 2 to the same place as fd 1. The operator is 2>&1.",
            "title_ar": 'إعادة توجيه stderr إلى ملف',
            "question_ar": "نفّذ 'ls /nonexistent_dir_xyz' وأعِد توجيه جميع المخرجات (stdout و stderr معاً) إلى ملف 'output.txt'.",
            "concept_ar": 'fd 1=stdout، fd 2=stderr. الرمز >ملف يعيد توجيه stdout. الرمز 2>&1 ينسخ fd2 إلى وجهة fd1 الحالية. الترتيب مهم.',
            "hint_ar": 'تحتاج إعادة توجيه fd 2 إلى نفس مكان fd 1. المعامل هو 2>&1.',

            "accepted": ["ls /root > output.txt 2>&1", "ls /root &> output.txt", "ls /root &>output.txt",
                         "ls /nonexistent_dir_xyz > output.txt 2>&1", "ls /nonexistent_dir_xyz &> output.txt"],
            "keywords": ["output.txt", "2>&1"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                os.path.isfile(os.path.join(sb, "output.txt")) and
                os.path.getsize(os.path.join(sb, "output.txt")) > 0,
                "output.txt must exist and must not be empty (it should contain the error message)"
            ),
        },
        {
            "id": 27, "level": "medium",
            "title": "Print specific column",
            "question": "Print only the 3rd column of a space-separated file called 'stats.txt'.",
            "concept": "awk processes each line as fields split by a delimiter. $3 means field 3. awk is a full programming language — it can do arithmetic, conditions, and formatting that grep cannot.",
            "hint": "awk is the right tool. Fields are accessed as $1, $2, $3...",
            "title_ar": 'طباعة عمود محدد',
            "question_ar": "اطبع العمود الثالث فقط من ملف 'stats.txt' المفصول بمسافات.",
            "concept_ar": 'الأمر awk يعالج كل سطر كحقول مفصولة بمحدد. $3 يعني الحقل الثالث. awk لغة برمجة كاملة — يمكنها ما لا يستطيعه grep.',
            "hint_ar": 'awk هو الأداة المناسبة. الحقول تُستدعى كـ $1, $2, $3...',

            "accepted": ["awk '{print $3}' stats.txt", "awk '{ print $3 }' stats.txt"],
            "keywords": ["awk", "$3", "stats.txt"],
            "check_type": "keyword",
            "setup": "printf 'host cpu mem\nweb01 45 2.1\ndb01 78 8.4\napp01 23 1.2\n' > stats.txt",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "mem" in out and "2.1" in out and "8.4" in out and "host" not in out,
                "Output must contain the 3rd column values: mem, 2.1, 8.4, 1.2. No 'host' or 'web01'."
            ),
        },
        {
            "id": 28, "level": "medium",
            "title": "Find top repeated lines",
            "question": "Show the 3 most frequent lines in 'access.log', sorted by frequency descending.",
            "concept": "sort groups identical lines → uniq -c counts consecutive duplicates → sort -rn orders by count descending → head -3 takes top 3. Classic frequency analysis pipeline.",
            "hint": "Build a pipeline: sort first, then count duplicates with uniq -c, then sort by count.",
            "title_ar": 'إيجاد الأسطر الأكثر تكراراً',
            "question_ar": "اعرض الأسطر الثلاثة الأكثر تكراراً في 'access.log' مرتبةً تنازلياً بالتكرار.",
            "concept_ar": 'sort يجمع الأسطر المتطابقة ← uniq -c يعدها ← sort -rn يرتبها تنازلياً ← head -3 يأخذ أعلى ثلاثة. أسلوب تحليل التكرار الكلاسيكي.',
            "hint_ar": 'ابنِ pipeline: sort أولاً، ثم عُدَّ التكرارات بـ uniq -c، ثم رتّب بالعدد.',

            "accepted": ["sort access.log | uniq -c | sort -rn | head -10", "sort access.log | uniq -c | sort -rn | head -n 10",
                         "sort access.log | uniq -c | sort -rn | head -3", "sort access.log | uniq -c | sort -rn | head -n 3"],
            "keywords": ["sort", "uniq", "-c", "sort", "-rn", "head"],
            "check_type": "keyword",
            "setup": "printf 'GET /home\nGET /api\nGET /home\nGET /home\nGET /api\nGET /about\nGET /home\nGET /api\n' > access.log",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "GET /home" in out and re.search(r'4\s+GET /home', out),
                "Must show 'GET /home' with count 4 as the top result"
            ),
        },
        {
            "id": 29, "level": "medium",
            "title": "Replace text in a file",
            "question": "Replace every occurrence of 'localhost' with '127.0.0.1' in 'config.txt'. Edit the file in place.",
            "concept": "sed -i writes to a temp file then renames it over the original — atomic replacement. The s/old/new/g syntax: s=substitute, g=global (all occurrences per line).",
            "hint": "sed with the -i (in-place) flag and a substitution expression s/old/new/g.",
            "title_ar": 'استبدال نص في ملف',
            "question_ar": "استبدل كل ظهور لكلمة 'localhost' بـ '127.0.0.1' في 'config.txt'. عدّل الملف في مكانه.",
            "concept_ar": 'الأمر sed -i يكتب إلى ملف مؤقت ثم يُعيد تسميته — استبدال ذري. الصيغة s/قديم/جديد/g: s=استبدل، g=عالمي (كل التكرارات في السطر).',
            "hint_ar": 'الأمر sed مع الخيار -i (في المكان) وتعبير الاستبدال s/قديم/جديد/g.',

            "accepted": ["sed -i 's/localhost/127.0.0.1/g' config.txt", "sed -i 's/localhost/127.0.0.1/g' config.txt"],
            "keywords": ["sed", "-i", "localhost", "127.0.0.1", "config.txt"],
            "check_type": "keyword",
            "setup": "printf 'host=localhost\ndb_host=localhost\nredis=localhost:6379\n' > config.txt",
            "verify": lambda sb, rc, out, err: (
                os.path.isfile(os.path.join(sb, "config.txt")) and
                "localhost" not in open(os.path.join(sb, "config.txt")).read() and
                "127.0.0.1" in open(os.path.join(sb, "config.txt")).read(),
                "config.txt must contain NO 'localhost' and must contain '127.0.0.1'"
            ),
        },
        {
            "id": 30, "level": "medium",
            "title": "View file without loading it",
            "question": "Open 'giant.log' for reading with the ability to scroll forward AND backward without loading it into RAM.",
            "concept": "less uses mmap() and reads only the visible portion. It is designed for large files. cat would load everything. more cannot scroll backward. less is the correct choice.",
            "hint": "less is more than more. It handles large files and supports bidirectional scrolling.",
            "title_ar": 'عرض ملف دون تحميله',
            "question_ar": "افتح 'giant.log' للقراءة مع إمكانية التمرير للأمام والخلف دون تحميله في الذاكرة.",
            "concept_ar": 'الأمر less يستخدم mmap() ويقرأ الجزء المرئي فقط. مُصمَّم للملفات الكبيرة. cat يحمّل كل شيء. more لا يدعم التمرير للخلف.',
            "hint_ar": 'less أقوى من more. يتعامل مع الملفات الكبيرة ويدعم التمرير ثنائي الاتجاه.',

            "accepted": ["less giant.log"],
            "keywords": ["less", "giant.log"],
            "check_type": "keyword",
        "setup": 'python3 -c "open(\'giant.log\',\'w\').write(\'line\\n\'*1000)"',
        "verify": lambda sb, rc, out, err: ("less" in err + out or rc != 127, "Must use less. Interactive pager exits without output; keyword check applies."),
        },
        {
            "id": 31, "level": "medium",
            "title": "View binary file content",
            "question": "Inspect the raw bytes of a binary file called 'firmware.bin' in hexadecimal with ASCII representation alongside.",
            "concept": "xxd reads binary bytes and outputs them as hex pairs alongside printable ASCII. od is the older alternative. cat on a binary file sends raw bytes to the terminal, often corrupting the display.",
            "hint": "xxd is the tool for hex+ASCII viewing of binary files.",
            "title_ar": 'عرض محتوى ملف ثنائي',
            "question_ar": "افحص البايتات الخام للملف الثنائي 'firmware.bin' بتمثيل سداسي عشري مع ASCII جانبه.",
            "concept_ar": 'الأمر xxd يقرأ البايتات الثنائية ويُخرجها كأزواج hex مع ASCII مقابلها. od هو البديل الأقدم. cat على ملف ثنائي يُرسل بايتات خام قد تُفسد عرض الطرفية.',
            "hint_ar": 'xxd هو الأداة لعرض الملفات الثنائية بصيغة hex+ASCII.',

            "accepted": ["xxd firmware.bin", "xxd firmware.bin | less"],
            "keywords": ["xxd", "firmware.bin"],
            "check_type": "keyword",
            "setup": "python3 -c \"import struct; open('firmware.bin','wb').write(bytes([0x7f,0x45,0x4c,0x46,0x02,0x01,0x01,0x00]*4))\"",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "7f 45 4c 46" in out.lower().replace("7f45", "7f 45").replace("  "," ") or
                rc == 0 and "7f45" in out.lower(),
                "Output must show hex representation including the ELF magic bytes (7f 45 4c 46)"
            ),
        },
        {
            "id": 32, "level": "medium",
            "title": "Show lines NOT matching a pattern",
            "question": "Print all lines in 'server.log' that do NOT contain the word 'DEBUG'.",
            "concept": "grep -v inverts the match — it prints lines where the pattern does NOT match. This is the set difference operation on lines. Essential for filtering noise from logs.",
            "hint": "grep has a flag to invert the match. It's -v for 'invert'.",
            "title_ar": 'عرض الأسطر التي لا تطابق نمطاً',
            "question_ar": "اطبع جميع الأسطر في 'server.log' التي لا تحتوي كلمة 'DEBUG'.",
            "concept_ar": 'الخيار -v في grep يعكس التطابق — يطبع الأسطر التي لا يتطابق فيها النمط. هذه عملية الفرق بين مجموعتين على مستوى الأسطر.',
            "hint_ar": "grep يمتلك خيار لعكس التطابق. هو -v للـ'عكس'.",

            "accepted": ["grep -v DEBUG server.log", "grep -v 'DEBUG' server.log"],
            "keywords": ["grep", "-v", "DEBUG", "server.log"],
            "check_type": "keyword",
            "setup": "printf 'INFO server started\nDEBUG init db\nINFO listening port 8080\nDEBUG cache miss\nERROR disk full\n' > server.log",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "DEBUG" not in out and "INFO server started" in out and "ERROR disk full" in out,
                "Output must have INFO/ERROR lines but NO lines containing 'DEBUG'"
            ),
        },
        {
            "id": 33, "level": "hard",
            "title": "Watch a file for changes",
            "question": "Run the command 'df -h' every 2 seconds and show the output refreshed in place in the terminal.",
            "concept": "watch uses curses to clear and redraw the terminal at fixed intervals. It is cleaner than a shell loop with sleep because it handles terminal resizing and shows a timestamp.",
            "hint": "The watch command runs another command repeatedly at an interval.",
            "title_ar": 'مراقبة ملف بحثاً عن تغييرات',
            "question_ar": "نفّذ الأمر 'df -h' كل ثانيتين واعرض المخرجات مُحدَّثة في مكانها في الطرفية.",
            "concept_ar": 'الأمر watch يستخدم curses لمسح الطرفية وإعادة رسمها على فترات ثابتة. أنظف من حلقة shell مع sleep لأنه يتعامل مع تغيير حجم الطرفية.',
            "hint_ar": 'الأمر watch يُشغِّل أمراً آخر بشكل متكرر على فترة زمنية.',

            "accepted": ["watch -n 2 'df -h'", "watch -n 2 df -h", "watch -n2 df -h"],
            "keywords": ["watch", "-n", "2", "df"],
            "check_type": "keyword",
        "setup": '',
        "verify": None,
        },
        {
            "id": 34, "level": "hard",
            "title": "Process substitution diff",
            "question": "Compare the output of 'ls /etc' and 'ls /usr/lib' as if they were files, without creating any temporary files.",
            "concept": "Process substitution <(cmd) creates a named pipe (FIFO) or /dev/fd entry. The shell passes the fd path as a filename argument. This lets you diff live command output without temp files.",
            "hint": "Use diff with process substitution syntax <(command). Available in bash.",
            "title_ar": 'مقارنة بالاستبدال العملياتي',
            "question_ar": "قارن مخرجات 'ls /etc' و 'ls /usr/lib' كما لو كانا ملفين، دون إنشاء أي ملفات مؤقتة.",
            "concept_ar": 'الاستبدال العملياتي <(cmd) يُنشئ أنبوباً مسمى أو مدخل /dev/fd. الشل يمرر مسار fd كاسم ملف. هذا يسمح بمقارنة مخرجات الأوامر الحية.',
            "hint_ar": 'استخدم diff مع صيغة الاستبدال العملياتي <(أمر). متاح في bash.',

            "accepted": ["diff <(ls /etc) <(ls /usr/etc)", "diff <(ls /etc/) <(ls /usr/etc/)",
                         "diff <(ls /etc) <(ls /usr/lib)", "diff <(ls /etc/) <(ls /usr/lib/)"],
            "keywords": ["diff", "<(ls"],
            "check_type": "keyword",
            "setup": "mkdir -p dira dirb && echo -e 'apple\nbanana\ncherry' > dira/list.txt && echo -e 'apple\nblueberry\ncherry' > dirb/list.txt",
            "verify": None,
        },
        {
            "id": 35, "level": "hard",
            "title": "Extract lines between patterns",
            "question": "Print all lines between (and including) 'START' and 'END' in a file called 'report.txt'.",
            "concept": "sed -n '/START/,/END/p' uses address ranges. The comma between two patterns means 'from first match to second match'. -n suppresses default output so only matched ranges print.",
            "hint": "sed with a range pattern /START/,/END/ and the p command. Use -n to suppress other lines.",
            "title_ar": 'استخراج الأسطر بين نمطين',
            "question_ar": "اطبع جميع الأسطر بين 'START' و 'END' شاملاً (من ملف 'report.txt').",
            "concept_ar": "الصيغة sed -n '/START/,/END/p' تستخدم نطاقات العناوين. الفاصلة بين نمطين تعني 'من أول تطابق إلى ثانيه'. -n يقمع الإخراج الافتراضي.",
            "hint_ar": 'sed مع نمط النطاق /START/,/END/ والأمر p. استخدم -n لقمع الأسطر الأخرى.',

            "accepted": ["sed -n '/START/,/END/p' report.txt", "awk '/START/,/END/' report.txt"],
            "keywords": ["report.txt"],
            "check_type": "keyword",
            "setup": "printf 'header line\npreamble\nSTART\nalpha\nbeta\ngamma\nEND\ntrailer line\n' > report.txt",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "START" in out and "END" in out and "alpha" in out and "header line" not in out and "trailer line" not in out,
                "Output must include START, END, and content between them, but NOT header or trailer lines"
            ),
        },
        {
            "id": 36, "level": "hard",
            "title": "Read process memory map",
            "question": "Show the full memory map of the current shell process, including all mapped files and memory regions.",
            "concept": "/proc/<pid>/maps exposes the process's virtual memory layout: address range, permissions, offset, device, inode, and pathname for each region. This is how debuggers and perf tools see memory.",
            "hint": "Every process has a 'maps' file under /proc/<pid>/. Use $$ for the current shell's PID.",
            "title_ar": 'قراءة خريطة ذاكرة العملية',
            "question_ar": 'اعرض خريطة الذاكرة الكاملة للعملية الحالية بما يشمل جميع الملفات والمناطق المُعيَّنة.',
            "concept_ar": '/proc/<pid>/maps يكشف تخطيط الذاكرة الافتراضية للعملية: نطاق العنوان والصلاحيات والإزاحة والجهاز والـ inode. هكذا يرى المصحّحون وأدوات الأداء الذاكرة.',
            "hint_ar": "كل عملية لديها ملف 'maps' تحت /proc/<pid>/. استخدم $$ لـ PID الشل الحالي.",

            "accepted": ["cat /proc/999/maps", "sudo cat /proc/999/maps",
                         "cat /proc/$$/maps", "cat /proc/self/maps"],
            "keywords": ["maps"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and re.search(r'[0-9a-f]+-[0-9a-f]+\s+[rwxp-]{4}', out),
                "Output must contain memory map entries in format: address-range permissions offset dev inode path"
            ),
        },
        {
            "id": 37, "level": "hard",
            "title": "Filter with multiple patterns",
            "question": "Show lines in 'events.log' that contain 'WARN' OR 'ERROR' but NOT 'ignored'.",
            "concept": "grep -E enables extended regex. The | operator means OR. Piping to another grep -v applies a second independent filter. Each grep in a pipeline processes one line at a time — O(1) memory.",
            "hint": "Chain two grep commands with a pipe. First grep for WARN|ERROR, then grep -v to exclude.",
            "title_ar": 'تصفية بنمط متعدد',
            "question_ar": "اعرض الأسطر في 'events.log' التي تحتوي 'WARN' أو 'ERROR' لكن لا تحتوي 'ignored'.",
            "concept_ar": 'الخيار -E في grep يُفعّل regex الموسع. المعامل | يعني أو. التمرير إلى grep -v آخر يطبق مرشحاً ثانياً مستقلاً.',
            "hint_ar": 'سلسل أمري grep بأنبوب. الأول يبحث عن WARN|ERROR، الثاني يستثني مع -v.',

            "accepted": ["grep -E 'WARN|ERROR' events.log | grep -v ignored", "grep -E 'WARN|ERROR' events.log | grep -v 'ignored'"],
            "keywords": ["grep", "WARN", "ERROR", "grep", "-v", "ignored"],
            "check_type": "keyword",
            "setup": "printf 'INFO start\nWARN low disk\nERROR timeout\nWARN ignored threshold\nERROR db down\nINFO stop\n' > events.log",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "WARN low disk" in out and "ERROR timeout" in out and "ERROR db down" in out and "ignored" not in out and "INFO" not in out,
                "Must show WARN/ERROR lines but NOT the 'ignored' line or any INFO lines"
            ),
        },
        {
            "id": 38, "level": "insane",
            "title": "Stream large file without memory",
            "question": "Count how many lines in 'bigdata.log' contain 'CRITICAL', using the minimum possible RAM.",
            "concept": "grep is fully streaming: it reads one line, checks the regex, discards the line, reads the next. Memory usage is O(line length), not O(file size). wc -l then just counts newlines in the grep output stream.",
            "hint": "grep + wc -l in a pipeline. grep is streaming and never holds the whole file in memory.",
            "title_ar": 'بث ملف ضخم دون استهلاك الذاكرة',
            "question_ar": "عُدَّ عدد الأسطر في 'bigdata.log' التي تحتوي 'CRITICAL'، باستخدام أقل قدر ممكن من الذاكرة.",
            "concept_ar": 'grep بثّي تماماً: يقرأ سطراً، يتحقق من regex، يتجاهل السطر، يقرأ التالي. استخدام الذاكرة O(طول السطر) وليس O(حجم الملف).',
            "hint_ar": 'grep + wc -l في pipeline. grep بثّي ولا يحتجز الملف في الذاكرة.',

            "accepted": ["grep -c CRITICAL bigdata.log", "grep 'CRITICAL' bigdata.log | wc -l", "grep -c 'CRITICAL' bigdata.log"],
            "keywords": ["grep", "CRITICAL", "bigdata.log"],
            "check_type": "keyword",
            "setup": "printf 'INFO start\nCRITICAL disk full\nINFO ok\nCRITICAL oom\nINFO done\nCRITICAL cpu overload\n' > bigdata.log",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "3" in out.strip(),
                "Output must contain the count '3' — there are exactly 3 CRITICAL lines"
            ),
        },
        {
            "id": 39, "level": "insane",
            "title": "Live log monitoring with inotify",
            "question": "Run a command that executes 'echo new line detected' every time a new line is written to 'app.log'.",
            "concept": "inotifywait uses the kernel inotify subsystem. Unlike sleep-based polling, it registers a watch with the kernel and sleeps in epoll_wait() until a filesystem event fires — truly event-driven, zero CPU waste.",
            "hint": "Use inotifywait in a while loop. -e modify watches for writes.",
            "title_ar": 'مراقبة السجل المباشر بـ inotify',
            "question_ar": "نفّذ أمراً يُشغّل 'echo تم اكتشاف سطر جديد' في كل مرة يُكتب فيها سطر جديد في 'app.log'.",
            "concept_ar": 'inotifywait تستخدم نظام inotify في النواة. خلافاً للاستطلاع، تُسجّل مراقبة مع النواة وتنام في epoll_wait() حتى يُطلَق حدث نظام ملفات — حدثي حقيقي.',
            "hint_ar": 'استخدم inotifywait في حلقة while. -e modify يراقب الكتابات.',

            "accepted": ["while inotifywait -e modify app.log; do echo 'new line detected'; done"],
            "keywords": ["inotifywait", "-e", "modify", "app.log"],
            "check_type": "keyword",
        "setup": 'touch app.log',
        "verify": lambda sb, rc, out, err: ("inotifywait" in err + out or rc == 127, "Must use inotifywait in a loop."),
        },
        {
            "id": 40, "level": "insane",
            "title": "Decode binary log format",
            "question": "A binary file 'journal.bin' starts with a 4-byte magic number. Show just the first 4 bytes as hex without any other output.",
            "concept": "xxd -l limits byte count. xxd -p outputs plain hex with no formatting or ASCII. Combining both gives you exactly N bytes of raw hex — the foundation of binary protocol analysis.",
            "hint": "xxd has a -l flag to limit bytes and -p for plain hex output.",
            "title_ar": 'فك تشفير صيغة سجل ثنائي',
            "question_ar": "ملف ثنائي 'journal.bin' يبدأ برقم سحري من 4 بايتات. اعرض الـ 4 بايتات الأولى فقط كـ hex دون أي مخرجات أخرى.",
            "concept_ar": 'الخيار -l في xxd يحدد عدد البايتات. الخيار -p يُخرج hex عادياً دون تنسيق أو ASCII. دمجهما يعطيك بالضبط N بايت كـ hex خام.',
            "hint_ar": 'xxd يمتلك الخيار -l لتحديد البايتات و -p للإخراج العادي.',

            "accepted": ["xxd -l 4 -p journal.bin", "xxd -l4 -p journal.bin", "head -c 4 journal.bin | xxd -p"],
            "keywords": ["xxd", "-l", "4", "journal.bin"],
            "check_type": "keyword",
            "setup": "python3 -c \"open('journal.bin','wb').write(bytes([0xDE,0xAD,0xBE,0xEF,0x01,0x02,0x03,0x04,0x05]))\"",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "deadbeef" in (out + err).lower().replace(" ", "").replace("\n", "") or
                (rc == 0 and "de" in out.lower() and "ad" in out.lower()),
                "Output must show the 4 magic bytes (deadbeef) in hex"
            ),
        },
    ],

    "permissions": [
        {
            "id": 41, "level": "easy",
            "title": "View file permissions",
            "question": "Show detailed file permissions, owner, group, and size for all files in the current directory.",
            "concept": "ls -l calls stat() on each file and formats the inode metadata. The permission string rwxrwxrwx is three groups of three bits: owner, group, others.",
            "hint": "ls with the long format flag.",
            "title_ar": 'عرض صلاحيات الملفات',
            "question_ar": 'اعرض صلاحيات الملفات المفصّلة والمالك والمجموعة والحجم لجميع الملفات في المجلد الحالي.',
            "concept_ar": 'ls -l يستدعي stat() على كل ملف ويُنسّق بيانات الـ inode. سلسلة الصلاحيات rwxrwxrwx هي ثلاث مجموعات من ثلاثة بتات: المالك والمجموعة والآخرون.',
            "hint_ar": 'الأمر ls مع خيار التنسيق الطويل.',

            "accepted": ["ls -l", "ls -la", "ls -lh"],
            "keywords": ["ls", "-l"],
            "check_type": "keyword",
            "setup": "touch secret.key deploy.sh config.cfg && chmod 600 secret.key && chmod 755 deploy.sh",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "-rw" in out and "deploy.sh" in out,
                "Output must show long format with permission strings (e.g. -rw, -rwx)"
            ),
        },
        {
            "id": 42, "level": "easy",
            "title": "Make a script executable",
            "question": "Make a file called 'deploy.sh' executable by its owner only. Do not change group or other permissions.",
            "concept": "chmod u+x sets the execute bit only for the user (owner). chmod +x would set it for all, subject to umask. The kernel checks the execute bit during execve() before loading the binary.",
            "hint": "chmod with 'u+x' sets execute only for the user/owner.",
            "title_ar": 'جعل سكريبت قابلاً للتنفيذ',
            "question_ar": "اجعل الملف 'deploy.sh' قابلاً للتنفيذ من قِبل مالكه فقط. لا تغيّر صلاحيات المجموعة أو الآخرين.",
            "concept_ar": 'chmod u+x يضبط بت التنفيذ للمستخدم (المالك) فقط. chmod +x سيضبطه للجميع. النواة تتحقق من بت التنفيذ أثناء execve() قبل تحميل البرنامج.',
            "hint_ar": "chmod مع 'u+x' يضبط التنفيذ للمستخدم/المالك فقط.",

            "accepted": ["chmod u+x deploy.sh", "chmod 744 deploy.sh"],
            "keywords": ["chmod", "u+x", "deploy.sh"],
            "check_type": "keyword",
            "setup": "echo '#!/bin/bash\necho hello' > deploy.sh && chmod 644 deploy.sh",
            "verify": lambda sb, rc, out, err: (
                bool(os.stat(os.path.join(sb, "deploy.sh")).st_mode & stat.S_IXUSR) and
                not bool(os.stat(os.path.join(sb, "deploy.sh")).st_mode & stat.S_IXGRP) and
                not bool(os.stat(os.path.join(sb, "deploy.sh")).st_mode & stat.S_IXOTH),
                "deploy.sh must have owner execute (+x) but NOT group or other execute"
            ),
        },
        {
            "id": 43, "level": "easy",
            "title": "Set permissions with octal",
            "question": "Set permissions on 'secret.key' to: owner can read+write, group can read only, others have no access.",
            "concept": "Octal 640: 6=rw- (110), 4=r-- (100), 0=--- (000). Each digit is 3 binary bits for r,w,x. chmod calls the chmod() syscall to update the inode's mode field.",
            "hint": "Use octal notation. Owner rw=6, group r=4, others none=0. That's chmod 640.",
            "title_ar": 'ضبط الصلاحيات بالترميز الثماني',
            "question_ar": "اضبط صلاحيات 'secret.key' على: المالك قراءة+كتابة، المجموعة قراءة فقط، الآخرون لا صلاحيات.",
            "concept_ar": 'الثماني 640: 6=rw-(110)، 4=r--(100)، 0=---(000). كل رقم 3 بتات ثنائية لـ r,w,x. chmod يستدعي chmod() لتحديث حقل mode في الـ inode.',
            "hint_ar": 'استخدم الترميز الثماني. المالك rw=6، المجموعة r=4، الآخرون لا شيء=0. أي chmod 640.',

            "accepted": ["chmod 640 secret.key", "chmod 640 ./secret.key"],
            "keywords": ["chmod", "640", "secret.key"],
            "check_type": "keyword",
            "setup": "echo 'private key data' > secret.key && chmod 777 secret.key",
            "verify": lambda sb, rc, out, err: (
                oct(os.stat(os.path.join(sb, "secret.key")).st_mode)[-3:] == "640",
                f"secret.key must have mode 640 (rw-r-----). Got: {oct(os.stat(os.path.join(sb, 'secret.key')).st_mode)[-3:]}"
            ),
        },
        {
            "id": 44, "level": "easy",
            "title": "Change file owner",
            "question": "Change the owner of 'report.pdf' to user 'alice' and group to 'finance'.",
            "concept": "chown calls the chown() syscall. Only root can change a file's owner to another user. The colon separates user and group: user:group. -R recurses directories.",
            "hint": "chown with user:group syntax. The colon separates owner from group.",
            "title_ar": 'تغيير مالك الملف',
            "question_ar": "غيّر مالك الملف 'report.pdf' إلى المستخدم 'alice' والمجموعة إلى 'finance'.",
            "concept_ar": 'chown يستدعي chown(). المسؤول root فقط يمكنه تغيير مالك الملف إلى مستخدم آخر. النقطتان تفصلان المستخدم عن المجموعة: user:group.',
            "hint_ar": 'chown مع صيغة user:group. النقطتان تفصلان المالك عن المجموعة.',

            "accepted": ["chown alice:finance report.pdf", "sudo chown alice:finance report.pdf"],
            "keywords": ["chown", "alice", "finance", "report.pdf"],
            "check_type": "keyword",
        "setup": 'touch report.pdf',
        "verify": lambda sb, rc, out, err: ("chown" in err + out or rc in (0,1), "Must use chown with user:group syntax."),
        },
        {
            "id": 45, "level": "easy",
            "title": "Run command as root",
            "question": "Run the command 'apt update' with root privileges without switching to the root account.",
            "concept": "sudo execve()s the target command after verifying /etc/sudoers. It sets euid=0 for that one command only, logs the action, and returns to normal user after completion.",
            "hint": "sudo runs a single command with elevated privileges.",
            "title_ar": 'تشغيل أمر كمسؤول',
            "question_ar": "نفّذ الأمر 'apt update' بصلاحيات المسؤول دون التبديل إلى حساب root.",
            "concept_ar": 'sudo يستدعي execve() على الأمر المستهدف بعد التحقق من /etc/sudoers. يضبط euid=0 لذلك الأمر فقط ويُسجّل الإجراء.',
            "hint_ar": 'sudo يُشغّل أمراً واحداً بصلاحيات مرتفعة.',

            "accepted": ["sudo apt update", "sudo apt-get update"],
            "keywords": ["sudo"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("sudo" in err + out or rc in (0,1), "Must use sudo to run command with elevated privileges."),
        },
        {
            "id": 46, "level": "medium",
            "title": "View current umask",
            "question": "Show the current umask value in octal format and explain what it means for newly created files.",
            "concept": "umask is a process attribute that clears permission bits from the default creation mode. Files default to 666, dirs to 777. umask 022 gives 644 files and 755 dirs. Inherited by child processes.",
            "hint": "umask is a shell builtin. Use it with the -S flag or just call it alone.",
            "title_ar": 'عرض قناع umask الحالي',
            "question_ar": 'اعرض قيمة umask الحالية بالتنسيق الثماني واشرح ما تعنيه للملفات المُنشأة حديثاً.',
            "concept_ar": 'umask سمة عملية تحذف بتات الصلاحية من وضع الإنشاء الافتراضي. الملفات تُنشأ افتراضياً بـ666، المجلدات بـ777. umask 022 يعطي ملفات 644.',
            "hint_ar": 'umask أمر مدمج في الشل. استخدمه مع -S أو استدعِه وحده.',

            "accepted": ["umask", "umask -S"],
            "keywords": ["umask"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and bool(re.search(r'[0-7]{3,4}', out) or "u=" in out),
                "Output must contain a umask value in octal (e.g. 0022) or symbolic (e.g. u=rwx,g=rx,o=rx)"
            ),
        },
        {
            "id": 47, "level": "medium",
            "title": "Set sticky bit on directory",
            "question": "Set the sticky bit on a shared directory 'shared/' so users can only delete their own files.",
            "concept": "Sticky bit (+t) on a directory prevents users from deleting files they don't own even if they have write permission on the directory. Used on /tmp and shared directories.",
            "hint": "chmod with +t sets the sticky bit. Or use 1777 in octal.",
            "title_ar": 'ضبط بت الـ sticky على مجلد',
            "question_ar": "اضبط بت الـ sticky على المجلد المشترك 'shared/' حتى يتمكن المستخدمون من حذف ملفاتهم فقط.",
            "concept_ar": 'بت الـ sticky (+t) على مجلد يمنع المستخدمين من حذف الملفات التي لا يملكونها حتى لو كانت لديهم صلاحية الكتابة على المجلد.',
            "hint_ar": 'chmod مع +t يضبط بت الـ sticky. أو استخدم 1777 بالثماني.',

            "accepted": ["chmod +t /srv/shared", "chmod 1777 /srv/shared", "chmod 1775 /srv/shared",
                         "chmod +t shared", "chmod 1777 shared", "chmod 1775 shared/"],
            "keywords": ["chmod", "shared"],
            "check_type": "keyword",
            "setup": "mkdir shared && chmod 777 shared",
            "verify": lambda sb, rc, out, err: (
                bool(os.stat(os.path.join(sb, "shared")).st_mode & stat.S_ISVTX),
                "The 'shared' directory must have the sticky bit set (S_ISVTX)"
            ),
        },
        {
            "id": 48, "level": "medium",
            "title": "Find all SUID binaries",
            "question": "Find all SUID (Set User ID) executable files anywhere under the current directory.",
            "concept": "SUID binaries run with the file owner's euid instead of the caller's. find -perm /4000 uses the octal SUID bit mask. These are privilege escalation targets if misconfigured.",
            "hint": "Use find with -perm and the SUID bit mask /4000. The / prefix means 'any of these bits'.",
            "title_ar": 'البحث عن جميع الملفات ذات SUID',
            "question_ar": 'ابحث عن جميع الملفات التنفيذية ذات SUID في أي مكان تحت المجلد الحالي.',
            "concept_ar": 'الملفات ذات SUID تعمل بـ euid مالكها بدلاً من المستدعي. find -perm /4000 يستخدم قناع بت SUID. هذه أهداف تصعيد الامتيازات إذا كانت مُعطَّلة.',
            "hint_ar": "استخدم find مع -perm وقناع SUID /4000. البادئة / تعني 'أي من هذه البتات'.",

            "accepted": ["find / -perm /4000 -type f", "find / -perm -4000 -type f", "find / -perm /4000 -type f 2>/dev/null", "find / -perm -u=s -type f",
                         "find . -perm /4000 -type f", "find . -perm -4000 -type f"],
            "keywords": ["find", "-perm", "4000"],
            "check_type": "keyword",
            "setup": "cp /bin/ls ./fake_suid && chmod u+s ./fake_suid && touch regular.sh && chmod 755 regular.sh",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "fake_suid" in out and "regular.sh" not in out,
                "Must find fake_suid (has SUID bit) but NOT regular.sh (no SUID)"
            ),
        },
        {
            "id": 49, "level": "medium",
            "title": "Add ACL for specific user",
            "question": "Give user 'bob' read access to 'private.txt' without changing the file's owner, group, or standard permissions.",
            "concept": "ACLs (Access Control Lists) extend UGO permissions with per-user/per-group rules. setfacl -m u:bob:r adds bob's rule without touching the standard permission bits.",
            "hint": "setfacl modifies ACL entries. -m means modify, u:user:perms is the format.",
            "title_ar": 'إضافة ACL لمستخدم محدد',
            "question_ar": "امنح المستخدم 'bob' صلاحية القراءة على 'private.txt' دون تغيير المالك أو المجموعة أو الصلاحيات القياسية.",
            "concept_ar": 'الـ ACLs تمدد صلاحيات UGO بقواعد لكل مستخدم/مجموعة. setfacl -m u:bob:r يضيف قاعدة bob دون المساس ببتات الصلاحية القياسية.',
            "hint_ar": 'setfacl يعدّل مدخلات ACL. -m تعني تعديل، u:مستخدم:صلاحيات هو التنسيق.',

            "accepted": ["setfacl -m u:bob:r private.txt", "setfacl -m u:bob:r-- private.txt"],
            "keywords": ["setfacl", "-m", "bob", "private.txt"],
            "check_type": "keyword",
        "setup": 'touch private.txt && chmod 600 private.txt',
        "verify": lambda sb, rc, out, err: ("setfacl" in err + out or rc == 0, "Must use setfacl to add ACL entry."),
        },
        {
            "id": 50, "level": "medium",
            "title": "View ACL of a file",
            "question": "Display the full Access Control List of a file called 'shared_doc.txt'.",
            "concept": "getfacl reads the file's ACL from the filesystem extended attributes. It shows the standard UGO permissions and any additional ACL entries. The 'mask' entry limits effective permissions.",
            "hint": "getfacl is the companion to setfacl.",
            "title_ar": 'عرض ACL ملف',
            "question_ar": "اعرض قائمة التحكم في الوصول كاملةً للملف 'shared_doc.txt'.",
            "concept_ar": 'getfacl يقرأ الـ ACL من السمات الموسعة لنظام الملفات. يُظهر صلاحيات UGO القياسية وأي مدخلات ACL إضافية.',
            "hint_ar": 'getfacl هو رفيق setfacl.',

            "accepted": ["getfacl shared_doc.txt"],
            "keywords": ["getfacl", "shared_doc.txt"],
            "check_type": "keyword",
            "setup": "touch shared_doc.txt && chmod 644 shared_doc.txt",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and ("owner:" in out or "user::" in out),
                "Output must contain ACL entries showing owner, group, other permissions"
            ),
        },
        {
            "id": 51, "level": "medium",
            "title": "Set setgid on a shared directory",
            "question": "Configure the 'team/' directory so all new files created inside it automatically inherit its group ownership.",
            "concept": "SGID on a directory makes new files inherit the directory's group instead of the creator's primary group. Essential for shared team directories where consistent group ownership is needed.",
            "hint": "chmod g+s sets the setgid bit. New files then inherit the directory's group.",
            "title_ar": 'ضبط setgid على مجلد مشترك',
            "question_ar": "هيّئ مجلد 'team/' حتى ترث الملفات الجديدة داخله ملكية مجموعته تلقائياً.",
            "concept_ar": 'SGID على مجلد يجعل الملفات الجديدة ترث مجموعة المجلد بدلاً من المجموعة الرئيسية للمنشئ. ضروري لمجلدات العمل المشتركة.',
            "hint_ar": 'chmod g+s يضبط بت setgid. الملفات الجديدة ترث مجموعة المجلد.',

            "accepted": ["chmod g+s /srv/team", "chmod 2775 /srv/team",
                         "chmod g+s team", "chmod g+s team/", "chmod 2775 team"],
            "keywords": ["chmod", "team"],
            "check_type": "keyword",
            "setup": "mkdir team && chmod 775 team",
            "verify": lambda sb, rc, out, err: (
                bool(os.stat(os.path.join(sb, "team")).st_mode & stat.S_ISGID),
                "The 'team' directory must have the setgid bit set (S_ISGID)"
            ),
        },
        {
            "id": 52, "level": "medium",
            "title": "Recursively change permissions",
            "question": "Set permissions 755 on the 'website/' directory and all its subdirectories and files recursively.",
            "concept": "chmod -R recurses the directory tree and applies the mode to every entry. Be careful: 755 on files makes them executable, which may not be desired. Consider using find to apply different modes to files vs dirs.",
            "hint": "chmod with the -R flag recurses into all subdirectories.",
            "title_ar": 'تغيير الصلاحيات بشكل متكرر',
            "question_ar": "اضبط الصلاحيات 755 على مجلد 'website/' وجميع مجلداته الفرعية وملفاته بشكل متكرر.",
            "concept_ar": 'chmod -R يتجول في شجرة المجلدات ويطبق الوضع على كل مدخل. تنبّه: 755 على الملفات يجعلها قابلة للتنفيذ وهو ما قد لا يكون مرغوباً.',
            "hint_ar": 'chmod مع الخيار -R يتجول في جميع المجلدات الفرعية.',

            "accepted": ["chmod -R 755 /srv/website", "chmod -R 755 /srv/website/",
                         "chmod -R 755 website", "chmod -R 755 website/"],
            "keywords": ["chmod", "-R", "755"],
            "check_type": "keyword",
            "setup": "mkdir -p website/css website/js && touch website/index.html website/css/style.css website/js/app.js && chmod -R 600 website",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and
                oct(os.stat(os.path.join(sb, "website")).st_mode)[-3:] == "755" and
                oct(os.stat(os.path.join(sb, "website", "index.html")).st_mode)[-3:] == "755",
                "website/ and website/index.html must both have mode 755"
            ),
        },
        {
            "id": 53, "level": "hard",
            "title": "Grant capability without sudo",
            "question": "Allow the binary '/usr/bin/myserver' to bind to port 80 without running as root. Use Linux capabilities.",
            "concept": "cap_net_bind_service allows binding to ports below 1024 without root. setcap replaces the all-or-nothing root model with granular privileges. The +ep suffix means effective+permitted.",
            "hint": "setcap assigns capabilities to a binary. cap_net_bind_service is the specific capability needed.",
            "title_ar": 'منح قدرة دون sudo',
            "question_ar": "اسمح للبرنامج '/usr/bin/myserver' بالربط على المنفذ 80 دون تشغيله كمسؤول. استخدم قدرات Linux.",
            "concept_ar": 'cap_net_bind_service يسمح بالربط على المنافذ أقل من 1024 دون مسؤول. setcap يستبدل نموذج الكل أو لا شيء بصلاحيات دقيقة.',
            "hint_ar": 'setcap يعيّن القدرات لبرنامج. cap_net_bind_service هي القدرة المحددة المطلوبة.',

            "accepted": ["setcap cap_net_bind_service+ep /usr/bin/myserver", "sudo setcap cap_net_bind_service+ep /usr/bin/myserver"],
            "keywords": ["setcap", "cap_net_bind_service", "/usr/bin/myserver"],
            "check_type": "keyword",
        "setup": 'cp /bin/ls ./myserver',
        "verify": lambda sb, rc, out, err: ("setcap" in err + out or rc in (0,1), "Must use setcap to grant cap_net_bind_service capability."),
        },
        {
            "id": 54, "level": "hard",
            "title": "Check effective capabilities of a process",
            "question": "Show the capability sets (effective, permitted, inherited) of a running process with PID 1500.",
            "concept": "Every process has 5 capability sets stored in task_struct. /proc/<pid>/status exposes CapEff, CapPrm, CapInh, CapBnd, CapAmb as hex bitmasks. capsh --decode converts them to names.",
            "hint": "Check /proc/<pid>/status and look for the Cap* fields.",
            "title_ar": 'التحقق من القدرات الفعّالة لعملية',
            "question_ar": 'اعرض مجموعات القدرات (الفعّالة والمسموحة والموروثة) لعملية تعمل بـ PID 1500.',
            "concept_ar": 'كل عملية لها 5 مجموعات قدرات مخزنة في task_struct. /proc/<pid>/status يكشف CapEff وCapPrm وCapInh كقيم hex.',
            "hint_ar": 'تحقق من /proc/<pid>/status وابحث عن حقول Cap*.',

            "accepted": ["cat /proc/1500/status | grep Cap", "grep Cap /proc/1500/status",
                         "cat /proc/$$/status | grep Cap", "grep Cap /proc/self/status"],
            "keywords": ["Cap"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and bool(re.search(r'Cap(Eff|Prm|Inh|Bnd|Amb):\s+[0-9a-f]+', out)),
                "Output must contain capability hex values like 'CapEff: 0000003fffffffff'"
            ),
        },
        {
            "id": 55, "level": "hard",
            "title": "Lock down a file completely",
            "question": "Make 'critical.conf' undeletable and unmodifiable by anyone (including root) using filesystem-level immutability.",
            "concept": "chattr +i sets the immutable attribute in the inode's flags field. Even root cannot modify or delete an immutable file. The attribute is stored in the filesystem, not in standard permission bits.",
            "hint": "chattr sets special filesystem attributes. The +i flag means immutable.",
            "title_ar": 'قفل ملف بشكل كامل',
            "question_ar": "اجعل 'critical.conf' غير قابل للحذف أو التعديل من قِبل أي أحد بما فيهم المسؤول باستخدام خاصية عدم القابلية للتغيير.",
            "concept_ar": 'chattr +i يضبط سمة عدم القابلية للتغيير في حقل flags الـ inode. حتى المسؤول لا يستطيع تعديل أو حذف ملف ثابت. السمة مخزنة في نظام الملفات.',
            "hint_ar": 'chattr يضبط سمات نظام الملفات الخاصة. الخيار +i يعني ثابت.',

            "accepted": ["chattr +i critical.conf", "sudo chattr +i critical.conf"],
            "keywords": ["chattr", "+i", "critical.conf"],
            "check_type": "keyword",
            "setup": "echo 'production config' > critical.conf",
            "verify": lambda sb, rc, out, err: (
                (rc == 0 and (
                    subprocess.run(["lsattr", os.path.join(sb, "critical.conf")],
                        capture_output=True, text=True).stdout.strip().startswith("----i") or
                    "Operation not supported" in subprocess.run(["lsattr", os.path.join(sb, "critical.conf")],
                        capture_output=True, text=True).stderr
                )),
                "critical.conf must have the immutable 'i' attribute set (or filesystem doesn't support it)"
            ),
        },
        {
            "id": 56, "level": "hard",
            "title": "Check immutable attribute",
            "question": "Check if 'critical.conf' has the immutable attribute set.",
            "concept": "lsattr reads the extended inode flags from the filesystem. The 'i' flag in the output means immutable. This is different from permissions — it's a separate attribute stored in the inode.",
            "hint": "lsattr is the companion to chattr — it lists attributes.",
            "title_ar": 'التحقق من سمة عدم القابلية للتغيير',
            "question_ar": "تحقق مما إذا كان 'critical.conf' يمتلك سمة عدم القابلية للتغيير.",
            "concept_ar": "lsattr يقرأ flags الـ inode الموسعة من نظام الملفات. العلامة 'i' في المخرجات تعني ثابت. هذا مختلف عن الصلاحيات — سمة منفصلة في الـ inode.",
            "hint_ar": 'lsattr هو رفيق chattr — يسرد السمات.',

            "accepted": ["lsattr critical.conf"],
            "keywords": ["lsattr", "critical.conf"],
            "check_type": "keyword",
            "setup": "echo 'data' > critical.conf",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and ("i" in out or "Operation not supported" in err),
                "Output must show the 'i' immutable flag, or filesystem doesn't support it"
            ),
        },
        {
            "id": 57, "level": "hard",
            "title": "Find world-writable directories",
            "question": "Find all world-writable directories under the current directory that do NOT have the sticky bit set.",
            "concept": "World-writable dirs without sticky bit let any user delete any file inside — a serious security hole. find -perm -002 finds world-writable, ! -perm -1000 excludes sticky. These are pentest findings.",
            "hint": "Use find with -perm -002 for world-writable and negate the sticky bit with ! -perm -1000.",
            "title_ar": 'البحث عن المجلدات القابلة للكتابة عالمياً',
            "question_ar": 'ابحث عن جميع المجلدات القابلة للكتابة عالمياً تحت المجلد الحالي والتي لا تمتلك بت الـ sticky.',
            "concept_ar": 'المجلدات القابلة للكتابة عالمياً بدون sticky تسمح لأي مستخدم بحذف أي ملف — ثغرة أمنية خطيرة. find -perm -002 يجد القابلة للكتابة عالمياً.',
            "hint_ar": 'استخدم find مع -perm -002 للقابلة للكتابة عالمياً وانفِ بت sticky بـ ! -perm -1000.',

            "accepted": ["find / -type d -perm -002 ! -perm -1000 2>/dev/null", "find / -type d -perm -o+w ! -perm -1000 2>/dev/null",
                         "find . -type d -perm -002 ! -perm -1000", "find . -type d -perm -o+w ! -perm -1000"],
            "keywords": ["find", "-type", "d", "-perm", "-002"],
            "check_type": "keyword",
            "setup": "mkdir safe_dir risky_dir sticky_dir && chmod 777 risky_dir && chmod 1777 sticky_dir && chmod 755 safe_dir",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "risky_dir" in out and "sticky_dir" not in out and "safe_dir" not in out,
                "Must find 'risky_dir' (world-writable, no sticky) but NOT 'sticky_dir' (has sticky) or 'safe_dir' (not world-writable)"
            ),
        },
        {
            "id": 58, "level": "insane",
            "title": "Audit all sudo actions",
            "question": "Show the last 20 sudo commands executed on this system by any user.",
            "concept": "sudo logs every invocation to /var/log/auth.log (Debian/Ubuntu) or /var/log/secure (RHEL). grep for 'COMMAND' extracts the actual commands run. This is the audit trail for privileged access.",
            "hint": "sudo logs to /var/log/auth.log. grep for 'sudo' or 'COMMAND' entries.",
            "title_ar": 'تدقيق جميع إجراءات sudo',
            "question_ar": 'اعرض آخر 20 أمر sudo نُفِّذ على هذا النظام من قِبل أي مستخدم.',
            "concept_ar": 'sudo يُسجّل كل استدعاء في /var/log/auth.log (Debian/Ubuntu) أو /var/log/secure (RHEL). البحث عن COMMAND يستخرج الأوامر الفعلية المُشغَّلة.',
            "hint_ar": "sudo يُسجّل في /var/log/auth.log. ابحث عن مدخلات 'sudo' أو 'COMMAND'.",

            "accepted": ["grep sudo /var/log/auth.log | tail -20", "grep COMMAND /var/log/auth.log | tail -20", "tail -20 /var/log/auth.log | grep sudo"],
            "keywords": ["grep", "sudo", "/var/log/auth.log"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("auth.log" in err + out or "COMMAND" in out or rc in (0,1), "Must grep /var/log/auth.log for sudo COMMAND entries."),
        },
        {
            "id": 59, "level": "insane",
            "title": "Trace permission check on a file",
            "question": "Use strace to observe the exact syscall the kernel uses to check permissions when you run 'cat secret.txt'.",
            "concept": "strace intercepts every syscall. openat() is the syscall that triggers the kernel's permission check (generic_permission()). The EACCES error appears right in the strace output if access is denied.",
            "hint": "strace traces syscalls. Run strace on cat and look for the open/openat syscall.",
            "title_ar": 'تتبع فحص الصلاحيات على ملف',
            "question_ar": "استخدم strace لمراقبة استدعاء النظام الذي تستخدمه النواة لفحص الصلاحيات عند تشغيل 'cat secret.txt'.",
            "concept_ar": 'strace يعترض كل استدعاء نظام. openat() هو الاستدعاء الذي يُطلق فحص صلاحيات النواة. خطأ EACCES يظهر مباشرةً في مخرجات strace.',
            "hint_ar": 'strace يتتبع استدعاءات النظام. شغّل strace على cat وابحث عن استدعاء open/openat.',

            "accepted": ["strace cat secret.txt", "strace -e openat cat secret.txt", "strace -e open,openat cat secret.txt"],
            "keywords": ["strace", "cat", "secret.txt"],
            "check_type": "keyword",
            "setup": "echo 'top secret data' > secret.txt",
            "verify": lambda sb, rc, out, err: (
                "openat" in err or "open(" in err,
                "strace output (stderr) must show openat() or open() syscalls"
            ),
        },
        {
            "id": 60, "level": "insane",
            "title": "Drop all capabilities from a process",
            "question": "Run 'python3 server.py' with ALL Linux capabilities dropped — a fully de-privileged process even if started by root.",
            "concept": "capsh --drop=all -- -c 'cmd' removes all capabilities before exec. Combined with --user, it sets uid/gid and clears the bounding set. This is how containers achieve privilege separation.",
            "hint": "capsh is the capability shell wrapper. --drop= removes capabilities before executing.",
            "title_ar": 'إسقاط جميع القدرات من عملية',
            "question_ar": "شغّل 'python3 server.py' مع إسقاط جميع قدرات Linux — عملية مُجرَّدة تماماً حتى لو بدأها المسؤول.",
            "concept_ar": "capsh --drop=all -- -c 'أمر' يزيل جميع القدرات قبل exec. مع --user يضبط uid/gid ويمسح مجموعة الحد. هكذا تُحقق الحاويات فصل الامتيازات.",
            "hint_ar": 'capsh هو غلاف شل القدرات. --drop= يزيل القدرات قبل التنفيذ.',

            "accepted": ["capsh --drop=all -- -c 'python3 server.py'", "capsh --drop=all -- -c \"python3 server.py\""],
            "keywords": ["capsh", "--drop", "python3", "server.py"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("capsh" in err + out or rc in (0,1,127), "Must use capsh --drop=all to strip all capabilities before exec."),
        },
    ],

    "processes": [
        {
            "id": 61, "level": "easy",
            "title": "List all running processes",
            "question": "Show all processes currently running on the system with their PID, user, CPU%, memory%, and command.",
            "concept": "ps reads /proc/<pid>/stat and /proc/<pid>/cmdline for each process. 'a' shows all users, 'u' shows user-oriented format, 'x' includes processes without a controlling terminal.",
            "hint": "ps with the flags a, u, x combined.",
            "title_ar": 'سرد جميع العمليات الجارية',
            "question_ar": 'اعرض جميع العمليات الجارية على النظام مع PID والمستخدم ونسبة CPU والذاكرة والأمر.',
            "concept_ar": "ps يقرأ /proc/<pid>/stat و/proc/<pid>/cmdline لكل عملية. 'a' تعرض جميع المستخدمين، 'u' تعرض تنسيق المستخدم، 'x' تشمل العمليات بدون طرفية.",
            "hint_ar": 'الأمر ps مع الأعلام a و u و x مدمجة.',

            "accepted": ["ps", "ps -aux"],
            "keywords": ["ps", "aux"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and "PID" in out and "CMD" in out and out.strip().count("\n") > 2,
                "Output must show process headers (PID, CMD) and multiple process rows"
            ),
        },
        {
            "id": 62, "level": "easy",
            "title": "Find a process by name",
            "question": "Find the PID of a process called 'bash' without using ps | grep.",
            "concept": "pgrep searches /proc for processes matching a pattern against their name or cmdline. It returns only PIDs — cleaner than ps|grep which also matches the grep process itself.",
            "hint": "pgrep is designed specifically for finding process IDs by name.",
            "title_ar": 'البحث عن عملية بالاسم',
            "question_ar": "ابحث عن PID عملية اسمها 'bash' دون استخدام ps | grep.",
            "concept_ar": 'pgrep يبحث في /proc عن العمليات المطابقة للنمط. يُعيد PID فقط — أنظف من ps|grep الذي يطابق عملية grep نفسها.',
            "hint_ar": 'pgrep مُصمَّم خصيصاً للبحث عن معرّفات العمليات بالاسم.',

            "accepted": ["pgrep nginx", "pgrep -l nginx", "pgrep bash", "pgrep -l bash"],
            "keywords": ["pgrep"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and bool(re.search(r'^\d+', out, re.MULTILINE)),
                "Output must contain at least one PID (a number) on its own line"
            ),
        },
        {
            "id": 63, "level": "easy",
            "title": "Kill a process gracefully",
            "question": "Send a graceful termination signal to a process with PID 4567, giving it a chance to clean up.",
            "concept": "SIGTERM (15) is the polite kill signal. The process can catch it, close files, flush buffers, and exit cleanly. SIGKILL (9) cannot be caught — use it only as a last resort.",
            "hint": "kill sends SIGTERM by default. Or specify signal 15 explicitly.",
            "title_ar": 'إيقاف عملية بشكل لطيف',
            "question_ar": 'أرسل إشارة إنهاء لطيفة إلى العملية ذات PID 4567 مع منحها فرصة للتنظيف.',
            "concept_ar": 'SIGTERM (15) هي إشارة الإيقاف المهذبة. يمكن للعملية اعتراضها وإغلاق الملفات وتفريغ المخازن والخروج بنظام. SIGKILL (9) لا يمكن اعتراضها.',
            "hint_ar": 'kill يرسل SIGTERM افتراضياً. أو حدد الإشارة 15 صراحةً.',

            "accepted": ["kill 4567", "kill -15 4567", "kill -SIGTERM 4567", "kill -TERM 4567"],
            "keywords": ["kill", "4567"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("kill" in err + out or rc in (0,1), "Must use kill with SIGTERM (default or -15). rc=1 is normal if PID doesn't exist."),
        },
        {
            "id": 64, "level": "easy",
            "title": "Run a process in background",
            "question": "Start 'sleep 60' in the background so the terminal remains usable.",
            "concept": "Appending & forks a child process and puts it in a background job group. The shell assigns it a job number and immediately returns the prompt. The process inherits the terminal as its controlling tty.",
            "hint": "A single character appended to any command sends it to the background.",
            "title_ar": 'تشغيل عملية في الخلفية',
            "question_ar": "شغّل 'sleep 60' في الخلفية حتى تبقى الطرفية قابلة للاستخدام.",
            "concept_ar": 'إضافة & تُشعّب عملية فرعية وتضعها في مجموعة مهام الخلفية. الشل يعيّن لها رقم مهمة ويعود للمحث فوراً.',
            "hint_ar": 'حرف واحد يُضاف لأي أمر يرسله للخلفية.',

            "accepted": ["python3 server.py &", "sleep 60 &"],
            "keywords": ["&"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0,
                "Command must start successfully in the background (exit code 0)"
            ),
        },
        {
            "id": 65, "level": "easy",
            "title": "View process tree",
            "question": "Show all running processes in a tree format that displays parent-child relationships.",
            "concept": "pstree reads PPID from /proc/<pid>/status to reconstruct the parent-child tree. Every process except PID 1 has a parent. The tree reveals process lineage and helps identify orphaned or zombie processes.",
            "hint": "pstree displays the process hierarchy as a tree.",
            "title_ar": 'عرض شجرة العمليات',
            "question_ar": 'اعرض جميع العمليات الجارية بتنسيق شجري يُظهر علاقات الأب والابن.',
            "concept_ar": 'pstree يقرأ PPID من /proc/<pid>/status لإعادة بناء الشجرة الهرمية. كل عملية ما عدا PID 1 لها أب.',
            "hint_ar": 'pstree يعرض هرمية العمليات كشجرة.',

            "accepted": ["pstree", "pstree -p"],
            "keywords": ["pstree"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and ("─" in out or "-" in out or "└" in out or "├" in out or "systemd" in out or "init" in out),
                "Output must show a tree structure with branches connecting processes"
            ),
        },
        {
            "id": 66, "level": "medium",
            "title": "Run process immune to hangup",
            "question": "Start 'sleep 300' so it continues running even after you log out of the SSH session.",
            "concept": "Closing an SSH session sends SIGHUP to the process group. nohup makes the process immune to SIGHUP and redirects stdout/stderr to nohup.out. combine with & to also background it.",
            "hint": "nohup stands for 'no hangup'. Combine it with & to background the process.",
            "title_ar": 'تشغيل عملية محصّنة ضد الإغلاق',
            "question_ar": "شغّل 'sleep 300' حتى تستمر في العمل بعد تسجيل خروجك من جلسة SSH.",
            "concept_ar": 'إغلاق جلسة SSH يرسل SIGHUP إلى مجموعة العمليات. nohup يجعل العملية محصّنة ضد SIGHUP ويعيد توجيه المخرجات إلى nohup.out.',
            "hint_ar": "nohup تعني 'لا علاقة'. ادمجها مع & لتخليف العملية في الخلفية.",

            "accepted": ["nohup ./backup.sh &", "nohup bash backup.sh &", "nohup sleep 300 &"],
            "keywords": ["nohup", "&"],
            "check_type": "keyword",
            "setup": "",
            "verify": None,
        },
        {
            "id": 67, "level": "medium",
            "title": "View what a process has open",
            "question": "List all files, sockets, and file descriptors currently open by the current shell process.",
            "concept": "lsof (list open files) reads /proc/<pid>/fd and /proc/<pid>/fdinfo for each fd. In Linux, everything is a file — sockets, pipes, and devices all appear as open fds.",
            "hint": "lsof lists open files. Use -p to filter by PID. Use $$ for the current shell PID.",
            "title_ar": 'عرض ما تفتحه عملية',
            "question_ar": 'سرد جميع الملفات والمقابس وواصفات الملفات المفتوحة حالياً من قِبل عملية الشل الحالية.',
            "concept_ar": 'lsof يقرأ /proc/<pid>/fd و/proc/<pid>/fdinfo لكل واصف. في Linux كل شيء ملف — المقابس والأنابيب والأجهزة تظهر كواصفات مفتوحة.',
            "hint_ar": 'lsof يسرد الملفات المفتوحة. استخدم -p للتصفية بـ PID. $$ لـ PID الشل الحالي.',

            "accepted": ["lsof -p 2222", "sudo lsof -p 2222", "lsof -p $$"],
            "keywords": ["lsof", "-p"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and ("FD" in out or "TYPE" in out) and out.strip().count("\n") > 1,
                "Output must show lsof column headers (FD, TYPE) and at least 2 rows"
            ),
        },
        {
            "id": 68, "level": "medium",
            "title": "Change process priority",
            "question": "Lower the CPU scheduling priority of a running process with PID 3333 to nice value 15.",
            "concept": "renice adjusts a running process's nice value. Nice ranges -20 (highest priority) to +19 (lowest). Normal users can only increase nice (lower priority). Root can decrease it.",
            "hint": "renice changes the priority of a running process. Syntax: renice -n VALUE -p PID.",
            "title_ar": 'تغيير أولوية عملية',
            "question_ar": 'خفّض أولوية جدولة CPU للعملية ذات PID 3333 إلى قيمة nice 15.',
            "concept_ar": 'renice يضبط قيمة nice لعملية جارية. تتراوح بين -20 (أعلى أولوية) و+19 (أدنى أولوية). المستخدمون العاديون يمكنهم فقط زيادة nice.',
            "hint_ar": 'renice يغيّر أولوية عملية جارية. الصيغة: renice -n قيمة -p PID.',

            "accepted": ["renice -n 15 -p 3333", "renice 15 3333", "renice 15 -p 3333"],
            "keywords": ["renice", "15", "3333"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("renice" in err + out or rc in (0,1), "Must use renice to change a process's nice value."),
        },
        {
            "id": 69, "level": "medium",
            "title": "Trace process system calls",
            "question": "Trace all system calls made by the 'ls' command and show which syscalls are used.",
            "concept": "strace uses the ptrace() syscall to intercept every kernel transition made by a process. It reveals what a program actually does at the OS boundary — invaluable for debugging and security analysis.",
            "hint": "strace is the system call tracer. Just prepend it to any command.",
            "title_ar": 'تتبع استدعاءات نظام العملية',
            "question_ar": "تتبع جميع استدعاءات النظام التي يُجريها الأمر 'ls' واعرض الاستدعاءات المستخدمة.",
            "concept_ar": 'strace يستخدم استدعاء ptrace() لاعتراض كل انتقال للنواة. يكشف ما يفعله البرنامج فعلياً على حدود نظام التشغيل.',
            "hint_ar": 'strace هو متتبع استدعاءات النظام. ضعه أمام أي أمر.',

            "accepted": ["strace ls /tmp", "strace ls"],
            "keywords": ["strace", "ls"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                bool(re.search(r'\w+\(.*\)\s+=\s+\d', err)),
                "strace output (stderr) must show syscall traces in format: syscall(args) = retval"
            ),
        },
        {
            "id": 70, "level": "medium",
            "title": "Send a signal to all matching processes",
            "question": "Send SIGTERM to all running processes named 'worker.py'.",
            "concept": "pkill sends a signal to all processes matching a pattern — the complement to pgrep. It reads /proc to find matches and sends the signal in one command. More reliable than ps|grep|awk|xargs chains.",
            "hint": "pkill is like pgrep but sends a signal. Default signal is SIGTERM.",
            "title_ar": 'إرسال إشارة إلى جميع العمليات المطابقة',
            "question_ar": "أرسل SIGTERM إلى جميع العمليات الجارية المسماة 'worker.py'.",
            "concept_ar": 'pkill يرسل إشارة إلى جميع العمليات المطابقة لنمط — مكمّل pgrep. يقرأ /proc ويُرسل الإشارة في أمر واحد.',
            "hint_ar": 'pkill مثل pgrep لكنه يرسل إشارة. الإشارة الافتراضية SIGTERM.',

            "accepted": ["pkill -f worker.py", "pkill worker.py", "pkill -15 -f worker.py"],
            "keywords": ["pkill", "worker.py"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("pkill" in err + out or rc in (0,1), "Must use pkill to send SIGTERM to matching processes."),
        },
        {
            "id": 71, "level": "medium",
            "title": "View process resource usage",
            "question": "Show real-time CPU and memory usage of all processes, sorted by CPU consumption.",
            "concept": "top reads /proc/<pid>/stat for each process and computes CPU% from the difference in jiffies between refreshes. Press P to sort by CPU, M by memory, q to quit.",
            "hint": "top is the classic interactive process viewer. Use it sorted by CPU by default.",
            "title_ar": 'عرض استخدام موارد العمليات',
            "question_ar": 'اعرض استخدام CPU والذاكرة في الوقت الفعلي لجميع العمليات مرتبةً بالاستهلاك الأعلى.',
            "concept_ar": 'top يقرأ /proc/<pid>/stat لكل عملية ويحسب نسبة CPU من الفرق في jiffies بين التحديثات.',
            "hint_ar": 'top هو عارض العمليات التفاعلي الكلاسيكي.',

            "accepted": ["top", "top -o %CPU"],
            "keywords": ["top"],
            "check_type": "keyword",
        "setup": '',
        "verify": None,
        },
        {
            "id": 72, "level": "medium",
            "title": "Check zombie processes",
            "question": "Show only zombie processes currently on the system.",
            "concept": "A zombie (Z state) has exited but its parent has not called wait(). It holds a task_struct in the kernel but no memory. Only the parent's wait() or the parent dying (re-parenting to PID 1) removes it.",
            "hint": "ps with a filter for state Z (zombie).",
            "title_ar": 'التحقق من العمليات الزومبي',
            "question_ar": 'اعرض العمليات الزومبي فقط الموجودة حالياً على النظام.',
            "concept_ar": 'الزومبي (حالة Z) انتهى لكن أبوه لم يستدع wait() بعد. يحتفظ بـ task_struct في النواة لكن دون ذاكرة. فقط wait() للأب أو وفاة الأب يزيله.',
            "hint_ar": 'ps مع مرشح للحالة Z (زومبي).',

            "accepted": ["ps aux | grep -w Z", "ps aux | awk '$8==\"Z\"'", "ps -el | grep Z"],
            "keywords": ["ps", "Z"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0,
                "Command must run successfully (exit code 0). It may return nothing if no zombies exist — that's correct."
            ),
        },
        {
            "id": 73, "level": "hard",
            "title": "Trace process and children",
            "question": "Trace the system calls of 'bash -c \"ls\"' AND all child processes it spawns.",
            "concept": "strace -f follows fork() calls and traces child processes. Without -f, you only see the parent's syscalls and miss everything spawned by the script. -f uses PTRACE_O_TRACEFORK.",
            "hint": "strace -f follows child processes created by fork().",
            "title_ar": 'تتبع عملية وعملياتها الفرعية',
            "question_ar": 'تتبع استدعاءات النظام لـ \'bash -c "ls"\' وجميع العمليات الفرعية التي يُولّدها.',
            "concept_ar": 'strace -f يتبع استدعاءات fork() ويتتبع العمليات الفرعية. بدون -f ترى استدعاءات الأب فقط وتُفوّت كل ما ولّده السكريبت.',
            "hint_ar": 'strace -f يتبع العمليات الفرعية التي يُنشئها fork().',

            "accepted": ["strace -f bash script.sh", "strace -f -o trace.log bash script.sh",
                         "strace -f bash -c 'ls'", "strace -f ls"],
            "keywords": ["strace", "-f"],
            "check_type": "keyword",
            "setup": "echo 'ls /tmp && echo done' > script.sh",
            "verify": lambda sb, rc, out, err: (
                bool(re.search(r'clone|fork|execve', err)),
                "strace -f output must show clone()/fork()/execve() syscalls from child processes"
            ),
        },
        {
            "id": 74, "level": "hard",
            "title": "Inspect kernel stack of frozen process",
            "question": "A process with PID 7777 is in D state (uninterruptible sleep). Show what kernel function it is waiting in.",
            "concept": "D state means the process is blocked inside the kernel holding a lock — SIGKILL cannot interrupt it. /proc/<pid>/wchan shows the kernel function it's waiting in. /proc/<pid>/stack shows the full kernel call stack.",
            "hint": "Look in /proc/<pid>/wchan for the wait channel — the kernel function the process is sleeping in.",
            "title_ar": 'فحص مكدس النواة لعملية متجمدة',
            "question_ar": 'عملية بـ PID 7777 في حالة D (نوم غير قابل للمقاطعة). اعرض دالة النواة التي تنتظر فيها.',
            "concept_ar": 'حالة D تعني أن العملية محجوبة داخل النواة وتحمل قفلاً — SIGKILL لا تستطيع مقاطعتها. /proc/<pid>/wchan يُظهر دالة النواة التي تنتظر فيها.',
            "hint_ar": 'ابحث في /proc/<pid>/wchan عن قناة الانتظار. استخدم $$ أو self للعملية الحالية.',

            "accepted": ["cat /proc/7777/wchan", "cat /proc/7777/stack", "sudo cat /proc/7777/stack",
                         "cat /proc/$$/wchan", "cat /proc/self/wchan"],
            "keywords": ["wchan"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and bool(out.strip()),
                "Output must contain the kernel wait channel name (a non-empty string)"
            ),
        },
        {
            "id": 75, "level": "hard",
            "title": "View OOM score of a process",
            "question": "Show the OOM killer score of the current shell process to understand how likely it is to be killed under memory pressure.",
            "concept": "The OOM killer scores each process based on memory usage and oom_score_adj. /proc/<pid>/oom_score shows the current calculated score. Higher score = more likely to be killed first.",
            "hint": "The OOM score is in /proc/<pid>/oom_score. Use $$ or 'self' to reference the current process.",
            "title_ar": 'عرض درجة OOM لعملية',
            "question_ar": 'اعرض درجة OOM killer للعملية الحالية لفهم احتمالية قتلها تحت ضغط الذاكرة.',
            "concept_ar": 'OOM killer يُصنّف كل عملية بناءً على استخدام الذاكرة وoom_score_adj. /proc/<pid>/oom_score يُظهر الدرجة المحسوبة. درجة أعلى = احتمالية قتل أكبر.',
            "hint_ar": "درجة OOM موجودة في /proc/<pid>/oom_score. استخدم $$ أو 'self' للعملية الحالية.",

            "accepted": ["cat /proc/1000/oom_score", "sudo cat /proc/1000/oom_score",
                         "cat /proc/$$/oom_score", "cat /proc/self/oom_score"],
            "keywords": ["oom_score"],
            "check_type": "keyword",
            "setup": "",
            "verify": lambda sb, rc, out, err: (
                rc == 0 and bool(re.search(r'^\d+', out.strip())),
                "Output must be a numeric OOM score (e.g. '0' or '250')"
            ),
        },
        {
            "id": 76, "level": "hard",
            "title": "Protect process from OOM killer",
            "question": "Configure the current process so the OOM killer will NEVER kill it, even under severe memory pressure.",
            "concept": "Writing -1000 to oom_score_adj sets the minimum possible score. The OOM killer always picks the highest-scoring process. -1000 makes it effectively immune. Used to protect databases and init.",
            "hint": "Write -1000 to /proc/<pid>/oom_score_adj. Use $$ for the current shell PID.",
            "title_ar": 'حماية عملية من OOM killer',
            "question_ar": 'هيّئ العملية الحالية حتى لا يقتلها OOM killer أبداً حتى تحت ضغط ذاكرة شديد.',
            "concept_ar": 'كتابة -1000 في oom_score_adj يضبط أدنى درجة ممكنة. OOM killer يختار العملية ذات الدرجة الأعلى دائماً. -1000 تجعلها محصّنة فعلياً.',
            "hint_ar": 'اكتب -1000 في /proc/<pid>/oom_score_adj. استخدم $$ لـ PID الشل الحالي.',

            "accepted": ["echo -1000 > /proc/1000/oom_score_adj", "sudo bash -c 'echo -1000 > /proc/1000/oom_score_adj'",
                         "echo -1000 > /proc/$$/oom_score_adj", "echo -1000 > /proc/self/oom_score_adj"],
            "keywords": ["oom_score_adj", "-1000"],
            "check_type": "keyword",
            "setup": "",
            "verify": None,
        },
        {
            "id": 77, "level": "hard",
            "title": "Limit process CPU with cgroup",
            "question": "Using cgroup v2, limit a process with PID 5555 to use at most 50% of one CPU core.",
            "concept": "cgroup v2 cpu.max format is 'quota period'. 50000 100000 means 50ms of CPU per 100ms period = 50% of one core. Writing PID to cgroup.procs assigns the process to the cgroup.",
            "hint": "Create a cgroup under /sys/fs/cgroup, set cpu.max, then write the PID to cgroup.procs.",
            "title_ar": 'تحديد CPU للعملية بـ cgroup',
            "question_ar": 'باستخدام cgroup v2، حدّد العملية ذات PID 5555 باستخدام 50% كحد أقصى من نواة CPU واحدة.',
            "concept_ar": "تنسيق cpu.max في cgroup v2 هو 'حصة فترة'. 50000 100000 تعني 50 مللي ثانية CPU كل 100 مللي ثانية = 50% من نواة واحدة.",
            "hint_ar": 'أنشئ cgroup تحت /sys/fs/cgroup، اضبط cpu.max، ثم اكتب PID في cgroup.procs.',

            "accepted": [
                "mkdir /sys/fs/cgroup/limited && echo '50000 100000' > /sys/fs/cgroup/limited/cpu.max && echo 5555 > /sys/fs/cgroup/limited/cgroup.procs",
                "echo '50000 100000' > /sys/fs/cgroup/limited/cpu.max"
            ],
            "keywords": ["cgroup", "cpu.max"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("cpu.max" in err + out or "cgroup" in err + out or rc in (0,1), "Must reference cgroup cpu.max to set CPU quota."),
        },
        {
            "id": 78, "level": "insane",
            "title": "Capture full process state",
            "question": "Dump the complete state (memory, registers, file descriptors) of a running process with PID 9000 to disk so it can be restored later.",
            "concept": "CRIU (Checkpoint/Restore In Userspace) freezes a process, serializes its entire kernel state (mm_struct, file descriptors, signals, timers) to disk. restore re-creates the exact kernel state. Used in live migration.",
            "hint": "CRIU is the tool for process checkpoint and restore. Use its 'dump' subcommand.",
            "title_ar": 'التقاط حالة عملية كاملة',
            "question_ar": 'احفظ الحالة الكاملة (الذاكرة والسجلات وواصفات الملفات) للعملية ذات PID 9000 على القرص حتى يمكن استعادتها لاحقاً.',
            "concept_ar": 'CRIU يُجمّد عملية ويُسلسل حالتها الكاملة (mm_struct، واصفات الملفات، الإشارات، المؤقتات) على القرص. restore يُعيد بناء الحالة الكاملة.',
            "hint_ar": "CRIU هي أداة نقطة تفتيش واستعادة العمليات. استخدم الأمر الفرعي 'dump'.",

            "accepted": ["criu dump -t 9000 -D /tmp/checkpoint", "sudo criu dump -t 9000 -D /tmp/checkpoint"],
            "keywords": ["criu", "dump", "9000"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("criu" in err + out or rc in (0,1,127), "Must use criu dump to checkpoint process state."),
        },
        {
            "id": 79, "level": "insane",
            "title": "Run process in new namespace",
            "question": "Start 'bash' in a completely isolated PID namespace where it sees itself as PID 1 and cannot see any host processes.",
            "concept": "unshare --pid --fork --mount-proc creates a new PID namespace. The process gets PID 1 in its namespace view. /proc is re-mounted to show only processes in the new namespace. This is the foundation of container isolation.",
            "hint": "unshare creates new namespaces. --pid creates a new PID namespace, --mount-proc re-mounts /proc.",
            "title_ar": 'تشغيل عملية في فضاء اسم جديد',
            "question_ar": "شغّل 'bash' في فضاء اسم PID معزول تماماً حيث يرى نفسه كـ PID 1 ولا يرى أي عمليات مضيف.",
            "concept_ar": 'unshare --pid --fork --mount-proc يُنشئ فضاء اسم PID جديداً. العملية تحصل على PID 1 في منظورها. /proc يُعاد تحميله لإظهار العمليات في الفضاء الجديد فقط.',
            "hint_ar": 'unshare يُنشئ فضاءات أسماء جديدة. --pid ينشئ فضاء PID، --mount-proc يُعيد تحميل /proc.',

            "accepted": ["unshare --pid --fork --mount-proc bash", "sudo unshare --pid --fork --mount-proc bash"],
            "keywords": ["unshare", "--pid", "--fork", "--mount-proc", "bash"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("unshare" in err + out or rc in (0,1), "Must use unshare --pid --fork --mount-proc to create isolated PID namespace."),
        },
        {
            "id": 80, "level": "insane",
            "title": "Profile which syscalls a program uses most",
            "question": "Run 'curl https://example.com' and show a summary of how many times each system call was made, sorted by frequency.",
            "concept": "strace -c counts syscalls and measures time spent in each. It uses PTRACE_SYSCALL to intercept every kernel entry/exit and builds a histogram. Essential for performance analysis and security auditing.",
            "hint": "strace -c gives a count summary instead of a trace. -S calls sorts by call count.",
            "title_ar": 'تحليل استدعاءات النظام الأكثر استخداماً',
            "question_ar": "شغّل 'curl https://example.com' واعرض ملخصاً لعدد مرات إجراء كل استدعاء نظام مرتباً بالتكرار.",
            "concept_ar": 'strace -c يعد استدعاءات النظام ويقيس الوقت في كل منها. يستخدم PTRACE_SYSCALL لاعتراض كل دخول/خروج للنواة ويبني رسماً بيانياً.',
            "hint_ar": 'strace -c يعطي ملخص عدد بدلاً من التتبع. -S calls يرتب بعدد الاستدعاءات.',

            "accepted": ["strace -c curl https://example.com", "strace -c -S calls curl https://example.com"],
            "keywords": ["strace", "-c", "curl"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("strace" in err + out and "-c" in err + out or rc in (0,1), "Must use strace -c to get a syscall count summary."),
        },
    ],

    "networking": [
        {
            "id": 81, "level": "easy",
            "title": "Show network interfaces",
            "question": "Show all network interfaces on this machine with their IP addresses and status.",
            "concept": "ip addr reads from the rtnetlink socket — the modern kernel interface for network configuration. ifconfig is deprecated (net-tools). ip is from iproute2 and communicates with the kernel via netlink.",
            "hint": "The modern command is 'ip addr'. ifconfig is the older deprecated alternative.",
            "title_ar": 'عرض واجهات الشبكة',
            "question_ar": 'اعرض جميع واجهات الشبكة على هذا الجهاز مع عناوين IP والحالة.',
            "concept_ar": 'ip addr يقرأ من مقبس rtnetlink — واجهة النواة الحديثة لتكوين الشبكة. ifconfig مهجور. ip من iproute2 يتواصل مع النواة عبر netlink.',
            "hint_ar": "الأمر الحديث هو 'ip addr'. ifconfig هو البديل القديم المهجور.",

            "accepted": ["ip addr", "ip addr show", "ip a", "ip a show"],
            "keywords": ["ip", "addr"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: (rc == 0 and bool(__import__("re").search(r"\d+: \w+:", out)), "ip addr must list interfaces in format N: name:"),
        },
        {
            "id": 82, "level": "easy",
            "title": "Test host reachability",
            "question": "Test if the host 'google.com' is reachable and measure round-trip time. Send exactly 4 packets.",
            "concept": "ping sends ICMP Echo Request packets. The kernel's network stack replies with Echo Reply. -c 4 sends exactly 4 packets then stops. RTT measures network latency, not TCP performance.",
            "hint": "ping with -c to set the count of packets to send.",
            "title_ar": 'اختبار الوصول إلى مضيف',
            "question_ar": "اختبر إمكانية الوصول إلى 'google.com' وقِس وقت الرحلة ذهاباً وإياباً. أرسل 4 حزم بالضبط.",
            "concept_ar": 'ping يرسل حزم ICMP Echo Request. مكدس شبكة النواة يرد بـ Echo Reply. -c 4 يرسل 4 حزم بالضبط ثم يتوقف.',
            "hint_ar": 'ping مع -c لضبط عدد الحزم المُرسَلة.',

            "accepted": ["ping -c 4 google.com", "ping -c4 google.com"],
            "keywords": ["ping", "-c", "4", "google.com"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("ping" in err + out or rc in (0,1,2), "Must use ping -c 4. Network may not be available in sandbox."),
        },
        {
            "id": 83, "level": "easy",
            "title": "Check which port a service uses",
            "question": "Show all TCP and UDP ports currently listening on this machine with the process name that owns each port.",
            "concept": "ss queries the kernel's socket table via netlink. -t=TCP, -u=UDP, -l=listening, -p=process, -n=numeric. Much faster than netstat which is deprecated.",
            "hint": "ss is the modern replacement for netstat. Use flags t, u, l, p, n.",
            "title_ar": 'التحقق من المنافذ التي تستمع إليها الخدمات',
            "question_ar": 'اعرض جميع منافذ TCP وUDP التي تستمع إليها حالياً مع اسم العملية المالكة.',
            "concept_ar": 'ss يستعلم جدول مقابس النواة عبر netlink. -t=TCP، -u=UDP، -l=استماع، -p=عملية، -n=رقمي. أسرع بكثير من netstat المهجور.',
            "hint_ar": 'ss هو البديل الحديث لـ netstat. استخدم الأعلام t و u و l و p و n.',

            "accepted": ["ss -tulpn", "ss -tlpn", "ss -tulpn", "netstat -tulpn"],
            "keywords": ["ss", "-tulpn"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: (rc == 0 and ("State" in out or "LISTEN" in out or "Recv-Q" in out), "ss -tulpn must show socket state table."),
        },
        {
            "id": 84, "level": "easy",
            "title": "Resolve a hostname to IP",
            "question": "Find the IP address of 'github.com' using a DNS lookup.",
            "concept": "dig queries DNS resolvers and shows the full response including TTL, record type, and which server responded. It uses the system resolver in /etc/resolv.conf by default.",
            "hint": "dig or nslookup perform DNS lookups. dig gives more detail.",
            "title_ar": 'حل اسم مضيف إلى IP',
            "question_ar": "ابحث عن عنوان IP لـ 'github.com' باستخدام استعلام DNS.",
            "concept_ar": 'dig يستعلم محللات DNS ويُظهر الاستجابة الكاملة بما يشمل TTL ونوع السجل والخادم الذي استجاب.',
            "hint_ar": 'dig أو nslookup يُجريان استعلامات DNS. dig يعطي تفاصيل أكثر.',

            "accepted": ["dig github.com", "nslookup github.com", "host github.com", "dig +short github.com"],
            "keywords": ["github.com"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: (rc == 0 and bool(__import__("re").search(r"\d+\.\d+\.\d+\.\d+", out) or "NXDOMAIN" in out or "ANSWER" in out), "DNS lookup must produce an IP or DNS response."),
        },
        {
            "id": 85, "level": "easy",
            "title": "View routing table",
            "question": "Display the kernel's routing table to see how packets are routed to different networks.",
            "concept": "ip route reads the kernel FIB (Forwarding Information Base) via rtnetlink. The default route (0.0.0.0/0) is the gateway of last resort. Longest-prefix match selects which route handles each packet.",
            "hint": "ip route shows the routing table. The 'default' line shows the gateway.",
            "title_ar": 'عرض جدول التوجيه',
            "question_ar": 'اعرض جدول التوجيه في النواة لفهم كيفية توجيه الحزم إلى الشبكات المختلفة.',
            "concept_ar": 'ip route يقرأ FIB للنواة (قاعدة بيانات إعادة التوجيه) عبر rtnetlink. المسار الافتراضي (0.0.0.0/0) هو بوابة الملاذ الأخير.',
            "hint_ar": "ip route يُظهر جدول التوجيه. سطر 'default' يُظهر البوابة.",

            "accepted": ["ip route", "ip route show", "ip r", "route -n"],
            "keywords": ["ip", "route"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: (rc == 0 and bool(__import__("re").search(r"\d+\.\d+\.\d+\.\d+|default", out)), "ip route must show routing entries with IPs or a default route."),
        },
        {
            "id": 86, "level": "medium",
            "title": "Trace network path to host",
            "question": "Show the full network path (all hops) from this machine to 'cloudflare.com'.",
            "concept": "traceroute sends probes with TTL starting at 1, incrementing each round. Each router decrements TTL; at 0 it sends ICMP Time Exceeded revealing its IP. This TTL-trick maps the entire path.",
            "hint": "traceroute traces the route packets take through the network.",
            "title_ar": 'تتبع مسار الشبكة إلى مضيف',
            "question_ar": "اعرض مسار الشبكة الكامل (جميع القفزات) من هذا الجهاز إلى 'cloudflare.com'.",
            "concept_ar": 'traceroute يرسل حزم استكشاف بقيم TTL متزايدة. كل موجّه يُقلّل TTL؛ عند الصفر يرسل ICMP Time Exceeded كاشفاً IP القفزة.',
            "hint_ar": 'traceroute يتتبع المسار الذي تسلكه الحزم في الشبكة.',

            "accepted": ["traceroute cloudflare.com", "tracepath cloudflare.com"],
            "keywords": ["traceroute", "cloudflare.com"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("traceroute" in err + out or rc in (0,1), "Must use traceroute or tracepath."),
        },
        {
            "id": 87, "level": "medium",
            "title": "Capture network packets",
            "question": "Capture all TCP traffic on port 443 on interface eth0 and save it to a file called 'capture.pcap'.",
            "concept": "tcpdump uses BPF (Berkeley Packet Filter) — a kernel VM that filters packets before they reach userspace. Only matching packets are copied, minimizing overhead. -w writes raw pcap format for Wireshark.",
            "hint": "tcpdump with -i for interface, -w to write to file, and a BPF filter expression.",
            "title_ar": 'التقاط حزم الشبكة',
            "question_ar": "التقط جميع حركة TCP على المنفذ 443 على واجهة eth0 واحفظها في ملف 'capture.pcap'.",
            "concept_ar": 'tcpdump يستخدم BPF — آلة نواة افتراضية تُصفّي الحزم قبل وصولها لفضاء المستخدم. الحزم المطابقة فقط تُنسخ، مما يُقلل العبء. -w يكتب بصيغة pcap خام.',
            "hint_ar": 'tcpdump مع -i للواجهة، -w للحفظ في ملف، وتعبير BPF.',

            "accepted": ["tcpdump -i eth0 'tcp port 443' -w capture.pcap", "tcpdump -i eth0 tcp port 443 -w capture.pcap"],
            "keywords": ["tcpdump", "-i", "eth0", "443", "capture.pcap"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("tcpdump" in err + out or rc in (0,1), "Must use tcpdump with -i, port filter, and -w to save pcap."),
        },
        {
            "id": 88, "level": "medium",
            "title": "Check if a port is open",
            "question": "Test if port 22 is open on host '192.168.1.100' from the command line without installing additional tools.",
            "concept": "nc (netcat) attempts a TCP connection. -z means scan mode (don't send data). -v shows verbose output. /dev/tcp in bash is an alternative. This is the simplest port connectivity test.",
            "hint": "nc (netcat) is the network swiss army knife. Use it with -z for port scanning.",
            "title_ar": 'التحقق من فتح منفذ',
            "question_ar": "اختبر ما إذا كان المنفذ 22 مفتوحاً على المضيف '192.168.1.100' من سطر الأوامر دون تثبيت أدوات إضافية.",
            "concept_ar": 'nc (netcat) يحاول اتصال TCP. -z تعني وضع الفحص (لا إرسال بيانات). -v يُظهر إخراجاً تفصيلياً. هذا أبسط اختبار اتصال بمنفذ.',
            "hint_ar": 'nc (netcat) هو السكين السويسري للشبكات. استخدمه مع -z لفحص المنافذ.',

            "accepted": ["nc -zv 192.168.1.100 22", "nc -z 192.168.1.100 22", "nmap -p 22 192.168.1.100"],
            "keywords": ["192.168.1.100", "22"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("nc" in err + out or "nmap" in err + out or rc in (0,1), "Must use nc -z or nmap to test port connectivity."),
        },
        {
            "id": 89, "level": "medium",
            "title": "Block incoming traffic with iptables",
            "question": "Block all incoming TCP connections on port 8080 using iptables.",
            "concept": "iptables -A INPUT appends a rule to the INPUT chain. -p tcp matches TCP protocol. --dport matches destination port. -j DROP silently drops the packet. Rules are checked top-to-bottom; first match wins.",
            "hint": "iptables with -A INPUT, specify protocol and destination port, then -j DROP.",
            "title_ar": 'حظر الحركة الواردة بـ iptables',
            "question_ar": 'احظر جميع اتصالات TCP الواردة على المنفذ 8080 باستخدام iptables.',
            "concept_ar": 'iptables -A INPUT يُضيف قاعدة إلى سلسلة INPUT. -p tcp يطابق بروتوكول TCP. --dport يطابق المنفذ الوجهة. -j DROP يُسقط الحزمة صامتاً.',
            "hint_ar": 'iptables مع -A INPUT، حدد البروتوكول والمنفذ الوجهة، ثم -j DROP.',

            "accepted": ["iptables -A INPUT -p tcp --dport 8080 -j DROP", "sudo iptables -A INPUT -p tcp --dport 8080 -j DROP"],
            "keywords": ["iptables", "-A", "INPUT", "tcp", "8080", "DROP"],
            "check_type": "keyword",
        "setup": '',
        "verify": None,
        },
        {
            "id": 90, "level": "medium",
            "title": "Show active TCP connections",
            "question": "Show all established TCP connections with remote addresses, local ports, and the process name.",
            "concept": "ss -tp shows TCP sockets with process info. 'ESTABLISHED' state means the three-way handshake completed and the connection is active. The kernel tracks each connection as a struct tcp_sock.",
            "hint": "ss with flags for TCP, established state, and process info.",
            "title_ar": 'عرض اتصالات TCP النشطة',
            "question_ar": 'اعرض جميع اتصالات TCP المُنشأة مع العناوين البعيدة والمنافذ المحلية واسم العملية.',
            "concept_ar": "ss -tp يُظهر مقابس TCP مع معلومات العملية. حالة 'ESTABLISHED' تعني اكتمال المصافحة الثلاثية والاتصال نشط.",
            "hint_ar": 'ss مع أعلام لـ TCP وحالة التأسيس ومعلومات العملية.',

            "accepted": ["ss -tp", "ss -t state established", "ss -tp state established", "netstat -tp"],
            "keywords": ["ss", "-tp"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: (rc == 0 and ("Recv-Q" in out or "State" in out or "ESTAB" in out), "ss output must show TCP connection state information."),
        },
        {
            "id": 91, "level": "medium",
            "title": "Download a file from URL",
            "question": "Download a file from 'https://example.com/file.tar.gz' and save it with its original filename.",
            "concept": "curl -O saves with the remote filename (capital O = Output). wget -O - streams to stdout. Both use the HTTP GET method over a TCP connection. curl is more scriptable; wget handles recursive downloads.",
            "hint": "curl with the -O flag (capital O) saves the file with its remote filename.",
            "title_ar": 'تنزيل ملف من رابط',
            "question_ar": "نزّل ملفاً من 'https://example.com/file.tar.gz' واحفظه باسمه الأصلي.",
            "concept_ar": 'curl -O يحفظ باسم الملف البعيد (O كبير = Output). wget يُنزّل بشكل افتراضي باسم الملف. كلاهما يستخدم HTTP GET على اتصال TCP.',
            "hint_ar": 'curl مع الخيار -O (O كبير) يحفظ الملف باسمه البعيد.',

            "accepted": ["curl -O https://example.com/file.tar.gz", "wget https://example.com/file.tar.gz"],
            "keywords": ["https://example.com/file.tar.gz"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("curl" in err + out or "wget" in err + out or rc in (0,1), "Must use curl -O or wget to download with original filename."),
        },
        {
            "id": 92, "level": "medium",
            "title": "Show ARP table",
            "question": "Display the ARP cache to see which IP addresses have been resolved to MAC addresses.",
            "concept": "The ARP cache maps IP addresses to MAC addresses on a local network. arp -n shows numeric addresses. ip neigh is the modern equivalent. Stale entries can indicate ARP poisoning attacks.",
            "hint": "arp -n shows the ARP cache. ip neigh is the modern alternative.",
            "title_ar": 'عرض جدول ARP',
            "question_ar": 'اعرض ذاكرة ARP المؤقتة لمعرفة عناوين IP التي جرى حلها إلى عناوين MAC.',
            "concept_ar": 'ذاكرة ARP المؤقتة تربط عناوين IP بعناوين MAC على الشبكة المحلية. ip neigh هو البديل الحديث. المدخلات القديمة قد تشير إلى تسمم ARP.',
            "hint_ar": 'arp -n يُظهر ذاكرة ARP المؤقتة. ip neigh هو البديل الحديث.',

            "accepted": ["arp -n", "ip neigh", "ip neighbor", "ip neigh show"],
            "keywords": ["arp"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: (rc == 0, "ARP/neighbour command must run successfully."),
        },
        {
            "id": 93, "level": "hard",
            "title": "Capture and read HTTP headers",
            "question": "Make an HTTP GET request to 'http://example.com' and show ONLY the response headers, not the body.",
            "concept": "curl -I sends a HEAD request (or -D - dumps headers separately). HTTP/1.1 headers are plaintext before the body. Understanding header structure is fundamental for web security testing.",
            "hint": "curl has a flag to show only headers. -I sends a HEAD request.",
            "title_ar": 'التقاط رؤوس HTTP وقراءتها',
            "question_ar": "أجرِ طلب HTTP GET إلى 'http://example.com' واعرض رؤوس الاستجابة فقط، ليس الجسم.",
            "concept_ar": 'curl -I يرسل طلب HEAD. رؤوس HTTP/1.1 نص عادي قبل الجسم. فهم بنية الرأس أساسي لاختبار أمان تطبيقات الويب.',
            "hint_ar": 'curl لديه خيار لعرض الرؤوس فقط. -I يرسل طلب HEAD.',

            "accepted": ["curl -I http://example.com", "curl -I http://example.com/", "curl --head http://example.com"],
            "keywords": ["curl", "-I", "http://example.com"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: (rc == 0 and ("HTTP/" in out or "Content-Type" in out or "Server:" in out), "curl -I must return HTTP headers from example.com."),
        },
        {
            "id": 94, "level": "hard",
            "title": "Create a network namespace",
            "question": "Create a new isolated network namespace called 'testnet' where you can test networking independently from the host.",
            "concept": "Network namespaces give a process its own independent network stack: interfaces, routing table, iptables rules, and sockets. ip netns uses clone() with CLONE_NEWNET. This is how Docker isolates container networks.",
            "hint": "ip netns is the command for managing network namespaces.",
            "title_ar": 'إنشاء فضاء اسم شبكة',
            "question_ar": "أنشئ فضاء اسم شبكة معزولاً جديداً اسمه 'testnet'.",
            "concept_ar": 'فضاءات أسماء الشبكة تمنح العملية مكدس شبكة مستقلاً: واجهات وجدول توجيه وقواعد iptables ومقابس. ip netns يستخدم clone() مع CLONE_NEWNET.',
            "hint_ar": 'ip netns هو الأمر لإدارة فضاءات أسماء الشبكة.',

            "accepted": ["ip netns add testnet", "sudo ip netns add testnet"],
            "keywords": ["ip", "netns", "add", "testnet"],
            "check_type": "keyword",
        "setup": '',
        "verify": None,
        },
        {
            "id": 95, "level": "hard",
            "title": "Inspect TCP connection states",
            "question": "Show a count of TCP connections grouped by state (ESTABLISHED, TIME_WAIT, CLOSE_WAIT, etc.).",
            "concept": "TIME_WAIT holds a socket for 2×MSL after close to absorb delayed packets. Many TIME_WAIT = high connection turnover (normal). Many CLOSE_WAIT = application not closing sockets (bug). Understanding states is key for diagnosing server issues.",
            "hint": "Combine ss or netstat with awk or grep to count connections by state.",
            "title_ar": 'فحص حالات اتصال TCP',
            "question_ar": 'اعرض عدد اتصالات TCP مجمّعةً بالحالة (ESTABLISHED، TIME_WAIT، CLOSE_WAIT، إلخ).',
            "concept_ar": 'TIME_WAIT يحتفظ بالمقبس لـ 2×MSL بعد الإغلاق لاستيعاب الحزم المتأخرة. كثير من TIME_WAIT = دوران اتصالات عالٍ. كثير من CLOSE_WAIT = التطبيق لا يغلق المقابس.',
            "hint_ar": 'ادمج ss أو netstat مع awk أو grep لعد الاتصالات بالحالة.',

            "accepted": ["ss -t | awk 'NR>1 {print $1}' | sort | uniq -c", "netstat -nt | awk '{print $6}' | sort | uniq -c", "ss -tan | awk 'NR>1 {print $1}' | sort | uniq -c"],
            "keywords": ["ss", "uniq", "-c"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: (rc == 0 and bool(__import__("re").search(r"\d+\s+\w+", out)), "Output must show count+state pairs like 5 ESTABLISHED."),
        },
        {
            "id": 96, "level": "hard",
            "title": "Sniff DNS queries",
            "question": "Capture only DNS queries (UDP port 53) on any interface and print them to the terminal in real time.",
            "concept": "DNS uses UDP port 53. tcpdump with BPF filter 'udp port 53' captures only DNS traffic. The -l flag line-buffers output so you see DNS queries in real time as they happen.",
            "hint": "tcpdump on any interface (-i any) with a filter for udp port 53.",
            "title_ar": 'التجسس على استعلامات DNS',
            "question_ar": 'التقط استعلامات DNS فقط (UDP منفذ 53) على أي واجهة وعرضها في الطرفية في الوقت الفعلي.',
            "concept_ar": "DNS يستخدم UDP منفذ 53. tcpdump مع مرشح BPF 'udp port 53' يلتقط حركة DNS فقط. الخيار -l يُنهي التخزين المؤقت لترى الاستعلامات فورياً.",
            "hint_ar": 'tcpdump على أي واجهة (-i any) مع مرشح udp port 53.',

            "accepted": ["tcpdump -i any -l 'udp port 53'", "tcpdump -i any udp port 53", "sudo tcpdump -i any udp port 53"],
            "keywords": ["tcpdump", "udp", "53"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: ("tcpdump" in err + out or rc in (0,1), "Must use tcpdump with udp port 53 filter."),
        },
        {
            "id": 97, "level": "hard",
            "title": "Enable IP forwarding",
            "question": "Enable IP packet forwarding on this Linux machine so it can act as a router between two networks.",
            "concept": "ip_forward=1 enables the kernel's FORWARD chain processing. Without it, the kernel drops packets destined for other hosts. This is the kernel toggle that makes a Linux box a router or NAT gateway.",
            "hint": "Write 1 to /proc/sys/net/ipv4/ip_forward to enable forwarding.",
            "title_ar": 'تفعيل إعادة توجيه IP',
            "question_ar": 'فعّل إعادة توجيه حزم IP على هذا الجهاز حتى يتمكن من العمل كموجّه بين شبكتين.',
            "concept_ar": 'ip_forward=1 يُفعّل معالجة سلسلة FORWARD في النواة. بدونه تُسقط النواة الحزم المُوجَّهة لمضيفين آخرين. هذا هو مفتاح التبديل الذي يجعل Linux موجّهاً.',
            "hint_ar": 'اكتب 1 في /proc/sys/net/ipv4/ip_forward لتفعيل التوجيه.',

            "accepted": ["echo 1 > /proc/sys/net/ipv4/ip_forward", "sysctl -w net.ipv4.ip_forward=1", "sudo sysctl -w net.ipv4.ip_forward=1"],
            "keywords": ["ip_forward"],
            "check_type": "keyword",
        "setup": '',
        "verify": None,
        },
        {
            "id": 98, "level": "insane",
            "title": "Set up NAT masquerading",
            "question": "Configure this machine to share its internet connection (on eth0) with machines on the private network 192.168.1.0/24 connected via eth1.",
            "concept": "MASQUERADE is dynamic SNAT that automatically uses eth0's current IP. The kernel's conntrack module tracks each connection to translate reply packets back. Combined with ip_forward, this creates a full NAT router.",
            "hint": "You need iptables MASQUERADE on POSTROUTING chain and ip_forward enabled.",
            "title_ar": 'إعداد NAT masquerading',
            "question_ar": 'هيّئ هذا الجهاز لمشاركة اتصاله بالإنترنت (على eth0) مع أجهزة الشبكة الخاصة 192.168.1.0/24.',
            "concept_ar": 'MASQUERADE هو SNAT ديناميكي يستخدم تلقائياً IP الحالي لـ eth0. وحدة conntrack في النواة تتتبع كل اتصال لترجمة حزم الرد. مع ip_forward يُنشئ موجّه NAT كامل.',
            "hint_ar": 'تحتاج iptables MASQUERADE على سلسلة POSTROUTING وتفعيل ip_forward.',

            "accepted": [
                "iptables -t nat -A POSTROUTING -s 192.168.1.0/24 -o eth0 -j MASQUERADE",
                "sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE"
            ],
            "keywords": ["iptables", "MASQUERADE", "POSTROUTING"],
            "check_type": "keyword",
        "setup": '',
        "verify": None,
        },
        {
            "id": 99, "level": "insane",
            "title": "Create a virtual ethernet pair",
            "question": "Create a veth (virtual ethernet) pair called 'veth0' and 'veth1' — a virtual cable connecting two network namespaces.",
            "concept": "veth pairs are a kernel virtual cable: packets in one end come out the other instantly in kernel space, no userspace involved. Used by Docker to connect container network namespaces to the host bridge. Created via netlink.",
            "hint": "ip link add with type veth creates both ends of the pair simultaneously.",
            "title_ar": 'إنشاء زوج ethernet افتراضي',
            "question_ar": "أنشئ زوج veth (ethernet افتراضي) يسمى 'veth0' و'veth1' — كابل افتراضي يربط فضاءي اسم شبكة.",
            "concept_ar": 'أزواج veth كابل افتراضي في النواة: الحزم التي تدخل من طرف تخرج من الآخر فورياً في فضاء النواة. تستخدمها Docker لربط فضاءات أسماء شبكة الحاويات بجسر المضيف.',
            "hint_ar": 'ip link add مع type veth يُنشئ كلا الطرفين في آنٍ واحد.',

            "accepted": ["ip link add veth0 type veth peer name veth1", "sudo ip link add veth0 type veth peer name veth1"],
            "keywords": ["ip", "link", "add", "veth0", "type", "veth", "peer", "veth1"],
            "check_type": "keyword",
        "setup": '',
        "verify": None,
        },
        {
            "id": 100, "level": "insane",
            "title": "Load a simple eBPF program",
            "question": "Use bpftool to list all currently loaded eBPF programs on the kernel, showing their type and attachment points.",
            "concept": "eBPF programs run in a kernel JIT-compiled VM attached to hooks (XDP, tc, kprobes, tracepoints). bpftool reads the kernel's eBPF program table via the bpf() syscall. This is how modern observability tools like Cilium work.",
            "hint": "bpftool prog list shows all loaded eBPF programs.",
            "title_ar": 'تحميل برنامج eBPF',
            "question_ar": 'استخدم bpftool لسرد جميع برامج eBPF المحمّلة حالياً في النواة، مع إظهار نوعها ونقاط تعلّقها.',
            "concept_ar": 'برامج eBPF تعمل في آلة JIT افتراضية في النواة مرتبطة بخطافات (XDP، tc، kprobes). bpftool يقرأ جدول برامج eBPF في النواة عبر استدعاء bpf(). هكذا تعمل أدوات الرصد الحديثة.',
            "hint_ar": 'bpftool prog list يسرد جميع برامج eBPF المحمّلة.',

            "accepted": ["bpftool prog list", "bpftool prog show", "sudo bpftool prog list"],
            "keywords": ["bpftool", "prog"],
            "check_type": "keyword",
        "setup": '',
        "verify": lambda sb, rc, out, err: (rc in (0,1,127), "bpftool prog list must run. rc=127 means not installed — acceptable."),
        },
    ],
}

# ─────────────────────────────────────────────────────────────
# EXTERNAL PLUGIN / TASK LOADER
# ─────────────────────────────────────────────────────────────
import glob

PLUGIN_TASKS = {}   # domain_name -> [task_dicts]  (loaded from tasks/*.json or tasks/*.yaml)
_PLUGIN_META = {}   # domain_name -> {name, description, author}

def _load_plugins():
    """
    Scan the tasks/ directory next to this script for JSON/YAML plugin files.
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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tasks_dir  = os.path.join(script_dir, "tasks")
    if not os.path.isdir(tasks_dir):
        return

    # Attempt YAML import
    try:
        import yaml as _yaml
        _has_yaml = True
    except ImportError:
        _has_yaml = False

    patterns = [os.path.join(tasks_dir, "*.json")]
    if _has_yaml:
        patterns.append(os.path.join(tasks_dir, "*.yaml"))
        patterns.append(os.path.join(tasks_dir, "*.yml"))

    for pattern in patterns:
        for filepath in sorted(glob.glob(pattern)):
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

# ─────────────────────────────────────────────────────────────
# CHALLENGE MODE
# ─────────────────────────────────────────────────────────────
CHALLENGES = [
    # ── Beginner ──────────────────────────────────────────────
    {
        "id": "C01",
        "level": "beginner",
        "title": "The Missing Config",
        "description": "A web server refuses to start. The config directory exists but is missing its main file. Restore the situation.",
        "steps": [
            {
                "prompt": "Step 1 — Create the directory /etc/webserver/ if it does not exist.",
                "hint": "mkdir with -p creates parent dirs too.",
                "accepted": ["mkdir -p /etc/webserver", "mkdir /etc/webserver"],
                "keywords": ["mkdir"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (os.path.isdir(os.path.join(sb, "etc", "webserver")) or rc == 0, "Directory must exist"),
            },
            {
                "prompt": "Step 2 — Create an empty file called 'webserver.conf' inside that directory.",
                "hint": "touch creates an empty file.",
                "accepted": ["touch etc/webserver/webserver.conf", "touch webserver.conf"],
                "keywords": ["touch", "webserver.conf"],
                "setup": "mkdir -p etc/webserver",
                "verify": lambda sb, rc, out, err: (
                    os.path.isfile(os.path.join(sb, "etc", "webserver", "webserver.conf")) or
                    os.path.isfile(os.path.join(sb, "webserver.conf")),
                    "webserver.conf must exist"
                ),
            },
            {
                "prompt": "Step 3 — Set its permissions to owner read+write only (no group or other access).",
                "hint": "chmod with octal 600.",
                "accepted": ["chmod 600 etc/webserver/webserver.conf", "chmod 600 webserver.conf"],
                "keywords": ["chmod", "600"],
                "setup": "mkdir -p etc/webserver && touch etc/webserver/webserver.conf",
                "verify": lambda sb, rc, out, err: (
                    any(
                        os.path.isfile(p) and oct(os.stat(p).st_mode)[-3:] == "600"
                        for p in [
                            os.path.join(sb, "etc", "webserver", "webserver.conf"),
                            os.path.join(sb, "webserver.conf"),
                        ] if os.path.exists(p)
                    ),
                    "File must have mode 600"
                ),
            },
        ],
    },
    {
        "id": "C02",
        "level": "beginner",
        "title": "Log Triage",
        "description": "An app is spewing logs. Find and count the critical errors, then extract them to a separate file.",
        "steps": [
            {
                "prompt": "Step 1 — Count how many lines in 'app.log' contain the word CRITICAL.",
                "hint": "grep -c counts matching lines.",
                "accepted": ["grep -c CRITICAL app.log", "grep -c 'CRITICAL' app.log"],
                "keywords": ["grep", "-c", "CRITICAL", "app.log"],
                "setup": "printf 'INFO ok\nCRITICAL disk full\nINFO ok\nCRITICAL oom kill\nCRITICAL segfault\n' > app.log",
                "verify": lambda sb, rc, out, err: (rc == 0 and "3" in out, "Must output count 3"),
            },
            {
                "prompt": "Step 2 — Extract all CRITICAL lines from 'app.log' into a new file called 'critical.log'.",
                "hint": "grep with output redirection.",
                "accepted": ["grep CRITICAL app.log > critical.log", "grep 'CRITICAL' app.log > critical.log"],
                "keywords": ["grep", "CRITICAL", "app.log", "critical.log"],
                "setup": "printf 'INFO ok\nCRITICAL disk full\nINFO ok\nCRITICAL oom kill\nCRITICAL segfault\n' > app.log",
                "verify": lambda sb, rc, out, err: (
                    os.path.isfile(os.path.join(sb, "critical.log")) and
                    open(os.path.join(sb, "critical.log")).read().count("CRITICAL") == 3,
                    "critical.log must contain exactly 3 CRITICAL lines"
                ),
            },
            {
                "prompt": "Step 3 — Show the 3rd line of 'critical.log' only.",
                "hint": "Combine head and tail, or use sed with a line number.",
                "accepted": ["sed -n '3p' critical.log", "head -3 critical.log | tail -1", "awk 'NR==3' critical.log"],
                "keywords": ["critical.log"],
                "setup": "printf 'CRITICAL disk full\nCRITICAL oom kill\nCRITICAL segfault\n' > critical.log",
                "verify": lambda sb, rc, out, err: (rc == 0 and "segfault" in out, "Output must show the 3rd line containing 'segfault'"),
            },
        ],
    },
    # ── Intermediate ───────────────────────────────────────────
    {
        "id": "C03",
        "level": "intermediate",
        "title": "Broken Permissions Chain",
        "description": "A shared project directory has wrong permissions throughout. Audit and fix the entire tree.",
        "steps": [
            {
                "prompt": "Step 1 — Show the current permissions of 'project/' and all files inside it (long format, recursive).",
                "hint": "ls -lR shows long format recursively.",
                "accepted": ["ls -lR project", "ls -lR project/"],
                "keywords": ["ls", "-lR", "project"],
                "setup": "mkdir -p project/src project/docs && touch project/src/main.py project/docs/readme.txt && chmod 000 project/src/main.py",
                "verify": lambda sb, rc, out, err: (rc == 0 and "main.py" in out, "Must list project/ contents recursively"),
            },
            {
                "prompt": "Step 2 — Give the owner read+write+execute on 'project/' recursively, group read+execute, others nothing.",
                "hint": "chmod -R 750 sets rwxr-x--- on all entries.",
                "accepted": ["chmod -R 750 project", "chmod -R 750 project/"],
                "keywords": ["chmod", "-R", "750", "project"],
                "setup": "mkdir -p project/src project/docs && touch project/src/main.py project/docs/readme.txt",
                "verify": lambda sb, rc, out, err: (
                    rc == 0 and oct(os.stat(os.path.join(sb, "project")).st_mode)[-3:] == "750" and
                    oct(os.stat(os.path.join(sb, "project", "src", "main.py")).st_mode)[-3:] == "750",
                    "All entries must have mode 750"
                ),
            },
            {
                "prompt": "Step 3 — Set the setgid bit on 'project/' so new files inherit its group.",
                "hint": "chmod g+s sets the setgid bit.",
                "accepted": ["chmod g+s project", "chmod g+s project/"],
                "keywords": ["chmod", "g+s", "project"],
                "setup": "mkdir -p project/src && chmod 750 project",
                "verify": lambda sb, rc, out, err: (
                    bool(os.stat(os.path.join(sb, "project")).st_mode & stat.S_ISGID),
                    "project/ must have setgid bit set"
                ),
            },
            {
                "prompt": "Step 4 — Find any world-writable files inside 'project/' (a security risk).",
                "hint": "find with -perm -002 matches world-writable.",
                "accepted": ["find project -perm -002", "find project/ -perm -002 -type f"],
                "keywords": ["find", "project", "-perm", "-002"],
                "setup": "mkdir -p project/src && touch project/src/backdoor.sh && chmod 777 project/src/backdoor.sh",
                "verify": lambda sb, rc, out, err: (rc == 0 and "backdoor.sh" in out, "Must find backdoor.sh (world-writable)"),
            },
        ],
    },
    {
        "id": "C04",
        "level": "intermediate",
        "title": "Rogue Process Hunt",
        "description": "A process is consuming too much CPU and writing to suspicious files. Identify and neutralise it.",
        "steps": [
            {
                "prompt": "Step 1 — List all running processes sorted by CPU usage (highest first).",
                "hint": "ps aux sorted by %CPU, or use top -b -n1.",
                "accepted": ["ps aux --sort=-%cpu", "ps aux --sort=-%CPU", "top -b -n1 | head -20", "ps aux | sort -rk3"],
                "keywords": ["ps", "aux"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (rc == 0 and "PID" in out, "Must show processes with PID column"),
            },
            {
                "prompt": "Step 2 — Show all open files held by the process with PID 1 (use PID 1 as a safe substitute).",
                "hint": "lsof -p shows open files for a PID.",
                "accepted": ["lsof -p 1", "sudo lsof -p 1", "ls /proc/1/fd"],
                "keywords": ["lsof", "-p"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (rc == 0 or rc == 1, "lsof must run without crashing"),
            },
            {
                "prompt": "Step 3 — Send SIGTERM to a process named 'suspicious' (it may not exist — that's fine).",
                "hint": "pkill sends a signal to all matching process names.",
                "accepted": ["pkill suspicious", "pkill -15 suspicious", "pkill -TERM suspicious"],
                "keywords": ["pkill", "suspicious"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (rc in (0, 1), "pkill must run; rc=1 means no match, which is acceptable"),
            },
            {
                "prompt": "Step 4 — Show the OOM score of the current shell process to understand its memory priority.",
                "hint": "Read /proc/self/oom_score.",
                "accepted": ["cat /proc/self/oom_score", "cat /proc/$$/oom_score"],
                "keywords": ["oom_score"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (rc == 0 and bool(re.search(r'^\d+', out.strip())), "Must output a numeric OOM score"),
            },
        ],
    },
    # ── Advanced ───────────────────────────────────────────────
    {
        "id": "C05",
        "level": "advanced",
        "title": "Network Forensics",
        "description": "Investigate active network connections, identify suspicious listeners, and lock them down.",
        "steps": [
            {
                "prompt": "Step 1 — List all listening TCP ports with their process names.",
                "hint": "ss -tulpn shows listening sockets with processes.",
                "accepted": ["ss -tulpn", "ss -tlpn", "netstat -tulpn"],
                "keywords": ["ss", "-tulpn"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (rc == 0 and ("State" in out or "LISTEN" in out or "Recv-Q" in out), "Must show socket state table"),
            },
            {
                "prompt": "Step 2 — Show the full routing table to understand packet flow.",
                "hint": "ip route shows the kernel routing table.",
                "accepted": ["ip route", "ip route show", "ip r", "route -n"],
                "keywords": ["ip", "route"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (rc == 0 and bool(re.search(r'\d+\.\d+\.\d+\.\d+|default', out)), "Must show routing entries"),
            },
            {
                "prompt": "Step 3 — Block all incoming connections on port 4444 using iptables (a common backdoor port).",
                "hint": "iptables -A INPUT -p tcp --dport 4444 -j DROP",
                "accepted": ["iptables -A INPUT -p tcp --dport 4444 -j DROP", "sudo iptables -A INPUT -p tcp --dport 4444 -j DROP"],
                "keywords": ["iptables", "4444", "DROP"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (rc == 0, "iptables rule must be added successfully"),
            },
            {
                "prompt": "Step 4 — Capture 10 packets on the loopback interface and display them (don't save to file).",
                "hint": "tcpdump -i lo -c 10 captures 10 packets on loopback.",
                "accepted": ["tcpdump -i lo -c 10", "sudo tcpdump -i lo -c 10", "tcpdump -c 10 -i lo"],
                "keywords": ["tcpdump", "-c", "10"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (rc in (0, 1, 2) and "tcpdump" in err + out or rc == 0, "tcpdump must attempt to capture"),
            },
            {
                "prompt": "Step 5 — Check IP forwarding status and disable it if enabled.",
                "hint": "Read /proc/sys/net/ipv4/ip_forward, then write 0 to disable.",
                "accepted": ["cat /proc/sys/net/ipv4/ip_forward", "echo 0 > /proc/sys/net/ipv4/ip_forward", "sysctl -w net.ipv4.ip_forward=0"],
                "keywords": ["ip_forward"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (rc == 0, "Must access ip_forward successfully"),
            },
        ],
    },
    {
        "id": "C06",
        "level": "advanced",
        "title": "Filesystem Archaeology",
        "description": "Recover information from a corrupted environment: find deleted files, recover content, and repair permissions.",
        "steps": [
            {
                "prompt": "Step 1 — Find all files modified in the last 5 minutes anywhere under /tmp.",
                "hint": "find -mmin -5 matches files modified within 5 minutes.",
                "accepted": ["find /tmp -mmin -5", "find /tmp -mmin -5 -type f"],
                "keywords": ["find", "/tmp", "-mmin", "-5"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (rc == 0, "find must run successfully"),
            },
            {
                "prompt": "Step 2 — A file 'evidence.dat' exists but is empty. Write the text 'RECOVERED' into it using only the shell.",
                "hint": "echo with output redirection writes to a file.",
                "accepted": ["echo 'RECOVERED' > evidence.dat", "echo RECOVERED > evidence.dat", "printf 'RECOVERED\\n' > evidence.dat"],
                "keywords": ["evidence.dat"],
                "setup": "touch evidence.dat",
                "verify": lambda sb, rc, out, err: (
                    os.path.isfile(os.path.join(sb, "evidence.dat")) and
                    "RECOVERED" in open(os.path.join(sb, "evidence.dat")).read(),
                    "evidence.dat must contain the word RECOVERED"
                ),
            },
            {
                "prompt": "Step 3 — Create a hard link called 'evidence.bak' pointing to 'evidence.dat' (backup by inode sharing).",
                "hint": "ln without -s creates a hard link.",
                "accepted": ["ln evidence.dat evidence.bak"],
                "keywords": ["ln", "evidence.dat", "evidence.bak"],
                "setup": "echo 'RECOVERED' > evidence.dat",
                "verify": lambda sb, rc, out, err: (
                    os.path.isfile(os.path.join(sb, "evidence.bak")) and
                    not os.path.islink(os.path.join(sb, "evidence.bak")) and
                    os.stat(os.path.join(sb, "evidence.dat")).st_ino == os.stat(os.path.join(sb, "evidence.bak")).st_ino,
                    "evidence.bak must be a hard link sharing evidence.dat's inode"
                ),
            },
            {
                "prompt": "Step 4 — Count the number of inodes used on the root filesystem.",
                "hint": "df -i shows inode usage per filesystem.",
                "accepted": ["df -i", "df -i /", "df --inodes", "df --inodes /"],
                "keywords": ["df", "-i"],
                "setup": "",
                "verify": lambda sb, rc, out, err: (rc == 0 and ("Inode" in out or "IUsed" in out or "IFree" in out), "Must show inode statistics"),
            },
            {
                "prompt": "Step 5 — Make 'evidence.dat' append-only so no one can overwrite its content (only add to it).",
                "hint": "chattr +a sets the append-only attribute.",
                "accepted": ["chattr +a evidence.dat", "sudo chattr +a evidence.dat"],
                "keywords": ["chattr", "+a", "evidence.dat"],
                "setup": "echo 'RECOVERED' > evidence.dat",
                "verify": lambda sb, rc, out, err: (rc == 0 or "Operation not supported" in err, "chattr +a must run or filesystem limitation reported"),
            },
        ],
    },
]

CHALLENGE_LEVEL_ORDER = ["beginner", "intermediate", "advanced"]
CHALLENGE_LEVEL_COLORS = {
    "beginner":     C.GREEN,
    "intermediate": C.YELLOW,
    "advanced":     C.RED,
}

def run_challenge_step(step: dict, user_cmd: str):
    """
    Execute one challenge step in a sandbox.
    Returns same dict format as run_sandboxed_task().
    """
    # Wrap step as a minimal task dict for the sandbox
    pseudo_task = {
        "setup":    step.get("setup", ""),
        "verify":   step.get("verify"),
        "accepted": step.get("accepted", []),
        "keywords": step.get("keywords", []),
    }
    return run_sandboxed_task(pseudo_task, user_cmd)

def show_challenges(progress):
    """Full challenge mode UI — multi-step scenarios with sandbox verification."""
    while True:
        clear()
        print()
        print(f"  {C.BOLD}{C.ORANGE}{'─'*55}{C.RESET}")
        print(f"  {C.BOLD}{C.ORANGE}  {T('challenges_title')}{C.RESET}")
        print(f"  {C.GRAY}  {T('challenges_sub')}{C.RESET}")
        print(f"  {C.BOLD}{C.ORANGE}{'─'*55}{C.RESET}\n")

        ch_progress = progress.get("challenges", {})

        # Group by level
        for lvl in CHALLENGE_LEVEL_ORDER:
            col = CHALLENGE_LEVEL_COLORS.get(lvl, C.WHITE)
            challenges_in_level = [c for c in CHALLENGES if c["level"] == lvl]
            print(f"  {col}── {lvl.upper()} ──────────────────────────────────────{C.RESET}")
            for c in challenges_in_level:
                cid = c["id"]
                done = ch_progress.get(cid, {}).get("completed", False)
                steps_done = ch_progress.get(cid, {}).get("steps_done", 0)
                total_steps = len(c["steps"])
                marker = f"{C.GREEN}✓{C.RESET}" if done else f"{C.GRAY}○{C.RESET}"
                step_str = f"{C.GRAY}({steps_done}/{total_steps} steps){C.RESET}" if not done else f"{C.GREEN}(complete){C.RESET}"
                print(f"  {marker} {C.CYAN}{cid}{C.RESET}. {C.WHITE}{c['title']}{C.RESET}  {step_str}")
                print(f"       {C.DIM}{c['description'][:70]}{C.RESET}")
            print()

        hr()
        print(f"\n  {C.GRAY}b{C.RESET}. {T('back')}\n")
        try:
            choice = input(f"  {C.GREEN}❯{C.RESET} {T('choose_challenge', n=len(CHALLENGES))}: ").strip().upper()
        except (KeyboardInterrupt, EOFError):
            break

        if choice in ("B", "BACK", ""):
            break

        # Find challenge by ID
        challenge = next((c for c in CHALLENGES if c["id"] == choice), None)
        if challenge is None:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(CHALLENGES):
                    challenge = CHALLENGES[idx]
            except ValueError:
                continue

        if challenge:
            _run_challenge(challenge, progress)

def _run_challenge(challenge: dict, progress):
    """Run a single multi-step challenge."""
    cid = challenge["id"]
    col = CHALLENGE_LEVEL_COLORS.get(challenge["level"], C.WHITE)
    steps = challenge["steps"]
    n_steps = len(steps)
    ch_progress = progress.setdefault("challenges", {})
    ch_entry    = ch_progress.setdefault(cid, {"completed": False, "steps_done": 0})

    for step_idx, step in enumerate(steps):
        step_num = step_idx + 1
        while True:
            clear()
            print()
            print(f"  {col}{'─'*60}{C.RESET}")
            print(f"  {col}  {challenge['title']}  [{challenge['level'].upper()}]{C.RESET}")
            print(f"  {C.GRAY}  {challenge['description']}{C.RESET}")
            print(f"  {col}{'─'*60}{C.RESET}\n")
            print(f"  {C.BOLD}{T('challenge_step', n=step_num, total=n_steps)}{C.RESET}")
            print(f"\n  {C.WHITE}{step['prompt']}{C.RESET}\n")
            print(f"  {C.DIM}hint | answer | b(back){C.RESET}\n")

            try:
                cmd = input(f"  {C.GREEN}$ {C.RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                return

            if not cmd:
                continue
            if cmd.lower() in ("b", "back"):
                return
            if cmd.lower() == "hint":
                print(f"\n  {C.YELLOW}💡 {step['hint']}{C.RESET}\n")
                continue
            if cmd.lower() == "answer":
                print(f"\n  {C.ORANGE}Answer: {C.BOLD}{step['accepted'][0]}{C.RESET}\n")
                input(f"  {C.GRAY}[Enter] to continue...{C.RESET} ")
                # Don't count as completed
                break

            print(f"  {C.DIM}⏳ Verifying...{C.RESET}", end="\r")
            result = run_challenge_step(step, cmd)
            print(" " * 40, end="\r")

            if result["passed"]:
                print(f"\n  {C.GREEN}{'─'*60}{C.RESET}")
                print(f"  {C.GREEN}{T('challenge_pass')}{C.RESET}")
                if result["message"].strip():
                    print(f"  {C.DIM}{result['message'].strip()[:120]}{C.RESET}")
                print(f"  {C.GREEN}{'─'*60}{C.RESET}\n")
                ch_entry["steps_done"] = max(ch_entry.get("steps_done", 0), step_num)
                save_progress(progress)
                time.sleep(1)
                break  # next step
            else:
                print(f"\n  {C.RED}{T('challenge_fail')}{C.RESET}  {C.GRAY}{T('attempt')}{C.RESET}")
                if result["mode"] == "sandbox" and result["message"].strip():
                    print(f"  {C.GRAY}{result['message'].strip()[:150]}{C.RESET}")
                elif result["mode"] == "keyword":
                    missing = [k for k in step.get("keywords", []) if k.lower() not in cmd.lower()]
                    if missing:
                        print(f"  {C.GRAY}{T('missing_keywords')} {', '.join(missing[:3])}{C.RESET}")
                print()

    # All steps passed
    ch_entry["completed"] = True
    ch_entry["steps_done"] = n_steps
    save_progress(progress)
    clear()
    print()
    print(f"  {C.BOLD}{C.GREEN}{'═'*60}{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}  🏆 {T('challenge_complete')}{C.RESET}")
    print(f"  {C.WHITE}  {challenge['title']}{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}{'═'*60}{C.RESET}\n")
    time.sleep(3)

def show_plugins(progress):
    """Show plugin domain browser."""
    clear()
    print()
    print(f"  {C.BOLD}{C.PURPLE}  {T('plugins_title')}{C.RESET}\n")
    hr()
    print()

    if not PLUGIN_TASKS:
        print(f"  {C.GRAY}{T('plugins_none')}{C.RESET}")
        print(f"  {C.DIM}  Create a tasks/ directory next to commandlab.py")
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
LOGO = f"""
{C.GREEN}  ____ ___  __  __ __  __    _    _   _ ____  _        _    ____  {C.RESET}
{C.GREEN} / ___/ _ \\|  \\/  |  \\/  |  / \\  | \\ | |  _ \\| |      / \\  | __ ){C.RESET}
{C.GREEN}| |  | | | | |\\/| | |\\/| | / _ \\ |  \\| | | | | |     / _ \\ |  _ \\{C.RESET}
{C.GREEN}| |__| |_| | |  | | |  | |/ ___ \\| |\\  | |_| | |___ / ___ \\| |_) |{C.RESET}
{C.GREEN} \\____\\___/|_|  |_|_|  |_/_/   \\_\\_| \\_|____/|_____/_/   \\_\\____/ {C.RESET}
{C.DIM}  [ command-line learning toolkit ]{C.RESET}
"""

DIFF_COLORS = {
    "easy":   C.GREEN,
    "medium": C.YELLOW,
    "hard":   C.ORANGE,
    "insane": C.RED,
}

DOMAIN_ICONS = {
    "files":       "📁",
    "viewing":     "👁 ",
    "permissions": "🔐",
    "processes":   "⚙️ ",
    "networking":  "🌐",
}

# Difficulty levels in order — each locks the next
LEVEL_ORDER = ["easy", "medium", "hard", "insane"]

def get_level_tasks(domain_name, level):
    """Return all tasks in a domain at a given difficulty level."""
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

def clear():
    os.system("clear")

def hr(char="─", color=C.GRAY):
    w = min(term_width(), 90)
    print(f"{color}{char * w}{C.RESET}")

def box(lines, color=C.BLUE, padding=2):
    w = min(term_width() - 4, 86)
    pad = " " * padding
    print(f"{color}┌{'─' * (w)}┐{C.RESET}")
    for line in lines:
        visible = C.strip(line)
        spaces = w - len(visible) - padding * 2
        if spaces < 0:
            spaces = 0
        print(f"{color}│{C.RESET}{pad}{line}{' ' * spaces}{pad}{color}│{C.RESET}")
    print(f"{color}└{'─' * (w)}┘{C.RESET}")

def diff_badge(level):
    color = DIFF_COLORS.get(level, C.WHITE)
    return f"{color}[{level.upper()}]{C.RESET}"

def progress_bar(done, total, width=30, color=C.GREEN):
    if total == 0:
        return ""
    filled = int(width * done / total)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * done / total)
    return f"{color}{bar}{C.RESET} {C.BOLD}{done}/{total}{C.RESET} {C.GRAY}({pct}%){C.RESET}"

def wrap_text(text, width=80, indent=""):
    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)

def domain_stats(domain_name, progress):
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
    for i, (domain, tasks) in enumerate(PLUGIN_TASKS.items(), len(domain_list) + 1):
        meta = _PLUGIN_META.get(domain, {})
        done = sum(1 for t in tasks if t["id"] in completed_ids)
        total = len(tasks)
        bar = progress_bar(done, total, width=18)
        print(f"  {C.CYAN}{i}{C.RESET}. 🔌 {C.BOLD}{meta.get('name', domain).upper():14s}{C.RESET}  {bar}  {C.GRAY}[plugin]{C.RESET}")

    print()
    hr()

    # Extra menu row
    ch_done = sum(1 for c in CHALLENGES if progress.get("challenges", {}).get(c["id"], {}).get("completed", False))
    ch_total = len(CHALLENGES)
    print(f"\n  {C.ORANGE}c{C.RESET}. ⚔  {T('challenges')}  {C.GRAY}({ch_done}/{ch_total}){C.RESET}"
          f"    {C.PURPLE}p{C.RESET}. 🔌 {T('plugins')}"
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

def task_field(task, field):
    """Return the Arabic version of a task field when AR mode is active."""
    if _LANG == "ar":
        ar_val = task.get(f"{field}_ar", "").strip()
        if ar_val:
            return ar_val
    return task.get(field, "")

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

    # Challenge stats
    ch_progress = progress.get("challenges", {})
    if ch_progress:
        ch_done = sum(1 for c in CHALLENGES if ch_progress.get(c["id"], {}).get("completed", False))
        print(f"  ⚔  {T('challenges'):14s}  {progress_bar(ch_done, len(CHALLENGES), width=20, color=C.ORANGE)}")
        print()

    # Plugin stats
    for domain, tasks in PLUGIN_TASKS.items():
        meta = _PLUGIN_META.get(domain, {})
        d = sum(1 for t in tasks if t["id"] in completed_ids)
        t = len(tasks)
        print(f"  🔌 {meta.get('name', domain)[:14]:14s}  {progress_bar(d, t, width=20, color=C.PURPLE)}")
    if PLUGIN_TASKS:
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

        # ── Challenges ───────────────────────────────────────
        if choice == "c":
            show_challenges(progress)
            continue

        # ── Plugins ──────────────────────────────────────────
        if choice == "p":
            show_plugins(progress)
            continue

        # ── Language switch ───────────────────────────────────
        if choice == "l":
            new_lang = "ar" if _LANG == "en" else "en"
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
                import random
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

if __name__ == "__main__":
    main()
