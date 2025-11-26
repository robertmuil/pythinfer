# GitHub Actions & Coverage Badge Setup

## Overview

This project is configured with:
- ✅ **GitHub Actions workflow** (`test.yml`) - Runs tests on Python 3.10, 3.11, 3.12
- ✅ **Coverage reporting** - Generates XML coverage reports
- ✅ **Codecov integration** - Uploads coverage to codecov.io
- ✅ **README badges** - Displays test status and coverage percentage

## What the Workflow Does

The `.github/workflows/test.yml` file:

1. **Triggers on:** Push to `main`, `develop`, `no-project-file` branches; PRs to `main`, `develop`
2. **Matrix testing:** Runs on Python 3.10, 3.11, and 3.12
3. **Steps:**
   - Checks out code
   - Sets up Python
   - Installs `uv` (dependency manager)
   - Installs dependencies via `uv sync`
   - Runs tests with coverage: `pytest --cov=src/pythinfer --cov-report=xml`
   - Uploads coverage to Codecov

## Coverage Badges in README

Two badges have been added:

```markdown
[![Tests](https://github.com/robertmuil/pythinfer/actions/workflows/test.yml/badge.svg)](https://github.com/robertmuil/pythinfer/actions)
[![codecov](https://codecov.io/gh/robertmuil/pythinfer/graph/badge.svg?token=)](https://codecov.io/gh/robertmuil/pythinfer)
```

- **Tests badge:** Shows workflow status (green=passing, red=failing)
- **Coverage badge:** Shows current coverage percentage

## Setup Instructions

### Step 1: Enable GitHub Actions

GitHub Actions is enabled by default. Just push code to trigger workflows.

### Step 2: Set Up Codecov (Optional but Recommended)

1. Go to [https://codecov.io](https://codecov.io)
2. Click "Sign up" and authorize with GitHub
3. Select your repositories (including `robertmuil/pythinfer`)
4. Codecov will automatically detect coverage uploads from your workflow

**Note:** Codecov is free for public repositories and open-source projects.

### Step 3: Get Codecov Token (Optional)

For private repositories, you may need a token:

1. Go to your Codecov repository settings
2. Copy the `CODECOV_TOKEN`
3. Add to GitHub repo secrets:
   - Go to GitHub repo → Settings → Secrets → New repository secret
   - Name: `CODECOV_TOKEN`
   - Value: (paste token from Codecov)

For public repositories, the token is optional (as configured in the workflow).

### Step 4: Verify Badges Work

After the first workflow run:
1. Go to GitHub Actions tab - should see ✅ or ❌ status
2. Badge links should work automatically
3. Coverage badge will update after Codecov processes the report (1-2 minutes)

## Badge URLs

If you need to update badges later, use these format:

**Tests Badge:**
```
https://github.com/robertmuil/pythinfer/actions/workflows/test.yml/badge.svg
```

**Coverage Badge (with token):**
```
https://codecov.io/gh/robertmuil/pythinfer/graph/badge.svg?token=YOUR_TOKEN
```

**Coverage Badge (without token, public repos):**
```
https://codecov.io/gh/robertmuil/pythinfer/graph/badge.svg
```

## What Gets Reported

- **Coverage percentage** - Overall code coverage (currently 78%)
- **Module breakdown** - Coverage by file:
  - `cli.py` - 86%
  - `merge.py` - 100%
  - `infer.py` - 77%
  - `inout.py` - 90%
  - `rdflibplus.py` - 86%
- **Trend tracking** - Codecov tracks coverage changes over time

## Local Testing

To generate coverage locally (same as CI):

```bash
pytest tests/ --cov=src/pythinfer --cov-report=xml --cov-report=term-missing
```

This generates:
- `coverage.xml` - Machine-readable coverage data
- Terminal output - Human-readable coverage summary

## CI/CD Pipeline

```
Push to GitHub
    ↓
GitHub Actions triggered (.github/workflows/test.yml)
    ↓
Matrix: Python 3.10, 3.11, 3.12
    ↓
Install dependencies (uv sync)
    ↓
Run tests with coverage (pytest --cov=...)
    ↓
Generate coverage.xml
    ↓
Upload to Codecov.io
    ↓
Codecov processes and displays badge
    ↓
Badge updates in README ✨
```

## Troubleshooting

### Badge shows "unknown"
- Codecov hasn't processed the report yet (wait 1-2 minutes)
- Check Actions tab to see if workflow passed
- Verify `coverage.xml` was generated in workflow logs

### Workflow fails
- Check GitHub Actions tab for error logs
- Common issues:
  - Python version not available (update matrix versions)
  - Dependencies not installing (check `pyproject.toml`)
  - Tests failing (check test output)

### Codecov not receiving reports
- Ensure workflow runs successfully (check Actions tab)
- Verify `coverage.xml` generation step passed
- For private repos, check that `CODECOV_TOKEN` is set correctly

## Future Enhancements

- [ ] Add coverage badge to main branch only
- [ ] Add PR comment with coverage change
- [ ] Add coverage diff in PRs (Codecov feature)
- [ ] Add minimum coverage threshold enforcement
- [ ] Add code quality checks (pylint, black, etc.)

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Codecov Documentation](https://docs.codecov.io/)
- [Pytest Coverage Documentation](https://pytest-cov.readthedocs.io/)
