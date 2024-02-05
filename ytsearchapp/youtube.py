from youtubesearchpython import *

def recent_youtube_videos(query, max_limit=100):
    videos_search = CustomSearch(query, VideoSortOrder.uploadDate, limit=max_limit)
    results = videos_search.result()
    return results["result"]

class YoutubeVideoSearch:
    # constructor
    def __init__(self, query, max_limit=100):
        self.search = VideosSearch(query, limit=max_limit)

    def search_youtube_videos(self):
        return self.search.result()["result"]

    def search_more_videos(self):
        self.search.next()
        return self.search_youtube_videos()

class YoutubePlaylistSearch:
    def __init__(self, playlist):
        self.playlistsSearch = PlaylistsSearch(playlist)
    
    def search_youtube_playlist(self):
        playlists = self.playlistsSearch.result()
        return playlists["result"]

def get_playlist_videos(query):
    playlistVideos = Playlist.getVideos(query)
    return playlistVideos

def get_video_detail(query):
    videoInfo = Video.getInfo(query)
    return videoInfo

def get_video_comments(video_id):
    return Comments.get(video_id)['result']

def search_video_suggestions(query):
    suggestions = Suggestions(language='en', region='US')
    return suggestions.get(query)['result']