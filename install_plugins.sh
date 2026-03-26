#!/usr/bin/env bash
# ============================================================
#  CommandLab — Plugin Installer
#  Place your plugin files (.json or .yaml) in the same
#  directory as this script, then run it from anywhere.
#
#  Usage:
#    bash install_plugins.sh
#    bash install_plugins.sh /path/to/commandlab-project
# ============================================================

set -e

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[*]${RESET} $1"; }
success() { echo -e "${GREEN}[✓]${RESET} $1"; }
warn()    { echo -e "${YELLOW}[!]${RESET} $1"; }
error()   { echo -e "${RED}[✗]${RESET} $1"; exit 1; }

# ── Banner ────────────────────────────────────────────────────
clear
echo -e "${GREEN}${BOLD}"
echo "  CommandLab — Plugin Installer"
echo -e "${RESET}"
echo "  Installs .json / .yaml plugin files into CommandLab."
echo ""

# ── Directory where this script (and the plugin files) live ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Locate CommandLab project root ───────────────────────────
# Priority:
#   1. Path passed as argument:  bash install_plugins.sh /path/to/project
#   2. Same directory as this script
#   3. Current working directory
#   4. Walk up from the script directory looking for commandlab/

find_commandlab() {
    local dir="$1"
    while [[ "$dir" != "/" ]]; do
        if [[ -d "$dir/commandlab" && -f "$dir/commandlab/__main__.py" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    return 1
}

COMMANDLAB_ROOT=""

if [[ -n "$1" ]]; then
    # Argument provided — use it directly
    COMMANDLAB_ROOT="$(cd "$1" 2>/dev/null && pwd)" || error "Path not found: $1"
    if [[ ! -d "$COMMANDLAB_ROOT/commandlab" ]]; then
        error "commandlab/ package not found in: $COMMANDLAB_ROOT"
    fi
elif [[ -d "$SCRIPT_DIR/commandlab" && -f "$SCRIPT_DIR/commandlab/__main__.py" ]]; then
    # Script is already inside the project root
    COMMANDLAB_ROOT="$SCRIPT_DIR"
elif [[ -d "$PWD/commandlab" && -f "$PWD/commandlab/__main__.py" ]]; then
    # Current working directory is the project root
    COMMANDLAB_ROOT="$PWD"
else
    # Walk upward from the script location
    COMMANDLAB_ROOT="$(find_commandlab "$SCRIPT_DIR")" || true
    if [[ -z "$COMMANDLAB_ROOT" ]]; then
        error "Could not find the CommandLab project (commandlab/ directory).\nRun this script from inside the project, or pass the project path:\n  bash install_plugins.sh /path/to/commandlab-project"
    fi
fi

success "CommandLab project found at: $COMMANDLAB_ROOT"

# ── Ensure tasks/ directory exists inside the project ────────
TASKS_DIR="$COMMANDLAB_ROOT/tasks"
if [[ ! -d "$TASKS_DIR" ]]; then
    info "Creating tasks/ directory inside CommandLab project..."
    mkdir -p "$TASKS_DIR"
    success "Created $TASKS_DIR"
fi

# ── Collect plugin files from the script's own directory ─────
info "Scanning for plugin files in $SCRIPT_DIR ..."

# Files to skip (non-plugin JSON/YAML files that live here)
SKIP_FILES=("package.json" "package-lock.json")

INSTALLED=0
SKIPPED=0
ERRORS=0

shopt -s nullglob
ALL_FILES=("$SCRIPT_DIR"/*.json "$SCRIPT_DIR"/*.yaml "$SCRIPT_DIR"/*.yml)
shopt -u nullglob

# ── Show already-installed plugins ───────────────────────────
shopt -s nullglob
EXISTING=("$TASKS_DIR"/*.json "$TASKS_DIR"/*.yaml "$TASKS_DIR"/*.yml)
shopt -u nullglob

if [[ ${#EXISTING[@]} -gt 0 ]]; then
    echo -e "  ${BOLD}Currently installed plugins (${#EXISTING[@]}):${RESET}"
    for f in "${EXISTING[@]}"; do
        echo -e "    ${GREEN}•${RESET} $(basename "$f")"
    done
    echo ""
fi

if [[ ${#ALL_FILES[@]} -eq 0 ]]; then
    warn "No .json or .yaml files found next to this installer."
    echo ""
    echo "  To install new plugins, place your .json or .yaml files here:"
    echo "    $SCRIPT_DIR"
    echo ""
    echo "  Then run this installer again."
    echo ""
    exit 0
fi

for PLUGIN_FILE in "${ALL_FILES[@]}"; do
    BASENAME="$(basename "$PLUGIN_FILE")"

    # Skip known non-plugin files
    for SKIP in "${SKIP_FILES[@]}"; do
        if [[ "$BASENAME" == "$SKIP" ]]; then
            continue 2
        fi
    done

    # Skip this script itself (in case someone names it .json)
    [[ "$BASENAME" == "install_plugins.sh" ]] && continue

    # Check Python 3 is available for validation
    if ! command -v python3 &>/dev/null; then
        warn "python3 not found — skipping validation for $BASENAME (will copy anyway)"
        cp "$PLUGIN_FILE" "$TASKS_DIR/$BASENAME"
        success "Installed (unvalidated): $BASENAME"
        ((INSTALLED++)) || true
        continue
    fi

    # Validate: must have "domain" and "tasks" fields
    VALID=$(python3 - "$PLUGIN_FILE" <<'PYCHECK'
import sys, json, pathlib
path = pathlib.Path(sys.argv[1])
try:
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        try:
            import yaml
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except ImportError:
            print("no_yaml")
            sys.exit(0)

    entries = data if isinstance(data, list) else [data]
    for entry in entries:
        if not entry.get("domain") or not entry.get("tasks"):
            print("invalid")
            sys.exit(0)
        if not isinstance(entry["tasks"], list) or len(entry["tasks"]) == 0:
            print("invalid")
            sys.exit(0)
    print("ok")
except Exception as e:
    print(f"error: {e}")
PYCHECK
    )

    case "$VALID" in
        ok)
            cp "$PLUGIN_FILE" "$TASKS_DIR/$BASENAME"
            success "Installed: $BASENAME"
            ((INSTALLED++)) || true
            ;;
        invalid)
            warn "Skipped (missing 'domain' or 'tasks' field): $BASENAME"
            ((SKIPPED++)) || true
            ;;
        no_yaml)
            warn "Skipped (PyYAML not installed, cannot read .yaml): $BASENAME"
            warn "  Install it with: pip3 install pyyaml"
            ((SKIPPED++)) || true
            ;;
        error:*)
            warn "Skipped (parse error) $BASENAME: ${VALID#error: }"
            ((ERRORS++)) || true
            ;;
        *)
            warn "Skipped (unknown error): $BASENAME"
            ((ERRORS++)) || true
            ;;
    esac
done

# ── Summary ───────────────────────────────────────────────────
echo ""
echo -e "  ${BOLD}─────────────────────────────────${RESET}"
echo -e "  ${GREEN}Installed : $INSTALLED plugin(s)${RESET}"
[[ $SKIPPED -gt 0 ]] && echo -e "  ${YELLOW}Skipped   : $SKIPPED file(s)${RESET}"
[[ $ERRORS  -gt 0 ]] && echo -e "  ${RED}Errors    : $ERRORS file(s)${RESET}"
echo -e "  ${BOLD}─────────────────────────────────${RESET}"
echo ""

if [[ $INSTALLED -gt 0 ]]; then
    success "Plugins are now in: $TASKS_DIR"
    echo ""
    echo "  Launch CommandLab and go to Plugins to see them:"
    echo "    bash $COMMANDLAB_ROOT/installer.sh"
    echo ""
else
    warn "No plugins were installed."
    echo ""
fi
