import re
import shutil


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
