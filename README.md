# py-wiki-crawler

A small python programm to crawl wiki pages recursively and fetch all the available data. Utilizes the offizial api of known wiki page providers like fandom.

## Tech-Stack

- **Sprache:** Python
- **Build / Packaging:** uv
- **CI/CD:** GitHub Actions
## Ordnerstruktur

```text
py-wiki-crawler/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── build.py
│   └── tools.py
├── tests/
│   └── test_main.py
├── .github/workflows/ci.yml├── .gitignore
├── pyproject.toml
└── README.md
```

## Quickstart

```bash
git clone <repo-url>
cd py-wiki-crawler
uv sync

# App ausführen
uv run main
# oder:
uv run py-wiki-crawler

# Tests ausführen
uv run test

# Exe-Datei mit PyInstaller erstellen
uv run build
```