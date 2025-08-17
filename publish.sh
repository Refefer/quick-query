#!/usr/bin/env bash

set -euo pipefail

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $0 <command> [options]

Commands:
  clean               Remove previous build artefacts (dist/, build/, *.egg-info)
  bump [type]         Bump version (type can be patch|minor|major, default: patch)
  build               Build source distribution and wheel (python -m build)
  upload              Upload the contents of dist/ to PyPI via Twine
  release             Run clean → bump → build → upload in sequence
  -h | --help         Show this help message
EOF
}

# ----------------------------------------------------------------------
# Path variables
# ----------------------------------------------------------------------
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION_FILE="${ROOT_DIR}/VERSION"
DIST_DIR="${ROOT_DIR}/dist"

# ----------------------------------------------------------------------
# Clean command
# ----------------------------------------------------------------------
clean() {
    echo "🧹 Cleaning previous build artefacts..."
    rm -rf "${ROOT_DIR}/build" "${ROOT_DIR}/dist" "${ROOT_DIR}"/*.egg-info
}

# ----------------------------------------------------------------------
# Version bump command (semantic versioning)
# ----------------------------------------------------------------------
bump() {
    local part="${1:-patch}"
    if [[ ! -f "${VERSION_FILE}" ]]; then
        echo "⚠️ VERSION file not found – creating with 0.0.0"
        echo "0.0.0" > "${VERSION_FILE}"
    fi

    IFS='.' read -r major minor patch < "${VERSION_FILE}"
    case "$part" in
        major) major=$((major + 1)); minor=0; patch=0 ;;
        minor) minor=$((minor + 1)); patch=0 ;;
        patch) patch=$((patch + 1)) ;;
        *) echo "Invalid bump type: $part (use patch|minor|major)"; exit 1 ;;
    esac
    new_version="${major}.${minor}.${patch}"
    echo "${new_version}" > "${VERSION_FILE}"
    echo "🔢 Bumped version to ${new_version}"

    # Commit & tag
    git add "${VERSION_FILE}" quick_query/__init__.py
    git commit -m "Bump version to ${new_version}"
    git tag "v${new_version}"
}

# ----------------------------------------------------------------------
# Build command
# ----------------------------------------------------------------------
build() {
    echo "📦 Building distribution…"
    python -m build .
}

# ----------------------------------------------------------------------
# Upload command (uses Twine – expects TWINE_USERNAME / TWINE_PASSWORD or TWINE_API_TOKEN)
# ----------------------------------------------------------------------
upload() {
    if [[ -z "${TWINE_USERNAME:-}" && -z "${TWINE_API_TOKEN:-}" ]]; then
        echo "⚠️ Twine credentials not found in environment variables."
        echo "Set TWINE_USERNAME/TWINE_PASSWORD or TWINE_API_TOKEN."
        exit 1
    fi
    echo "🚀 Uploading to PyPI via Twine…"
    twine upload "${DIST_DIR}"/*
}

# ----------------------------------------------------------------------
# Release command – orchestrates the full flow
# ----------------------------------------------------------------------
release() {
    clean
    bump "$@"
    build
    upload
}

# ----------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------
if [[ $# -eq 0 ]]; then
    usage
    exit 0
fi

cmd="$1"
shift
case "$cmd" in
    clean)   clean "$@" ;;
    bump)    bump "$@" ;;
    build)   build "$@" ;;
    upload)  upload "$@" ;;
    release) release "$@" ;;
    -h|--help) usage ;;
    *) echo "Unknown command: $cmd"; usage; exit 1 ;;
esac

exit 0
