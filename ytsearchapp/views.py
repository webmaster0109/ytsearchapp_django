from django.shortcuts import render, get_object_or_404, redirect
import time
from .youtube import *
from dateutil import parser
from django.utils.safestring import mark_safe
from django.template.defaultfilters import urlize
# Create your views here.

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

def playlist_videos(request):

    playlist_id = request.GET.get('list')
    start_time = time.time()
    playlist_link = f'https://www.youtube.com/playlist?list={playlist_id}'
    playlist_video = get_playlist_videos(playlist_link)['videos']
    end_time = time.time()

    if playlist_video:
        elapsed_time_seconds = end_time - start_time
        videos_length = len(playlist_video)
        playlist_videos = playlist_video

    return render(request, "playlist.html", context={
        'time': f'{elapsed_time_seconds:.2f}',
        'length': videos_length,
        'playlists': playlist_videos
    })