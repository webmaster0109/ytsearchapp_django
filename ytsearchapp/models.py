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
    verification_token = models.CharField(max_length=100, null=True, blank=True)
    is_verified = models.BooleanField(default=False, null=True, blank=True)
    forgot_password_token = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

def send_registration_email(user_obj):
    subject = f'Congrats {user_obj.first_name} {user_obj.last_name}! You have done registration in YT Search APP.'
    # Change the following line to the admin's email address
    recipient_email = f'{user_obj.email}'
    message = f"Hi {user_obj.email},\n\nYou've successfully registered! Now you can login your account.\n\n\nYour username is {user_obj.username}"

    admin_subject = f'New Registration on YT Search APP'
    admin_message = f'User Details:\n\nUser Name: {user_obj.first_name} {user_obj.last_name}\nUser Email: {user_obj.email}\n\nThank you!\nSee your admin panel to see complete details of Users.'
    admin_email = settings.EMAIL_HOST_USER 

    try:
        send_mail(subject=subject, message=message, from_email=settings.EMAIL_HOST_USER, recipient_list=[recipient_email])
        send_mail(subject=admin_subject, message=admin_message, from_email=settings.EMAIL_HOST_USER, recipient_list=[admin_email])
    except Exception as e:
        print(f"Failed to send registration email to {recipient_email}. Error: {e}")

def send_forgot_password_mail(request, user_obj, token):
    # forgot password email
    website_url = request.build_absolute_uri('/')[:-1]
    forgot_password_subject = "Your forgot password link"
    forgot_password_message = f"Hi {user_obj.first_name}!\nClick on the link to reset your password {website_url}/change-password/{token}"
    recipient_email = user_obj.email

    try:
        send_mail(subject=forgot_password_subject, message=forgot_password_message, from_email=settings.EMAIL_HOST_USER, recipient_list=[recipient_email])
        return True
    except Exception as e:
        print(f"Failed to send registration email to {recipient_email}. Error: {e}")

def send_verification_mail(request, email, token):
    try:
        website_url = request.build_absolute_uri('/')[:-1]
        forgot_password_subject = "Your registered account needs to be verified."
        forgot_password_message = f"Hi {email}!\nClick on the link to verify your account {website_url}/verify-account/{token}"
        recipient_email = email
        send_mail(subject=forgot_password_subject, message=forgot_password_message, from_email=settings.EMAIL_HOST_USER, recipient_list=[recipient_email])
    except Exception as e:
        print(f"Failed to send registration email to {recipient_email}. Error: {e}")
        return False
    
    return True

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