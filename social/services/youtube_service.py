import requests
from django.conf import settings
from datetime import datetime, timedelta

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# Positive keywords (real hazard indicators)
POSITIVE_KEYWORDS = [
    "flood", "waterlogging", "heavy rain",
    "river overflow", "dam overflow",
    "rescue", "evacuation", "alert",
    "bridge collapse", "rain damage"
]

# Negative keywords (fun / irrelevant content)
NEGATIVE_KEYWORDS = [
    "funny", "comedy", "meme", "prank",
    "movie", "song", "trailer",
    "reaction", "minecraft", "game"
]


def is_serious_video(title, description):
    """
    Filters out non-serious content.
    """
    text = (title + " " + description).lower()

    # Reject negative content
    if any(word in text for word in NEGATIVE_KEYWORDS):
        return False

    # Must contain at least one positive hazard keyword
    if not any(word in text for word in POSITIVE_KEYWORDS):
        return False

    return True


def matches_region(title, description, region):
    """
    Ensures video belongs to requested region.
    """
    text = (title + " " + description).lower()
    return region.lower() in text


def fetch_youtube_hazards(region_query=None):
    """
    Fetches recent YouTube videos related to water hazards.
    """

    # Only last 24 hours
    # published_after = (
    #     datetime.utcnow() - timedelta(days=100)
    # ).isoformat("T") + "Z"
    

    # Hazard query
    query = "flood OR waterlogging OR heavy rainfall OR dam overflow"

    if region_query:
        query += f" {region_query}"

    params = {
        "key": settings.YOUTUBE_API_KEY,
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 20,
        "order": "date",
        
        "regionCode": "IN",
        "relevanceLanguage": "en"
    }

    response = requests.get(YOUTUBE_SEARCH_URL, params=params)
    data = response.json()

    results = []

    for item in data.get("items", []):
        title = item["snippet"]["title"]
        description = item["snippet"]["description"]

        # Filter serious content
        if not is_serious_video(title, description):
            continue

        # Filter by region
        if region_query and not matches_region(title, description, region_query):
            continue

        results.append({
            "videoId": item["id"]["videoId"],
            "title": title,
            "description": description,
            "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
            "channelTitle": item["snippet"]["channelTitle"],
            "publishedAt": item["snippet"]["publishedAt"]
        })

    return results