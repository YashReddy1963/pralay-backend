import requests
from django.conf import settings
from datetime import datetime, timedelta
import logging

NEWS_URL = "https://newsapi.org/v2/everything"
logger = logging.getLogger(__name__)

# Strong flood-related keywords
POSITIVE_TERMS = [
    "flood", "flash flood", "waterlogging",
    "inundation", "submerged",
    "dam overflow", "river overflow",
    "levee breach", "embankment breach",
    "evacuation", "rescue",
    "flood alert", "flood warning"
]

# Remove unwanted topics
NEGATIVE_TERMS = [
    "politics", "election", "stock market",
    "movie", "celebrity", "review",
    "analysis", "editorial", "opinion"
]


def is_relevant_news(title, description):
    text = (title + " " + (description or "")).lower()

    # Remove irrelevant topics
    if any(word in text for word in NEGATIVE_TERMS):
        return False

    # Must contain hazard keywords
    if not any(word in text for word in POSITIVE_TERMS):
        return False

    return True


def fetch_news_hazards(region_query=None, days=None):
    """
    Fetch hazard-related news filtered by region and time.
    """

    # Strong query structure
    query = (
        '("flash flood" OR flood OR "flood warning" OR "flood alert" '
        'OR waterlogging OR inundation OR "dam overflow" OR "river overflow" '
        'OR "levee breach" OR "embankment breach")'
    )

    if region_query:
        query += f" AND {region_query}"

    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "apiKey": settings.NEWS_API_KEY,
        "pageSize": 20
    }

    # Optional time filter
    if days:
        from_date = (
            datetime.utcnow() - timedelta(days=int(days))
        ).strftime("%Y-%m-%d")

        params["from"] = from_date

    try:
        response = requests.get(NEWS_URL, params=params, timeout=12)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.warning("News API request failed: %s", exc)
        return []
    except ValueError as exc:
        logger.warning("News API invalid JSON response: %s", exc)
        return []

    results = []

    for article in data.get("articles", []):
        title = article.get("title", "")
        description = article.get("description", "")

        if not is_relevant_news(title, description):
            continue

        results.append({
            "title": title,
            "description": description,
            "url": article.get("url"),
            "source": article.get("source", {}).get("name"),
            "publishedAt": article.get("publishedAt"),
            "image": article.get("urlToImage"),
            "priority": "high" if "evacuation" in title.lower() else "medium"
        })

    return results