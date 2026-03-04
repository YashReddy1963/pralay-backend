from django.urls import path
from .views import youtube_hazards,news_hazards,google_news_hazards

urlpatterns = [
    path("youtube/", youtube_hazards),
    path("news/", news_hazards),
    path("google-news/", google_news_hazards),


]