from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from crm import views

router = DefaultRouter(trailing_slash=False)
router.register("leads", views.LeadViewSet, basename="lead")
router.register("activities", views.ActivityViewSet, basename="activity")
router.register("tasks", views.TaskViewSet, basename="task")
router.register("email-templates", views.EmailTemplateViewSet, basename="emailtemplate")
router.register("users", views.UserViewSet, basename="user")

api = [
    # Public
    path("public/leads", views.public_lead_view),
    path("auth/login", views.login_view),
    # Auth
    path("auth/me", views.me_view),
    path("auth/refresh", views.refresh_view),
    path("auth/logout", views.logout_view),
    path("auth/profile", views.profile_view),
    # Reference
    path("stages", views.stages_view),
    path("custom-fields", views.custom_fields_view),
    # Leads extras
    path("leads-import", views.bulk_import_view),
    # Emails
    path("emails/send", views.send_email_view),
    # Reports
    path("reports/dashboard", views.report_dashboard),
    path("reports/pipeline", views.report_pipeline),
    path("reports/sources", views.report_sources),
    path("reports/team", views.report_team),
    path("reports/trend", views.report_trend),
    # Exports
    path("exports/leads.csv", views.export_leads_csv),
    path("exports/pipeline.pdf", views.export_pipeline_pdf),
    # Notifications
    path("notifications", views.notifications_view),
    path("notifications/read", views.notifications_read_view),
    *router.urls,
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api)),
]
