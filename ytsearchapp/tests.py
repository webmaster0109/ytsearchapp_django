from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Profile
from .views import home
from .youtube import PlaylistVideos, SafePlaylistsSearch, SafeVideosSearch


class SafeYouTubeComponentTests(SimpleTestCase):
    def test_video_without_channel_id_is_still_parsed(self):
        search = object.__new__(SafeVideosSearch)
        element = {
            'videoRenderer': {
                'videoId': 'video-id',
                'title': {'runs': [{'text': 'Example video'}]},
                'ownerText': {'runs': [{'text': 'Example channel'}]},
            }
        }

        result = search._getVideoComponent(element)

        self.assertEqual(result['id'], 'video-id')
        self.assertEqual(result['channel']['name'], 'Example channel')
        self.assertIsNone(result['channel']['id'])
        self.assertIsNone(result['channel']['link'])

    def test_video_with_channel_id_keeps_channel_link(self):
        search = object.__new__(SafeVideosSearch)
        element = {
            'videoRenderer': {
                'videoId': 'video-id',
                'title': {'runs': [{'text': 'Example video'}]},
                'ownerText': {
                    'runs': [{
                        'text': 'Example channel',
                        'navigationEndpoint': {
                            'browseEndpoint': {'browseId': 'channel-id'}
                        },
                    }]
                },
            }
        }

        result = search._getVideoComponent(element)

        self.assertEqual(result['channel']['link'], 'https://www.youtube.com/channel/channel-id')

    def test_playlist_without_channel_id_is_still_parsed(self):
        search = object.__new__(SafePlaylistsSearch)
        element = {
            'playlistRenderer': {
                'playlistId': 'playlist-id',
                'title': {'simpleText': 'Example playlist'},
                'shortBylineText': {'runs': [{'text': 'Example channel'}]},
            }
        }

        result = search._getPlaylistComponent(element)

        self.assertEqual(result['id'], 'playlist-id')
        self.assertIsNone(result['channel']['id'])
        self.assertIsNone(result['channel']['link'])


class HomeViewTests(SimpleTestCase):
    def test_home_without_query_does_not_call_youtube(self):
        request = RequestFactory().get('/')

        with patch('ytsearchapp.views.render') as render, \
                patch('ytsearchapp.views.YoutubeVideoSearch') as video_search, \
                patch('ytsearchapp.views.YoutubePlaylistSearch') as playlist_search:
            response = home(request)

        render.assert_called_once()
        video_search.assert_not_called()
        playlist_search.assert_not_called()
        context = render.call_args.kwargs['context']
        self.assertEqual(response, render.return_value)
        self.assertEqual(context['videos'], [])
        self.assertEqual(context['playlists'], [])
        self.assertEqual(context['length'], 0)

    @override_settings(YOUTUBE_SEARCH_PAGES=2, YOUTUBE_CACHE_SECONDS=0)
    def test_video_search_accumulates_distinct_pages(self):
        request = RequestFactory().get('/', {'search_query': 'django', 'find': 'videos'})
        search = type('SearchStub', (), {
            'search_youtube_videos': lambda self: [{'id': 'first'}],
            'search_more_videos': lambda self: [{'id': 'second'}],
        })()

        with patch('ytsearchapp.views.YoutubeVideoSearch', return_value=search), \
                patch('ytsearchapp.views.search_video_suggestions', return_value=[]), \
                patch('ytsearchapp.views.render') as render:
            home(request)

        context = render.call_args.kwargs['context']
        self.assertEqual(context['videos'], [{'id': 'first'}])
        self.assertEqual(context['next_videos'], [{'id': 'second'}])
        self.assertEqual(context['length'], 2)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SITE_URL='https://example.com',
)
class AccountFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_registration_stores_only_a_digest_and_verification_logs_in(self):
        captured = {}

        def capture_email(email, token):
            captured['email'] = email
            captured['token'] = token
            return True

        with patch('ytsearchapp.views.send_verification_mail', side_effect=capture_email):
            response = self.client.post(reverse('register'), {
                'first_name': 'Ada',
                'last_name': 'Lovelace',
                'email': 'ada@example.com',
                'password': 'A-valid-password-123!',
                'confirm_password': 'A-valid-password-123!',
            })

        self.assertRedirects(response, reverse('login'))
        user = User.objects.get(email='ada@example.com')
        profile = Profile.objects.get(user=user)
        self.assertNotEqual(profile.verification_token, captured['token'])
        self.assertEqual(len(profile.verification_token), 64)

        response = self.client.get(reverse('verify_account', args=[captured['token']]))

        self.assertRedirects(response, reverse('home'))
        self.assertTrue(Profile.objects.get(pk=profile.pk).is_verified)
        self.assertIsNone(Profile.objects.get(pk=profile.pk).verification_token)
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_invalid_next_cannot_redirect_to_another_host(self):
        user = User.objects.create_user(username='verified', password='A-valid-password-123!')
        Profile.objects.create(user=user, is_verified=True)

        response = self.client.post(reverse('login'), {
            'username': 'verified',
            'password': 'A-valid-password-123!',
            'next': 'https://evil.example/steal',
        })

        self.assertRedirects(response, reverse('home'))

    def test_password_reset_token_controls_the_target_user(self):
        owner = User.objects.create_user(
            username='owner', email='owner@example.com', password='Owner-old-123!'
        )
        Profile.objects.create(user=owner, is_verified=True)
        other = User.objects.create_user(
            username='other', email='other@example.com', password='Other-old-123!'
        )
        Profile.objects.create(user=other, is_verified=True)
        captured = {}

        def capture_reset(user, token):
            captured['token'] = token
            return True

        with patch('ytsearchapp.views.send_forgot_password_mail', side_effect=capture_reset):
            self.client.post(reverse('forgot_password'), {'identifier': 'owner'})

        response = self.client.post(
            reverse('change_password', args=[captured['token']]),
            {
                'password': 'Owner-new-123!',
                'confirm-password': 'Owner-new-123!',
                'user_id': str(other.pk),
            },
        )

        self.assertRedirects(response, reverse('login'))
        owner.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(owner.check_password('Owner-new-123!'))
        self.assertTrue(other.check_password('Other-old-123!'))

    def test_password_reset_is_generic_for_unknown_accounts(self):
        response = self.client.post(
            reverse('forgot_password'),
            {'identifier': 'missing'},
            follow=True,
        )

        self.assertNotContains(response, 'missing')


class PlaylistLimitTests(SimpleTestCase):
    def test_playlist_fetch_stops_at_configured_page_limit(self):
        playlist = object.__new__(PlaylistVideos)
        playlist.max_pages = 2
        playlist.max_videos = 3
        playlist.playlist = type('PlaylistStub', (), {
            'hasMoreVideos': True,
            'videos': [{'id': '1'}],
            'getNextVideos': lambda self: self.videos.extend([{'id': '2'}]),
        })()

        result = playlist.get_more_playlist_videos()

        self.assertEqual(result, [{'id': '1'}, {'id': '2'}, {'id': '2'}])


class SavedVideoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='saved-user', password='Saved-password-123!')
        Profile.objects.create(user=self.user, is_verified=True)
        self.other = User.objects.create_user(username='other-saved-user', password='Saved-password-123!')
        Profile.objects.create(user=self.other, is_verified=True)
        self.client.force_login(self.user)

    @patch('ytsearchapp.views.get_video_detail')
    def test_user_can_save_and_remove_only_their_video(self, get_video):
        get_video.return_value = {
            'id': 'video-id',
            'title': 'Saved title',
            'description': 'Saved description',
            'link': 'https://www.youtube.com/watch?v=video-id',
            'thumbnails': [{'url': 'https://img.example/video.jpg'}],
            'viewCount': {'text': '10'},
            'publishDate': '2024-01-01',
            'channel': {'name': 'Channel'},
        }

        response = self.client.post(reverse('save_video'), {
            'video_id': 'video-id',
            'next': reverse('home'),
        })

        self.assertRedirects(response, reverse('home'))
        self.assertEqual(self.user.saved_videos.count(), 1)
        saved = self.user.saved_videos.get()
        self.assertEqual(self.client.get(reverse('saved_videos')).status_code, 200)
        self.client.post(reverse('remove_saved_video', args=[saved.pk]))
        self.assertFalse(self.user.saved_videos.exists())

        other_saved = self.other.saved_videos.create(video_link='https://www.youtube.com/watch?v=other-id')
        self.client.post(reverse('remove_saved_video', args=[other_saved.pk]))
        self.assertTrue(self.other.saved_videos.filter(pk=other_saved.pk).exists())
