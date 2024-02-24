from django.shortcuts import render, get_object_or_404, redirect
import time
from .youtube import *
from dateutil import parser
from django.utils.safestring import mark_safe
from django.template.defaultfilters import urlize
from .models import Profile, SavedVideos, send_registration_email, send_forgot_password_mail, send_verification_mail
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
import uuid
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from datetime import timedelta
# Create your views here.

def login_attempt(request):
    if request.user.is_authenticated:
        return redirect(reverse('home'))
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user_obj = authenticate(request, username=username, password=password)
        if user_obj:
            profile_obj = Profile.objects.get(user=user_obj)
            if not profile_obj.is_verified:
                messages.warning(request, 'Your account is not verified. Please check your email for the verification link.')
                return redirect('login')

            login(request, user_obj)
            if 'next' in request.POST:
                return redirect(request.POST['next'])
            return redirect('home')
        else:
            messages.warning(request, 'Invalid username or password. Please try again.')
            return redirect('login')
    return render(request, template_name="login.html")

def register_attempt(request):
    if request.user.is_authenticated:
        return redirect(reverse('home'))
    if request.method == "POST":
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.warning(request, "Passwords do not match. Please enter matching passwords.")
            return redirect('register')

        try:
            username = str(email).split('@')[0]
            user_obj, created = User.objects.get_or_create(email=email, defaults={'first_name': first_name, 'last_name': last_name, 'username': username})
            user_obj.set_password(password)
            if not created:
                messages.warning(request, 'Email or username is already taken.')
                return redirect('register')
            user_obj.save()
            profile_obj = Profile.objects.create(user=user_obj, verification_token=str(uuid.uuid4()))
            profile_obj.save()
            send_verification_mail(request, email, profile_obj.verification_token)
            
        except Exception as e:
            print(e)
        
        # login(request, user_obj)
        # if 'next' in request.POST:
        #     return redirect(request.POST['next'])
        return redirect('login')
    
    return render(request, template_name="register.html")

def verify_account(request, token):
    try:
        profile_obj = Profile.objects.get(verification_token=token)
        if profile_obj.is_verified:
            messages.warning(request, "Your account is already verified.")
            return redirect('home')
        profile_obj.is_verified = True
        profile_obj.save()
        user_obj = profile_obj.user
        send_registration_email(user_obj)

        login(request, user_obj)
        if 'next' in request.POST:
            return redirect(request.POST['next'])
        return redirect('home')
    
    except Exception as e:
        print(e)
    # return render()

def signout(request):
    logout(request)
    return redirect("home")

def forgot_password(request):
    try:
        if request.method == "POST":
            username = request.POST.get('username')
            if not User.objects.filter(username=username).first():
                messages.warning(request, f"Sorry, There is no username of {username} exists. Register now!")
                return redirect('register')
            else:
                user_obj = User.objects.get(username=username)
                token = str(uuid.uuid4())
                profile_obj = Profile.objects.get(user=user_obj)
                profile_obj.forgot_password_token = token
                profile_obj.save()
                send_forgot_password_mail(request, user_obj, token)
                messages.success(request, f"We've sent you forgot password link on your {user_obj.email}")
                return redirect('forgot_password')

    except Exception as e:
        print(e)
    return render(request, template_name="forgot_password.html")

def change_password(request, token):
    try:
        profile_obj = Profile.objects.filter(forgot_password_token=token).first()
        if profile_obj and profile_obj.created_at + timedelta(hours=1) < timezone.now():
            # Token has expired, remove it from the database
            profile_obj.forgot_password_token = None
            profile_obj.save()
            messages.warning(request, "The password reset link has expired. Please request a new one.")
            return redirect('/auth/forgot-password')

        context = {'profile': profile_obj.user.id}
        if request.method == "POST":
            new_password = request.POST.get("password")
            confirm_new_password = request.POST.get("confirm-password")
            user_id = request.POST.get("user_id")

            if user_id is None:
                messages.warning(request, "Oops! No User ID found.")
                return redirect(f'/change-password/{token}')
            
            if new_password != confirm_new_password:
                messages.warning(request, "Both passwords must be same!")
                return redirect(f'/change-password/{token}')
            
            user_obj = User.objects.get(id=user_id)

            if check_password(new_password, user_obj.password):
                messages.warning(request, "You've chosen the old password. Please create a new and different one.")
                return redirect(f'/change-password/{token}')

            user_obj.set_password(new_password)
            user_obj.save()
            profile_obj.forgot_password_token = None
            profile_obj.save()
            messages.success(request, "Succesfully, Password has changed. Login now!")
            return redirect('/auth/login')
    except Exception as e:
        print(e)
    return render(request, template_name="change_password.html", context=context)

@login_required(login_url='/auth/login')
def home(request):
    option_selected = None
    if request.method == "GET":
        search_query = request.GET.get("search_query")
        option_selected = request.GET.get("find")

    start_time = time.time()
    video_class = YoutubeVideoSearch(search_query, max_limit=200)
    videos = video_class.search_youtube_videos()
    next_videos = []
    for _ in range(3):  # Fetch results from the next three pages
        next_videos = video_class.search_more_videos()
        next_videos.extend(next_videos)
    end_time = time.time()
    suggestions = search_video_suggestions(search_query)

    # playlist
    start_time_playlist = time.time()
    playlist_class = YoutubePlaylistSearch(search_query)
    playlist = playlist_class.search_youtube_playlist()
    end_time_playlist = time.time()

    if videos or playlist:
        elapsed_time_second = end_time - start_time
        video_length = len(videos + next_videos)
        videos_content = videos
        next_videos = next_videos

        elapsed_time_second_playlist = end_time_playlist - start_time_playlist
        elapsed_time_second_playlist = f'{elapsed_time_second_playlist:.2f}'
        playlist_length = len(playlist)
        playlist_content = playlist

    return render(
        request,
        "index.html",
        context={
            'time': f'{elapsed_time_second:.2f}',
            'time_playlist': elapsed_time_second_playlist,
            'length': video_length, 
            'videos': videos_content,
            'next_videos':next_videos,
            'suggestions': suggestions,
            'option_selected': option_selected,
            'playlist_length': playlist_length,
            'playlists': playlist_content
        })

@login_required(login_url='/auth/login')
def watch_video(request):

    video_id = request.GET.get('video_id')

    get_video = get_video_detail(video_id)

    get_comments = get_video_comments(video_id)

    if get_video:
        views_int = get_video['viewCount']['text']
        views = f'{int(views_int):,} views'

        description = get_video['description']
        safe_description = mark_safe(urlize(description))

        # Your input string
        datetime_str = get_video['publishDate']
        datetime_object = parser.parse(datetime_str)
        formatted_datetime = datetime_object.strftime("%d %B %Y")
    
    if get_comments:
        comment_length = len(get_comments)
        comments = get_comments

    return render(
        request,
        "video.html",
        context={
            'video': get_video,
            'comments': comments,
            'views': views,
            'description': safe_description,
            'publishedDate': formatted_datetime,
            'length': comment_length
        })

@login_required(login_url='/auth/login')
def playlist_videos(request):
    playlist_id = request.GET.get('list')
    start_time = time.time()
    playlist = PlaylistVideos(playlist_id)
    
    if playlist.get_more_playlist_videos() is None:
        playlist_video = playlist.get_playlist_videos()
    else:
        playlist_video = playlist.get_more_playlist_videos()

    videos_length = len(playlist_video)
    end_time = time.time()
    elapsed_time_seconds = end_time - start_time
    time_in_seconds = f'{elapsed_time_seconds:.2f}'

    playlist_videos = playlist_video if playlist_video else []

    return render(request, "playlist.html", context={
        'time': time_in_seconds,
        'length': videos_length,
        'playlists': playlist_videos
    })