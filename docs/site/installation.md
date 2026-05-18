# Installation

## Requirements

- Python **3.10** or later
- No external runtime dependencies

## Install from GitHub

chronomemory is not yet on PyPI. Install directly from GitHub:

```bash
pip install git+https://github.com/layer1labs/chronomemory.git
```

To pin a specific commit:

```bash
pip install git+https://github.com/layer1labs/chronomemory.git@<commit-sha>
```

## Install from a local clone

```bash
git clone https://github.com/layer1labs/chronomemory.git
pip install -e /path/to/chronomemory
```

The `-e` flag installs in editable mode — changes to `src/chronomemory/` take effect immediately without reinstalling.

## Verify installation

```python
from chronomemory import ChronoStore, ChronoRecord, EsdbBridge
print("OK")
```

Or from the command line:

```bash
python -c "from chronomemory import ChronoStore; print('OK')"
```

## Add to a project

In `pyproject.toml`:

```toml
[project]
dependencies = [
    "chronomemory @ git+https://github.com/layer1labs/chronomemory.git",
]
```

In `requirements.txt`:

```
chronomemory @ git+https://github.com/layer1labs/chronomemory.git
```

## Install documentation dependencies

```bash
pip install -e ".[docs]"
mkdocs serve   # preview at http://localhost:8000
```

## Dependency policy

`chronomemory` has **zero runtime dependencies**. It uses only Python stdlib:
`hashlib`, `json`, `os`, `shutil`, `pathlib`, `dataclasses`, `typing`.

This is enforced by the CI `zero-deps` job which installs the package with
`pip install --no-deps` and asserts the `dependencies` field is empty.

## Platform support

| Platform | Status |
|----------|--------|
| Linux (Ubuntu 22.04+) | ✅ CI tested |
| macOS (12+) | ✅ CI tested |
| Windows (Server 2019+) | ✅ CI tested |
