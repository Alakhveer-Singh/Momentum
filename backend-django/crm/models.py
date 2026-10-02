from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        REP = "rep", "Telecaller"

    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.REP)
    phone = models.CharField(max_length=30, blank=True, default="")
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    otp_code = models.CharField(max_length=6, blank=True, default="")
    otp_expires_at = models.DateTimeField(null=True, blank=True)

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
    # Each product owns its own funnel. product=NULL is the global/default funnel
    # used by leads that have no product assigned.
    product = models.ForeignKey("Product", null=True, blank=True, on_delete=models.CASCADE, related_name="pipeline_stages")
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
    color = models.CharField(max_length=20, default="#6366f1")
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
    label = models.CharField(max_length=100, blank=True, default="")
    color = models.CharField(max_length=20, default="#6366f1")
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
    color = models.CharField(max_length=20, default="#6366f1")
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
    products = models.ManyToManyField("Product", related_name="leads_multi", blank=True)
    stage = models.ForeignKey(PipelineStage, on_delete=models.PROTECT, related_name="leads")
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="leads")
    score = models.PositiveIntegerField(default=0)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, default="")
    photo = models.ImageField(upload_to="lead_photos/", null=True, blank=True)
    custom_fields = models.JSONField(null=True, blank=True)
    lost_reason = models.CharField(max_length=255, blank=True, default="")
    last_activity_at = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)  # soft delete

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["deleted_at", "-created_at"]),
            models.Index(fields=["deleted_at", "stage", "-created_at"]),
        ]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.full_name


class LeadAttachment(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="attachment_files")
    file = models.FileField(upload_to="lead_attachments/")
    name = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


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


class LeadComment(models.Model):
    """A threaded discussion comment on a lead. Supports @mentions of team members."""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="lead_comments")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.user.name if self.user else 'Unknown'} on lead {self.lead_id}"


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


class Campaign(models.Model):
    class MessageType(models.TextChoices):
        SMS = "sms", "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"
        OTHER = "other", "Other"

    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name="campaigns")
    message_type = models.CharField(max_length=10, choices=MessageType.choices)
    message_type_other = models.CharField(max_length=50, blank=True, default="")
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.get_message_type_display()})"


class CampaignView(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="campaign_views")
    viewed_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("campaign", "user")
        ordering = ["-viewed_at"]


def ensure_product_stages(product):
    """Give a product its own copy of the funnel, cloned from the global (product=NULL)
    stages, the first time its funnel is opened. Idempotent — does nothing if the
    product already owns stages. Also remaps that product's leads off the shared
    global stages onto its own clones (matched by name)."""
    import re

    if product is None or product.pipeline_stages.exists():
        return
    name_to_clone = {}
    for g in PipelineStage.objects.filter(product__isnull=True).order_by("position"):
        base = (re.sub(r"[^a-z0-9]+", "-", g.name.lower()).strip("-") or "stage") + f"-{product.id}"
        slug, n = base, 1
        while PipelineStage.objects.filter(slug=slug).exists():
            slug = f"{base}-{n}"
            n += 1
        clone = PipelineStage.objects.create(
            product=product, name=g.name, slug=slug, position=g.position, color=g.color,
            stage_type=g.stage_type, is_won=g.is_won, is_lost=g.is_lost,
        )
        name_to_clone[g.name] = clone
    # Move this product's existing leads from the shared global stages to its own clones.
    for lead in Lead.objects.filter(product=product, stage__product__isnull=True).select_related("stage"):
        clone = name_to_clone.get(lead.stage.name)
        if clone:
            Lead.objects.filter(pk=lead.pk).update(stage=clone)
