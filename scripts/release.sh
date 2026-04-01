#!/bin/bash
# Usage: ./scripts/release.sh [major|minor|patch]
#
# This script:
# 1. Validates working directory is clean
# 2. Runs lint and type checks
# 3. Bumps version using uv
# 4. Updates CHANGELOG.md
# 5. Commits changes
# 6. Creates git tag
# 7. Pushes to GitHub (triggers CI/CD)

set -e

BUMP_TYPE="${1:-patch}"

if [[ ! "$BUMP_TYPE" =~ ^(major|minor|patch)$ ]]; then
    echo "Error: Invalid bump type. Use: major, minor, or patch"
    exit 1
fi

echo "Starting release process with bump type: $BUMP_TYPE"

# Validate clean working directory
if [[ -n $(git status -s) ]]; then
    echo "Error: Working directory not clean. Commit or stash changes."
    exit 1
fi

# Ensure on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo "Error: Must be on main branch. Currently on: $CURRENT_BRANCH"
    exit 1
fi

# Pull latest changes
echo "Pulling latest changes from origin/main..."
git pull origin main

# Run validation
echo "Running pre-release validation..."
uv sync --group dev
uv run ruff check src/batuta/
uv run mypy src/batuta/

# Bump version
echo "Bumping version ($BUMP_TYPE)..."
OLD_VERSION=$(uv version)
uv version --bump "$BUMP_TYPE"
NEW_VERSION=$(uv version)

echo "Version: $OLD_VERSION -> $NEW_VERSION"

# Update CHANGELOG
echo "Updating CHANGELOG.md..."
git cliff --tag "v$NEW_VERSION" -o CHANGELOG.md

# Commit changes
echo "Committing version bump and changelog..."
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): bump version to $NEW_VERSION"

# Create annotated tag
echo "Creating git tag v$NEW_VERSION..."
CHANGELOG_EXCERPT=$(git cliff --tag "v$NEW_VERSION" --unreleased --strip all)
git tag -a "v$NEW_VERSION" -m "Release $NEW_VERSION

$CHANGELOG_EXCERPT"

# Push changes
echo "Pushing to GitHub..."
git push origin main
git push origin "v$NEW_VERSION"

echo ""
echo "Release v$NEW_VERSION initiated successfully!"
echo "Monitor CI/CD: https://github.com/luca-regne/batuta/actions"
