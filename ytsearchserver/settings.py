from pathlib import Path
import secrets
from urllib.parse import urlsplit

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

DEBUG = env.bool('DJANGO_DEBUG', default=False)
SECRET_KEY = env('DJANGO_SECRET_KEY', default='')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY before starting the application.')
    SECRET_KEY = secrets.token_urlsafe(64)

ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['localhost', '127.0.0.1', '[::1]'])
if '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must list explicit hostnames.')
SITE_URL = env('SITE_URL', default='http://localhost:8000').rstrip('/')
site = urlsplit(SITE_URL)
if (site.scheme not in {'http', 'https'} or not site.netloc or site.path
        or site.query or site.fragment or site.username or site.password):
    raise ImproperlyConfigured('SITE_URL must be an absolute HTTP(S) origin without a path.')
if not DEBUG and site.scheme != 'https':
    raise ImproperlyConfigured('Use an HTTPS SITE_URL in production.')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'ytsearchapp.apps.YtsearchappConfig',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'ytsearchserver.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'ytsearchserver.wsgi.application'
ASGI_APPLICATION = 'ytsearchserver.asgi.application'
DATABASES = {'default': env.db_url('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')}
DATABASES['default'].setdefault('OPTIONS', {})
if DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    DATABASES['default']['OPTIONS']['timeout'] = 20

CACHES = {'default': env.cache_url('CACHE_URL', default='locmemcache://ytsearch')}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LOGIN_URL = 'login'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

EMAIL_BACKEND = env('EMAIL_BACKEND', default=(
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'
))
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@localhost')
EMAIL_TIMEOUT = 5
if not DEBUG and EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD or DEFAULT_FROM_EMAIL.endswith('@localhost'):
        raise ImproperlyConfigured(
            'Configure EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, and a real DEFAULT_FROM_EMAIL in production.'
        )

SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=not DEBUG)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=not DEBUG)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=not DEBUG)
SECURE_REFERRER_POLICY = 'no-referrer'
# Only enable this behind a proxy that strips and sets this header itself.
if env.bool('TRUST_PROXY_HTTPS', default=False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

VERIFICATION_TOKEN_TIMEOUT = 86400
PASSWORD_RESET_TIMEOUT = 600
YOUTUBE_TIMEOUT = 3
YOUTUBE_SEARCH_LIMIT = 20
YOUTUBE_SEARCH_PAGES = 2
YOUTUBE_PLAYLIST_PAGES = 2
YOUTUBE_PLAYLIST_LIMIT = 100
YOUTUBE_CACHE_SECONDS = 300
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'ytsearchapp': {'handlers': ['console'], 'level': 'INFO', 'propagate': False}},
}
