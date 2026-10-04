import os
import secrets
from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Load simple KEY=VALUE pairs without requiring a third-party package."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value[:1] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / '.env')


def _env(name, default=None):
    return os.environ.get(name, default)


def _env_bool(name, default=False):
    value = _env(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise ImproperlyConfigured(f'{name} must be a boolean value.')


def _env_int(name, default):
    value = _env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ImproperlyConfigured(f'{name} must be an integer.') from error


def _env_list(name, default):
    value = _env(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(',') if item.strip()]


def _database_config():
    database_url = _env('DATABASE_URL')
    if not database_url:
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }

    parsed = urlsplit(database_url)
    if parsed.scheme in {'sqlite', 'sqlite3'}:
        name = unquote(parsed.path)
        if name == '/:memory:':
            name = ':memory:'
        elif parsed.netloc and name:
            name = f'//{parsed.netloc}{name}'
        if not name:
            raise ImproperlyConfigured('DATABASE_URL must include a SQLite database path.')
        return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': name}

    if parsed.scheme in {'postgres', 'postgresql'}:
        if not parsed.path.strip('/') or not parsed.hostname:
            raise ImproperlyConfigured('DATABASE_URL must include a PostgreSQL host and database name.')
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': unquote(parsed.path.lstrip('/')),
            'USER': unquote(parsed.username or ''),
            'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname,
            'PORT': str(parsed.port or ''),
        }

    raise ImproperlyConfigured('DATABASE_URL must use sqlite://, postgres://, or postgresql://.')


def _cache_config():
    cache_url = _env('CACHE_URL', 'locmemcache://ytsearch')
    parsed = urlsplit(cache_url)
    if parsed.scheme in {'locmemcache', 'locmem'}:
        location = (parsed.netloc + parsed.path).strip('/') or 'ytsearch'
        return {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': location,
        }
    if parsed.scheme == 'redis':
        return {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': cache_url,
        }
    if parsed.scheme == 'dummycache':
        return {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}
    raise ImproperlyConfigured('CACHE_URL must use locmemcache://, redis://, or dummycache://.')


DEBUG = _env_bool('DJANGO_DEBUG', default=False)
SECRET_KEY = _env('DJANGO_SECRET_KEY', default='')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY before starting the application.')
    SECRET_KEY = secrets.token_urlsafe(64)

ALLOWED_HOSTS = _env_list('DJANGO_ALLOWED_HOSTS', ['localhost', '127.0.0.1', '[::1]'])
if '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must list explicit hostnames.')
SITE_URL = (_env('SITE_URL', default='http://localhost:8000') or '').rstrip('/')
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
DATABASES = {'default': _database_config()}
DATABASES['default'].setdefault('OPTIONS', {})
if DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    DATABASES['default']['OPTIONS']['timeout'] = 20
CACHES = {'default': _cache_config()}

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

EMAIL_BACKEND = _env('EMAIL_BACKEND', default=(
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'
))
EMAIL_HOST = _env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = _env_int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = _env_bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = _env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = _env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = _env('DEFAULT_FROM_EMAIL', default='noreply@localhost')
EMAIL_TIMEOUT = 5
if not DEBUG and EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD or DEFAULT_FROM_EMAIL.endswith('@localhost'):
        raise ImproperlyConfigured(
            'Configure EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, and a real DEFAULT_FROM_EMAIL in production.'
        )

SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', default=not DEBUG)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = _env_int('SECURE_HSTS_SECONDS', default=0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=not DEBUG)
SECURE_HSTS_PRELOAD = _env_bool('SECURE_HSTS_PRELOAD', default=not DEBUG)
SECURE_REFERRER_POLICY = 'no-referrer'
if _env_bool('TRUST_PROXY_HTTPS', default=False):
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
