from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .services.youtube_service import fetch_youtube_hazards


@api_view(["GET"])
def youtube_hazards(request):
    """
    API Endpoint:
    /api/social/youtube/?region=Pune
    """
    region = request.GET.get("region")
    data = fetch_youtube_hazards(region_query=region)
    return Response(data)

from .services.news_service import fetch_news_hazards
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(["GET"])
def news_hazards(request):
    region = request.GET.get("region")
    days = request.GET.get("days")

    data = fetch_news_hazards(region_query=region, days=days)
    return Response(data)


from .services.google_news_service import fetch_google_news

@api_view(["GET"])
def google_news_hazards(request):
    region = request.GET.get("region")
    year = request.GET.get("year")

    data = fetch_google_news(region_query=region, year=year)
    return Response(data)