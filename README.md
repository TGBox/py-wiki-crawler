# py-wiki-crawler

Ein moderner, modularer Wiki-Downloader und Markdown-Konverter für Python.
Erfasst Spiele-Wikis und Dokumentationen (Fandom, MediaWiki sowie generische HTML-Wikis ohne API) rekursiv und erzeugt eine vollständige, offline navigierbare Markdown-Wissensdatenbank (z. B. für Obsidian, Logseq oder Markdown-Viewer) inklusive aller verlinkten Referenzgrafiken.

## Highlights & Features

- **Grafische Benutzeroberfläche (PySide6 GUI):**
  - Unterstützt sowohl **Vollbildmodus** als auch **Fenstermodus** (umschaltbar per Tastenkürzel `F11`, `Esc` oder Button).
  - Live-Statistiken (Exportierte Seiten, Bilder, Fehler, Stoppuhr).
  - Farbkodiertes Aktivitäts-Protokoll und dynamische Fortschrittsanzeige.
  - Asynchroner Hintergrund-Thread (`QThread`), der ein Einfrieren der Oberfläche verhindert.
- **MediaWiki & Fandom API-Unterstützung:** Erkennt automatisch `api.php` für maximale Geschwindigkeit, Namespace-Filterung und native Redirect-Auflösung.
- **HTML Fallback-Crawler:** Rekursiver Breadth-First-Crawler (BFS) mit Klicktiefenbegrenzung (`--max-depth`) und automatischer Filterung von Edit-, Versions- und Spezialseiten für Wikis ohne API.
- **Vollauflösende Grafiken & SHA-256 Deduplizierung:** Bereinigt verkleinerte Thumbnail-Parameter auf Originaldateien und speichert Bilder dedupliziert in `assets/images/`.
- **Intelligente Querverlinkung:** Interne Wiki-Links (`/wiki/Item/Sword`) werden in relative Pfade auf die lokalen `.md`-Dateien umgeschrieben.
- **SQLite-Checkpointing & Resilienz:** Speichert den Zustand fortlaufend in `.crawler_state.db` und setzt bei jedem erneuten Lauf automatisch fort: Fertige Seiten werden übersprungen, fehlgeschlagene Seiten und Seiten mit fehlenden Bildern erneut versucht (`--force` lädt alles neu).
- **Höfliches Scraping:** Integriertes Rate-Limiting mit Exponential Backoff bei HTTP 429 / 5xx.
- **Rich Terminal UI:** Übersichtliche Konsolenanzeige mit Live-Fortschrittsbalken und Abschluss-Statistik.

## Tech-Stack

- **Sprache:** Python >= 3.11
- **Paketmanager:** [uv](https://github.com/astral-sh/uv)
- **Parsing & Konvertierung:** `beautifulsoup4`, `markdownify`
- **Netzwerk & Terminal:** `requests`, `rich`, `tqdm`
- **Code-Qualität:** `ruff`, `pytest`

## Ordnerstruktur

```text
py-wiki-crawler/
├── pyproject.toml
├── src/
│   ├── py_wiki_crawler/
│   │   ├── cli.py             # Rich-Terminal-Interface & Argument Parsing
│   │   ├── core/
│   │   │   ├── engine.py      # Zentraler Crawl- & Export-Orchestrator
│   │   │   ├── state.py       # SQLite-Zustands- und Checkpoint-Verwaltung
│   │   │   └── rate_limiter.py# Anfragedrosselung & Exponential Backoff
│   │   ├── extractors/
│   │   │   ├── base.py        # Basis-Interface für Wiki-Extraktoren
│   │   │   ├── mediawiki.py   # MediaWiki API Extraktor (Fandom & co.)
│   │   │   └── html_crawler.py# Fallback HTML BFS Crawler
│   │   ├── converters/
│   │   │   ├── markdown.py    # HTML zu Markdown Konvertierung & Link-Rewriting
│   │   │   └── images.py      # Vollauflösungs-Download & SHA-256 Deduplizierung
│   │   └── utils/
│   │       ├── path_utils.py  # Bereinigung ungültiger Zeichen & Pfadkalkulation
│   │       └── url_utils.py   # URL-Normalisierung & Filterprüfung
│   ├── build.py               # PyInstaller Build-Skript
│   ├── main.py                # Einstiegspunkt
│   └── tools.py               # Format- & Lint-Helfer
└── tests/                     # Umfangreiche Testsuite (pytest)
```

## Quickstart

```bash
# Repository klonen & Abhängigkeiten synchronisieren
uv sync

# Grafische Benutzeroberfläche (GUI) starten
uv run gui
# oder per CLI-Flag:
uv run py-wiki-crawler --gui

# Wiki im Terminal mit Standardeinstellungen herunterladen
uv run py-wiki-crawler https://genshin-impact.fandom.com

# Mit Optionen (z. B. Zielordner, Begrenzung und ohne Bilder)
uv run py-wiki-crawler https://hollowknight.fandom.com -o mein_wiki -m 50

# Erneuter Lauf in denselben Ordner: lädt nur Fehlgeschlagenes/Neues nach
uv run py-wiki-crawler https://hollowknight.fandom.com -o mein_wiki

# Alles neu laden
uv run py-wiki-crawler https://hollowknight.fandom.com -o mein_wiki --force

# Tests ausführen
uv run pytest

# Linter & Formatter prüfen
uv run ruff check .
uv run ruff format .
```

## CLI-Optionen

| Parameter | Beschreibung | Standardwert |
| :--- | :--- | :--- |
| `url` | Start-URL des Wikis | *(erforderlich)* |
| `-o`, `--output` | Zielverzeichnis für Markdown & Assets | `wiki_export` |
| `-d`, `--delay` | Pause zwischen Anfragen in Sekunden | `0.4` |
| `-m`, `--max-pages` | Maximale Seitenanzahl zum Herunterladen | `None` (alle) |
| `--max-depth` | Maximale Klicktiefe für HTML-Crawler | `5` |
| `--no-images` | Download von Bildern deaktivieren | `False` |
| `--force` | Alle Seiten neu laden statt nur Fehlgeschlagenes/Neues | `False` |
| `-v`, `--verbose` | Ausführliches Debug-Logging | `False` |
| `--version` | Programmversion anzeigen | - |
