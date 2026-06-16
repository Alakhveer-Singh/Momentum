"""Server-rendered HTML UI for Quibus LMS (Django templates, no SPA).

Reads are rendered server-side from the ORM. Mutations are performed by small
fetch() calls in the page JS against the existing DRF /api endpoints (session
auth + CSRF). Realtime uses the Channels consumer, authenticated with a short
JWT embedded in the page.
"""

import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Activity, EmailTemplate, Lead, LoginActivity, PipelineStage, Task, User

SOURCES = [
    "web_form", "referral", "google_ads", "facebook_ads",
    "cold_call", "linkedin", "manual", "import",
]


def _ws_token(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    return str(refresh.access_token)


def _lead_scope(user):
    qs = Lead.objects.filter(deleted_at__isnull=True)
    return qs.filter(owner=user) if user.role == "rep" else qs


def _base_ctx(request):
    user = request.user
    unread = user.crm_notifications.filter(read_at__isnull=True).count()
    return {
        "me": user,
        "ws_token": _ws_token(user),
        "notifications": user.crm_notifications.all()[:20],
        "unread_count": unread,
    }


# --- Auth -------------------------------------------------------------------
def login_page(request):
    if request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        email = request.POST.get("email", "")
        password = request.POST.get("password", "")
        ip = request.META.get("REMOTE_ADDR", "")
        ua = request.META.get("HTTP_USER_AGENT", "")
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            LoginActivity.objects.create(email=email, ip_address=ip, user_agent=ua, success=False, reason="Invalid credentials")
            return render(request, "login.html", {"error": "Invalid credentials.", "email": email})
        if not user.check_password(password):
            LoginActivity.objects.create(email=email, ip_address=ip, user_agent=ua, success=False, reason="Invalid credentials")
            return render(request, "login.html", {"error": "Invalid credentials.", "email": email})
        if not user.is_active:
            LoginActivity.objects.create(email=email, ip_address=ip, user_agent=ua, success=False, reason="Account deactivated", user=user)
            admin = User.objects.filter(role="admin").first()
            admin_email = admin.email if admin else "admin@quibus.in"
            admin_phone = admin.phone if admin else "N/A"
            error_msg = f"Your account has been suspended by the Super Admin. If you think we made a mistake and would like to turn your account back on, please contact the Super Admin ({admin_email}, {admin_phone})"
            return render(request, "login.html", {"error": error_msg, "email": email})
        LoginActivity.objects.create(email=email, ip_address=ip, user_agent=ua, success=True, user=user)
        login(request, user)
        return redirect("/")
    return render(request, "login.html", {})


def logout_view(request):
    logout(request)
    return redirect("/login")


# --- Dashboard --------------------------------------------------------------
@login_required
def dashboard(request):
    user = request.user
    won = PipelineStage.objects.filter(is_won=True).first()
    lost = PipelineStage.objects.filter(is_lost=True).first()
    open_ids = list(PipelineStage.objects.filter(is_won=False, is_lost=False).values_list("id", flat=True))
    won_c = _lead_scope(user).filter(stage=won).count()
    lost_c = _lead_scope(user).filter(stage=lost).count()
    closed = won_c + lost_c
    ptasks = Task.objects.filter(status="pending")
    if user.role == "rep":
        ptasks = ptasks.filter(assigned_to=user)
    stats = {
        "total_leads": _lead_scope(user).count(),
        "open_leads": _lead_scope(user).filter(stage_id__in=open_ids).count(),
        "won_leads": won_c,
        "lost_leads": lost_c,
        "conversion_rate": round(won_c / closed * 100, 1) if closed else 0,
        "won_number": won_c,
        "new_this_week": _lead_scope(user).filter(created_at__gte=timezone.now() - timezone.timedelta(days=7)).count(),
        "avg_score": round(_lead_scope(user).aggregate(a=Avg("score"))["a"] or 0, 1),
        "pending_followups": ptasks.count(),
        "overdue_followups": ptasks.filter(due_at__lt=timezone.now()).count(),
    }
    tasks = Task.objects.select_related("lead", "assigned_to").filter(status="pending")
    if user.role == "rep":
        tasks = tasks.filter(assigned_to=user)
    tasks = tasks.order_by("due_at")[:5]
    activities = Activity.objects.select_related("lead", "user")
    if user.role == "rep":
        activities = activities.filter(lead__owner=user)
    activities = activities[:8]
    ctx = {**_base_ctx(request), "active": "dashboard", "stats": stats,
           "tasks": tasks, "activities": activities}
    return render(request, "dashboard.html", ctx)


# --- Pipeline ---------------------------------------------------------------
@login_required
def pipeline(request):
    stages = list(PipelineStage.objects.all())
    leads = _lead_scope(request.user).select_related("stage", "owner")
    by_stage = {s.id: [] for s in stages}
    totals = {s.id: 0.0 for s in stages}
    for lead in leads:
        by_stage.setdefault(lead.stage_id, []).append(lead)
        totals[lead.stage_id] = totals.get(lead.stage_id, 0) + float(lead.value)
    cols = [{"stage": s, "leads": by_stage.get(s.id, []), "total": totals.get(s.id, 0)} for s in stages]
    ctx = {**_base_ctx(request), "active": "pipeline", "cols": cols}
    return render(request, "pipeline.html", ctx)


# --- Leads ------------------------------------------------------------------
@login_required
def leads(request):
    user = request.user
    qs = _lead_scope(user).select_related("stage", "owner").annotate(
        activities_count=Count("activities", distinct=True),
    )
    search = request.GET.get("search", "").strip()
    source = request.GET.get("source", "")
    tab = request.GET.get("tab", "")  # '', 'unread', or stage id
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search) | Q(last_name__icontains=search)
            | Q(email__icontains=search)
        )
    if source:
        qs = qs.filter(source=source)
    if date_from:
        try:
            qs = qs.filter(created_at__gte=timezone.datetime.fromisoformat(date_from).replace(tzinfo=datetime.timezone.utc))
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            qs = qs.filter(created_at__lte=timezone.datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59, tzinfo=datetime.timezone.utc))
        except (ValueError, TypeError):
            pass
    if tab == "unread":
        qs = qs.filter(activities_count=0)
    elif tab:
        qs = qs.filter(stage_id=tab)
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page", 1))

    stages = list(PipelineStage.objects.all())
    counts = {s.id: 0 for s in stages}
    for row in _lead_scope(user).values("stage_id").annotate(c=Count("id")):
        counts[row["stage_id"]] = row["c"]
    unread_count = _lead_scope(user).annotate(ac=Count("activities")).filter(ac=0).count()
    ctx = {
        **_base_ctx(request), "active": "leads", "page_obj": page,
        "stages": stages, "stage_counts": counts, "unread_count": unread_count,
        "search": search, "source": source, "tab": tab, "sources": SOURCES,
        "date_from": date_from, "date_to": date_to,
        "users": User.objects.filter(is_active=True) if user.role != "rep" else [],
        "can_assign": user.role != "rep",
        "can_delete": user.is_manager_or_admin,
    }
    return render(request, "leads.html", ctx)


@login_required
def lead_detail(request, pk):
    user = request.user
    lead = get_object_or_404(Lead.objects.select_related("stage", "owner"), pk=pk, deleted_at__isnull=True)
    if user.role == "rep" and lead.owner_id != user.id:
        return redirect("/leads")
    ctx = {
        **_base_ctx(request), "active": "leads", "lead": lead,
        "activities": lead.activities.select_related("user").all(),
        "tasks": lead.tasks.all(),
        "stages": PipelineStage.objects.all(),
        "templates": EmailTemplate.objects.all(),
        "custom_fields": (lead.custom_fields or {}).items() if lead.custom_fields else [],
        "can_delete": user.is_manager_or_admin,
        "can_assign": user.role != "rep",
        "users": User.objects.filter(is_active=True) if user.role != "rep" else [],
        "lead_json": {
            "id": lead.id, "first_name": lead.first_name, "last_name": lead.last_name,
            "phone": lead.phone, "email": lead.email, "source": lead.source,
            "stage_id": lead.stage_id, "owner_id": lead.owner_id,
            "custom_fields": lead.custom_fields or {}, "notes": lead.notes,
        },
    }
    return render(request, "lead_detail.html", ctx)


# --- Tasks ------------------------------------------------------------------
@login_required
def tasks(request):
    user = request.user
    f = request.GET.get("filter", "pending")
    qs = Task.objects.select_related("lead", "assigned_to")
    if user.role == "rep":
        qs = qs.filter(assigned_to=user)
    if f == "overdue":
        qs = qs.filter(status="pending", due_at__lt=timezone.now())
    elif f in ("pending", "completed"):
        qs = qs.filter(status=f)
    qs = qs.order_by("due_at")
    ctx = {
        **_base_ctx(request), "active": "tasks", "tasks": qs, "filter": f,
        "now": timezone.now(),
        "filters": [("pending", "Pending"), ("overdue", "Overdue"),
                    ("completed", "Completed"), ("", "All")],
        "users": User.objects.filter(is_active=True) if user.role != "rep" else [],
        "can_assign": user.role != "rep",
    }
    return render(request, "tasks.html", ctx)


# --- Email templates --------------------------------------------------------
@login_required
def templates_page(request):
    ctx = {**_base_ctx(request), "active": "templates",
           "templates": EmailTemplate.objects.select_related("created_by").all()}
    return render(request, "templates.html", ctx)


# --- Reports ----------------------------------------------------------------
@login_required
def reports(request):
    user = request.user
    is_manager = user.role != "rep"
    pipeline_rows = []
    for stage in PipelineStage.objects.all():
        sleads = stage.leads.filter(deleted_at__isnull=True)
        if user.role == "rep":
            sleads = sleads.filter(owner=user)
        pipeline_rows.append({
            "name": stage.name, "color": stage.color,
            "leads_count": sleads.count(),
            "total_value": float(sleads.aggregate(s=Sum("value"))["s"] or 0),
        })
    max_stage = max([r["leads_count"] for r in pipeline_rows] + [1])
    for r in pipeline_rows:
        r["pct"] = r["leads_count"] / max_stage * 100

    trend_rows = (
        Lead.objects.filter(deleted_at__isnull=True, created_at__gte=timezone.now() - timezone.timedelta(days=183))
        .annotate(m=TruncMonth("created_at")).values("m")
        .annotate(leads=Count("id"), won=Count("id", filter=Q(converted_at__isnull=False)))
        .order_by("m")
    )
    trend = [{"month": r["m"].strftime("%Y-%m"), "label": r["m"].strftime("%m"),
              "leads": r["leads"], "won": r["won"]} for r in trend_rows]
    max_trend = max([t["leads"] for t in trend] + [1])
    for t in trend:
        t["leads_pct"] = t["leads"] / max_trend * 100
        t["won_pct"] = t["won"] / max_trend * 100

    sources, team = [], []
    if is_manager:
        won_id = PipelineStage.objects.filter(is_won=True).values_list("id", flat=True).first()
        for r in (Lead.objects.filter(deleted_at__isnull=True).values("source").annotate(
                total=Count("id"), won=Count("id", filter=Q(stage_id=won_id)),
                won_value=Sum("value", filter=Q(stage_id=won_id))).order_by("-total")):
            r["won_value"] = float(r["won_value"] or 0)
            r["conversion_rate"] = round(r["won"] / r["total"] * 100, 1) if r["total"] else 0
            sources.append(r)
        for u in User.objects.filter(is_active=True):
            ul = Lead.objects.filter(owner=u, deleted_at__isnull=True)
            won_leads = ul.filter(stage_id=won_id).count()
            total = ul.count()
            team.append({
                "name": u.name, "role": u.role, "total_leads": total, "won_leads": won_leads,
                "won_value": float(ul.filter(stage_id=won_id).aggregate(s=Sum("value"))["s"] or 0),
                "activities_30d": Activity.objects.filter(user=u, occurred_at__gte=timezone.now() - timezone.timedelta(days=30)).count(),
                "pct": (won_leads / total * 100) if total else 0,
            })
    ctx = {**_base_ctx(request), "active": "reports", "is_manager": is_manager,
           "pipeline_rows": pipeline_rows, "trend": trend, "sources": sources, "team": team}
    return render(request, "reports.html", ctx)


# --- Users (admin) ----------------------------------------------------------
def _is_admin(u):
    return u.is_authenticated and u.role == "admin"


@user_passes_test(_is_admin, login_url="/login")
def users_page(request):
    rows = User.objects.annotate(
        leads_count=Count("leads", distinct=True),
        tasks_count=Count("tasks", distinct=True),
    ).order_by("name")
    ctx = {**_base_ctx(request), "active": "users", "users": rows}
    return render(request, "users.html", ctx)


# --- Funnel -----------------------------------------------------------------
@login_required
def funnel(request):
    stages = list(PipelineStage.objects.all())
    ctx = {
        **_base_ctx(request), "active": "funnel",
        "entry": [s for s in stages if s.stage_type == "entry"],
        "middle": [s for s in stages if s.stage_type == "middle"],
        "won": [s for s in stages if s.stage_type == "won"],
        "lost": [s for s in stages if s.stage_type == "lost"],
        "can_edit": request.user.role in ("admin", "manager"),
    }
    return render(request, "funnel.html", ctx)


# --- Profile ----------------------------------------------------------------
@login_required
def profile(request):
    ctx = {**_base_ctx(request), "active": "profile"}
    return render(request, "profile.html", ctx)
