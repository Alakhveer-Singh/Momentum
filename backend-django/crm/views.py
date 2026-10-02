import csv
from io import BytesIO

from django.core.mail import send_mail
from django.db.models import Avg, Count, Max, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from . import scoring
from .models import (
    Activity,
    Campaign,
    CampaignView,
    CustomerProfile,
    CustomFieldDefinition,
    EmailTemplate,
    Lead,
    LeadAttachment,
    LeadComment,
    LeadSource,
    PipelineStage,
    Product,
    Task,
    User,
    ensure_product_stages,
)
from .pagination import LaravelStylePagination
from .permissions import IsAdmin, IsManagerOrAdmin
from .realtime import broadcast_lead, notify_user
from .serializers import (
    ActivitySerializer,
    CustomFieldDefinitionSerializer,
    EmailTemplateSerializer,
    LeadCommentSerializer,
    LeadDetailSerializer,
    LeadSerializer,
    NotificationSerializer,
    PipelineStageSerializer,
    TaskSerializer,
    UserSerializer,
    UserWriteSerializer,
)


def _pretty(s: str) -> str:
    return (s or "").replace("_", " ").title()


# --- Throttles --------------------------------------------------------------
class LoginThrottle(ScopedRateThrottle):
    scope = "login"


class PublicIntakeThrottle(ScopedRateThrottle):
    scope = "public-intake"


# --- Auth -------------------------------------------------------------------
def _token_response(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "token_type": "bearer",
        "expires_in": int(refresh.access_token.lifetime.total_seconds()),
        "user": UserSerializer(user).data,
    }


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login_view(request):
    email = request.data.get("email", "")
    password = request.data.get("password", "")
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"message": "Invalid credentials.", "errors": {"email": ["Invalid credentials."]}}, status=422)
    if not user.check_password(password):
        return Response({"message": "Invalid credentials.", "errors": {"email": ["Invalid credentials."]}}, status=422)
    if not user.is_active:
        admin = User.objects.filter(role="admin").first()
        admin_email = admin.email if admin else "admin@quibus.in"
        admin_phone = admin.phone if admin else "N/A"
        msg = f"Your account has been suspended by the Super Admin. If you think we made a mistake and would like to turn your account back on, please contact the Super Admin ({admin_email}, {admin_phone})"
        return Response({"message": msg, "errors": {"email": [msg]}}, status=422)
    return Response(_token_response(user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def refresh_view(request):
    return Response(_token_response(request.user))


@api_view(["GET"])
def me_view(request):
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
def logout_view(request):
    return Response({"message": "Logged out."})


@api_view(["PUT"])
def profile_view(request):
    user = request.user
    data = request.data
    if "name" in data:
        user.name = data["name"]
    if "phone" in data:
        user.phone = data["phone"] or ""
    if data.get("password"):
        if not user.check_password(data.get("current_password", "")):
            return Response({"message": "Current password is incorrect.", "errors": {"current_password": ["Incorrect."]}}, status=422)
        user.set_password(data["password"])
    user.save()
    return Response(UserSerializer(user).data)


# --- Public intake ----------------------------------------------------------
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PublicIntakeThrottle])
def public_lead_view(request):
    d = request.data
    if not d.get("first_name") or not d.get("email"):
        return Response({"message": "first_name and email are required."}, status=422)
    stage = PipelineStage.objects.get(slug="new")
    lead = Lead.objects.create(
        first_name=d["first_name"],
        last_name=d.get("last_name", ""),
        email=d["email"],
        phone=d.get("phone", ""),
        notes=d.get("message", ""),
        source="web_form",
        stage=stage,
        last_activity_at=timezone.now(),
    )
    Activity.objects.create(
        lead=lead, type="system", subject="Lead captured via web form",
        metadata={"ip": request.META.get("REMOTE_ADDR")}, occurred_at=timezone.now(),
    )
    scoring.recalculate(lead)
    broadcast_lead(lead, "created")
    return Response({"message": "Thank you! We will be in touch shortly."}, status=201)


# --- Reference data ---------------------------------------------------------
@api_view(["GET"])
def stages_view(request):
    return Response(PipelineStageSerializer(PipelineStage.objects.filter(product__isnull=True), many=True).data)


@api_view(["POST"])
def stage_create_view(request):
    if request.user.role not in ("admin", "manager"):
        return Response({"detail": "Forbidden"}, status=403)
    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"detail": "Name required"}, status=400)
    # Stages belong to a product's own funnel (product=NULL is the global funnel).
    product = Product.objects.filter(pk=request.data.get("product_id")).first()
    if PipelineStage.objects.filter(product=product, name__iexact=name).exists():
        return Response({"detail": f'A stage named "{name}" already exists.'}, status=400)
    color = request.data.get("color", "#6366f1")
    stage_type = request.data.get("stage_type", "middle")
    max_pos = PipelineStage.objects.filter(product=product, stage_type=stage_type).aggregate(m=Max("position"))["m"] or 0
    import re
    slug_base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "stage"
    if product:
        slug_base = f"{slug_base}-{product.id}"
    slug = slug_base
    n = 1
    while PipelineStage.objects.filter(slug=slug).exists():
        slug = f"{slug_base}-{n}"
        n += 1
    stage = PipelineStage.objects.create(product=product, name=name, slug=slug, position=max_pos + 1, color=color, stage_type=stage_type)
    return Response(PipelineStageSerializer(stage).data, status=201)


@api_view(["PATCH"])
def stage_update_view(request, pk):
    if request.user.role not in ("admin", "manager"):
        return Response({"detail": "Forbidden"}, status=403)
    stage = PipelineStage.objects.get(pk=pk)
    if name := (request.data.get("name") or "").strip():
        # Uniqueness is per-funnel, so the same stage name can exist across products.
        if PipelineStage.objects.filter(product=stage.product, name__iexact=name).exclude(pk=pk).exists():
            return Response({"detail": f'A stage named "{name}" already exists.'}, status=400)
        stage.name = name
    if color := request.data.get("color"):
        stage.color = color
    stage.save()
    return Response(PipelineStageSerializer(stage).data)


@api_view(["DELETE"])
def stage_delete_view(request, pk):
    if request.user.role not in ("admin", "manager"):
        return Response({"detail": "Forbidden"}, status=403)
    stage = PipelineStage.objects.get(pk=pk)
    # Move orphaned leads to the entry stage of the *same* funnel.
    entry = PipelineStage.objects.filter(product=stage.product, stage_type="entry").exclude(pk=pk).first()
    Lead.objects.filter(stage=stage).update(stage=entry)
    stage.delete()
    return Response(status=204)


@api_view(["POST"])
def stage_reorder_view(request):
    if request.user.role not in ("admin", "manager"):
        return Response({"detail": "Forbidden"}, status=403)
    ids = request.data.get("ids", [])
    # When a stage is dragged into a different section, the page sends that
    # section's type so the stage is reclassified (Top/Middle/Bottom) too.
    stage_type = request.data.get("stage_type")
    valid_type = stage_type in dict(PipelineStage.STAGE_TYPES)
    for pos, sid in enumerate(ids, start=1):
        fields = {"position": pos}
        if valid_type:
            fields["stage_type"] = stage_type
            fields["is_won"] = stage_type == PipelineStage.TYPE_WON
            fields["is_lost"] = stage_type == PipelineStage.TYPE_LOST
        PipelineStage.objects.filter(pk=sid).update(**fields)
    return Response({"ok": True})


@api_view(["GET"])
def custom_fields_view(request):
    return Response(CustomFieldDefinitionSerializer(CustomFieldDefinition.objects.all(), many=True).data)


# --- Leads ------------------------------------------------------------------
def _default_stage_for(product):
    """Entry stage of the lead's product funnel, or the global entry/new stage."""
    if product is not None:
        ensure_product_stages(product)
        return (product.pipeline_stages.filter(stage_type="entry").order_by("position").first()
                or product.pipeline_stages.order_by("position").first())
    return (PipelineStage.objects.filter(product__isnull=True, slug="new").first()
            or PipelineStage.objects.filter(product__isnull=True, stage_type="entry").order_by("position").first()
            or PipelineStage.objects.filter(product__isnull=True).order_by("position").first())


def _reject_duplicate_lead(data, exclude_pk=None):
    """A lead is a duplicate when the same full name matches an existing lead AND
    that lead shares the phone number OR the email. Name-only matches are allowed."""
    first = (data.get("first_name") or "").strip()
    last = (data.get("last_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()
    if not first and not last:
        return
    if not phone and not email:
        return
    qs = Lead.objects.filter(
        deleted_at__isnull=True,
        first_name__iexact=first,
        last_name__iexact=last,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    match = Q()
    if phone:
        match |= Q(phone__iexact=phone)
    if email:
        match |= Q(email__iexact=email)
    if qs.filter(match).exists():
        raise ValidationError({"detail": "A lead with this name and phone/email already exists."})


class LeadViewSet(viewsets.ModelViewSet):
    pagination_class = LaravelStylePagination

    def get_serializer_class(self):
        return LeadDetailSerializer if self.action == "retrieve" else LeadSerializer

    def base_queryset(self):
        qs = Lead.objects.filter(deleted_at__isnull=True).select_related("stage", "owner")
        if self.request.user.role == "rep":
            qs = qs.filter(owner=self.request.user)
        return qs

    def get_queryset(self):
        qs = self.base_queryset().annotate(
            activities_count=Count("activities", distinct=True),
            tasks_count=Count("tasks", distinct=True),
        )
        p = self.request.query_params
        if search := p.get("search"):
            qs = qs.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
                | Q(email__icontains=search) | Q(phone__icontains=search)
            )
        if phone := p.get("phone"):
            qs = qs.filter(phone=phone)
        if stage_id := p.get("stage_id"):
            qs = qs.filter(stage_id=stage_id)
        sources = p.getlist("source")
        if len(sources) > 1:
            qs = qs.filter(source__in=sources)
        elif source := p.get("source"):
            qs = qs.filter(source=source)
        if owner_id := p.get("owner_id"):
            qs = qs.filter(owner_id=owner_id)
        if p.get("unread") == "1":
            qs = qs.filter(activities_count=0)
        if date_from := p.get("date_from"):
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to := p.get("date_to"):
            qs = qs.filter(created_at__date__lte=date_to)
        sort = p.get("sort") or "created_at"
        direction = p.get("direction") or "desc"
        if sort in ("created_at", "score", "value", "last_activity_at"):
            qs = qs.order_by(sort if direction == "asc" else f"-{sort}")
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        if request.query_params.get("all"):
            return Response({"data": self.get_serializer(qs, many=True).data})
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def perform_create(self, serializer):
        _reject_duplicate_lead(serializer.validated_data)
        if "stage" not in serializer.validated_data:
            serializer.validated_data["stage"] = _default_stage_for(serializer.validated_data.get("product"))
        if not serializer.validated_data.get("owner"):
            serializer.validated_data["owner"] = self.request.user
        lead = serializer.save(last_activity_at=timezone.now())
        Activity.objects.create(lead=lead, user=self.request.user, type="system",
                                subject="Lead created manually", occurred_at=timezone.now())
        scoring.recalculate(lead)
        broadcast_lead(lead, "created")
        # Notify the owner if the new lead was assigned to someone other than its creator.
        if lead.owner_id and lead.owner_id != self.request.user.id:
            notify_user(lead.owner, {
                "type": "assignment",
                "message": f"You were assigned lead {lead.full_name}",
                "lead_id": lead.id,
            })

    def update(self, request, *args, **kwargs):
        lead = self.get_object()
        old_stage_id = lead.stage_id
        old_source = lead.source
        old_owner_id = lead.owner_id
        old_snapshot = {
            "first_name": lead.first_name, "last_name": lead.last_name,
            "email": lead.email, "phone": lead.phone, "value": str(lead.value),
            "notes": lead.notes, "product_id": lead.product_id,
        }
        serializer = self.get_serializer(lead, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        _reject_duplicate_lead({
            "first_name": serializer.validated_data.get("first_name", lead.first_name),
            "last_name": serializer.validated_data.get("last_name", lead.last_name),
            "phone": serializer.validated_data.get("phone", lead.phone),
            "email": serializer.validated_data.get("email", lead.email),
        }, exclude_pk=lead.pk)
        lead = serializer.save()

        acts = []
        new_stage_id = lead.stage_id
        if new_stage_id != old_stage_id:
            old_stage = PipelineStage.objects.get(pk=old_stage_id)
            new_stage = lead.stage
            acts.append(Activity(
                lead=lead, user=request.user, type="stage_change",
                subject=f"{old_stage.name} → {new_stage.name}",
                metadata={"from": old_stage_id, "to": new_stage_id}, occurred_at=timezone.now(),
            ))
            lead.converted_at = timezone.now() if new_stage.is_won else None
            lead.save(update_fields=["converted_at"])
            # Notify the lead's owner when it reaches a Won/Lost stage (not if they did it themselves).
            if (new_stage.is_won or new_stage.is_lost) and lead.owner_id and lead.owner_id != request.user.id:
                notify_user(lead.owner, {
                    "type": "stage",
                    "message": f"{lead.full_name} moved to {new_stage.name}",
                    "lead_id": lead.id,
                })
        if lead.source != old_source:
            acts.append(Activity(
                lead=lead, user=request.user, type="system",
                subject=f"Source changed: {_pretty(old_source)} → {_pretty(lead.source)}",
                metadata={"from": old_source, "to": lead.source}, occurred_at=timezone.now(),
            ))
        if lead.owner_id != old_owner_id:
            new_owner = lead.owner.name if lead.owner_id else "Unassigned"
            acts.append(Activity(
                lead=lead, user=request.user, type="system",
                subject=f"Assigned to {new_owner}",
                metadata={"from": old_owner_id, "to": lead.owner_id}, occurred_at=timezone.now(),
            ))
            # Notify the newly assigned owner (not if they assigned the lead to themselves).
            if lead.owner_id and lead.owner_id != request.user.id:
                notify_user(lead.owner, {
                    "type": "assignment",
                    "message": f"You were assigned lead {lead.full_name}",
                    "lead_id": lead.id,
                })
        new_snapshot = {
            "first_name": lead.first_name, "last_name": lead.last_name,
            "email": lead.email, "phone": lead.phone, "value": str(lead.value),
            "notes": lead.notes, "product_id": lead.product_id,
        }
        changed = [k for k, v in old_snapshot.items() if new_snapshot[k] != v]
        if changed:
            acts.append(Activity(
                lead=lead, user=request.user, type="note",
                subject="Lead details updated",
                metadata={"fields": changed}, occurred_at=timezone.now(),
            ))

        if acts:
            Activity.objects.bulk_create(acts)
            lead.last_activity_at = timezone.now()
            lead.save(update_fields=["last_activity_at"])
        scoring.recalculate(lead)
        broadcast_lead(lead, "updated")
        return Response(self.get_serializer(lead).data)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_manager_or_admin:
            return Response({"message": "Forbidden."}, status=403)
        lead = self.get_object()
        lead.deleted_at = timezone.now()
        lead.save(update_fields=["deleted_at"])
        broadcast_lead(lead, "deleted")
        return Response({"message": "Lead deleted."})


MAX_IMPORT_ROWS = 20000


@api_view(["POST"])
def bulk_import_view(request):
    import re
    from django.db import transaction

    rows = request.data.get("leads", [])
    if not rows:
        return Response({"message": "No leads provided."}, status=422)

    default_stage = (PipelineStage.objects.filter(product__isnull=True, slug="new").first()
                     or PipelineStage.objects.filter(product__isnull=True).order_by("position").first())
    if default_stage is None:
        return Response({"message": "No pipeline stages configured."}, status=422)

    # Optional "Stage" column: match a global stage by its name or slug (case-insensitive).
    stage_lookup = {}
    for s in PipelineStage.objects.filter(product__isnull=True):
        stage_lookup[s.name.strip().lower()] = s
        stage_lookup[s.slug.strip().lower()] = s

    # Optional "Owner" column: match a user by name or email (case-insensitive).
    owner_lookup = {}
    for u in User.objects.all():
        if u.name:
            owner_lookup[u.name.strip().lower()] = u
        if u.email:
            owner_lookup[u.email.strip().lower()] = u

    # Optional "Product / Service" column: match a product by name (case-insensitive).
    product_lookup = {p.name.strip().lower(): p for p in Product.objects.all()}

    def pick(row, *keys):
        """First non-empty value among the given header aliases."""
        for k in keys:
            v = row.get(k)
            if v not in (None, ""):
                return str(v).strip()
        return ""

    truncated = len(rows) > MAX_IMPORT_ROWS
    created = 0
    skipped = 0
    with transaction.atomic():
        for row in rows[:MAX_IMPORT_ROWS]:
            # Normalize headers: lowercase, collapse separators to underscores.
            row = {re.sub(r"[\s/]+", "_", str(k or "").strip().lower()): v for k, v in row.items()}

            first = pick(row, "first_name", "firstname")
            last = pick(row, "last_name", "lastname")
            if not first:
                # Fall back to a single combined "Name" column (the common case).
                full = pick(row, "name", "full_name", "fullname", "lead_name", "contact_name")
                if full:
                    parts = full.split()
                    first = parts[0]
                    last = last or " ".join(parts[1:])
            if not first:
                skipped += 1
                continue

            # Stage — by name or slug; default to the entry stage.
            stage = stage_lookup.get(pick(row, "stage", "stage_name").lower(), default_stage)

            # Source — normalize the label ("Web form") to its slug ("web_form").
            source = re.sub(r"[\s/-]+", "_", pick(row, "source").lower()) or "import"

            # Owner — explicit id, else match by name/email; otherwise leave unassigned.
            owner_id = pick(row, "owner_id")
            if not owner_id:
                owner = owner_lookup.get(pick(row, "owner", "owner_name", "assigned_to").lower())
                owner_id = owner.id if owner else None
            try:
                owner_id = int(owner_id) if owner_id else None
            except (TypeError, ValueError):
                owner_id = None

            # Value — tolerate currency symbols, thousands separators, etc.
            cleaned = re.sub(r"[^0-9.]", "", pick(row, "value", "deal_value", "amount"))
            try:
                value = float(cleaned) if cleaned else 0
            except ValueError:
                value = 0

            email = pick(row, "email", "email_address", "email_id", "e-mail", "e_mail")
            phone = pick(row, "phone", "phone_number", "mobile", "mobile_no",
                         "mobile_number", "contact", "contact_no")

            # Product / Service — link to a Product if one matches by name.
            ps = pick(row, "product", "product_service", "service")
            product = product_lookup.get(ps.lower()) if ps else None

            # Extra columns we don't have first-class fields for go on custom_fields.
            custom_fields = {}
            for key, *aliases in [
                ("current_profile", "profile", "customer_profile", "current_profile"),
                ("whatsapp", "whatsapp", "whatsapp_no", "whatsapp_number"),
                ("city", "city"),
                ("location", "location", "area"),
                ("highest_education", "highest_education", "education"),
            ]:
                val = pick(row, *aliases)
                if val:
                    custom_fields[key] = val
            if ps and product is None:
                custom_fields["product_service"] = ps

            lead = Lead.objects.create(
                first_name=first, last_name=last,
                email=email, phone=phone,
                company=pick(row, "company", "organization", "organisation"),
                job_title=pick(row, "job_title", "title", "designation"),
                source=source, value=value, stage=stage, product=product,
                owner_id=owner_id, notes=pick(row, "notes", "note", "remarks"),
                custom_fields=custom_fields or None,
            )
            Activity.objects.create(lead=lead, user=request.user, type="system",
                                    subject="Lead imported (bulk)", occurred_at=timezone.now())
            # Score inline — a freshly imported lead has no engagement activity yet.
            score = (scoring.SOURCE_WEIGHTS.get(source, 5)
                     + scoring.STAGE_WEIGHTS.get(stage.slug, 0)
                     + (1 if email else 0) + (1 if phone else 0)
                     + (2 if value and value > 0 else 0))
            Lead.objects.filter(pk=lead.pk).update(score=min(score, 100))
            created += 1

    message = f"{created} leads imported."
    if skipped:
        message += f" {skipped} row(s) skipped — no name found."
    if truncated:
        message += f" Only the first {MAX_IMPORT_ROWS} rows were processed."
    return Response({"message": message, "count": created, "skipped": skipped}, status=201)


# Student-profile fields kept on Lead.custom_fields (mirrors the Students UI).
LEAD_PROFILE_FIELDS = [
    "gender", "dob", "whatsapp", "education", "qualification",
    "guardian_name", "guardian_occupation", "guardian_number",
    "current_address", "permanent_address",
    "batch_time", "batch_number", "batch_start", "achievements",
]


def _lead_for_edit(request, pk):
    """Fetch a non-deleted lead, enforcing that reps only touch their own."""
    lead = get_object_or_404(Lead, pk=pk, deleted_at__isnull=True)
    if request.user.role == "rep" and lead.owner_id != request.user.id:
        return None
    return lead


@api_view(["POST"])
def lead_profile_save_view(request, pk):
    lead = _lead_for_edit(request, pk)
    if lead is None:
        return Response({"message": "Not allowed."}, status=403)

    data = request.data
    full_name = (data.get("full_name") or "").strip()
    if full_name:
        parts = full_name.split()
        lead.first_name = parts[0]
        lead.last_name = " ".join(parts[1:])
    if "phone" in data:
        lead.phone = (data.get("phone") or "").strip()
    if "email" in data:
        lead.email = (data.get("email") or "").strip()

    cf = dict(lead.custom_fields or {})
    for key in LEAD_PROFILE_FIELDS:
        if key in data:
            val = (data.get(key) or "").strip()
            if val:
                cf[key] = val
            else:
                cf.pop(key, None)
    lead.custom_fields = cf or None

    if request.FILES.get("photo"):
        lead.photo = request.FILES["photo"]
    lead.save()
    return Response({"message": "Profile saved."})


def _attachment_json(a):
    return {"id": a.id, "name": a.name, "size": a.size,
            "content_type": a.content_type, "url": a.file.url}


@api_view(["GET", "POST"])
def lead_attachments_view(request, pk):
    lead = _lead_for_edit(request, pk)
    if lead is None:
        return Response({"message": "Not allowed."}, status=403)

    if request.method == "GET":
        return Response([_attachment_json(a) for a in lead.attachment_files.all()])

    f = request.FILES.get("file")
    if not f:
        return Response({"message": "No file provided."}, status=422)
    a = LeadAttachment.objects.create(
        lead=lead, file=f, name=f.name, size=f.size,
        content_type=getattr(f, "content_type", "") or "",
    )
    return Response(_attachment_json(a), status=201)


@api_view(["POST"])
def lead_attachment_delete_view(request, pk, aid):
    lead = _lead_for_edit(request, pk)
    if lead is None:
        return Response({"message": "Not allowed."}, status=403)
    a = get_object_or_404(LeadAttachment, pk=aid, lead=lead)
    a.file.delete(save=False)
    a.delete()
    return Response({"message": "Deleted."})


# --- Activities -------------------------------------------------------------
class ActivityViewSet(viewsets.ModelViewSet):
    serializer_class = ActivitySerializer
    pagination_class = LaravelStylePagination
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        qs = Activity.objects.select_related("lead", "user")
        if self.request.user.role == "rep":
            qs = qs.filter(lead__owner=self.request.user)
        p = self.request.query_params
        if lead_id := p.get("lead_id"):
            qs = qs.filter(lead_id=lead_id)
        if t := p.get("type"):
            qs = qs.filter(type=t)
        return qs

    def perform_create(self, serializer):
        lead = serializer.validated_data["lead"]
        if self.request.user.role == "rep" and lead.owner_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Forbidden.")
        activity = serializer.save(user=self.request.user,
                                   occurred_at=serializer.validated_data.get("occurred_at") or timezone.now())
        lead.last_activity_at = activity.occurred_at
        lead.save(update_fields=["last_activity_at"])
        scoring.recalculate(lead)
        broadcast_lead(lead, "activity")

    def destroy(self, request, *args, **kwargs):
        activity = self.get_object()
        if not request.user.is_manager_or_admin and activity.user_id != request.user.id:
            return Response({"message": "Forbidden."}, status=403)
        return super().destroy(request, *args, **kwargs)


# --- Tasks ------------------------------------------------------------------
class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    pagination_class = LaravelStylePagination
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def get_queryset(self):
        qs = Task.objects.select_related("lead", "assigned_to")
        p = self.request.query_params
        if self.request.user.role == "rep":
            qs = qs.filter(assigned_to=self.request.user)
        elif assignee := p.get("assigned_to"):
            qs = qs.filter(assigned_to_id=assignee)
        if status_ := p.get("status"):
            qs = qs.filter(status=status_)
        if p.get("overdue"):
            qs = qs.filter(status="pending", due_at__lt=timezone.now())
        if lead_id := p.get("lead_id"):
            qs = qs.filter(lead_id=lead_id)
        return qs.order_by("due_at")

    def perform_create(self, serializer):
        task = serializer.save(created_by=self.request.user)
        if task.lead_id:
            due = f" (due {task.due_at:%d %b %Y %H:%M})" if task.due_at else ""
            Activity.objects.create(
                lead=task.lead, user=self.request.user, type="task",
                subject=f"Follow-up scheduled: {task.title}{due}", occurred_at=timezone.now(),
            )
            Lead.objects.filter(pk=task.lead_id).update(last_activity_at=timezone.now())
        if task.assigned_to_id != self.request.user.id:
            notify_user(task.assigned_to, {
                "task_id": task.id, "title": task.title,
                "message": f"New task assigned: {task.title}",
                "due_at": task.due_at.isoformat() if task.due_at else None,
                "lead": task.lead.full_name if task.lead_id else None,
            })

    def update(self, request, *args, **kwargs):
        task = self.get_object()
        if request.user.role == "rep" and task.assigned_to_id != request.user.id:
            return Response({"message": "Forbidden."}, status=403)
        new_status = request.data.get("status")
        prev_assignee_id = task.assigned_to_id
        serializer = self.get_serializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        # Notify the new assignee when a task is reassigned to someone else.
        if task.assigned_to_id != prev_assignee_id and task.assigned_to_id != request.user.id:
            notify_user(task.assigned_to, {
                "task_id": task.id, "title": task.title,
                "message": f"Task reassigned to you: {task.title}",
                "due_at": task.due_at.isoformat() if task.due_at else None,
                "lead": task.lead.full_name if task.lead_id else None,
            })
        if new_status == "completed":
            task.completed_at = task.completed_at or timezone.now()
            task.save(update_fields=["completed_at"])
        elif new_status == "pending":
            task.completed_at = None
            task.save(update_fields=["completed_at"])
        return Response(self.get_serializer(task).data)

    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        if not request.user.is_manager_or_admin and task.created_by_id != request.user.id:
            return Response({"message": "Forbidden."}, status=403)
        return super().destroy(request, *args, **kwargs)


# --- Email templates --------------------------------------------------------
class EmailTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = EmailTemplateSerializer
    queryset = EmailTemplate.objects.select_related("created_by").all()
    pagination_class = None
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@api_view(["POST"])
def send_email_view(request):
    template_id = request.data.get("template_id")
    lead_ids = request.data.get("lead_ids", [])
    template = EmailTemplate.objects.get(pk=template_id)
    sent = 0
    for lead in Lead.objects.filter(id__in=lead_ids[:200]):
        if not lead.email:
            continue
        rendered = template.render(lead)
        send_mail(rendered["subject"], rendered["body"], None, [lead.email], fail_silently=True)
        Activity.objects.create(lead=lead, user=request.user, type="email",
                                subject=f"Email sent: {rendered['subject']}",
                                metadata={"template_id": template.id}, occurred_at=timezone.now())
        lead.last_activity_at = timezone.now()
        lead.save(update_fields=["last_activity_at"])
        scoring.recalculate(lead)
        broadcast_lead(lead, "activity")
        sent += 1
    return Response({"message": f"Email sent to {sent} lead(s).", "sent": sent})


# --- Reports ----------------------------------------------------------------
def _lead_scope(user):
    qs = Lead.objects.filter(deleted_at__isnull=True)
    return qs.filter(owner=user) if user.role == "rep" else qs


@api_view(["GET"])
def report_dashboard(request):
    user = request.user
    won = PipelineStage.objects.filter(product__isnull=True, is_won=True).first()
    lost = PipelineStage.objects.filter(product__isnull=True, is_lost=True).first()
    open_ids = list(PipelineStage.objects.filter(is_won=False, is_lost=False).values_list("id", flat=True))
    total = _lead_scope(user).count()
    won_c = _lead_scope(user).filter(stage=won).count()
    lost_c = _lead_scope(user).filter(stage=lost).count()
    closed = won_c + lost_c
    tasks = Task.objects.filter(status="pending")
    if user.role == "rep":
        tasks = tasks.filter(assigned_to=user)
    return Response({
        "total_leads": total,
        "open_leads": _lead_scope(user).filter(stage_id__in=open_ids).count(),
        "won_leads": won_c,
        "lost_leads": lost_c,
        "conversion_rate": round(won_c / closed * 100, 1) if closed else 0,
        "pipeline_value": float(_lead_scope(user).filter(stage_id__in=open_ids).aggregate(s=Sum("value"))["s"] or 0),
        "won_value": float(_lead_scope(user).filter(stage=won).aggregate(s=Sum("value"))["s"] or 0),
        "new_this_week": _lead_scope(user).filter(created_at__gte=timezone.now() - timezone.timedelta(days=7)).count(),
        "avg_score": round(_lead_scope(user).aggregate(a=Avg("score"))["a"] or 0, 1),
        "pending_tasks": tasks.count(),
        "overdue_tasks": tasks.filter(due_at__lt=timezone.now()).count(),
    })


@api_view(["GET"])
def report_pipeline(request):
    out = []
    for stage in PipelineStage.objects.filter(product__isnull=True):
        leads = stage.leads.filter(deleted_at__isnull=True)
        if request.user.role == "rep":
            leads = leads.filter(owner=request.user)
        data = PipelineStageSerializer(stage).data
        data["leads_count"] = leads.count()
        data["total_value"] = float(leads.aggregate(s=Sum("value"))["s"] or 0)
        out.append(data)
    return Response(out)


@api_view(["GET"])
@permission_classes([IsManagerOrAdmin])
def report_sources(request):
    won_id = PipelineStage.objects.filter(product__isnull=True, is_won=True).values_list("id", flat=True).first()
    rows = (
        Lead.objects.filter(deleted_at__isnull=True)
        .values("source")
        .annotate(
            total=Count("id"),
            won=Count("id", filter=Q(stage_id=won_id)),
            won_value=Sum("value", filter=Q(stage_id=won_id)),
            total_value=Sum("value"),
        )
        .order_by("-total")
    )
    out = []
    for r in rows:
        r["won_value"] = float(r["won_value"] or 0)
        r["total_value"] = float(r["total_value"] or 0)
        r["conversion_rate"] = round(r["won"] / r["total"] * 100, 1) if r["total"] else 0
        out.append(r)
    return Response(out)


@api_view(["GET"])
@permission_classes([IsManagerOrAdmin])
def report_team(request):
    won_id = PipelineStage.objects.filter(product__isnull=True, is_won=True).values_list("id", flat=True).first()
    out = []
    for u in User.objects.filter(is_active=True):
        leads = Lead.objects.filter(owner=u, deleted_at__isnull=True)
        out.append({
            "id": u.id, "name": u.name, "role": u.role,
            "total_leads": leads.count(),
            "won_leads": leads.filter(stage_id=won_id).count(),
            "won_value": float(leads.filter(stage_id=won_id).aggregate(s=Sum("value"))["s"] or 0),
            "pipeline_value": float(leads.aggregate(s=Sum("value"))["s"] or 0),
            "activities_30d": Activity.objects.filter(user=u, occurred_at__gte=timezone.now() - timezone.timedelta(days=30)).count(),
            "pending_tasks": Task.objects.filter(assigned_to=u, status="pending").count(),
        })
    return Response(out)


@api_view(["GET"])
def report_trend(request):
    rows = (
        Lead.objects.filter(deleted_at__isnull=True, created_at__gte=timezone.now() - timezone.timedelta(days=183))
        .annotate(m=TruncMonth("created_at"))
        .values("m")
        .annotate(leads=Count("id"), won=Count("id", filter=Q(converted_at__isnull=False)))
        .order_by("m")
    )
    return Response([{"month": r["m"].strftime("%Y-%m"), "leads": r["leads"], "won": r["won"]} for r in rows])


# --- Exports ----------------------------------------------------------------
class _Echo:
    def write(self, value):
        return value


@api_view(["GET"])
def export_leads_csv(request):
    qs = Lead.objects.filter(deleted_at__isnull=True).select_related("stage", "owner")
    if request.user.role == "rep":
        qs = qs.filter(owner=request.user)
    if stage_id := request.query_params.get("stage_id"):
        qs = qs.filter(stage_id=stage_id)

    def rows():
        writer = csv.writer(_Echo())
        yield writer.writerow(["ID", "First Name", "Last Name", "Email", "Phone", "Job Title",
                               "Source", "Stage", "Owner", "Score", "Value", "Created At"])
        for l in qs.iterator():
            yield writer.writerow([
                l.id, l.first_name, l.last_name, l.email, l.phone, l.job_title,
                l.source, l.stage.name if l.stage_id else "", l.owner.name if l.owner_id else "",
                l.score, l.value, l.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ])

    resp = StreamingHttpResponse(rows(), content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="leads-{timezone.now():%Y-%m-%d}.csv"'
    return resp


@api_view(["GET"])
def export_pipeline_pdf(request):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Pipeline Report")
    styles = getSampleStyleSheet()
    elems = [Paragraph("Momentum — Pipeline Report", styles["Title"]),
             Paragraph(f"Generated {timezone.now():%d %b %Y, %H:%M} by {request.user.name}", styles["Normal"]),
             Spacer(1, 16)]
    for stage in PipelineStage.objects.filter(product__isnull=True):
        leads = list(stage.leads.filter(deleted_at__isnull=True).select_related("owner"))
        if request.user.role == "rep":
            leads = [l for l in leads if l.owner_id == request.user.id]
        total = sum(float(l.value) for l in leads)
        elems.append(Paragraph(f"<b>{stage.name}</b> — {len(leads)} lead(s), ₹{total:,.0f}", styles["Heading3"]))
        data = [["Name", "Owner", "Score", "Value"]]
        for l in leads:
            data.append([l.full_name, l.owner.name if l.owner_id else "", str(l.score), f"₹{l.value:,.0f}"])
        if len(data) > 1:
            t = Table(data, colWidths=[150, 120, 60, 90])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e5e7eb")),
                ("ALIGN", (3, 0), (4, -1), "RIGHT"),
            ]))
            elems.append(t)
        else:
            elems.append(Paragraph("<i>No leads in this stage.</i>", styles["Normal"]))
        elems.append(Spacer(1, 12))
    doc.build(elems)
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="pipeline-report-{timezone.now():%Y-%m-%d}.pdf"'
    return resp


# --- Notifications ----------------------------------------------------------
@api_view(["GET"])
def notifications_view(request):
    qs = request.user.crm_notifications.all()[:50]
    return Response({
        "notifications": NotificationSerializer(qs, many=True).data,
        "unread_count": request.user.crm_notifications.filter(read_at__isnull=True).count(),
    })


@api_view(["POST"])
def notifications_read_view(request):
    qs = request.user.crm_notifications.filter(read_at__isnull=True)
    if nid := request.data.get("id"):
        qs = qs.filter(id=nid)
    qs.update(read_at=timezone.now())
    return Response({"message": "Marked as read."})


@api_view(["POST"])
def notifications_send_view(request):
    """Admin: push a notification to a specific user or broadcast to all active users."""
    if not request.user.role == "admin":
        return Response({"error": "Forbidden."}, status=403)
    message = request.data.get("message", "").strip()
    if not message:
        return Response({"error": "message is required."}, status=400)
    user_id = request.data.get("user_id")
    if user_id:
        recipients = User.objects.filter(pk=user_id, is_active=True)
    else:
        recipients = User.objects.filter(is_active=True)
    payload = {"type": "announcement", "message": message}
    count = 0
    for user in recipients:
        notify_user(user, payload)
        count += 1
    return Response({"sent_to": count})


# --- Users (admin) ----------------------------------------------------------
class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    pagination_class = None
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def get_queryset(self):
        return User.objects.annotate(
            leads_count=Count("leads", distinct=True),
            tasks_count=Count("tasks", distinct=True),
        ).order_by("name")

    def get_serializer_class(self):
        return UserWriteSerializer if self.action in ("create", "update", "partial_update") else UserSerializer

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        new_role = request.data.get("role", user.role)
        new_active = request.data.get("is_active", user.is_active)
        if user.role == "admin" and (new_role != "admin" or new_active is False):
            if User.objects.filter(role="admin", is_active=True).count() <= 1:
                return Response({"message": "Cannot demote or deactivate the last active admin."}, status=422)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.id == request.user.id:
            return Response({"message": "You cannot delete your own account."}, status=422)
        if user.role == "admin" and User.objects.filter(role="admin").count() <= 1:
            return Response({"message": "Cannot delete the last admin."}, status=422)
        return super().destroy(request, *args, **kwargs)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reset_user_password(request, pk):
    if not request.user.is_manager_or_admin:
        return Response({"detail": "Forbidden"}, status=403)
    user = User.objects.get(pk=pk)
    new_password = request.data.get("password", "")
    if len(new_password) < 8:
        return Response({"detail": "Password must be at least 8 characters"}, status=400)
    user.set_password(new_password)
    user.save()
    return Response({"message": f"Password reset for {user.email}"}, status=200)


# --- Source Master -----------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sources_list_view(request):
    sources = LeadSource.objects.all()
    return Response([{"id": s.id, "slug": s.slug, "label": s.label, "position": s.position, "color": s.color} for s in sources])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def source_create_view(request):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    label = (request.data.get("label") or "").strip()
    if not label:
        return Response({"detail": "Label required"}, status=400)
    if LeadSource.objects.filter(label__iexact=label).exists():
        return Response({"detail": f'A source named "{label}" already exists.'}, status=400)
    import re
    slug_base = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    slug = slug_base
    n = 1
    while LeadSource.objects.filter(slug=slug).exists():
        slug = f"{slug_base}_{n}"
        n += 1
    max_pos = LeadSource.objects.count()
    source = LeadSource.objects.create(slug=slug, label=label, position=max_pos)
    return Response({"id": source.id, "slug": source.slug, "label": source.label, "color": source.color}, status=201)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def source_update_view(request, pk):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    source = LeadSource.objects.get(pk=pk)
    if label := (request.data.get("label") or "").strip():
        if LeadSource.objects.filter(label__iexact=label).exclude(pk=pk).exists():
            return Response({"detail": f'A source named "{label}" already exists.'}, status=400)
        source.label = label
    if color := request.data.get("color"):
        source.color = color
    source.save()
    return Response({"id": source.id, "slug": source.slug, "label": source.label, "color": source.color})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def source_delete_view(request, pk):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    source = LeadSource.objects.get(pk=pk)
    source.delete()
    return Response(status=204)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def source_reorder_view(request):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    ids = request.data.get("ids", [])
    for pos, sid in enumerate(ids, start=1):
        LeadSource.objects.filter(pk=sid).update(position=pos)
    return Response({"ok": True})


# --- Products & Services -----------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def products_list_view(request):
    qs = Product.objects.all()
    if request.query_params.get("active") == "1":
        qs = qs.filter(is_active=True)
    return Response([
        {"id": p.id, "name": p.name, "kind": p.kind, "label": p.label, "color": p.color, "description": p.description, "is_active": p.is_active}
        for p in qs
    ])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def product_create_view(request):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"detail": "Name required"}, status=400)
    if Product.objects.filter(name__iexact=name).exists():
        return Response({"detail": f'A product named "{name}" already exists.'}, status=400)
    label = (request.data.get("label") or "").strip()
    pos = Product.objects.count()
    p = Product.objects.create(name=name, label=label, description=(request.data.get("description") or "").strip(), position=pos)
    return Response({"id": p.id, "name": p.name, "kind": p.kind, "label": p.label, "color": p.color, "description": p.description, "is_active": p.is_active}, status=201)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def product_update_view(request, pk):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    p = Product.objects.get(pk=pk)
    if "name" in request.data and request.data["name"].strip():
        new_name = request.data["name"].strip()
        if Product.objects.filter(name__iexact=new_name).exclude(pk=pk).exists():
            return Response({"detail": f'A product named "{new_name}" already exists.'}, status=400)
        p.name = new_name
    if "label" in request.data:
        p.label = (request.data["label"] or "").strip()
    if color := request.data.get("color"):
        p.color = color
    if "description" in request.data:
        p.description = (request.data["description"] or "").strip()
    if "is_active" in request.data:
        p.is_active = bool(request.data["is_active"])
    p.save()
    return Response({"id": p.id, "name": p.name, "kind": p.kind, "label": p.label, "color": p.color, "description": p.description, "is_active": p.is_active})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def product_delete_view(request, pk):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    Product.objects.filter(pk=pk).delete()
    return Response(status=204)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def product_reorder_view(request):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    for pos, pid in enumerate(request.data.get("ids", []), start=1):
        Product.objects.filter(pk=pid).update(position=pos)
    return Response({"ok": True})


# --- Customer Profiles -------------------------------------------------------
def _profile_json(p):
    return {"id": p.id, "name": p.name, "position": p.position, "color": p.color, "is_active": p.is_active}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profiles_list_view(request):
    qs = CustomerProfile.objects.all()
    if request.query_params.get("active") == "1":
        qs = qs.filter(is_active=True)
    return Response([_profile_json(p) for p in qs])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def profile_create_view(request):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"detail": "Name required"}, status=400)
    if CustomerProfile.objects.filter(name__iexact=name).exists():
        return Response({"detail": f'A profile named "{name}" already exists.'}, status=400)
    p = CustomerProfile.objects.create(name=name, position=CustomerProfile.objects.count())
    return Response(_profile_json(p), status=201)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def profile_update_view(request, pk):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    p = CustomerProfile.objects.get(pk=pk)
    if "name" in request.data and request.data["name"].strip():
        new_name = request.data["name"].strip()
        if CustomerProfile.objects.filter(name__iexact=new_name).exclude(pk=pk).exists():
            return Response({"detail": f'A profile named "{new_name}" already exists.'}, status=400)
        p.name = new_name
    if color := request.data.get("color"):
        p.color = color
    if "is_active" in request.data:
        p.is_active = bool(request.data["is_active"])
    p.save()
    return Response(_profile_json(p))


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def profile_delete_view(request, pk):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    CustomerProfile.objects.filter(pk=pk).delete()
    return Response(status=204)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def profile_reorder_view(request):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)
    for pos, pid in enumerate(request.data.get("ids", []), start=1):
        CustomerProfile.objects.filter(pk=pid).update(position=pos)
    return Response({"ok": True})


# --- Bulk lead actions -------------------------------------------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def leads_bulk_assign_view(request):
    if request.user.role == "rep":
        return Response({"detail": "Forbidden"}, status=403)
    ids = request.data.get("ids", [])
    owner_id = request.data.get("owner_id")
    owner = User.objects.filter(pk=owner_id).first() if owner_id else None
    if owner_id and not owner:
        return Response({"detail": "Invalid owner"}, status=400)
    leads = list(Lead.objects.filter(pk__in=ids, deleted_at__isnull=True))
    now = timezone.now()
    Lead.objects.filter(pk__in=[l.pk for l in leads]).update(owner=owner, last_activity_at=now)
    name = owner.name if owner else "Unassigned"
    Activity.objects.bulk_create([
        Activity(lead=l, user=request.user, type="system",
                 subject=f"Assigned to {name}", occurred_at=now)
        for l in leads
    ])
    # Notify the new owner once, summarising the batch (not if they assigned to themselves).
    if owner and owner.id != request.user.id and leads:
        msg = (f"You were assigned lead {leads[0].full_name}" if len(leads) == 1
               else f"You were assigned {len(leads)} leads")
        notify_user(owner, {"type": "assignment", "message": msg,
                            "lead_id": leads[0].id if len(leads) == 1 else None})
    return Response({"updated": len(leads)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def leads_bulk_delete_view(request):
    if not request.user.is_manager_or_admin:
        return Response({"detail": "Forbidden"}, status=403)
    ids = request.data.get("ids", [])
    n = Lead.objects.filter(pk__in=ids, deleted_at__isnull=True).update(deleted_at=timezone.now())
    return Response({"deleted": n})


# --- Campaigns (SMS/WhatsApp for team) -----------------------------------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def campaigns_create_view(request):
    if request.user.role != "admin":
        return Response({"detail": "Forbidden"}, status=403)

    title = request.data.get("title", "").strip()
    content = request.data.get("content", "").strip()
    message_type = request.data.get("message_type", "sms")
    message_type_other = request.data.get("message_type_other", "").strip()

    if not title or not content:
        return Response({"detail": "Title and content required"}, status=400)
    if message_type == "other" and not message_type_other:
        return Response({"detail": "Please specify the message type"}, status=400)

    campaign = Campaign.objects.create(
        admin=request.user,
        title=title,
        content=content,
        message_type=message_type,
        message_type_other=message_type_other if message_type == "other" else "",
    )
    label = campaign.message_type_other if campaign.message_type == "other" else campaign.get_message_type_display()

    # Create notifications for all team members
    team_users = User.objects.exclude(pk=request.user.pk)
    for user in team_users:
        notify_user(user, {
            "type": "campaign",
            "message": f"New {label} campaign: {title}",
            "campaign_id": campaign.id
        })
        CampaignView.objects.create(campaign=campaign, user=user)

    return Response({
        "id": campaign.id,
        "title": campaign.title,
        "content": campaign.content,
        "message_type": label,
        "created_at": campaign.created_at
    }, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def campaigns_list_view(request):
    campaigns = Campaign.objects.all().order_by("-created_at")

    data = []
    for c in campaigns:
        view = CampaignView.objects.filter(campaign=c, user=request.user).first()
        data.append({
            "id": c.id,
            "title": c.title,
            "content": c.content,
            "message_type": c.message_type_other if c.message_type == "other" else c.get_message_type_display(),
            "admin": c.admin.name,
            "created_at": c.created_at,
            "viewed_at": view.viewed_at if view else None,
            "read_at": view.read_at if view else None
        })

    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def campaigns_mark_read_view(request):
    campaign_id = request.data.get("campaign_id")
    try:
        campaign = Campaign.objects.get(pk=campaign_id)
    except Campaign.DoesNotExist:
        return Response({"detail": "Campaign not found"}, status=404)

    view, _ = CampaignView.objects.get_or_create(campaign=campaign, user=request.user)
    view.read_at = timezone.now()
    view.save(update_fields=["read_at"])

    return Response({"success": True})


# --- Lead comments (discussion thread + @mentions) --------------------------
def _notify_mentions(body, comment, author, lead):
    """Parse @mentions in a comment body and notify matched active users.

    A token like @reena matches an active user whose first name (or email
    localpart) equals the token, case-insensitively. Each matched user is
    notified once; the author never notifies themselves.
    """
    import re

    tokens = {t.lower() for t in re.findall(r"@([A-Za-z0-9_.]+)", body)}
    if not tokens:
        return
    notified = set()
    for user in User.objects.filter(is_active=True):
        first = (user.name or "").split(" ")[0].lower()
        localpart = (user.email or "").split("@")[0].lower()
        if (first in tokens or localpart in tokens) and user.id != author.id and user.id not in notified:
            notify_user(user, {
                "type": "mention",
                "lead_id": lead.id,
                "comment_id": comment.id,
                "message": f"{author.name} mentioned you on {lead.full_name}",
            })
            notified.add(user.id)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def lead_comments_view(request, pk):
    """List or add discussion comments on a lead."""
    try:
        lead = Lead.objects.get(pk=pk, deleted_at__isnull=True)
    except Lead.DoesNotExist:
        return Response({"detail": "Lead not found"}, status=404)

    # Reps can only touch their own leads.
    if request.user.role == "rep" and lead.owner_id != request.user.id:
        return Response({"detail": "Forbidden."}, status=403)

    if request.method == "GET":
        comments = lead.comments.select_related("user").all()
        return Response(LeadCommentSerializer(comments, many=True).data)

    body = (request.data.get("body") or "").strip()
    if not body:
        return Response({"detail": "Comment body is required."}, status=400)

    comment = LeadComment.objects.create(lead=lead, user=request.user, body=body)
    _notify_mentions(body, comment, request.user, lead)
    return Response(LeadCommentSerializer(comment).data, status=201)
