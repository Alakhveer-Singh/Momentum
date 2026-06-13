# Quibus LMS — Django Backend

Django 6 + DRF + SimpleJWT + Channels backend for Quibus LMS. API-compatible with the
React frontend in `../frontend` (same `/api/...` routes and JSON shapes as the Laravel build).

## Stack (latest)

| Concern | Library |
|---|---|
| Framework | Django 6.0 |
| REST API | Django REST Framework 3.17 |
| JWT auth | djangorestframework-simplejwt 5.5 (`Authorization: Bearer <token>`) |
| Sessions | Django session framework (`SessionAuthentication` also enabled) |
| DB driver | PyMySQL 1.2 (pure-Python MariaDB/MySQL driver — no C build needed) |
| WebSockets | Channels 4 + Daphne (ASGI), in-memory channel layer |
| PDF | reportlab |
| CORS | django-cors-headers |
| Admin (CMS) | Django Admin — customized site at `/admin/` for managing leads, stages, users, templates |

> `mysqlclient` needs `pkg-config` + MariaDB C headers, which aren't present here, so the
> pure-Python **PyMySQL** driver is used via `pymysql.install_as_MySQLdb()` in `settings.py`.

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

### 4. Run (ASGI server — serves HTTP API + WebSockets on one port)
```bash
.venv/bin/daphne -p 8000 quibus.asgi:application
```

API: http://127.0.0.1:8000/api/  ·  WebSocket: ws://127.0.0.1:8000/ws/crm?token=<JWT>
Admin CMS: http://127.0.0.1:8000/admin/ (create a Django superuser with
`manage.py createsuperuser`, or log in via the seeded admin after granting staff).

### 5. Frontend
```bash
cd ../frontend && npm install && npm run dev
```
Vite proxies `/api` → `:8000`. The frontend's WebSocket client (`src/echo.js`) connects to
`ws://<host>:8000/ws/crm` with the JWT — no Pusher/Reverb needed.

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
- Run under Daphne/Uvicorn behind nginx; serve the built frontend (`npm run build`) statically.
- Restrict `CORS_ALLOW_ALL_ORIGINS` / `ALLOWED_HOSTS`.
- Configure a real SMTP backend (`EMAIL_BACKEND`) — dev prints emails to the console.
