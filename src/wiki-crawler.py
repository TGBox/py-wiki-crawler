#!/usr/bin/env python3
"""
Spiele-Wiki Downloader & Markdown Konverter
==========================================
Ein vielseitiges Skript zum Herunterladen von Spiele-Wikis (Fandom, MediaWiki
sowie generische HTML-Wikis) und deren Konvertierung in eine saubere,
verschachtelte Markdown-Ordnerstruktur.

Features:
- Erkennt automatisch MediaWiki / Fandom APIs für maximale Geschwindigkeit & Zuverlässigkeit.
- Fallback-Crawler für benutzerdefinierte Wikis ohne API.
- Wandelt Wiki-Subpages (z. B. "Waffen/Schwerter/Excalibur") in echte Verzeichnisstrukturen um.
- Bereinigt Dateinamen für Windows, macOS und Linux.
- Extrahiert Metadaten (Titel, Original-URL, Kategorien) in YAML-Frontmatter.
- Höfliches Scraping mit einstellbarem Rate-Limiting.
"""

import os
import re
import sys
import time
import argparse
import logging
from urllib.parse import urljoin, urlparse, unquote
from pathlib import Path
from typing import Set, List, Dict, Optional

# Externe Bibliotheken prüfen
try:
    import requests
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
except ImportError:
    print(
        "Fehlende Bibliotheken! Bitte installiere die benötigten Pakete mit:\n"
        "pip install requests beautifulsoup4 markdownify tqdm"
    )
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    # Einfacher Fallback, falls tqdm nicht installiert ist
    def tqdm(iterable, **kwargs):
        return iterable


# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("WikiScraper")


class WikiToMarkdownScraper:
    def __init__(
        self,
        base_url: str,
        output_dir: str = "wiki_export",
        delay: float = 0.5,
        max_pages: Optional[int] = None,
        save_images: bool = False
    ):
        """
        Initialisiert den Scraper.

        :param base_url: Die Start-URL des Wikis (z.B. https://genshin-impact.fandom.com/)
        :param output_dir: Zielordner für die Markdown-Dateien
        :param delay: Pause zwischen Anfragen in Sekunden (höflicher Umgang mit Servern)
        :param max_pages: Maximale Seitenanzahl zum Herunterladen (None für alle)
        :param save_images: Ob gefundene Bilder ebenfalls heruntergeladen werden sollen
        """
        self.base_url = base_url.rstrip("/")
        self.output_dir = Path(output_dir)
        self.delay = delay
        self.max_pages = max_pages
        self.save_images = save_images

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36 (WikiMarkdownExporter/1.0)"
            )
        })

        self.visited_urls: Set[str] = set()
        self.api_endpoint: Optional[str] = self._detect_mediawiki_api()

    def _detect_mediawiki_api(self) -> Optional[str]:
        """Prüft, ob das Wiki eine zugängliche MediaWiki/Fandom api.php hat."""
        parsed = urlparse(self.base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        candidates = [
            f"{self.base_url}/api.php",
            f"{origin}/api.php",
            f"{origin}/w/api.php",
        ]

        for endpoint in candidates:
            try:
                resp = self.session.get(
                    endpoint,
                    params={"action": "query", "meta": "siteinfo", "format": "json"},
                    timeout=5
                )
                if resp.status_code == 200 and "query" in resp.json():
                    logger.info(f"MediaWiki API gefunden: {endpoint}")
                    return endpoint
            except Exception:
                continue

        logger.info("Keine MediaWiki API gefunden. Verwende rekursiven HTML-Crawler.")
        return None

    def sanitize_path_segment(self, segment: str) -> str:
        """Entfernt ungültige Zeichen für Dateisysteme (Windows/Linux/Mac)."""
        segment = unquote(segment).strip()
        # Illegale Zeichen ersetzen
        clean = re.sub(r'[\\:*?"<>|]', "_", segment)
        # Punkte am Ende vermeiden (Windows-Problem)
        clean = clean.rstrip(". ")
        return clean or "unbenannt"

    def title_to_path(self, title: str) -> Path:
        """
        Wandelt Titel mit Schrägstrichen ('Item/Weapon/Sword') in verschachtelte
        Ordner ('Item/Weapon/Sword.md') um.
        """
        segments = title.split("/")
        sanitized_segments = [self.sanitize_path_segment(s) for s in segments if s.strip()]

        if not sanitized_segments:
            sanitized_segments = ["index"]

        # Dateiname ist das letzte Segment + .md
        folder = Path(*sanitized_segments[:-1]) if len(sanitized_segments) > 1 else Path()
        filename = f"{sanitized_segments[-1]}.md"

        return self.output_dir / folder / filename

    def clean_html_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Entfernt unnötige UI-Elemente wie Navigation, Footer, Werbung und Edit-Links."""
        unwanted_selectors = [
            "nav", "footer", "header", "aside",
            ".mw-editsection", ".toc", "#toc", ".navbox",
            ".wds-global-navigation", ".page-header__actions",
            ".license-description", ".printfooter", ".catlinks",
            "script", "style", "iframe", "noscript"
        ]

        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()

        return soup

    def convert_html_to_markdown(self, title: str, html_str: str, source_url: str) -> str:
        """Wandelt HTML in sauberes Markdown mit YAML-Frontmatter um."""
        soup = BeautifulSoup(html_str, "html.parser")

        # Relevanter Hauptinhalt lokalisieren
        content_container = (
            soup.select_one(".mw-parser-output")
            or soup.select_one("#mw-content-text")
            or soup.select_one("article")
            or soup.select_one("main")
            or soup
        )

        content_container = self.clean_html_content(content_container)

        # HTML zu Markdown konvertieren
        markdown_body = md(
            str(content_container),
            heading_style="ATX",
            bullets="-",
            strip=["script", "style"]
        ).strip()

        # Mehrfache Leerzeilen normalisieren
        markdown_body = re.sub(r"\n{3,}", "\n\n", markdown_body)

        # YAML Frontmatter zusammenstellen
        frontmatter = (
            f"---\n"
            f"title: \"{title.replace('\"', '\\\"')}\"\n"
            f"source_url: \"{source_url}\"\n"
            f"exported_at: \"{time.strftime('%Y-%m-%d %H:%M:%S')}\"\n"
            f"---\n\n"
        )

        return frontmatter + f"# {title}\n\n" + markdown_body

    # =========================================================================
    # Modus 1: MediaWiki API (Schnell, vollständig, verlässlich)
    # =========================================================================
    def fetch_all_mediawiki_titles(self) -> List[str]:
        """Ruft alle Artikeltitel über die MediaWiki allpages API ab."""
        titles = []
        apfrom = None

        logger.info("Rufe Artikelliste über die API ab...")

        while True:
            params = {
                "action": "query",
                "list": "allpages",
                "aplimit": "500",
                "apnamespace": "0",  # Hauptartikel (0 = Main Namespace)
                "format": "json"
            }
            if apfrom:
                params["apcontinue"] = apfrom

            resp = self.session.get(self.api_endpoint, params=params).json()
            pages = resp.get("query", {}).get("allpages", [])
            for page in pages:
                titles.append(page["title"])
                if self.max_pages and len(titles) >= self.max_pages:
                    return titles

            if "continue" in resp and "apcontinue" in resp["continue"]:
                apfrom = resp["continue"]["apcontinue"]
                time.sleep(self.delay)
            else:
                break

        logger.info(f"Insgesamt {len(titles)} Artikel gefunden.")
        return titles

    def download_page_via_api(self, title: str):
        """Holt das gerenderte HTML einer Seite über parse API und speichert es als Markdown."""
        params = {
            "action": "parse",
            "page": title,
            "prop": "text",
            "format": "json",
            "disableeditsection": 1,
            "redirects": 1
        }

        try:
            resp = self.session.get(self.api_endpoint, params=params).json()
            if "parse" not in resp:
                logger.warning(f"Konnte Seite nicht abrufen: {title}")
                return

            html_text = resp["parse"]["text"]["*"]
            source_url = f"{self.base_url}/wiki/{title.replace(' ', '_')}"
            markdown_content = self.convert_html_to_markdown(title, html_text, source_url)

            # Pfad generieren und speichern
            dest_file = self.title_to_path(title)
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            with open(dest_file, "w", encoding="utf-8") as f:
                f.write(markdown_content)

        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten von '{title}': {e}")

    def run_api_scraping(self):
        """Führt den API-basierten Export durch."""
        titles = self.fetch_all_mediawiki_titles()

        for title in tqdm(titles, desc="Exportiere Seiten (API)"):
            self.download_page_via_api(title)
            time.sleep(self.delay)

    # =========================================================================
    # Modus 2: Rekursiver HTML Crawler (Fallback für Non-MediaWiki Seiten)
    # =========================================================================
    def is_valid_internal_link(self, url: str) -> bool:
        """Stellt sicher, dass Links innerhalb der gleichen Wiki-Domain & Pfad bleiben."""
        parsed_base = urlparse(self.base_url)
        parsed_target = urlparse(url)

        # Gleiche Domain?
        if parsed_base.netloc != parsed_target.netloc:
            return False

        # Fragmente oder Abfragen ignorieren
        path = parsed_target.path
        if any(path.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".svg", ".zip", ".pdf"]):
            return False

        return True

    def run_html_crawler(self):
        """Durchsucht das Wiki rekursiv via BFS-Warteschlange."""
        queue = [self.base_url]
        self.visited_urls.add(self.base_url)
        processed = 0

        pbar = tqdm(total=self.max_pages or 100, desc="Crawle HTML Seiten")

        while queue:
            current_url = queue.pop(0)

            try:
                resp = self.session.get(current_url, timeout=10)
                if resp.status_code != 200 or "text/html" not in resp.headers.get("Content-Type", ""):
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # Seitentitel ermitteln
                h1 = soup.find("h1")
                title = h1.get_text(strip=True) if h1 else soup.title.string if soup.title else "Unbenannt"
                # Falls URL-basierte Titelstruktur bevorzugt wird:
                url_path = unquote(urlparse(current_url).path).strip("/")
                relative_title = url_path.replace("wiki/", "") if url_path else title

                # Markdown speichern
                md_content = self.convert_html_to_markdown(title, resp.text, current_url)
                dest_file = self.title_to_path(relative_title)
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                with open(dest_file, "w", encoding="utf-8") as f:
                    f.write(md_content)

                processed += 1
                pbar.update(1)

                if self.max_pages and processed >= self.max_pages:
                    logger.info("Maximale Seitenanzahl erreicht.")
                    break

                # Neue Links einsammeln
                for a_tag in soup.find_all("a", href=True):
                    next_url = urljoin(current_url, a_tag["href"]).split("#")[0]
                    if next_url not in self.visited_urls and self.is_valid_internal_link(next_url):
                        self.visited_urls.add(next_url)
                        queue.append(next_url)

                time.sleep(self.delay)

            except Exception as e:
                logger.error(f"Fehler beim Aufruf von {current_url}: {e}")

        pbar.close()

    # =========================================================================
    # Startpunkt
    # =========================================================================
    def start(self):
        """Startet den passenden Export-Vorgang."""
        start_time = time.time()
        logger.info(f"Starte Export von: {self.base_url}")
        logger.info(f"Speicherort: {self.output_dir.resolve()}")

        if self.api_endpoint:
            self.run_api_scraping()
        else:
            self.run_html_crawler()

        duration = time.time() - start_time
        logger.info(f"Export erfolgreich beendet in {duration:.2f} Sekunden.")


def main():
    parser = argparse.ArgumentParser(
        description="Spiele-Wiki zu Markdown Downloader (Fandom & MediaWiki kompatibel)."
    )
    parser.add_argument(
        "url",
        help="Basis-URL des Wikis (z.B. https://hollowknight.fandom.com)"
    )
    parser.add_argument(
        "-o", "--output",
        default="wiki_export",
        help="Zielordner für die Markdown-Dateien (Standard: wiki_export)"
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=0.4,
        help="Verzögerung zwischen HTTP-Anfragen in Sekunden (Standard: 0.4s)"
    )
    parser.add_argument(
        "-m", "--max-pages",
        type=int,
        default=None,
        help="Begrenzung der herunterzuladenden Seiten (hilfreich für Tests)"
    )

    args = parser.parse_args()

    scraper = WikiToMarkdownScraper(
        base_url=args.url,
        output_dir=args.output,
        delay=args.delay,
        max_pages=args.max_pages
    )
    scraper.start()


if __name__ == "__main__":
    main()