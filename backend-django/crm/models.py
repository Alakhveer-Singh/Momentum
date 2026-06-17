from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        REP = "rep", "Telecaller"

    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.REP)
    phone = models.CharField(max_length=30, blank=True, default="")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    @property
    def is_manager_or_admin(self) -> bool:
        return self.role in (self.Role.ADMIN, self.Role.MANAGER)

    def __str__(self):
        return self.name or self.email


class PipelineStage(models.Model):
    TYPE_ENTRY = "entry"
    TYPE_MIDDLE = "middle"
    TYPE_WON = "won"
    TYPE_LOST = "lost"
    STAGE_TYPES = [
        (TYPE_ENTRY, "Entry"),
        (TYPE_MIDDLE, "Middle"),
        (TYPE_WON, "Won"),
        (TYPE_LOST, "Lost"),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    position = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=20, default="#6366f1")
    stage_type = models.CharField(max_length=20, choices=STAGE_TYPES, default=TYPE_MIDDLE)
    is_won = models.BooleanField(default=False)
    is_lost = models.BooleanField(default=False)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return self.name


class LeadSource(models.Model):
    slug = models.SlugField(unique=True)
    label = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "label"]

    def __str__(self):
        return self.label


class Product(models.Model):
    KIND_PRODUCT = "product"
    KIND_SERVICE = "service"
    KIND_CHOICES = [(KIND_PRODUCT, "Product"), (KIND_SERVICE, "Service")]

    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_PRODUCT)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


class CustomerProfile(models.Model):
    name = models.CharField(max_length=120)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


class CustomFieldDefinition(models.Model):
    class FieldType(models.TextChoices):
        TEXT = "text"
        NUMBER = "number"
        DATE = "date"
        SELECT = "select"
        BOOLEAN = "boolean"

    label = models.CharField(max_length=255)
    key = models.SlugField(unique=True)
    type = models.CharField(max_length=10, choices=FieldType.choices, default=FieldType.TEXT)
    options = models.JSONField(null=True, blank=True)


class Lead(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField(blank=True, default="", db_index=True)
    phone = models.CharField(max_length=30, blank=True, default="")
    company = models.CharField(max_length=255, blank=True, default="")
    job_title = models.CharField(max_length=255, blank=True, default="")
    source = models.CharField(max_length=50, default="manual", db_index=True)
    product = models.ForeignKey("Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="leads")
    stage = models.ForeignKey(PipelineStage, on_delete=models.PROTECT, related_name="leads")
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="leads")
    score = models.PositiveIntegerField(default=0)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default="")
    custom_fields = models.JSONField(null=True, blank=True)
    lost_reason = models.CharField(max_length=255, blank=True, default="")
    last_activity_at = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # soft delete

    class Meta:
        ordering = ["-created_at"]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.full_name


class Activity(models.Model):
    class Type(models.TextChoices):
        CALL = "call"
        EMAIL = "email"
        MEETING = "meeting"
        NOTE = "note"
        STAGE_CHANGE = "stage_change"
        TASK = "task"
        SYSTEM = "system"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="activities")
    type = models.CharField(max_length=15, choices=Type.choices, db_index=True)
    subject = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    metadata = models.JSONField(null=True, blank=True)
    occurred_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name_plural = "activities"


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"

    class Status(models.TextChoices):
        PENDING = "pending"
        COMPLETED = "completed"

    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.CASCADE, related_name="tasks")
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tasks")
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class EmailTemplate(models.Model):
    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def render(self, lead: Lead) -> dict:
        replacements = {
            "{{first_name}}": lead.first_name,
            "{{last_name}}": lead.last_name,
            "{{full_name}}": lead.full_name,
            "{{company}}": lead.company,
            "{{email}}": lead.email,
        }
        subject, body = self.subject, self.body
        for key, val in replacements.items():
            subject = subject.replace(key, val)
            body = body.replace(key, val)
        return {"subject": subject, "body": body}


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="crm_notifications")
    data = models.JSONField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class LoginActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_activities", null=True, blank=True)
    email = models.EmailField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, default="")
    success = models.BooleanField(default=False)
    reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"]), models.Index(fields=["email", "-created_at"])]
