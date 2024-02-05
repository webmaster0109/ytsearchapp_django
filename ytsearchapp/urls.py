from django.urls import path
from .views import *

urlpatterns = [
    path('', home, name="home"),
    path('watch', watch_video, name="watch_video"),
    path('playlist', playlist_videos, name="playlist")
]
