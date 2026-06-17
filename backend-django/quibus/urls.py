from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from crm import views, web_views

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
    path("stages/reorder", views.stage_reorder_view),
    path("stages/create", views.stage_create_view),
    path("stages/<int:pk>", views.stage_update_view),
    path("stages/<int:pk>/delete", views.stage_delete_view),
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
    # Admin
    path("users/<int:pk>/reset-password", views.reset_user_password),
    # Sources
    path("sources", views.sources_list_view),
    path("sources/create", views.source_create_view),
    path("sources/reorder", views.source_reorder_view),
    path("sources/<int:pk>", views.source_update_view),
    path("sources/<int:pk>/delete", views.source_delete_view),
    # Products & services
    path("products", views.products_list_view),
    path("products/create", views.product_create_view),
    path("products/reorder", views.product_reorder_view),
    path("products/<int:pk>", views.product_update_view),
    path("products/<int:pk>/delete", views.product_delete_view),
    # Customer profiles
    path("profiles", views.profiles_list_view),
    path("profiles/create", views.profile_create_view),
    path("profiles/reorder", views.profile_reorder_view),
    path("profiles/<int:pk>", views.profile_update_view),
    path("profiles/<int:pk>/delete", views.profile_delete_view),
    # Bulk lead actions (must precede router's leads/<pk> route)
    path("leads/bulk-assign", views.leads_bulk_assign_view),
    path("leads/bulk-delete", views.leads_bulk_delete_view),
    *router.urls,
]

web = [
    path("", web_views.dashboard),
    path("login", web_views.login_page),
    path("logout", web_views.logout_view),
    path("pipeline", web_views.pipeline),
    path("leads", web_views.leads),
    path("leads/<int:pk>", web_views.lead_detail),
    path("tasks", web_views.tasks),
    path("templates", web_views.templates_page),
    path("reports", web_views.reports),
    path("users", web_views.users_page),
    path("funnel", web_views.funnel),
    path("sources", web_views.source_master),
    path("products", web_views.products_page),
    path("masters", web_views.masters_hub),
    path("masters/profiles", web_views.customer_profiles_page),
    path("profile", web_views.profile),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api)),
    *web,
]

urlpatterns += staticfiles_urlpatterns()
