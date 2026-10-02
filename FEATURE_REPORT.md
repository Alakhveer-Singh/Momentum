# Quibus LMS — Feature Report (As-Built)

Verified against source on 2026-06-19. Describes what is **actually implemented** in the code (vs the aspirational roadmap in `FEATURES.md`). Reflects recent changes: Reports merged into Dashboard, Email Templates feature removed.

A lead-management / CRM for an education business (telecallers → managers → admins). Django + DRF + Channels, server-rendered Tailwind templates, MariaDB, served via Daphne (ASGI). Currency INR, timezone Asia/Kolkata.

---

## 1. Roles & Access Control
Three roles (`crm.User.role`):

| Role | Internal value | Scope |
|------|----------------|-------|
| Admin | `admin` | Everything incl. SuperAdmin Masters + Team & Roles |
| Manager | `manager` | All leads, full analytics, team performance |
| Telecaller | `rep` | Only own leads/tasks; restricted views |

- Per-role lead scoping (`_lead_scope`): reps see only leads they own.
- Admin-only: SuperAdmin Masters group, Team & Roles.
- Manager-or-admin: delete leads, assign/reassign owners.

## 2. Authentication & Security
- Login by **email + password**; JWT (`simplejwt`) + Django session auth for the web UI.
- Account deactivation → suspended message with Super Admin contact (email + phone).
- **Login audit log** (`LoginActivity`): email, IP, user-agent, success/failure + reason, indexed by user/email.
- Admin password reset for any user.
- JWT refresh + logout endpoints.

## 3. Navigation (tiered sidebar)
```
Dashboard
Leads
Pipeline
Follow-ups
Students
──────────────  divider
SuperAdmin Masters ▸   (admin)  — Lead Funnel · Source Master · Products & Services · Customer Profile
Product Leads ▸
Team & Roles           (admin)
```

## 4. Pages & Features

### Dashboard (`/`)
- KPI cards: open leads, conversion rate, won count, new-this-week, avg lead score, pending & overdue follow-ups.
- Upcoming tasks (5) + recent activity (8), role-scoped.
- **Analytics (merged from former Reports page):** pipeline by stage (count+value), 6-month lead-volume trend (new vs won), Lead Source ROI table (manager/admin), Team performance (manager/admin), Pipeline PDF export.
- Live auto-refresh on `lead-updated` websocket events. `/reports` redirects here.

### Pipeline (`/pipeline`)
- Kanban, one column per **configurable** stage; per-stage count + total value; 50 cards/column sorted by recent activity; drag-to-change stage (logged as activity).

### Leads (`/leads`)
- Paginated (configurable page size, elided range).
- Filters: text search (name/email), multi-source, date range, product, tab (unread / stage). "Unread" = zero activities, with live count.
- Bulk assign-owner, bulk soft-delete. CSV import + streaming CSV export.
- **Lead detail** (`/leads/<id>`): contact, stage changer, owner assign, activity timeline, tasks, custom fields, student profile, photo upload, soft delete.
- Soft delete only (`deleted_at`); no hard delete from UI.

### Lead Scoring (0–100, auto)
Source-quality weight + stage-progression weight + engagement (meeting 8 / call 5 / email 3 / note 1, capped 30) + profile completeness (email/phone +1 each) + value present (+2). Recalculated on activity/stage change.

### Activities
Per-lead timeline. Types: call, email, meeting, note, stage_change, task, system. Feeds scoring and `last_activity_at`.

### Follow-ups / Tasks (`/tasks`)
Lead-linked tasks; priority (low/med/high), status (pending/completed), due date. Filters: pending/overdue/completed/all. Reps see own; managers/admins assign. Dashboard shows pending + overdue.

### Students (`/students`)
Student-oriented view over leads using profile fields in `Lead.custom_fields` (gender, dob, whatsapp, education, qualification, guardian details, addresses, batch time/number/start).

### Product Leads (`/product-leads`, `/product-leads/<id>`)
Leads grouped/filtered by Product or Service; active products shown as sidebar quick-filters.

### SuperAdmin Masters (admin)
- **Lead Funnel** (`/funnel`) — funnel/stage view.
- **Source Master** (`/sources`) — sources CRUD + reorder.
- **Products & Services** (`/products`) — CRUD, kind (product/service), active flag, ordering.
- **Customer Profile** (`/masters/profiles`) — profile master CRUD + ordering.
- **Pipeline stages** (API) — create/reorder/edit/delete, color, type (entry/middle/won/lost), won/lost flags.
- **Custom field definitions** — text/number/date/select/boolean.

### Team & Roles (`/users`, admin)
User CRUD, activate/deactivate, role assignment, password reset.

### Profile (`/profile`)
Self profile (name, email, phone, password).

## 5. Real-time (WebSockets)
Django Channels over ASGI; endpoint `ws/crm` (`CrmConsumer`). In-memory channel layer. Groups: `leads` (board/list updates) + `user.<id>` (private notifications). `broadcast_lead()` pushes create/update/activity; UI auto-refreshes.

### Notifications
Persistent `Notification` rows + live push to user's private channel. Endpoints: list, mark-read.

## 6. Reports & Exports
- Web analytics live on the Dashboard.
- Exports: Leads CSV (streaming), Pipeline PDF.
- JSON report API: `reports/dashboard`, `reports/pipeline`, `reports/sources`, `reports/team`, `reports/trend`.

## 7. Public Lead Intake
`POST /api/public/leads` — unauthenticated capture (web forms); requires `first_name` + `email`.

## 8. REST API Surface (`/api/…`)
- Auth: login, me, refresh, logout, profile.
- Router resources: leads, activities, tasks, users.
- Leads extras: import, per-lead profile update, bulk-assign, bulk-delete.
- Config: stages (+reorder/create/update/delete), custom-fields, sources, products, profiles.
- Reports: dashboard/pipeline/sources/team/trend. Exports: leads.csv, pipeline.pdf. Notifications: list, read. Admin: user password reset.

## 9. Data Model
`User`, `PipelineStage`, `LeadSource`, `Product`, `CustomerProfile`, `CustomFieldDefinition`, `Lead` (soft-delete, photo, custom_fields JSON, score, value), `Activity`, `Task`, `Notification`, `LoginActivity`.

## 10. Tech Stack
Django + DRF + Channels + SimpleJWT · Daphne ASGI (:8000) · MariaDB 12.3 `quibus_django` (:3306) · Django templates + Tailwind (prebuilt/purged `app.css`) + Lucide icons · INR / Asia-Kolkata.

---

## Discrepancies vs `FEATURES.md` (old roadmap)
- **Email Templates** — listed there as done; **removed** from the app. `Lead.email`/`User.email` and the `email` activity type retained.
- **Reports** — now merged into the Dashboard, not a separate page.
- **Roles** — actual values are `admin` / `manager` / `rep` (Telecaller); old doc says `sales_rep`.
- **Custom pipeline stages** — old doc marks "Custom stage creation" as not-done; the stages API supports create/reorder/edit/delete.
- **Login attempt tracking** — old doc marks not-done; `LoginActivity` audit log exists.
