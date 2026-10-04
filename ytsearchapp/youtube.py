from youtubesearchpython import (
    Comments,
    CustomSearch,
    Playlist,
    PlaylistsSearch,
    Suggestions,
    VideoSortOrder,
    VideosSearch,
)
from youtubesearchpython.core.componenthandler import getVideoId
from youtubesearchpython.core.constants import ResultMode, playlistElementKey, videoElementKey
from youtubesearchpython.core.video import VideoCore


def _youtube_url(base_url, identifier):
    """Build a YouTube URL only when YouTube returned an identifier."""
    if not identifier:
        return None
    return f'{base_url}{identifier}'


class _SafeComponentMixin:
    """Work around missing channel metadata in youtube-search-python.

    YouTube occasionally returns a video or playlist without a channel
    ``browseId``.  youtube-search-python 1.6.6 concatenates that missing value
    with a string while parsing the response, which raises ``TypeError`` and
    prevents all results from being returned.
    """

    def _getVideoComponent(self, element: dict, shelfTitle: str = None) -> dict:
        video = element[videoElementKey]
        video_id = self._getValue(video, ['videoId'])
        channel_id = self._getValue(
            video,
            ['ownerText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId'],
        )
        component = {
            'type': 'video',
            'id': video_id,
            'title': self._getValue(video, ['title', 'runs', 0, 'text']),
            'publishedTime': self._getValue(video, ['publishedTimeText', 'simpleText']),
            'duration': self._getValue(video, ['lengthText', 'simpleText']),
            'viewCount': {
                'text': self._getValue(video, ['viewCountText', 'simpleText']),
                'short': self._getValue(video, ['shortViewCountText', 'simpleText']),
            },
            'thumbnails': self._getValue(video, ['thumbnail', 'thumbnails']),
            'richThumbnail': self._getValue(
                video,
                ['richThumbnail', 'movingThumbnailRenderer', 'movingThumbnailDetails', 'thumbnails', 0],
            ),
            'descriptionSnippet': self._getValue(
                video,
                ['detailedMetadataSnippets', 0, 'snippetText', 'runs'],
            ),
            'channel': {
                'name': self._getValue(video, ['ownerText', 'runs', 0, 'text']),
                'id': channel_id,
                'thumbnails': self._getValue(
                    video,
                    [
                        'channelThumbnailSupportedRenderers',
                        'channelThumbnailWithLinkRenderer',
                        'thumbnail',
                        'thumbnails',
                    ],
                ),
            },
            'accessibility': {
                'title': self._getValue(video, ['title', 'accessibility', 'accessibilityData', 'label']),
                'duration': self._getValue(video, ['lengthText', 'accessibility', 'accessibilityData', 'label']),
            },
        }
        component['link'] = _youtube_url('https://www.youtube.com/watch?v=', video_id)
        component['channel']['link'] = _youtube_url(
            'https://www.youtube.com/channel/',
            channel_id,
        )
        component['shelfTitle'] = shelfTitle
        return component

    def _getPlaylistComponent(self, element: dict) -> dict:
        playlist = element[playlistElementKey]
        playlist_id = self._getValue(playlist, ['playlistId'])
        channel_id = self._getValue(
            playlist,
            ['shortBylineText', 'runs', 0, 'navigationEndpoint', 'browseEndpoint', 'browseId'],
        )
        component = {
            'type': 'playlist',
            'id': playlist_id,
            'title': self._getValue(playlist, ['title', 'simpleText']),
            'videoCount': self._getValue(playlist, ['videoCount']),
            'channel': {
                'name': self._getValue(playlist, ['shortBylineText', 'runs', 0, 'text']),
                'id': channel_id,
            },
            'thumbnails': self._getValue(
                playlist,
                ['thumbnailRenderer', 'playlistVideoThumbnailRenderer', 'thumbnail', 'thumbnails'],
            ),
        }
        component['link'] = _youtube_url('https://www.youtube.com/playlist?list=', playlist_id)
        component['channel']['link'] = _youtube_url(
            'https://www.youtube.com/channel/',
            channel_id,
        )
        return component


class SafeVideosSearch(_SafeComponentMixin, VideosSearch):
    """Video search with nullable channel metadata support."""


class SafeCustomSearch(_SafeComponentMixin, CustomSearch):
    """Custom video search with nullable channel metadata support."""


class SafePlaylistsSearch(_SafeComponentMixin, PlaylistsSearch):
    """Playlist search with nullable channel metadata support."""


def _usable_results(results):
    """Return result dictionaries that contain the ID required by templates."""
    return [
        result
        for result in results
        if isinstance(result, dict) and result.get('id')
    ]

def recent_youtube_videos(query, max_limit=100, timeout=3):
    videos_search = SafeCustomSearch(
        query,
        VideoSortOrder.uploadDate,
        limit=min(max(1, max_limit), 100),
        timeout=timeout,
    )
    results = videos_search.result()
    return _usable_results(results.get("result", []))

class YoutubeVideoSearch:
    def __init__(self, query, max_limit=20, timeout=3):
        self.search = SafeVideosSearch(query, limit=min(max(1, max_limit), 100), timeout=timeout)

    def search_youtube_videos(self):
        return _usable_results(self.search.result().get("result", []))

    def search_more_videos(self):
        if not self.search.next():
            return []
        return self.search_youtube_videos()

class YoutubePlaylistSearch:
    def __init__(self, playlist, timeout=3, max_limit=20):
        self.playlistsSearch = SafePlaylistsSearch(
            playlist,
            limit=min(max(1, max_limit), 100),
            timeout=timeout,
        )
    
    def search_youtube_playlist(self):
        playlists = self.playlistsSearch.result()
        return _usable_results(playlists.get("result", []))

class PlaylistVideos:
    def __init__(self, query, max_pages=2, max_videos=100, timeout=3):
        self.playlist = Playlist(
            f'https://www.youtube.com/playlist?list={query}',
            timeout=timeout,
        )
        self.max_pages = min(max(0, max_pages), 10)
        self.max_videos = min(max(1, max_videos), 500)

    def get_playlist_videos(self):
        return list(self.playlist.videos[:self.max_videos])
    
    def get_more_playlist_videos(self):
        pages = 0
        while self.playlist.hasMoreVideos and pages < self.max_pages:
            self.playlist.getNextVideos()
            pages += 1
            if len(self.playlist.videos) >= self.max_videos:
                break
        return self.get_playlist_videos()


def _get_video_detail_component(source, requested_id):
    """Build video details without assuming YouTube returned every field."""
    source = source or {}
    details = source.get('videoDetails') or {}
    microformat = (source.get('microformat') or {}).get('playerMicroformatRenderer') or {}
    video_id = details.get('videoId') or requested_id
    if not video_id:
        return None

    channel_id = details.get('channelId')
    duration_seconds = details.get('lengthSeconds')
    component = {
        'id': video_id,
        'title': details.get('title'),
        'duration': {'secondsText': duration_seconds},
        'viewCount': {'text': details.get('viewCount')},
        'thumbnails': (details.get('thumbnail') or {}).get('thumbnails'),
        'description': details.get('shortDescription'),
        'channel': {
            'name': details.get('author'),
            'id': channel_id,
            'link': _youtube_url('https://www.youtube.com/channel/', channel_id),
        },
        'allowRatings': details.get('allowRatings'),
        'averageRating': details.get('averageRating'),
        'keywords': details.get('keywords'),
        'isLiveContent': details.get('isLiveContent'),
        'publishDate': microformat.get('publishDate'),
        'uploadDate': microformat.get('uploadDate'),
        'isFamilySafe': microformat.get('isFamilySafe'),
        'category': microformat.get('category'),
    }
    component['isLiveNow'] = bool(
        component['isLiveContent'] and duration_seconds == '0'
    )
    component['link'] = _youtube_url('https://www.youtube.com/watch?v=', video_id)
    return component


def get_video_detail(query, timeout=3):
    """Fetch video details while tolerating incomplete YouTube responses.

    ``youtube-search-python`` calls ``Video.getInfo`` and unconditionally
    concatenates ``videoDetails.videoId`` into a URL. YouTube sometimes omits
    that field (for example for restricted or changed player responses), so
    use the package's request layer and parse the response defensively here.
    """
    requested_id = getVideoId(query)
    if not requested_id:
        return None

    video_core = VideoCore(query, 'getInfo', ResultMode.dict, timeout, True)
    video_core.sync_html_create()
    source = getattr(video_core, 'HTMLresponseSource', {}) or {}
    playability_status = (source.get('playabilityStatus') or {}).get('status')
    if playability_status and playability_status != 'OK' and not source.get('videoDetails'):
        return None
    return _get_video_detail_component(source, requested_id)

def get_video_comments(video_id, limit=50):
    return Comments.get(video_id).get('result', [])[:min(max(1, limit), 100)]

def search_video_suggestions(query, timeout=3):
    suggestions = Suggestions(language='en', region='US', timeout=timeout)
    return suggestions.get(query).get('result', [])[:20]
