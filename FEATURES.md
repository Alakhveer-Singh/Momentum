# Quibus LMS - Feature List

## Authentication & Access
- [x] JWT login/logout
- [x] Role-based access control (admin, manager, sales_rep)
- [x] Password hashing (PBKDF2)
- [x] 60-minute token lifetime
- [ ] Refresh token rotation
- [ ] Two-factor authentication
- [ ] SAML/OAuth integration

## Lead Management
- [x] Create leads (web form, import, manual)
- [x] Full lead profile (contact, company, deal value, custom fields)
- [x] Search by name, email, company
- [x] Filter by stage, source, owner
- [x] Soft-delete (preserve audit trail)
- [x] Lead scoring (0-100 auto-calculated)
- [x] CSV import (bulk add leads)
- [x] CSV export (all leads)
- [ ] Lead deduplication detection
- [ ] Merge duplicate leads
- [ ] Lead lifecycle history

## Pipeline & Kanban
- [x] Six fixed stages (New, Contacted, Qualified, Negotiating, Won, Lost)
- [x] Kanban board visualization
- [x] Drag-drop stage transitions
- [x] Optimistic UI updates
- [x] Stage-change activity logging
- [x] Pipeline value by stage (chart)
- [ ] Custom stage creation
- [ ] Stage templates
- [ ] WIP limits per stage

## Activity Tracking
- [x] Log calls, emails, meetings, notes
- [x] Auto-log stage changes
- [x] Auto-log task completions
- [x] Activity timeline per lead
- [x] Recent activity feed (dashboard)
- [x] Activity filtering (by lead, user, type)
- [ ] Activity attachments (files, images)
- [ ] @mention notifications in activities

## Task Management
- [x] Create, edit, delete tasks
- [x] Assign to users
- [x] Priority levels (high, medium, low)
- [x] Due dates (optional)
- [x] Status tracking (pending, completed)
- [x] Dashboard upcoming tasks widget
- [x] Overdue task alerts
- [ ] Recurring tasks
- [ ] Subtasks
- [ ] Task dependencies
- [ ] Email reminders

## Email Templates & Communication
- [x] Create reusable email templates
- [x] Placeholder support ({{first_name}}, {{company}}, etc.)
- [x] Edit/delete templates
- [x] Bulk send emails (1-100 leads per batch)
- [x] Activity logging per send
- [x] Template preview
- [ ] HTML email support
- [ ] Email send scheduling
- [ ] Delivery tracking / open rates
- [ ] Template versioning
- [ ] A/B testing templates

## Reporting & Analytics
- [x] Dashboard KPIs (8 metrics)
  - Open leads, Pipeline value, Conversion rate, Won value
  - New this week, Avg lead score, Pending tasks, Overdue tasks
- [x] Pipeline by stage (bar chart with counts & values)
- [x] 6-month trend (new leads vs won, dual-bar chart)
- [x] Lead source ROI (manager-only: leads, won, conversion %, value)
- [x] Team performance (manager-only: conversion %, activities/30d, won value)
- [x] PDF export (pipeline report)
- [ ] Custom date range picker
- [ ] Drill-down into stage leads
- [ ] Historical snapshots (point-in-time comparison)
- [ ] Predictive analytics (win probability, pipeline forecast)
- [ ] Custom reports builder

## User Management
- [x] Create users (admin only)
- [x] Edit user details (name, email, role, phone, active status)
- [x] Delete users
- [x] Role assignment (admin, manager, sales_rep)
- [x] Password hashing on create/update
- [ ] User preferences (language, timezone, notifications)
- [ ] Permission groups
- [ ] Login attempt tracking / lockout
- [ ] Password reset workflow

## Real-Time Updates
- [x] WebSocket connection (native, not Socket.io)
- [x] JWT authentication on socket
- [x] Lead update broadcasts
- [x] Notification broadcasts
- [x] Auto-reconnect on disconnect
- [x] Dashboard auto-refresh on lead changes
- [x] Pipeline auto-refresh on stage changes
- [ ] Heartbeat / keepalive ping-pong
- [ ] Message queueing on reconnect
- [ ] Per-user notification preferences
- [ ] Horizontal scaling (need Redis backend)

## User Interface
- [x] Professional lucide-react icons (no emoji)
- [x] Responsive design (mobile-friendly)
- [x] Sidebar navigation (collapsible on mobile)
- [x] Header with notifications & user menu
- [x] Dark mode support (partial)
- [x] Loading states on async actions
- [x] Error messages (clear, actionable)
- [x] Confirmation dialogs for destructive actions
- [x] Pagination (10/25/50 per page configurable)
- [x] Search with live filtering
- [ ] Dark mode complete
- [ ] Keyboard shortcuts
- [ ] Drag-drop file upload
- [ ] Inline editing on tables

## Custom Fields (Partial)
- [x] Custom field definition model
- [x] Custom field values storage (JSON)
- [x] Lead model supports custom_fields JSON
- [ ] Admin UI for field definition management
- [ ] Dynamic form rendering on lead form
- [ ] Field type validation (text, textarea, number, date, select)
- [ ] Field dependency rules

## Notifications (Partial)
- [x] Notification model
- [x] WebSocket broadcast events
- [x] Dashboard notification badge
- [ ] User notification preferences
- [ ] Email digest of notifications
- [ ] In-app notification center
- [ ] Notification history

## Data Management
- [x] CSV bulk import (leads)
- [x] CSV export (leads)
- [x] PDF export (pipeline report)
- [x] Soft-delete pattern (preserve audit trail)
- [x] Database migrations (Django ORM)
- [ ] Hard delete (permanent)
- [ ] Data archival
- [ ] Bulk actions (select multiple, perform action)

## Admin Features
- [x] Django Admin interface
  - User management
  - Lead search & filter
  - Activity history
  - Task list with filters
  - Template management
- [x] Demo data seeding (12 leads, 36 activities, etc.)
- [ ] Database backups (script ready)
- [ ] Data anonymization
- [ ] Audit trail UI

## Integration Points (Future)
- [ ] Zapier / Make.com
- [ ] Slack notifications
- [ ] Google Calendar sync
- [ ] Salesforce sync
- [ ] HubSpot import
- [ ] Stripe CRM integration

## Performance & Scalability
- [x] Pagination (cursor offset-based)
- [x] Database indexes (stage_id, owner_id, created_at)
- [x] API response caching (none, all fresh)
- [x] Single-process Daphne ASGI (dev only)
- [ ] Redis caching layer
- [ ] Redis channel layer (for horizontal scaling)
- [ ] Database connection pooling
- [ ] Query optimization (select_related, prefetch_related)
- [ ] API rate limiting

## Security
- [x] JWT token validation on all endpoints
- [x] Role-based permission checks (server-side)
- [x] CORS headers configured
- [x] Password hashing (Django default)
- [x] Soft-delete (audit trail, no permanent loss)
- [x] Input validation via DRF serializers
- [ ] CSRF token protection on forms
- [ ] SQL injection prevention (via ORM)
- [ ] XSS protection (React escaping)
- [ ] Rate limiting on login & bulk operations
- [ ] Secrets management (.env, no hardcoded keys)
- [ ] HTTPS enforcement
- [ ] HSTS headers

## Deployment
- [x] Docker-ready (not included, use as-is)
- [x] Environment variables via .env
- [x] Database migrations on startup
- [x] Demo seeding script
- [x] Vite build (production-optimized)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Containerized backend (Dockerfile)
- [ ] Containerized frontend (Dockerfile)
- [ ] Database backup automation
- [ ] Monitoring/logging (Sentry, Datadog)

## Testing
- [ ] Unit tests (backend: 0, frontend: 0)
- [ ] Integration tests
- [ ] End-to-end tests
- [ ] Performance tests
- [ ] Security tests

---

## Summary

**Completed: 80+ features**
- Core CRUD (leads, tasks, activities, templates, users)
- Kanban pipeline with real-time sync
- Lead scoring algorithm
- Reporting dashboards (8 KPI cards, 4 charts)
- Bulk operations (import, export, email send)
- Professional UI (lucide icons, responsive)
- WebSocket real-time updates
- Role-based access control

**Partially Complete: 5 features**
- Custom fields (model exists, UI missing)
- Notifications (model + broadcast exist, preferences missing)
- Admin features (Django Admin exists, custom UI missing)

**Not Started: 50+ features**
- Refresh tokens, 2FA, OAuth
- Lead deduplication, merge, lifecycle history
- Custom stages, WIP limits
- Activity attachments, @mentions
- Recurring tasks, subtasks, dependencies
- HTML emails, scheduling, open tracking
- Custom reports, predictive analytics
- User preferences, permission groups
- Email reminders, password reset
- Message queueing, horizontal scaling
- Dark mode, keyboard shortcuts, inline editing
- Zapier, Slack, HubSpot, Salesforce integrations
- CI/CD, monitoring, tests
