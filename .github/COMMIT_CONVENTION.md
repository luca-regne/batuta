# Commit Message Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/) specification.

## Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

## Type

Must be one of:

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **perf**: A code change that improves performance
- **test**: Adding missing tests or correcting existing tests
- **build**: Changes that affect the build system or external dependencies
- **ci**: Changes to CI configuration files and scripts
- **chore**: Other changes that don't modify src or test files
- **revert**: Reverts a previous commit

## Scope

Must be one of: `cli`, `core`, `models`, `utils`, `deps`, `release`

## Subject

- Use imperative, present tense: "change" not "changed" nor "changes"
- Don't capitalize first letter
- No period (.) at the end

## Breaking Changes

Add `!` after type/scope to indicate breaking changes:

```
feat(cli)!: remove deprecated --legacy flag

BREAKING CHANGE: The --legacy flag has been removed. Use --modern instead.
```

## Examples

```
feat(cli): add --verbose flag to decompile command
fix(core): handle missing AndroidManifest.xml gracefully
docs: update installation instructions
build(deps): bump androguard to 3.4.0
refactor(utils): simplify process wrapper interface
```

## Validation

Commits are validated automatically:
- Pre-commit hook validates your commit messages locally
- PR validation workflow checks all commits in pull requests
- Non-conforming commits will be rejected

## Setup

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install --hook-type commit-msg
```
