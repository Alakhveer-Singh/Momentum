# Quibus LMS — Django

Django 6 + DRF + SimpleJWT + Channels — the whole app. The UI is server-rendered with Django
templates (`templates/`, `static/`); mutations call the DRF `/api/...` endpoints. No SPA, no React.

## Stack (latest)

| Concern | Library |
|---|---|
| Framework | Django 6.0 |
| REST API | Django REST Framework 3.17 |
| JWT auth | djangorestframework-simplejwt 5.5 (`Authorization: Bearer <token>`) |
| Sessions | Django session framework (`SessionAuthentication` also enabled) |
| Database | MariaDB |
| DB driver | mysqlclient (C driver, built against MariaDB Connector) |
| WebSockets | Channels 4 + Daphne (ASGI), in-memory channel layer |
| PDF | reportlab |
| CORS | django-cors-headers |
| Admin (CMS) | Django Admin — customized site at `/admin/` for managing leads, stages, users, templates |

> `mysqlclient` is built against the MariaDB Connector/C bundled with the `mariadb` Homebrew
> formula. It registers itself as `MySQLdb`, so Django's `django.db.backends.mysql` uses it
> directly — no shim in `settings.py`.

## Setup

### 1. Database (MariaDB/MySQL)
```sql
CREATE DATABASE quibus_django CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. Python env
```bash
cd backend-django
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Adjust DB credentials in `quibus/settings.py` (`DATABASES`) if not root/empty-password.

### 3. Migrate + seed demo data
```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo      # 4 users, 12 leads, 36 activities, 12 tasks, 3 templates
```

### 4. Stylesheet (Tailwind via Node CLI)
```bash
npm install
npm run build:css     # static/css/app.css  (npm run watch:css to rebuild on change)
```

### 5. Run (ASGI server — serves UI + HTTP API + WebSockets on one port)
```bash
.venv/bin/daphne -p 8000 quibus.asgi:application
```

App: http://127.0.0.1:8000  ·  API: /api/  ·  WebSocket: ws://127.0.0.1:8000/ws/crm?token=<JWT>
Admin CMS: http://127.0.0.1:8000/admin/ (create a Django superuser with
`manage.py createsuperuser`, or log in via the seeded admin after granting staff).

The HTML UI authenticates with a Django **session** (login form posts to `/login`); the page mints a
short JWT only for the WebSocket connection. The DRF `/api` accepts both session (CSRF) and JWT.

## Demo accounts (password: `password`)
| Email | Role |
|---|---|
| admin@quibus.in | Admin |
| manager@quibus.in | Manager |
| anjali@quibus.in / vikram@quibus.in | Sales Rep |

## Realtime

- `broadcast_lead(lead, action)` → group `leads`, event `lead.updated`
- `notify_user(user, payload)` → persists a `Notification` row + pushes to group `user.<id>`, event `notification`

The consumer (`crm/consumers.py`) authenticates the socket from the `?token=` JWT and joins
both the `leads` group and the user's private group.

## Endpoints

Identical surface to the Laravel build — see [../API.md](../API.md). Differences:
- WebSocket transport is native Channels (single `ws/crm` socket) instead of Pusher channels.
- Soft-deleted leads use a `deleted_at` timestamp column (same as Laravel's SoftDeletes).

## Production notes
- Move `SECRET_KEY`, `DEBUG`, DB creds to environment variables (`.env.example` provided).
- Swap the in-memory channel layer for `channels-redis` so broadcasts work across processes.
- Run under Daphne/Uvicorn behind nginx; run `manage.py collectstatic` and serve `/static/` statically.
- Restrict `CORS_ALLOW_ALL_ORIGINS` / `ALLOWED_HOSTS`.
- Configure a real SMTP backend (`EMAIL_BACKEND`) — dev prints emails to the console.
