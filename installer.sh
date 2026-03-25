#!/usr/bin/env bash
# ============================================================
#  CommandLab — Installer & Launcher
#  For people who have never used Linux before.
#  Just run this script and it will handle everything.
# ============================================================

set -e

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ── Helpers ───────────────────────────────────────────────────
info()    { echo -e "${CYAN}[*]${RESET} $1"; }
success() { echo -e "${GREEN}[✓]${RESET} $1"; }
warn()    { echo -e "${YELLOW}[!]${RESET} $1"; }
error()   { echo -e "${RED}[✗]${RESET} $1"; exit 1; }

# ── Banner ────────────────────────────────────────────────────
clear
echo -e "${GREEN}"
cat << 'EOF'
  ____ ___  __  __ __  __    _    _   _ ____  _        _    ____
 / ___/ _ \|  \/  |  \/  |  / \  | \ | |  _ \| |      / \  | __ )
| |  | | | | |\/| | |\/| | / _ \ |  \| | | | | |     / _ \ |  _ \
| |__| |_| | |  | | |  | |/ ___ \| |\  | |_| | |___ / ___ \| |_) |
 \____\___/|_|  |_|_|  |_/_/   \_\_| \_|____/|_____/_/   \_\____/
  [ command-line learning toolkit ]
EOF
echo -e "${RESET}"
echo -e "${BOLD}  CommandLab Installer${RESET}"
echo -e "  This script will set up and launch CommandLab automatically."
echo ""

# ── Step 1: Check we are on Linux ────────────────────────────
info "Checking your operating system..."
if [[ "$(uname -s)" != "Linux" ]]; then
    error "CommandLab requires Linux. This script cannot run on macOS or Windows."
fi
success "Linux detected."

# ── Step 2: Check Python 3 ───────────────────────────────────
info "Checking for Python 3..."
if ! command -v python3 &>/dev/null; then
    warn "Python 3 not found. Attempting to install it..."

    # Try apt (Ubuntu/Debian)
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y python3
    # Try dnf (Fedora/RHEL)
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3
    # Try pacman (Arch)
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm python
    else
        error "Could not install Python 3 automatically.\nPlease install it manually: https://www.python.org/downloads/"
    fi
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
success "Python $PYTHON_VERSION found."

# Confirm Python 3.8+
PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
PYTHON_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
if [[ "$PYTHON_MAJOR" -lt 3 ]] || { [[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -lt 8 ]]; }; then
    error "CommandLab requires Python 3.8 or newer. You have Python $PYTHON_VERSION.\nPlease upgrade Python: https://www.python.org/downloads/"
fi

# ── Step 3: Check required files are present ─────────────────
info "Checking CommandLab files..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "$SCRIPT_DIR/commandlab.py" ]]; then
    error "commandlab.py not found in the current directory ($SCRIPT_DIR).\nMake sure you are running this script from inside the CommandLab folder."
fi

if [[ ! -f "$SCRIPT_DIR/command_classifier.py" ]]; then
    error "command_classifier.py not found in the current directory ($SCRIPT_DIR).\nBoth files must be in the same folder as this script."
fi

success "All required files are present."

# ── Step 4: Create plugins directory if missing ───────────────
if [[ ! -d "$SCRIPT_DIR/tasks" ]]; then
    mkdir -p "$SCRIPT_DIR/tasks"
    success "Created tasks/ directory for plugins."
fi

# ── Step 5: Enable sandbox (optional, best-effort) ───────────
info "Checking sandbox isolation support..."

SANDBOX_OK=false

# Check if we already have a working sandbox
if python3 - <<'PYCHECK' 2>/dev/null
import subprocess, sys
r = subprocess.run(
    ["unshare", "--user", "--map-root-user", "--mount", "echo", "ok"],
    capture_output=True, timeout=5
)
sys.exit(0 if r.returncode == 0 else 1)
PYCHECK
then
    SANDBOX_OK=true
    success "Full sandbox isolation is available."
else
    # Try to enable unprivileged user namespaces
    if [[ -f /proc/sys/kernel/unprivileged_userns_clone ]]; then
        CURRENT=$(cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null || echo "0")
        if [[ "$CURRENT" != "1" ]]; then
            warn "Sandbox isolation is disabled. Attempting to enable it..."
            if sudo sysctl -w kernel.unprivileged_userns_clone=1 &>/dev/null; then
                success "Sandbox isolation enabled."
                SANDBOX_OK=true
            else
                warn "Could not enable sandbox isolation automatically."
            fi
        else
            SANDBOX_OK=true
        fi
    else
        # Check if running as root
        if [[ "$EUID" -eq 0 ]]; then
            SANDBOX_OK=true
            success "Running as root — full sandbox isolation available."
        fi
    fi
fi

if [[ "$SANDBOX_OK" == "false" ]]; then
    echo ""
    warn "Full sandbox isolation is not available on this system."
    warn "CommandLab will still work, but will run in reduced-security mode."
    warn "Dangerous commands will be blocked automatically."
    echo ""
    warn "To enable full isolation in the future, run:"
    warn "  sudo sysctl -w kernel.unprivileged_userns_clone=1"
    echo ""
    read -rp "  Press Enter to continue anyway, or Ctrl+C to cancel... "
    echo ""
fi

# ── Step 6: Launch ────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  Everything is ready. Launching CommandLab...${RESET}"
echo ""
sleep 1

cd "$SCRIPT_DIR"
exec python3 commandlab.py
