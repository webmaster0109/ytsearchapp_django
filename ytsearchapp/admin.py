from django.contrib import admin
from .models import Profile, SavedVideos
# Register your models here.

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['get_username', 'created_at', 'modified_at']

    def get_username(self, obj):
        return obj.user.username if obj.user_id else '(no user)'


@admin.register(SavedVideos)
class SavedVideosAdmin(admin.ModelAdmin):
    list_display = ['video_title', 'user_profile', 'video_link']
    search_fields = ['video_title', 'video_channel_name', 'user_profile__username']
