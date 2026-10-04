from django.urls import path
from .views import (
    change_password,
    forgot_password,
    home,
    login_attempt,
    playlist_videos,
    register_attempt,
    remove_saved_video,
    resend_verification,
    save_video,
    saved_videos,
    signout,
    verify_account,
    watch_video,
)

urlpatterns = [
    path('', home, name="home"),
    path('watch', watch_video, name="watch_video"),
    path('playlist', playlist_videos, name="playlist"),
    path('auth/login', login_attempt, name="login"),
    path('auth/register', register_attempt, name="register"),
    path('verify-account/<str:token>', verify_account, name='verify_account'),
    path('resend-verification', resend_verification, name='resend_verification'),
    path('saved-videos', saved_videos, name='saved_videos'),
    path('saved-videos/save', save_video, name='save_video'),
    path('saved-videos/<int:video_pk>/remove', remove_saved_video, name='remove_saved_video'),
    path('logout', signout, name='logout'),
    path('forgot-password', forgot_password, name="forgot_password"),
    path('change-password/<str:token>', change_password, name="change_password"),
]
