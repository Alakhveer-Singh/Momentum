# Quibus LMS — API Reference

Base URL: `http://localhost:8000/api`

Authentication: `Authorization: Bearer <JWT>` header on all endpoints except the public ones. Obtain a token via `POST /auth/login`. Tokens expire after 60 minutes; refresh via `POST /auth/refresh`.

Roles: **admin** > **manager** > **rep**. Reps only see/modify their own leads and tasks.

## Public

| Method | Endpoint | Description |
|---|---|---|
| POST | `/public/leads` | Web-form lead intake. Body: `first_name`*, `email`*, `last_name`, `phone`, `company`, `message`. Rate limit 10/min/IP. |
| POST | `/auth/login` | Body: `email`, `password`. Returns `access_token`, `expires_in`, `user`. Rate limit 10/min. |

## Auth

| Method | Endpoint | Description |
|---|---|---|
| GET | `/auth/me` | Current user |
| POST | `/auth/refresh` | New token |
| POST | `/auth/logout` | Invalidate token |
| PUT | `/auth/profile` | Update `name`, `phone`; change password with `password` + `password_confirmation` + `current_password` |

## Reference Data

| Method | Endpoint | Description |
|---|---|---|
| GET | `/stages` | Pipeline stages (ordered) |
| GET | `/custom-fields` | Custom field definitions |

## Leads

| Method | Endpoint | Description |
|---|---|---|
| GET | `/leads` | Paginated. Query: `search`, `stage_id`, `source`, `owner_id`, `sort` (created_at/score/value/last_activity_at), `direction`, `per_page`, `page`, `all=1` (no pagination) |
| POST | `/leads` | Create. `first_name`* plus optional `last_name`, `email`, `phone`, `company`, `job_title`, `source`, `stage_id`, `owner_id`, `value`, `notes`, `custom_fields` (object) |
| GET | `/leads/{id}` | Full profile with activities + tasks |
| PUT | `/leads/{id}` | Update any creatable field. Changing `stage_id` auto-logs a stage_change activity and sets `converted_at` on Won |
| DELETE | `/leads/{id}` | Soft delete (manager/admin only) |
| POST | `/leads-import` | Bulk import. Body: `leads: [{first_name*, email, …}, …]` (max 1000) |

Lead score is computed server-side (source weight + stage weight + engagement + profile completeness, capped 100) and recalculated on every relevant change.

## Activities

| Method | Endpoint | Description |
|---|---|---|
| GET | `/activities` | Paginated. Query: `lead_id`, `type`, `per_page` |
| POST | `/activities` | `lead_id`*, `type`* (call/email/meeting/note), `subject`*, `description`, `occurred_at` |
| DELETE | `/activities/{id}` | Own activity, or manager/admin |

## Tasks

| Method | Endpoint | Description |
|---|---|---|
| GET | `/tasks` | Paginated. Query: `status` (pending/completed), `overdue=1`, `lead_id`, `assigned_to` |
| POST | `/tasks` | `title`*, `assigned_to`*, `lead_id`, `description`, `priority` (low/medium/high), `due_at`. Assignee gets a real-time notification |
| PUT | `/tasks/{id}` | Update; `status: completed` stamps `completed_at` |
| DELETE | `/tasks/{id}` | Creator or manager/admin |

## Email Templates & Sending

| Method | Endpoint | Description |
|---|---|---|
| GET | `/email-templates` | List |
| POST | `/email-templates` | `name`*, `subject`*, `body`*. Placeholders: `{{first_name}}`, `{{last_name}}`, `{{full_name}}`, `{{company}}`, `{{email}}` |
| PUT | `/email-templates/{id}` | Update |
| DELETE | `/email-templates/{id}` | Delete |
| POST | `/emails/send` | `template_id`*, `lead_ids`* (array, max 200). Sends via configured mailer, logs an email activity per lead |

## Reports

| Method | Endpoint | Description |
|---|---|---|
| GET | `/reports/dashboard` | KPI block: totals, conversion rate, pipeline/won value, pending/overdue tasks |
| GET | `/reports/pipeline` | Per-stage lead count + value |
| GET | `/reports/sources` | Source ROI: totals, won, conversion %, won value *(manager/admin)* |
| GET | `/reports/team` | Per-user performance *(manager/admin)* |
| GET | `/reports/trend` | Monthly lead volume + wins, last 6 months |

## Exports

| Method | Endpoint | Description |
|---|---|---|
| GET | `/exports/leads.csv` | CSV stream. Query: `stage_id` |
| GET | `/exports/pipeline.pdf` | PDF pipeline report |

## Notifications

| Method | Endpoint | Description |
|---|---|---|
| GET | `/notifications` | Latest 50 + unread count |
| POST | `/notifications/read` | Mark one (`id`) or all read |

## Users (admin only)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/users` | List with lead/task counts |
| POST | `/users` | `name`*, `email`*, `password`* (min 8), `role`* (admin/manager/rep), `phone` |
| PUT | `/users/{id}` | Update incl. `is_active`. Guards against demoting/deactivating the last admin |
| DELETE | `/users/{id}` | Guards: not self, not last admin |

## WebSockets (Laravel Reverb)

Auth endpoint: `POST /api/broadcasting/auth` (Bearer token).

| Channel | Event | Payload |
|---|---|---|
| `private-leads` | `lead.updated` | `{action: created\|updated\|deleted\|activity, lead: {id, full_name, company, stage_id, stage, score, owner_id}}` |
| `private-App.Models.User.{id}` | Laravel notification | Task assignment payloads |

## Error Format

Validation errors: HTTP 422 `{"message": "...", "errors": {field: [msgs]}}`. Auth failures: 401. Permission: 403.
