# Quibus LMS — Lead Management & CRM

Professional lead management system: pipeline kanban, lead scoring, activity tracking, tasks, email templates, reports, role-based access, and real-time notifications.

**One stack: Django + Python + MariaDB.** The UI is server-rendered with Django templates
(no SPA framework — no React). Realtime runs over native Django Channels WebSockets. Everything
is served by Django on a single port.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 / Django 6 + Django REST Framework |
| UI | Django templates (server-rendered) + vanilla JS |
| Styling | Tailwind CSS 4 (compiled via Node CLI to a static stylesheet) |
| Icons | Lucide (CDN) |
| Database | MariaDB |
| DB driver | mysqlclient (C driver, built against MariaDB Connector) |
| Auth | Django sessions (HTML UI) + JWT (`djangorestframework-simplejwt`, API & WS) |
| Real-time | Django Channels + Daphne (native WebSockets) |
| PDF | reportlab |
| Admin CMS | Django Admin at `/admin/` |

> The pages render server-side from the ORM; mutations (drag-drop, forms, inline edits) call the
> existing DRF `/api` endpoints via `fetch` (session auth + CSRF). No JS build step is required to
> run the app — only Tailwind needs Node to compile the stylesheet.

## Features

- **Lead intake**: public web-form endpoint (rate-limited), manual entry, bulk CSV import
- **Pipeline kanban**: drag-and-drop across New → Contacted → Qualified → Negotiating → Won/Lost
- **Contact profiles**: full details, custom fields (JSON), notes, deal value
- **Activity tracking**: calls, emails, meetings, notes + automatic system/stage-change logs
- **Lead scoring (0–100)**: source quality + stage progression + engagement + profile completeness
- **Tasks**: priorities, due dates, assignment, overdue tracking, broadcast notification on assignment
- **Email templates**: placeholder rendering (`{{first_name}}` etc.), single & bulk send, logged as activities
- **Reports**: dashboard KPIs, pipeline by stage, lead source ROI, team performance, 6-month trend
- **Roles**: admin (everything), manager (all leads + reports), rep (own leads/tasks only)
- **Real-time**: lead updates + notifications over WebSockets, browser Notification API
- **Exports**: leads CSV, pipeline PDF
- **Responsive**: mobile sidebar, adaptive tables/cards

## Local Setup

### Prerequisites
Python ≥ 3.11, MariaDB running locally, Node ≥ 20 (only to compile the Tailwind stylesheet).

### 1. Database (MariaDB on :3306)
```sql
CREATE DATABASE quibus_django CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
Load timezone tables (needed for the trend report):
```bash
mariadb-tzinfo-to-sql /usr/share/zoneinfo | mariadb -uroot mysql
```

### 2. Backend
```bash
cd backend-django
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # includes mysqlclient
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo         # 4 users, 12 leads, 36 activities, 12 tasks, 3 templates
```
Adjust DB credentials in `quibus/settings.py` (`DATABASES`) if not root/empty-password.

### 3. Stylesheet (Tailwind via Node)
```bash
npm install
npm run build:css        # writes static/css/app.css   (npm run watch:css to rebuild on change)
```

### 4. Run (ASGI — serves the UI, API, and WebSockets on one port)
```bash
.venv/bin/daphne -p 8000 quibus.asgi:application
```

Open **http://localhost:8000**

### Demo accounts (password: `password`)
| Email | Role |
|---|---|
| admin@quibus.in | Admin |
| manager@quibus.in | Manager |
| anjali@quibus.in / vikram@quibus.in | Sales Rep |

Admin CMS: http://localhost:8000/admin/

## Production Notes
- Move `SECRET_KEY`, `DEBUG`, and DB creds to environment variables.
- Run `manage.py collectstatic` and serve `/static/` via nginx (or WhiteNoise); proxy everything else to Daphne/Uvicorn.
- Swap the in-memory channel layer for `channels-redis` so broadcasts work across processes.
- Restrict `ALLOWED_HOSTS`.
- Configure a real SMTP `EMAIL_BACKEND` (dev prints emails to the console).

See [API.md](API.md) for endpoint documentation and [backend-django/README.md](backend-django/README.md) for backend details.
