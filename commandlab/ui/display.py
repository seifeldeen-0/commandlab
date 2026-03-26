import os
import textwrap

from commandlab.ui.colors import C, clen, term_width


LOGO = f"""
{C.GREEN}  ____ ___  __  __ __  __    _    _   _ ____  _        _    ____  {C.RESET}
{C.GREEN} / ___/ _ \|  \/  |  \/  |  / \  | \ | |  _ \| |      / \  | __ ){C.RESET}
{C.GREEN}| |  | | | | |\/| | |\/| | / _ \ |  \| | | | | |     / _ \ |  _ \{C.RESET}
{C.GREEN}| |__| |_| | |  | | |  | |/ ___ \| |\  | |_| | |___ / ___ \| |_) |{C.RESET}
{C.GREEN} \____\___/|_|  |_|_|  |_/_/   \_\_| \_|____/|_____/_/   \_\____/ {C.RESET}
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
