# YouTube Search App

A server-rendered Django application for public video/playlist search, embedded playback,
email-verified accounts, password recovery, and private saved videos.

## Local development

Use Python 3.12–3.14 and Django 5.2 LTS.

```sh
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Generate a `DJANGO_SECRET_KEY` and put it in `.env` for stable development sessions.
Development emails print to the console. The verification link opens a confirmation page;
click **Verify account**, then log in. Use **Resend verification** if delivery failed or a link expired.

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

## Production

Set `DJANGO_DEBUG=False`, a new random `DJANGO_SECRET_KEY`, explicit
`DJANGO_ALLOWED_HOSTS`, and a canonical HTTPS `SITE_URL`. Email links always use
`SITE_URL`, never the incoming Host header. Configure the SMTP backend, credentials,
and `DEFAULT_FROM_EMAIL` through environment variables. `DATABASE_URL` can override
the SQLite development database; install the appropriate database driver if using PostgreSQL.

Set `CACHE_URL=redis://...` for shared, atomic rate limits and cached YouTube results
across workers. The in-memory development cache is per-process. Behind a trusted TLS
terminating proxy, set `TRUST_PROXY_HTTPS=True` only if the proxy strips and replaces
`X-Forwarded-Proto`. Configure the proxy to set the client `REMOTE_ADDR` correctly;
untrusted forwarded-IP headers are deliberately ignored by the rate limiter.

```sh
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy --fail-level WARNING
gunicorn ytsearchserver.wsgi:application
```

Serve `STATIC_ROOT` through the web server and serve uploaded media separately without
script execution. The repository does not track databases, uploads, collected static files,
virtual environments, or bytecode. Existing local copies are preserved.

For an existing clone, `.gitignore` does not untrack files that were committed
previously. Before the next commit, remove generated/local artifacts from the
Git index while preserving local copies:

```sh
git rm --cached db.sqlite3
git rm -r --cached staticfiles
```

## Security migration

Previously committed SMTP credentials must be revoked at the provider, and the old
Django secret must be replaced. Removing them from the current files cannot revoke them
or remove historical Git copies. Previously tracked databases and sessions should be
treated as exposed; invalidate deployed sessions as part of rollout.

The account-security migration invalidates legacy plaintext verification/reset tokens.
Users can request new links. New tokens are random, hashed in the database, expire, and
are consumed once. Password changes derive the user exclusively from the validated token.

## YouTube integration

`youtube-search-python` uses YouTube's unofficial endpoints. The adapter preserves the
missing-channel-metadata workaround and supplies bounded timeouts with the HTTPX version
compatible with that library.
Search fetches at most two pages, playlist viewing at most two pages/100 videos, and
comments only the first page. Responses are cached for five minutes; upstream failures
produce a retry message instead of a server error. Live upstream availability is separate
from the mocked regression tests.
