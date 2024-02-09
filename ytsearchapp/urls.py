from django.urls import path
from .views import *

urlpatterns = [
    path('', home, name="home"),
    path('watch', watch_video, name="watch_video"),
    path('playlist', playlist_videos, name="playlist"),
    path('auth/login', login_attempt, name="login"),
    path('auth/register', register_attempt, name="register"),
    path('logout', signout, name="logout"),
]
