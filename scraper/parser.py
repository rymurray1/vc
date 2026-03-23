"""
Search result HTML parsers.
Extracts structured results from DuckDuckGo Lite HTML pages.
"""

import urllib.parse
from bs4 import BeautifulSoup


def parse_ddg_lite_html(html):
    """
    Parse DuckDuckGo Lite search results HTML into structured data.
    Returns dict matching Serper.dev response format:
    {
        "organic": [{"title": str, "link": str, "snippet": str}, ...],
        "knowledgeGraph": {}
    }
    """
    soup = BeautifulSoup(html, "html.parser")

    results = []

    # DDG Lite renders results as <a class="result-link"> tags
    # Each result link is followed by a snippet in a <td class="result-snippet">
    result_links = soup.find_all("a", class_="result-link")

    for a in result_links:
        title = a.get_text(strip=True)
        raw_href = a.get("href", "")

        # DDG Lite wraps URLs in a redirect: //duckduckgo.com/l/?uddg=<encoded_url>&rut=...
        link = _extract_ddg_url(raw_href)

        # Find the snippet — it's in the next <tr>'s <td class="result-snippet">
        snippet = _find_snippet(a)

        if title and link:
            results.append({
                "title": title,
                "link": link,
                "snippet": snippet,
            })

    return {
        "organic": results,
        "knowledgeGraph": {},  # DDG Lite doesn't have knowledge graph panels
    }


def _extract_ddg_url(raw_href):
    """Extract the actual URL from a DuckDuckGo redirect link."""
    if "uddg=" in raw_href:
        # Parse out the encoded URL
        try:
            encoded = raw_href.split("uddg=")[1].split("&")[0]
            return urllib.parse.unquote(encoded)
        except (IndexError, ValueError):
            pass

    # If no redirect wrapper, return as-is (strip protocol-relative prefix)
    if raw_href.startswith("//"):
        return "https:" + raw_href

    return raw_href


def _find_snippet(result_link_tag):
    """
    Find the snippet text for a result.
    In DDG Lite, snippets are in <td class="result-snippet"> in the next table row.
    """
    parent_td = result_link_tag.find_parent("td")
    if not parent_td:
        return ""

    parent_tr = parent_td.find_parent("tr")
    if not parent_tr:
        return ""

    next_tr = parent_tr.find_next_sibling("tr")
    if not next_tr:
        return ""

    snippet_td = next_tr.find("td", class_="result-snippet")
    if snippet_td:
        return snippet_td.get_text(strip=True)

    return ""


def is_blocked(html):
    """Check if the response HTML indicates we've been blocked."""
    if not html or len(html) < 500:
        return True

    lower = html.lower()

    block_markers = [
        "unusual traffic",
        "captcha",
        "blocked",
        "rate limit",
        "too many requests",
        "access denied",
    ]

    return any(marker in lower for marker in block_markers)
