import csv
from io import BytesIO

from django.core.mail import send_mail
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from . import scoring
from .models import (
    Activity,
    CustomFieldDefinition,
    EmailTemplate,
    Lead,
    PipelineStage,
    Task,
    User,
)
from .pagination import LaravelStylePagination
from .permissions import IsAdmin, IsManagerOrAdmin
from .realtime import broadcast_lead, notify_user
from .serializers import (
    ActivitySerializer,
    CustomFieldDefinitionSerializer,
    EmailTemplateSerializer,
    LeadDetailSerializer,
    LeadSerializer,
    NotificationSerializer,
    PipelineStageSerializer,
    TaskSerializer,
    UserSerializer,
    UserWriteSerializer,
)


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
    return Response(PipelineStageSerializer(PipelineStage.objects.all(), many=True).data)


@api_view(["POST"])
def stage_create_view(request):
    if request.user.role not in ("admin", "manager"):
        return Response({"detail": "Forbidden"}, status=403)
    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"detail": "Name required"}, status=400)
    color = request.data.get("color", "#6366f1")
    max_pos = PipelineStage.objects.filter(stage_type="middle").aggregate(m=__import__("django.db.models", fromlist=["Max"]).Max("position"))["m"] or 0
    import re
    slug_base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = slug_base
    n = 1
    while PipelineStage.objects.filter(slug=slug).exists():
        slug = f"{slug_base}-{n}"
        n += 1
    stage = PipelineStage.objects.create(name=name, slug=slug, position=max_pos + 1, color=color, stage_type="middle")
    return Response(PipelineStageSerializer(stage).data, status=201)


@api_view(["PATCH"])
def stage_update_view(request, pk):
    if request.user.role not in ("admin", "manager"):
        return Response({"detail": "Forbidden"}, status=403)
    stage = PipelineStage.objects.get(pk=pk)
    if stage.stage_type != "middle":
        return Response({"detail": "Cannot rename fixed stages"}, status=400)
    if name := (request.data.get("name") or "").strip():
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
    if stage.stage_type != "middle":
        return Response({"detail": "Cannot delete fixed stages"}, status=400)
    entry = PipelineStage.objects.filter(stage_type="entry").first()
    Lead.objects.filter(stage=stage).update(stage=entry)
    stage.delete()
    return Response(status=204)


@api_view(["POST"])
def stage_reorder_view(request):
    if request.user.role not in ("admin", "manager"):
        return Response({"detail": "Forbidden"}, status=403)
    ids = request.data.get("ids", [])
    for pos, sid in enumerate(ids, start=2):
        PipelineStage.objects.filter(pk=sid, stage_type="middle").update(position=pos)
    return Response({"ok": True})


@api_view(["GET"])
def custom_fields_view(request):
    return Response(CustomFieldDefinitionSerializer(CustomFieldDefinition.objects.all(), many=True).data)


# --- Leads ------------------------------------------------------------------
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
                | Q(email__icontains=search)
            )
        if stage_id := p.get("stage_id"):
            qs = qs.filter(stage_id=stage_id)
        if source := p.get("source"):
            qs = qs.filter(source=source)
        if owner_id := p.get("owner_id"):
            qs = qs.filter(owner_id=owner_id)
        if p.get("unread") == "1":
            qs = qs.filter(activities_count=0)
        sort = p.get("sort")
        if sort in ("created_at", "score", "value", "last_activity_at"):
            qs = qs.order_by(sort if p.get("direction") == "asc" else f"-{sort}")
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        if request.query_params.get("all"):
            return Response({"data": self.get_serializer(qs, many=True).data})
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def perform_create(self, serializer):
        if "stage" not in serializer.validated_data:
            serializer.validated_data["stage"] = PipelineStage.objects.get(slug="new")
        if not serializer.validated_data.get("owner"):
            serializer.validated_data["owner"] = self.request.user
        lead = serializer.save(last_activity_at=timezone.now())
        Activity.objects.create(lead=lead, user=self.request.user, type="system",
                                subject="Lead created manually", occurred_at=timezone.now())
        scoring.recalculate(lead)
        broadcast_lead(lead, "created")

    def update(self, request, *args, **kwargs):
        lead = self.get_object()
        old_stage_id = lead.stage_id
        serializer = self.get_serializer(lead, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        lead = serializer.save()
        new_stage_id = lead.stage_id
        if new_stage_id != old_stage_id:
            old_stage = PipelineStage.objects.get(pk=old_stage_id)
            new_stage = lead.stage
            Activity.objects.create(
                lead=lead, user=request.user, type="stage_change",
                subject=f"Stage changed: {old_stage.name} → {new_stage.name}",
                metadata={"from": old_stage_id, "to": new_stage_id}, occurred_at=timezone.now(),
            )
            lead.last_activity_at = timezone.now()
            lead.converted_at = timezone.now() if new_stage.is_won else None
            lead.save(update_fields=["last_activity_at", "converted_at"])
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


@api_view(["POST"])
def bulk_import_view(request):
    rows = request.data.get("leads", [])
    if not rows:
        return Response({"message": "No leads provided."}, status=422)
    stage = PipelineStage.objects.get(slug="new")
    created = 0
    for row in rows[:1000]:
        if not row.get("first_name"):
            continue
        lead = Lead.objects.create(
            first_name=row["first_name"], last_name=row.get("last_name", ""),
            email=row.get("email", ""), phone=row.get("phone", ""),
            job_title=row.get("job_title", ""),
            source=row.get("source", "import"), value=row.get("value") or 0,
            stage=stage, owner_id=row.get("owner_id") or request.user.id,
        )
        Activity.objects.create(lead=lead, user=request.user, type="system",
                                subject="Lead imported (bulk)", occurred_at=timezone.now())
        scoring.recalculate(lead)
        created += 1
    return Response({"message": f"{created} leads imported.", "count": created}, status=201)


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
        serializer = self.get_serializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
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
    won = PipelineStage.objects.filter(is_won=True).first()
    lost = PipelineStage.objects.filter(is_lost=True).first()
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
    for stage in PipelineStage.objects.all():
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
    won_id = PipelineStage.objects.filter(is_won=True).values_list("id", flat=True).first()
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
    won_id = PipelineStage.objects.filter(is_won=True).values_list("id", flat=True).first()
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
    elems = [Paragraph("Quibus LMS — Pipeline Report", styles["Title"]),
             Paragraph(f"Generated {timezone.now():%d %b %Y, %H:%M} by {request.user.name}", styles["Normal"]),
             Spacer(1, 16)]
    for stage in PipelineStage.objects.all():
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
