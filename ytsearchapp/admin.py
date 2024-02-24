from django.contrib import admin
from .models import Profile
# Register your models here.

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['get_username', 'created_at', 'modified_at']

    def get_username(self, obj):
        return obj.user.username