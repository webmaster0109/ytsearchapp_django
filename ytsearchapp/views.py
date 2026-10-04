import hashlib
import logging
import re
import secrets
import time
from datetime import timedelta

from dateutil import parser
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import redirect, render
from django.template.defaultfilters import urlize
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import (
    Profile,
    SavedVideos,
    send_forgot_password_mail,
    send_registration_email,
    send_verification_mail,
)
from .youtube import (
    PlaylistVideos,
    YoutubePlaylistSearch,
    YoutubeVideoSearch,
    get_video_comments,
    get_video_detail,
    search_video_suggestions,
)

logger = logging.getLogger(__name__)
VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{6,20}$')
PLAYLIST_ID_RE = re.compile(r'^[A-Za-z0-9_-]{5,100}$')


def _token_digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _new_token():
    token = secrets.token_urlsafe(32)
    return token, _token_digest(token)


def _safe_next_url(request):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return reverse('home')


def _rate_limit(request, action, limit, period):
    """Rate-limit by the direct peer address; never trust forwarded headers."""
    address = request.META.get('REMOTE_ADDR', 'unknown')
    key = f'ytsearch:rate:{action}:{hashlib.sha256(address.encode()).hexdigest()}'
    try:
        if cache.add(key, 1, timeout=period):
            return True
        count = cache.incr(key)
        return count <= limit
    except Exception:
        logger.exception('Rate limiter unavailable for action %s', action)
        return True


def _username_for_email(email):
    base = re.sub(r'[^a-zA-Z0-9._-]', '-', email.rsplit('@', 1)[0]).strip('-._')[:135] or 'user'
    username = base
    suffix = 1
    while User.objects.filter(username__iexact=username).exists():
        suffix += 1
        username = f'{base[:150 - len(str(suffix)) - 1]}-{suffix}'
    return username


def _profile_token_expired(sent_at, timeout):
    return not sent_at or sent_at + timedelta(seconds=timeout) < timezone.now()


def _clear_token(profile, token_field, timestamp_field):
    setattr(profile, token_field, None)
    setattr(profile, timestamp_field, None)
    profile.save(update_fields=[token_field, timestamp_field, 'modified_at'])


def login_attempt(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        if not _rate_limit(request, 'login', 10, 300):
            messages.error(request, 'Too many login attempts. Please try again later.')
            return redirect('login')
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        user_obj = authenticate(request, username=username, password=password)
        profile_obj = Profile.objects.filter(user=user_obj).first() if user_obj else None
        if user_obj and profile_obj and profile_obj.is_verified:
            login(request, user_obj)
            return redirect(_safe_next_url(request))
        if user_obj and (not profile_obj or not profile_obj.is_verified):
            messages.warning(
                request,
                'Your account is not verified. Check your email or request a new verification link.',
            )
        else:
            messages.warning(request, 'Invalid username or password. Please try again.')
        return redirect('login')
    return render(request, 'login.html', {'next': request.GET.get('next', '')})


def register_attempt(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        if not _rate_limit(request, 'register', 5, 3600):
            messages.error(request, 'Too many registration attempts. Please try again later.')
            return redirect('register')
        first_name = (request.POST.get('first_name') or '').strip()
        last_name = (request.POST.get('last_name') or '').strip()
        email = (request.POST.get('email') or '').strip().lower()
        password = request.POST.get('password') or ''
        confirm_password = request.POST.get('confirm_password') or ''

        if not first_name or not last_name or not email:
            messages.warning(request, 'Please complete all required fields.')
            return redirect('register')
        try:
            validate_email(email)
        except ValidationError:
            messages.warning(request, 'Enter a valid email address.')
            return redirect('register')
        if password != confirm_password:
            messages.warning(request, 'Passwords do not match. Please enter matching passwords.')
            return redirect('register')
        if User.objects.filter(email__iexact=email).exists():
            messages.warning(request, 'An account with that email already exists.')
            return redirect('register')

        try:
            with transaction.atomic():
                user_obj = User(
                    username=_username_for_email(email),
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
                validate_password(password, user_obj)
                user_obj.set_password(password)
                user_obj.save()
                raw_token, token_digest = _new_token()
                profile_obj = Profile.objects.create(
                    user=user_obj,
                    verification_token=token_digest,
                    verification_sent_at=timezone.now(),
                )
        except ValidationError as error:
            messages.warning(request, ' '.join(error.messages))
            return redirect('register')
        except Exception:
            logger.exception('Registration failed for %s', email)
            messages.error(request, 'Registration could not be completed. Please try again.')
            return redirect('register')

        if not send_verification_mail(email, raw_token):
            messages.warning(
                request,
                'Your account was created, but the verification email could not be sent. Request a new link.',
            )
        else:
            messages.success(request, 'Registration complete. Check your email to verify your account.')
        return redirect('login')
    return render(request, 'register.html')


def verify_account(request, token):
    profile_obj = Profile.objects.select_related('user').filter(
        verification_token=_token_digest(token),
        user__isnull=False,
    ).first()
    if not profile_obj:
        messages.warning(request, 'Invalid or expired verification link. Request a new one.')
        return redirect('login')
    if profile_obj.is_verified:
        messages.info(request, 'Your account is already verified.')
        return redirect('login')
    if _profile_token_expired(profile_obj.verification_sent_at, settings.VERIFICATION_TOKEN_TIMEOUT):
        _clear_token(profile_obj, 'verification_token', 'verification_sent_at')
        messages.warning(request, 'This verification link has expired. Request a new one.')
        return redirect('login')

    with transaction.atomic():
        profile_obj = Profile.objects.select_for_update().select_related('user').filter(
            pk=profile_obj.pk,
            verification_token=_token_digest(token),
        ).first()
        if not profile_obj or profile_obj.is_verified:
            messages.info(request, 'Your account is already verified.')
            return redirect('login')
        profile_obj.is_verified = True
        profile_obj.verification_token = None
        profile_obj.verification_sent_at = None
        profile_obj.save(update_fields=[
            'is_verified', 'verification_token', 'verification_sent_at', 'modified_at',
        ])
    send_registration_email(profile_obj.user)
    login(request, profile_obj.user)
    messages.success(request, 'Your account has been verified.')
    return redirect(_safe_next_url(request))


@require_POST
def resend_verification(request):
    if not _rate_limit(request, 'resend-verification', 5, 3600):
        messages.error(request, 'Too many requests. Please try again later.')
        return redirect('login')
    identifier = (request.POST.get('identifier') or '').strip()
    user_obj = User.objects.filter(username__iexact=identifier).first()
    if not user_obj and '@' in identifier:
        user_obj = User.objects.filter(email__iexact=identifier).first()
    profile_obj = Profile.objects.filter(user=user_obj).first() if user_obj else None
    if profile_obj and not profile_obj.is_verified and user_obj.email:
        raw_token, token_digest = _new_token()
        profile_obj.verification_token = token_digest
        profile_obj.verification_sent_at = timezone.now()
        profile_obj.save(update_fields=['verification_token', 'verification_sent_at', 'modified_at'])
        send_verification_mail(user_obj.email, raw_token)
    messages.success(request, 'If an unverified account matches, a new verification email has been sent.')
    return redirect('login')


@require_POST
def signout(request):
    logout(request)
    return redirect('home')


def forgot_password(request):
    if request.method == 'POST':
        identifier = (request.POST.get('identifier') or '').strip()
        allowed = _rate_limit(request, 'password-reset', 5, 3600)
        if allowed:
            user_obj = User.objects.filter(username__iexact=identifier, is_active=True).first()
            if not user_obj and '@' in identifier:
                user_obj = User.objects.filter(email__iexact=identifier, is_active=True).first()
            profile_obj = Profile.objects.filter(user=user_obj).first() if user_obj else None
            if profile_obj and profile_obj.is_verified and user_obj.email:
                raw_token, token_digest = _new_token()
                profile_obj.forgot_password_token = token_digest
                profile_obj.password_reset_sent_at = timezone.now()
                profile_obj.save(update_fields=[
                    'forgot_password_token', 'password_reset_sent_at', 'modified_at',
                ])
                send_forgot_password_mail(user_obj, raw_token)
        messages.success(request, 'If an eligible account matches, password-reset instructions have been sent.')
        return redirect('forgot_password')
    return render(request, 'forgot_password.html')


def change_password(request, token):
    profile_obj = Profile.objects.select_related('user').filter(
        forgot_password_token=_token_digest(token),
    ).first()
    if not profile_obj:
        messages.warning(request, 'Invalid or expired password reset link. Request a new one.')
        return redirect('forgot_password')
    if _profile_token_expired(profile_obj.password_reset_sent_at, settings.PASSWORD_RESET_TIMEOUT):
        _clear_token(profile_obj, 'forgot_password_token', 'password_reset_sent_at')
        messages.warning(request, 'This password reset link has expired. Request a new one.')
        return redirect('forgot_password')

    if request.method == 'POST':
        new_password = request.POST.get('password') or ''
        confirm_new_password = request.POST.get('confirm-password') or ''
        if new_password != confirm_new_password:
            messages.warning(request, 'Both passwords must be the same.')
            return redirect('change_password', token=token)
        if check_password(new_password, profile_obj.user.password):
            messages.warning(request, 'Choose a new password different from the old password.')
            return redirect('change_password', token=token)
        try:
            validate_password(new_password, profile_obj.user)
        except ValidationError as error:
            messages.warning(request, ' '.join(error.messages))
            return redirect('change_password', token=token)

        with transaction.atomic():
            profile_obj = Profile.objects.select_for_update().select_related('user').filter(
                pk=profile_obj.pk,
                forgot_password_token=_token_digest(token),
            ).first()
            if not profile_obj or _profile_token_expired(
                profile_obj.password_reset_sent_at,
                settings.PASSWORD_RESET_TIMEOUT,
            ):
                messages.warning(request, 'This password reset link has expired. Request a new one.')
                return redirect('forgot_password')
            profile_obj.user.set_password(new_password)
            profile_obj.user.save(update_fields=['password'])
            profile_obj.forgot_password_token = None
            profile_obj.password_reset_sent_at = None
            profile_obj.save(update_fields=[
                'forgot_password_token', 'password_reset_sent_at', 'modified_at',
            ])
        if request.user.is_authenticated and request.user.pk == profile_obj.user_id:
            update_session_auth_hash(request, profile_obj.user)
        messages.success(request, 'Your password has been changed. Log in now.')
        return redirect('login')

    return render(request, 'change_password.html')


def _home_context(option_selected=None):
    return {
        'time': '0.00',
        'time_playlist': '0.00',
        'length': 0,
        'videos': [],
        'next_videos': [],
        'suggestions': [],
        'option_selected': option_selected,
        'playlist_length': 0,
        'playlists': [],
        'search_query': '',
    }


def _cached_or_fetch(key, fetch, timeout):
    cached = cache.get(key)
    if cached is not None:
        return cached
    value = fetch()
    cache.set(key, value, timeout=timeout)
    return value


def home(request):
    search_query = (request.GET.get('search_query') or '').strip()[:200]
    option_selected = request.GET.get('find')
    context = _home_context(option_selected)
    context['search_query'] = search_query
    if not search_query:
        return render(request, 'index.html', context=context)
    if not _rate_limit(request, 'youtube-search', 60, 60):
        messages.error(request, 'Too many searches. Please try again shortly.')
        return render(request, 'index.html', context=context)
    if option_selected not in {'videos', 'playlist'}:
        option_selected = 'videos'
    context['option_selected'] = option_selected
    cache_key = hashlib.sha256(search_query.lower().encode()).hexdigest()

    if option_selected == 'playlist':
        start_time = time.monotonic()
        try:
            playlists = _cached_or_fetch(
                f'ytsearch:playlists:{cache_key}',
                lambda: YoutubePlaylistSearch(
                    search_query,
                    timeout=settings.YOUTUBE_TIMEOUT,
                    max_limit=settings.YOUTUBE_SEARCH_LIMIT,
                ).search_youtube_playlist(),
                settings.YOUTUBE_CACHE_SECONDS,
            )
        except Exception:
            logger.exception('YouTube playlist search failed for query %r', search_query)
            messages.error(request, 'Unable to fetch playlists right now. Please try again.')
            playlists = []
        context.update({
            'time_playlist': f'{time.monotonic() - start_time:.2f}',
            'playlist_length': len(playlists),
            'playlists': playlists,
        })
        return render(request, 'index.html', context=context)

    start_time = time.monotonic()
    try:
        def fetch_videos():
            search = YoutubeVideoSearch(
                search_query,
                max_limit=settings.YOUTUBE_SEARCH_LIMIT,
                timeout=settings.YOUTUBE_TIMEOUT,
            )
            first_page = search.search_youtube_videos()
            additional_pages = []
            for _ in range(settings.YOUTUBE_SEARCH_PAGES - 1):
                page = search.search_more_videos()
                if not page:
                    break
                additional_pages.extend(page)
            return first_page, additional_pages

        videos, next_videos = _cached_or_fetch(
            f'ytsearch:videos:{cache_key}',
            fetch_videos,
            settings.YOUTUBE_CACHE_SECONDS,
        )
    except Exception:
        logger.exception('YouTube video search failed for query %r', search_query)
        messages.error(request, 'Unable to fetch videos right now. Please try again.')
        videos, next_videos = [], []

    try:
        suggestions = _cached_or_fetch(
            f'ytsearch:suggestions:{cache_key}',
            lambda: search_video_suggestions(search_query, timeout=settings.YOUTUBE_TIMEOUT),
            settings.YOUTUBE_CACHE_SECONDS,
        )
    except Exception:
        logger.exception('YouTube suggestions lookup failed for query %r', search_query)
        suggestions = []
    context.update({
        'time': f'{time.monotonic() - start_time:.2f}',
        'length': len(videos) + len(next_videos),
        'videos': videos,
        'next_videos': next_videos,
        'suggestions': suggestions,
    })
    return render(request, 'index.html', context=context)


def watch_video(request):
    video_id = request.GET.get('video_id') or ''
    if not VIDEO_ID_RE.fullmatch(video_id):
        messages.error(request, 'That video link is invalid.')
        return redirect('home')
    try:
        video = get_video_detail(video_id, timeout=settings.YOUTUBE_TIMEOUT)
    except Exception:
        logger.exception('YouTube video lookup failed for %s', video_id)
        video = None
    if not video:
        messages.error(request, 'That video could not be found.')
        return redirect('home')

    try:
        comments = get_video_comments(video_id, limit=50)
    except Exception:
        logger.exception('YouTube comments lookup failed for %s', video_id)
        comments = []
        messages.warning(request, 'Comments are temporarily unavailable.')

    view_count = video.get('viewCount') or {}
    raw_views = str(view_count.get('text') or '0').replace(',', '')
    try:
        views = f'{int(raw_views):,} views'
    except ValueError:
        views = f'{view_count.get("text", "0")} views'
    description = video.get('description') or ''
    publish_date = video.get('publishDate') or video.get('uploadDate')
    try:
        formatted_datetime = parser.parse(publish_date).strftime('%d %B %Y') if publish_date else ''
    except (TypeError, ValueError, OverflowError):
        formatted_datetime = publish_date or ''
    return render(request, 'video.html', {
        'video': video,
        'comments': comments,
        'views': views,
        'description': urlize(description, autoescape=True),
        'publishedDate': formatted_datetime,
        'length': len(comments),
        'is_saved': request.user.is_authenticated and SavedVideos.objects.filter(
            user_profile=request.user,
            video_link=video.get('link') or f'https://www.youtube.com/watch?v={video_id}',
        ).exists(),
        'next_url': request.get_full_path(),
    })


@login_required
@require_POST
def save_video(request):
    video_id = request.POST.get('video_id') or ''
    if not VIDEO_ID_RE.fullmatch(video_id):
        messages.error(request, 'That video link is invalid.')
        return redirect('home')
    try:
        video = get_video_detail(video_id, timeout=settings.YOUTUBE_TIMEOUT)
    except Exception:
        logger.exception('YouTube video lookup failed while saving %s', video_id)
        video = None
    if not video:
        messages.error(request, 'That video could not be saved.')
        return redirect(_safe_next_url(request))

    video_link = video.get('link') or f'https://www.youtube.com/watch?v={video_id}'
    thumbnails = video.get('thumbnails') or []
    thumbnail = thumbnails[-1].get('url', '') if thumbnails and isinstance(thumbnails[-1], dict) else ''
    saved_video, created = SavedVideos.objects.get_or_create(
        user_profile=request.user,
        video_link=video_link,
        defaults={
            'video_title': video.get('title') or '',
            'video_desc': video.get('description') or '',
            'video_image': thumbnail,
            'video_views': str(video.get('viewCount', {}).get('text') or ''),
            'video_published_date': video.get('publishDate') or video.get('uploadDate') or '',
            'video_channel_name': (video.get('channel') or {}).get('name') or '',
        },
    )
    messages.success(request, 'Video saved.' if created else 'Video is already saved.')
    return redirect(_safe_next_url(request))


@login_required
def saved_videos(request):
    return render(request, 'saved_videos.html', {
        'saved_videos': SavedVideos.objects.filter(user_profile=request.user).order_by('-id'),
    })


@login_required
@require_POST
def remove_saved_video(request, video_pk):
    SavedVideos.objects.filter(pk=video_pk, user_profile=request.user).delete()
    messages.success(request, 'Video removed from saved videos.')
    return redirect('saved_videos')


@login_required
def playlist_videos(request):
    playlist_id = request.GET.get('list') or ''
    if not PLAYLIST_ID_RE.fullmatch(playlist_id):
        messages.error(request, 'That playlist link is invalid.')
        return redirect('home')
    start_time = time.monotonic()
    try:
        playlist = PlaylistVideos(
            playlist_id,
            max_pages=settings.YOUTUBE_PLAYLIST_PAGES,
            max_videos=settings.YOUTUBE_PLAYLIST_LIMIT,
            timeout=settings.YOUTUBE_TIMEOUT,
        )
        playlist_video = playlist.get_more_playlist_videos()
    except Exception:
        logger.exception('YouTube playlist lookup failed for %s', playlist_id)
        messages.error(request, 'Unable to fetch this playlist right now. Please try again.')
        playlist_video = []
    return render(request, 'playlist.html', {
        'time': f'{time.monotonic() - start_time:.2f}',
        'length': len(playlist_video),
        'playlists': playlist_video,
    })
