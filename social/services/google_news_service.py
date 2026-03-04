import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

import requests


logger = logging.getLogger(_name_)
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
MAX_RESULTS = 20
FULL_TEXT_RESULTS_LIMIT = 6
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _clean_news_text(text):
    if not text:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", text)
    return " ".join(unescape(without_tags).split())


def _build_search_queries(region_query=None):
    region = (region_query or "").strip()
    gcc_scope = "(GCC OR Bahrain OR Kuwait OR Oman OR Qatar OR \"Saudi Arabia\" OR UAE OR \"United Arab Emirates\")"
    water_hazard_scope = "(flood OR \"flash flood\" OR \"heavy rain\" OR waterlogging OR monsoon OR \"storm surge\" OR \"dam overflow\")"

    if not region:
        return [f"{water_hazard_scope} {gcc_scope}"]

    return [
        f"{water_hazard_scope} {gcc_scope} {region}",
        f"{water_hazard_scope} {region}",
    ]


def _resolve_google_news_url(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return url

    if "news.google.com" not in parsed.netloc:
        return url

    query = parse_qs(parsed.query)
    target = query.get("url", [None])[0]
    if target:
        return target

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=8, allow_redirects=True)
        response.raise_for_status()

        final_url = response.url
        if final_url:
            final_parsed = urlparse(final_url)
            if "news.google.com" not in final_parsed.netloc:
                return final_url

        canonical_match = re.search(
            r'(?is)<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
            response.text,
        )
        if canonical_match:
            canonical_url = canonical_match.group(1).strip()
            if canonical_url:
                canonical_parsed = urlparse(canonical_url)
                if canonical_parsed.netloc and "news.google.com" not in canonical_parsed.netloc:
                    return canonical_url
    except requests.RequestException:
        pass

    return url


def _remove_title_prefix(text, title):
    cleaned_text = _clean_news_text(text)
    cleaned_title = _clean_news_text(title)

    if not cleaned_text:
        return ""
    if not cleaned_title:
        return cleaned_text

    if cleaned_text.lower().startswith(cleaned_title.lower()):
        remainder = cleaned_text[len(cleaned_title):].strip(" -|,:.")
        return remainder or ""

    return cleaned_text


def _extract_paragraph_texts(html_text):
    if not html_text:
        return []

    cleaned = re.sub(r"(?is)<(script|style|noscript).?>.?</\\1>", " ", html_text)
    paragraphs = re.findall(r"(?is)<p[^>]>(.?)</p>", cleaned)

    texts = []
    for paragraph in paragraphs:
        cleaned_paragraph = _clean_news_text(paragraph)
        if not cleaned_paragraph:
            continue
        if len(cleaned_paragraph.split()) < 3:
            continue
        texts.append(cleaned_paragraph)

    return texts


def _build_summary_lines_from_paragraphs(paragraphs, max_lines=4):
    combined = " ".join(paragraphs).strip()
    if not combined:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", combined)
    lines = []

    for sentence in sentences:
        cleaned = sentence.strip()
        if not cleaned:
            continue
        if cleaned in lines:
            continue
        lines.append(cleaned)
        if len(lines) >= max_lines:
            break

    if not lines:
        return ""

    return "\n".join(lines)


def _fetch_article_summary(url, max_lines=4):
    resolved_url = _resolve_google_news_url(url)

    try:
        response = requests.get(resolved_url, headers=DEFAULT_HEADERS, timeout=8)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Article fetch failed: %s", exc)
        return ""

    paragraphs = _extract_paragraph_texts(response.text)
    return _build_summary_lines_from_paragraphs(paragraphs, max_lines=max_lines)


def _fetch_google_rss(search_query, since_dt, use_full_text=False):
    params = {
        "q": search_query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }

    try:
        response = requests.get(GOOGLE_NEWS_RSS_URL, params=params, timeout=12)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except requests.RequestException as exc:
        logger.warning("Google News RSS request failed: %s", exc)
        return []
    except ET.ParseError as exc:
        logger.warning("Google News RSS XML parse failed: %s", exc)
        return []

    results = []
    seen_urls = set()
    full_text_count = 0

    for item in root.findall("./channel/item"):
        url = item.findtext("link")
        if not url or url in seen_urls:
            continue

        published_at_raw = item.findtext("pubDate")
        published_at = published_at_raw
        if published_at_raw:
            try:
                published_dt = parsedate_to_datetime(published_at_raw)
                if published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)

                if published_dt < since_dt:
                    continue

                published_at = published_dt.isoformat()
            except (TypeError, ValueError):
                pass

        source = item.findtext("source") or "Google News"
        title = item.findtext("title") or ""
        description = _remove_title_prefix(item.findtext("description") or "", title)
        summary_lines = ""
        if use_full_text and url and full_text_count < FULL_TEXT_RESULTS_LIMIT:
            summary_lines = _fetch_article_summary(url, max_lines=4)
            if summary_lines:
                full_text_count += 1

        seen_urls.add(url)
        results.append({
            "title": title,
            "url": url,
            "publishedAt": published_at,
            "source": source,
            "description": description,
            "news": summary_lines or description,
        })

        if len(results) >= MAX_RESULTS:
            break

    return results


def fetch_google_news(region_query=None, year=None):
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    use_full_text = year is not None

    for search_query in _build_search_queries(region_query=region_query):
        results = _fetch_google_rss(
            search_query=search_query,
            since_dt=one_year_ago,
            use_full_text=use_full_text,
        )
        if results:
            return results

    return []