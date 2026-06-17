from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Activity,
    CustomerProfile,
    CustomFieldDefinition,
    EmailTemplate,
    Lead,
    LoginActivity,
    Notification,
    PipelineStage,
    Product,
    Task,
    User,
)

admin.site.site_header = "Quibus LMS Administration"
admin.site.site_title = "Quibus LMS"
admin.site.index_title = "Lead Management & CRM"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("name", "email", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("name", "email")
    ordering = ("name",)
    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        ("Profile", {"fields": ("name", "phone", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "name", "role", "password1", "password2")}),
    )


@admin.register(PipelineStage)
class PipelineStageAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "position", "is_won", "is_lost")
    list_editable = ("position",)
    ordering = ("position",)


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    fields = ("type", "subject", "user", "occurred_at")
    readonly_fields = ("created_at",)


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ("title", "assigned_to", "priority", "status", "due_at")
    fk_name = "lead"


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "source", "stage", "owner", "score", "value")
    list_filter = ("stage", "source", "owner")
    search_fields = ("first_name", "last_name", "email")
    inlines = (ActivityInline, TaskInline)
    readonly_fields = ("score", "created_at", "updated_at", "last_activity_at", "converted_at")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "lead", "assigned_to", "priority", "status", "due_at")
    list_filter = ("status", "priority", "assigned_to")
    search_fields = ("title",)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "created_by")
    search_fields = ("name", "subject")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("subject", "type", "lead", "user", "occurred_at")
    list_filter = ("type",)


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ("email", "success", "ip_address", "created_at")
    list_filter = ("success", "created_at")
    search_fields = ("email", "user__email")
    readonly_fields = ("email", "ip_address", "user_agent", "success", "reason", "created_at")
    date_hierarchy = "created_at"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "is_active", "position")
    list_filter = ("kind", "is_active")
    search_fields = ("name",)
    list_editable = ("position", "is_active")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "position", "is_active")
    list_editable = ("position", "is_active")


admin.site.register(CustomFieldDefinition)
admin.site.register(Notification)
