from django.db import models
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings


# Create your models here.

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    image = models.ImageField(upload_to="images/profile/", null=True, blank=True)
    dob = models.CharField(max_length=50, null=True, blank=True)
    number = models.CharField(max_length=20, null=True, blank=True)
    gender = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

def send_registration_email(user_obj):
    subject = f'Congrats {user_obj.first_name} {user_obj.last_name}! You have done registration in YT Search APP.'
    # Change the following line to the admin's email address
    recipient_email = f'{user_obj.email}'
    message = f"Hi {user_obj.email},\n\nYou've registered! Now login your account.\n\n\nYour username is {user_obj.username}"

    admin_subject = f'New Registration on YT Search APP'
    admin_message = f'User Details:\n\nUser Name: {user_obj.first_name} {user_obj.last_name}\nUser Email: {user_obj.email}\n\nThank you!\nSee your admin panel to see complete details of Users.'
    admin_email = settings.EMAIL_HOST_USER

    try:
        send_mail(subject=subject, message=message, from_email=settings.EMAIL_HOST_USER, recipient_list=[recipient_email])
        send_mail(subject=admin_subject, message=admin_message, from_email=settings.EMAIL_HOST_USER, recipient_list=[admin_email])
    except Exception as e:
        print(f"Failed to send registration email to {recipient_email}. Error: {e}")

class SavedVideos(models.Model):
    user_profile = models.ForeignKey(User, on_delete=models.CASCADE)
    video_title = models.CharField(max_length=255, null=True, blank=True)
    video_link = models.CharField(max_length=100, null=True, blank=True, unique=True)
    video_desc = models.TextField(default="", null=True, blank=True)
    video_image = models.CharField(max_length=100, null=True, blank=True)
    video_views = models.CharField(max_length=50, null=True, blank=True)
    video_published_date = models.CharField(max_length=50, null=True, blank=True)
    video_channel_name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.video_title