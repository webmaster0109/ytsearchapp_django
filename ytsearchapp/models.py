import logging
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import models

logger = logging.getLogger(__name__)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    image = models.ImageField(upload_to='images/profile/', null=True, blank=True)
    dob = models.CharField(max_length=50, null=True, blank=True)
    number = models.CharField(max_length=20, null=True, blank=True)
    gender = models.CharField(max_length=50, null=True, blank=True)
    # These fields contain SHA-256 digests, never usable tokens.
    verification_token = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    forgot_password_token = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    verification_sent_at = models.DateTimeField(null=True, blank=True)
    password_reset_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username if self.user_id and self.user else 'Profile'


def _send_email(subject, message, recipient_email):
    if not recipient_email:
        return False
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception('Email delivery failed for recipient %s', recipient_email)
        return False


def send_registration_email(user_obj):
    """Send a post-verification welcome email without exposing account details."""
    return _send_email(
        subject='Welcome to YT Search App',
        message=(
            f'Hi {user_obj.first_name or user_obj.username},\n\n'
            'Your YT Search App account has been verified successfully.\n'
            'You can now sign in and use the application.'
        ),
        recipient_email=user_obj.email,
    )


def send_forgot_password_mail(user_obj, token):
    reset_url = f'{settings.SITE_URL}/change-password/{token}'
    return _send_email(
        subject='Reset your YT Search App password',
        message=(
            f'Hi {user_obj.first_name or user_obj.username},\n\n'
            f'Use this link to reset your password within 10 minutes:\n{reset_url}\n\n'
            'If you did not request this, you can ignore this email.'
        ),
        recipient_email=user_obj.email,
    )


def send_verification_mail(email, token):
    verify_url = f'{settings.SITE_URL}/verify-account/{token}'
    return _send_email(
        subject='Verify your YT Search App account',
        message=(
            f'Hi {email},\n\n'
            f'Use this link to verify your account within 24 hours:\n{verify_url}'
        ),
        recipient_email=email,
    )


class SavedVideos(models.Model):
    user_profile = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_videos')
    video_title = models.CharField(max_length=255, blank=True, default='')
    video_link = models.URLField(max_length=500)
    video_desc = models.TextField(default='', blank=True)
    video_image = models.URLField(max_length=500, blank=True, default='')
    video_views = models.CharField(max_length=50, blank=True, default='')
    video_published_date = models.CharField(max_length=50, blank=True, default='')
    video_channel_name = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user_profile', 'video_link'],
                name='unique_saved_video_per_user',
            ),
        ]

    def __str__(self):
        return self.video_title or self.video_link

    @property
    def video_id(self):
        parsed = urlsplit(self.video_link)
        query_id = parse_qs(parsed.query).get('v', [None])[0]
        if query_id:
            return query_id
        if parsed.hostname in {'youtu.be', 'www.youtu.be'}:
            return parsed.path.strip('/').split('/')[0]
        return self.video_link
