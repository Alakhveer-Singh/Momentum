"""Server-rendered HTML UI for Momentum (Django templates, no SPA).

Reads are rendered server-side from the ORM. Mutations are performed by small
fetch() calls in the page JS against the existing DRF /api endpoints (session
auth + CSRF). Realtime uses the Channels consumer, authenticated with a short
JWT embedded in the page.
"""

import base64
import datetime
import json
import random
import re
import secrets
import urllib.parse
import urllib.request
from email.mime.image import MIMEImage

from django.conf import settings
from django.core import signing
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Activity, Campaign, CampaignView, CustomerProfile, EmailTemplate, Lead, LeadSource, LoginActivity, PipelineStage, Product, Task, User, ensure_product_stages

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


_STAGE_TYPE_ORDER = ["entry", "middle", "won", "lost"]


def _ordered_stages(product=None):
    """Stages ordered the same way the Funnel page groups them (entry, middle, won, lost),
    so the Leads tabs/dropdowns match the Funnel page order. Scoped to a product's own
    funnel when given, otherwise the global (product=NULL) funnel."""
    if product is not None:
        ensure_product_stages(product)
        stages = list(product.pipeline_stages.all())
    else:
        stages = list(PipelineStage.objects.filter(product__isnull=True))
    return sorted(stages, key=lambda s: (_STAGE_TYPE_ORDER.index(s.stage_type) if s.stage_type in _STAGE_TYPE_ORDER else len(_STAGE_TYPE_ORDER), s.position))


def _base_ctx(request):
    user = request.user
    notifications = list(user.crm_notifications.all()[:20])
    unread = sum(1 for n in notifications if n.read_at is None)
    try:
        active_product_id = int(request.GET.get("product"))
    except (TypeError, ValueError):
        active_product_id = None
    return {
        "me": user,
        "ws_token": _ws_token(user),
        "notifications": notifications,
        "unread_count": unread,
        "nav_products": Product.objects.filter(is_active=True),
        "active_product_id": active_product_id,
    }


# --- Auth -------------------------------------------------------------------
OTP_TTL_MINUTES = 10


def _otp_email_html(code, intro):
    """A simple, Spotify-style verification email: logo, big code, short copy."""
    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 0;">
    <tr><td align="center">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;">
        <tr><td align="center" style="padding:36px 40px 8px;">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td style="vertical-align:middle;"><img src="cid:momentumlogo" alt="Momentum" width="36" style="height:36px;width:auto;display:block;" /></td>
            <td style="padding-left:10px;font-size:20px;font-weight:bold;color:#0f172a;">Momentum</td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:24px 40px 0;color:#111827;font-size:15px;line-height:1.6;">Hi,</td></tr>
        <tr><td style="padding:16px 40px 0;color:#111827;font-size:15px;line-height:1.6;">{intro}</td></tr>
        <tr><td style="padding:24px 40px;"><div style="font-size:40px;font-weight:bold;letter-spacing:6px;color:#0f172a;">{code}</div></td></tr>
        <tr><td style="padding:0 40px;color:#374151;font-size:14px;line-height:1.6;">This code is valid for {OTP_TTL_MINUTES} minutes and can only be used once.</td></tr>
        <tr><td style="padding:16px 40px 0;color:#6b7280;font-size:14px;line-height:1.6;">If you didn&#39;t request this, you can safely ignore this email.</td></tr>
        <tr><td style="padding:28px 40px 40px;color:#111827;font-size:14px;line-height:1.6;">Best regards,<br>Momentum</td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _send_otp(user, purpose="login"):
    """Generate a fresh 6-digit code, persist it with an expiry, and email it.

    Sends a styled HTML email (with a plain-text fallback). With no SMTP
    credentials configured, the console backend prints it to the server log."""
    code = f"{random.randint(0, 999999):06d}"
    user.otp_code = code
    user.otp_expires_at = timezone.now() + datetime.timedelta(minutes=OTP_TTL_MINUTES)
    user.save(update_fields=["otp_code", "otp_expires_at"])
    if purpose == "reset":
        subject = "Reset your Momentum password"
        intro = "Enter this code to reset your password:"
    else:
        subject = "Your Momentum verification code"
        intro = "Enter this code to continue logging in:"
    text_body = (
        f"{intro}\n\n{code}\n\n"
        f"This code is valid for {OTP_TTL_MINUTES} minutes and can only be used once.\n"
        "If you didn't request this, you can safely ignore this email."
    )
    msg = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    msg.attach_alternative(_otp_email_html(code, intro), "text/html")
    _attach_logo(msg)
    msg.send(fail_silently=True)
    return code


def _attach_logo(msg):
    """Embed the logo inline (CID) so it renders in real inboxes — email clients
    can't load images from localhost/static URLs."""
    try:
        logo_path = settings.BASE_DIR / "static" / "img" / "momentum-logo-email.png"
        with open(logo_path, "rb") as f:
            logo = MIMEImage(f.read())
        logo.add_header("Content-ID", "<momentumlogo>")
        logo.add_header("Content-Disposition", "inline", filename="momentum.png")
        msg.attach(logo)
    except OSError:
        pass


def _magic_email_html(link):
    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 0;">
    <tr><td align="center">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;">
        <tr><td align="center" style="padding:36px 40px 8px;">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td style="vertical-align:middle;"><img src="cid:momentumlogo" alt="Momentum" width="36" style="height:36px;width:auto;display:block;" /></td>
            <td style="padding-left:10px;font-size:20px;font-weight:bold;color:#0f172a;">Momentum</td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:24px 40px 0;color:#111827;font-size:15px;line-height:1.6;">Hi,</td></tr>
        <tr><td style="padding:16px 40px 0;color:#111827;font-size:15px;line-height:1.6;">Click the button below to sign in to Momentum. No password needed.</td></tr>
        <tr><td style="padding:24px 40px;"><a href="{link}" style="display:inline-block;background:#0f172a;color:#ffffff;text-decoration:none;font-size:15px;font-weight:bold;padding:13px 28px;border-radius:10px;">Sign in to Momentum</a></td></tr>
        <tr><td style="padding:0 40px;color:#374151;font-size:14px;line-height:1.6;">This link is valid for 15 minutes and can only be used once.</td></tr>
        <tr><td style="padding:16px 40px 0;color:#6b7280;font-size:13px;line-height:1.6;word-break:break-all;">Or paste this URL into your browser:<br>{link}</td></tr>
        <tr><td style="padding:16px 40px 0;color:#6b7280;font-size:14px;line-height:1.6;">If you didn&#39;t request this, you can safely ignore this email.</td></tr>
        <tr><td style="padding:28px 40px 40px;color:#111827;font-size:14px;line-height:1.6;">Best regards,<br>Momentum</td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _otp_valid(user, code):
    return bool(
        code
        and user.otp_code
        and user.otp_code == code
        and user.otp_expires_at
        and user.otp_expires_at > timezone.now()
    )


def _clear_otp(user):
    user.otp_code = ""
    user.otp_expires_at = None
    user.save(update_fields=["otp_code", "otp_expires_at"])


def _read_code(request):
    """Read the joined hidden field, falling back to six individual digit boxes."""
    code = (request.POST.get("code", "") or "").strip()
    if not code:
        code = "".join((request.POST.get(f"d{i}", "") or "").strip() for i in range(6))
    return code


def _login_render(request, **extra):
    """Render the login page, always including whether Google sign-in is available."""
    return render(request, "login.html", {"google_enabled": bool(settings.GOOGLE_CLIENT_ID), **extra})


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
            return _login_render(request, error="Invalid credentials.", email=email)
        if not user.check_password(password):
            LoginActivity.objects.create(email=email, ip_address=ip, user_agent=ua, success=False, reason="Invalid credentials")
            return _login_render(request, error="Invalid credentials.", email=email)
        if not user.is_active:
            LoginActivity.objects.create(email=email, ip_address=ip, user_agent=ua, success=False, reason="Account deactivated", user=user)
            admin = User.objects.filter(role="admin").first()
            admin_email = admin.email if admin else "admin@quibus.in"
            admin_phone = admin.phone if admin else "N/A"
            error_msg = f"Your account has been suspended by the Super Admin. If you think we made a mistake and would like to turn your account back on, please contact the Super Admin ({admin_email}, {admin_phone})"
            return _login_render(request, error=error_msg, email=email)
        # Credentials OK → start 2FA: send a code and hold login until verified.
        _send_otp(user, purpose="login")
        request.session["pending_2fa_uid"] = user.id
        return redirect("/login/verify")
    return _login_render(request)


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def google_login_start(request):
    if not settings.GOOGLE_CLIENT_ID:
        return _login_render(request, error="Google sign-in isn't configured.")
    state = secrets.token_urlsafe(24)
    request.session["google_oauth_state"] = state
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return redirect(GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params))


def google_login_callback(request):
    if not settings.GOOGLE_CLIENT_ID:
        return _login_render(request, error="Google sign-in isn't configured.")
    if request.GET.get("state") != request.session.pop("google_oauth_state", None):
        return _login_render(request, error="Google sign-in failed (state mismatch). Please try again.")
    code = request.GET.get("code")
    if not code:
        return _login_render(request, error="Google sign-in was cancelled.")
    try:
        data = urllib.parse.urlencode({
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }).encode()
        with urllib.request.urlopen(urllib.request.Request(GOOGLE_TOKEN_URL, data=data), timeout=10) as r:
            access_token = json.load(r).get("access_token")
        req = urllib.request.Request(GOOGLE_USERINFO_URL, headers={"Authorization": "Bearer " + access_token})
        with urllib.request.urlopen(req, timeout=10) as r:
            info = json.load(r)
    except Exception:
        return _login_render(request, error="Could not verify your Google account. Please try again.")

    email = (info.get("email") or "").lower()
    if not email or not info.get("email_verified", True):
        return _login_render(request, error="Your Google email could not be verified.")
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return _login_render(request, error=f"No Momentum account exists for {email}. Ask an admin to add you first.")
    if not user.is_active:
        return _login_render(request, error="Your account is suspended. Please contact the Super Admin.")
    ip = request.META.get("REMOTE_ADDR", "")
    ua = request.META.get("HTTP_USER_AGENT", "")
    LoginActivity.objects.create(email=email, ip_address=ip, user_agent=ua, success=True, user=user)
    login(request, user)  # Google federates identity, so 2FA OTP is skipped here
    return redirect("/")


# --- Magic link (passwordless email sign-in) --------------------------------
MAGIC_SALT = "momentum-magic-login"
MAGIC_TTL_SECONDS = 15 * 60


def magic_link_request(request):
    if request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        email = (request.POST.get("email", "") or "").strip()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            token = signing.dumps({"uid": user.id}, salt=MAGIC_SALT)
            link = f"{settings.SITE_URL}/login/magic/verify?token={urllib.parse.quote(token)}"
            html = _magic_email_html(link)
            text = f"Click to sign in to Momentum:\n\n{link}\n\nThis link expires in 15 minutes. If you didn't request it, ignore this email."
            msg = EmailMultiAlternatives("Your Momentum sign-in link", text, settings.DEFAULT_FROM_EMAIL, [user.email])
            msg.attach_alternative(html, "text/html")
            _attach_logo(msg)
            msg.send(fail_silently=True)
        # Always show the same confirmation (don't reveal whether the email exists).
        return render(request, "magic_link.html", {"sent": True, "email": email})
    return render(request, "magic_link.html", {})


def magic_link_verify(request):
    token = request.GET.get("token", "")
    try:
        data = signing.loads(token, salt=MAGIC_SALT, max_age=MAGIC_TTL_SECONDS)
    except signing.SignatureExpired:
        return _login_render(request, error="That sign-in link has expired. Please request a new one.")
    except signing.BadSignature:
        return _login_render(request, error="That sign-in link is invalid.")
    user = User.objects.filter(id=data.get("uid"), is_active=True).first()
    if not user:
        return _login_render(request, error="Account not found or inactive.")
    ip = request.META.get("REMOTE_ADDR", "")
    ua = request.META.get("HTTP_USER_AGENT", "")
    LoginActivity.objects.create(email=user.email, ip_address=ip, user_agent=ua, success=True, user=user)
    login(request, user)  # link possession proves the email, so 2FA is satisfied
    return redirect("/")


# --- Phone OTP (SMS / WhatsApp) ---------------------------------------------
def _normalize_phone(raw):
    p = re.sub(r"[^\d+]", "", raw or "")
    if not p:
        return ""
    if p.startswith("+"):
        return p
    if len(p) == 10:  # bare local number → assume default country
        return settings.DEFAULT_PHONE_COUNTRY_CODE + p
    return "+" + p


def _send_sms(phone, body):
    """Send via Twilio (WhatsApp if configured, else SMS). Falls back to the
    server log when no Twilio credentials are set, so the flow works in dev."""
    sid, tok = settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
    use_wa = bool(settings.TWILIO_WHATSAPP_FROM)
    frm = settings.TWILIO_WHATSAPP_FROM or settings.TWILIO_FROM
    if not (sid and tok and frm):
        print(f"[DEV SMS → {phone}] {body}", flush=True)
        return
    to = ("whatsapp:" + phone) if use_wa else phone
    sender = ("whatsapp:" + frm) if (use_wa and not frm.startswith("whatsapp:")) else frm
    data = urllib.parse.urlencode({"To": to, "From": sender, "Body": body}).encode()
    req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=data)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{sid}:{tok}".encode()).decode())
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def _send_phone_otp(user):
    code = f"{random.randint(0, 999999):06d}"
    user.otp_code = code
    user.otp_expires_at = timezone.now() + datetime.timedelta(minutes=OTP_TTL_MINUTES)
    user.save(update_fields=["otp_code", "otp_expires_at"])
    _send_sms(user.phone, f"Your Momentum verification code is {code}. It expires in {OTP_TTL_MINUTES} minutes.")
    return code


def phone_login(request):
    if request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        phone = _normalize_phone(request.POST.get("phone", ""))
        user = None
        if phone:
            for u in User.objects.filter(is_active=True).exclude(phone=""):
                if _normalize_phone(u.phone) == phone:
                    user = u
                    break
        if not user:
            return render(request, "phone_login.html", {"error": "No account found with that phone number.", "phone": request.POST.get("phone", "")})
        _send_phone_otp(user)
        request.session["pending_phone_uid"] = user.id
        return redirect("/login/phone/verify")
    return render(request, "phone_login.html", {})


def phone_verify(request):
    uid = request.session.get("pending_phone_uid")
    user = User.objects.filter(id=uid).first() if uid else None
    if not user:
        return redirect("/login/phone")
    masked = "•••••" + (user.phone[-3:] if user.phone else "")
    ctx = {"phone_masked": masked}
    if request.method == "POST":
        if request.POST.get("action") == "resend":
            _send_phone_otp(user)
            return render(request, "phone_verify.html", {**ctx, "info": "A new code has been sent."})
        if _otp_valid(user, _read_code(request)):
            _clear_otp(user)
            request.session.pop("pending_phone_uid", None)
            ip = request.META.get("REMOTE_ADDR", "")
            ua = request.META.get("HTTP_USER_AGENT", "")
            LoginActivity.objects.create(email=user.email, ip_address=ip, user_agent=ua, success=True, user=user)
            login(request, user)
            return redirect("/")
        return render(request, "phone_verify.html", {**ctx, "error": "Invalid or expired code."})
    return render(request, "phone_verify.html", ctx)


def verify_login_otp(request):
    uid = request.session.get("pending_2fa_uid")
    user = User.objects.filter(id=uid).first() if uid else None
    if not user:
        return redirect("/login")
    ctx = {"email": user.email}
    if request.method == "POST":
        if request.POST.get("action") == "resend":
            _send_otp(user, purpose="login")
            return render(request, "verify_otp.html", {**ctx, "info": "A new code has been sent."})
        if _otp_valid(user, _read_code(request)):
            _clear_otp(user)
            request.session.pop("pending_2fa_uid", None)
            ip = request.META.get("REMOTE_ADDR", "")
            ua = request.META.get("HTTP_USER_AGENT", "")
            LoginActivity.objects.create(email=user.email, ip_address=ip, user_agent=ua, success=True, user=user)
            login(request, user)
            return redirect("/")
        return render(request, "verify_otp.html", {**ctx, "error": "Invalid or expired code."})
    return render(request, "verify_otp.html", ctx)


def forgot_password(request):
    if request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        email = request.POST.get("email", "")
        user = User.objects.filter(email=email).first()
        if not user:
            return render(request, "forgot_password.html", {"error": "No account found with that email.", "email": email})
        _send_otp(user, purpose="reset")
        request.session["pending_reset_uid"] = user.id
        return redirect("/reset-password")
    return render(request, "forgot_password.html", {})


def reset_password(request):
    uid = request.session.get("pending_reset_uid")
    user = User.objects.filter(id=uid).first() if uid else None
    if not user:
        return redirect("/forgot")
    ctx = {"email": user.email}
    if request.method == "POST":
        if request.POST.get("action") == "resend":
            _send_otp(user, purpose="reset")
            return render(request, "reset_password.html", {**ctx, "info": "A new code has been sent."})
        code = _read_code(request)
        pw = request.POST.get("password", "")
        pw2 = request.POST.get("password2", "")
        if not _otp_valid(user, code):
            return render(request, "reset_password.html", {**ctx, "error": "Invalid or expired code."})
        if len(pw) < 8:
            return render(request, "reset_password.html", {**ctx, "error": "Password must be at least 8 characters."})
        if pw != pw2:
            return render(request, "reset_password.html", {**ctx, "error": "Passwords do not match."})
        user.set_password(pw)
        user.otp_code = ""
        user.otp_expires_at = None
        user.save()  # full save so the new password is persisted alongside cleared OTP
        request.session.pop("pending_reset_uid", None)
        return redirect("/login?reset=1")
    return render(request, "reset_password.html", ctx)


def logout_view(request):
    logout(request)
    return redirect("/login")


# --- Dashboard --------------------------------------------------------------
@login_required
def dashboard(request):
    user = request.user
    won = PipelineStage.objects.filter(product__isnull=True, is_won=True).first()
    lost = PipelineStage.objects.filter(product__isnull=True, is_lost=True).first()
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
    user = request.user
    stages = list(PipelineStage.objects.filter(product__isnull=True))
    leads = _lead_scope(user).select_related("stage", "owner")
    by_stage = {s.id: [] for s in stages}
    totals = {s.id: 0.0 for s in stages}
    for lead in leads:
        by_stage.setdefault(lead.stage_id, []).append(lead)
        totals[lead.stage_id] = totals.get(lead.stage_id, 0) + float(lead.value)
    cols = [{"stage": s, "leads": by_stage.get(s.id, []), "total": totals.get(s.id, 0)} for s in stages]
    ctx = {
        **_base_ctx(request), "active": "pipeline", "cols": cols, "stages": stages,
        "sources": SOURCES,
        "products": Product.objects.filter(is_active=True),
        "profiles": CustomerProfile.objects.filter(is_active=True),
        "users": User.objects.filter(is_active=True) if user.role != "rep" else [],
        "can_assign": user.role != "rep",
        "can_delete": user.is_manager_or_admin,
    }
    return render(request, "pipeline.html", ctx)


# --- Leads ------------------------------------------------------------------
@login_required
def leads(request):
    user = request.user
    qs = _lead_scope(user).select_related("stage", "owner").prefetch_related("products")
    count_scope = _lead_scope(user)  # separate scope for stage counts — no annotation to avoid GROUP BY fan-out
    search = request.GET.get("search", "").strip()
    selected_sources = [s for s in request.GET.getlist("source") if s]
    tab = request.GET.get("tab", "")  # '', 'unread', or stage id
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    # Default to last 7 days if no date filter provided
    if not date_from and not date_to:
        date_from = (timezone.now() - datetime.timedelta(days=6)).strftime("%Y-%m-%d")
        date_to = timezone.now().strftime("%Y-%m-%d")

    if search:
        sf = Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search)
        qs = qs.filter(sf)
        count_scope = count_scope.filter(sf)
    if selected_sources:
        qs = qs.filter(source__in=selected_sources)
        count_scope = count_scope.filter(source__in=selected_sources)
    product_id = request.GET.get("product")
    funnel_product = None
    if product_id:
        try:
            funnel_product = Product.objects.filter(pk=int(product_id)).first()
            qs = qs.filter(product_id=int(product_id))
            count_scope = count_scope.filter(product_id=int(product_id))
        except (ValueError, TypeError):
            pass
    if date_from:
        try:
            dt_from = timezone.datetime.fromisoformat(date_from).replace(tzinfo=datetime.timezone.utc)
            qs = qs.filter(created_at__gte=dt_from)
            count_scope = count_scope.filter(created_at__gte=dt_from)
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            dt_to = timezone.datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59, tzinfo=datetime.timezone.utc)
            qs = qs.filter(created_at__lte=dt_to)
            count_scope = count_scope.filter(created_at__lte=dt_to)
        except (ValueError, TypeError):
            pass
    if tab:
        qs = qs.filter(stage_id=tab)
    sort = request.GET.get("sort", "created_at")
    direction = request.GET.get("direction", "desc")
    sort_field = {"created_at": "created_at", "updated_at": "updated_at", "name": "first_name"}.get(sort, "created_at")
    qs = qs.order_by(sort_field if direction == "asc" else f"-{sort_field}")
    # Rows per page — user-controllable via the "Show N per page" box.
    try:
        page_size = int(request.GET.get("page_size", 10))
    except (TypeError, ValueError):
        page_size = 10
    page_size = max(1, min(page_size, 500))
    paginator = Paginator(qs, page_size)
    page = paginator.get_page(request.GET.get("page", 1))
    page_range = paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)
    # Preserve active filters (everything but the page number) on pagination links.
    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()

    # Tabs/pills follow the selected product's own funnel (or the global one).
    stages = _ordered_stages(funnel_product)
    counts = {s.id: 0 for s in stages}
    all_count = 0
    for row in count_scope.values("stage_id").annotate(c=Count("id")):
        all_count += row["c"]
        if row["stage_id"] in counts:
            counts[row["stage_id"]] = row["c"]
    ctx = {
        **_base_ctx(request), "active": "leads", "page_obj": page,
        "page_size": page_size, "page_range": page_range, "querystring": querystring,
        "stages": stages, "stage_counts": counts, "all_count": all_count,
        "search": search, "selected_sources": selected_sources, "tab": tab, "sources": SOURCES,
        "date_from": date_from, "date_to": date_to,
        "products": Product.objects.filter(is_active=True),
        "profiles": CustomerProfile.objects.filter(is_active=True),
        "users": User.objects.filter(is_active=True) if user.role != "rep" else [],
        "can_assign": user.role != "rep",
        "can_delete": user.is_manager_or_admin,
    }
    return render(request, "leads.html", ctx)


@login_required
def lead_detail(request, pk):
    user = request.user
    lead = get_object_or_404(Lead.objects.select_related("stage", "owner", "product"), pk=pk, deleted_at__isnull=True)
    if user.role == "rep" and lead.owner_id != user.id:
        return redirect("/leads")
    all_stages = _ordered_stages(lead.product)
    visible_stages = []
    for s in all_stages:
        visible_stages.append(s)
        if s.id == lead.stage_id:
            break
    ctx = {
        **_base_ctx(request), "active": "leads", "lead": lead,
        "activities": lead.activities.select_related("user").all(),
        "tasks": lead.tasks.all(),
        "stages": all_stages,
        "visible_stages": visible_stages,
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
    qs = list(qs.order_by("due_at"))
    tasks_json = [
        {
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "status": t.status,
            "due_at": t.due_at.isoformat() if t.due_at else None,
            "lead_id": t.lead_id,
            "lead_name": f"{t.lead.first_name} {t.lead.last_name}" if t.lead_id else None,
        }
        for t in qs
    ]
    ctx = {
        **_base_ctx(request), "active": "tasks", "tasks": qs, "filter": f,
        "now": timezone.now(), "tasks_json": tasks_json,
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
    for stage in PipelineStage.objects.filter(product__isnull=True):
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
        won_id = PipelineStage.objects.filter(product__isnull=True, is_won=True).values_list("id", flat=True).first()
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
@user_passes_test(_is_admin, login_url="/login")
def funnel(request):
    # Product-wise funnel: a product must be selected first. Each product owns its
    # own stages, so edits here never affect any other product's funnel.
    selected_product = None
    product_id = request.GET.get("product")
    if product_id:
        try:
            selected_product = Product.objects.filter(pk=int(product_id)).first()
        except (ValueError, TypeError):
            selected_product = None

    sections, counts = [], {}
    if selected_product:
        ensure_product_stages(selected_product)
        stages = list(selected_product.pipeline_stages.all())
        sections = [
            ("entry", "Top", [s for s in stages if s.stage_type == "entry"]),
            ("middle", "Middle", [s for s in stages if s.stage_type == "middle"]),
            ("won", "Bottom", [s for s in stages if s.stage_type == "won"]),
        ]
        counts = {s.id: 0 for s in stages}
        leads_qs = Lead.objects.filter(deleted_at__isnull=True, product_id=selected_product.id)
        for row in leads_qs.values("stage_id").annotate(c=Count("id")):
            if row["stage_id"] in counts:
                counts[row["stage_id"]] = row["c"]
    ctx = {
        **_base_ctx(request), "active": "funnel", "sections": sections, "can_edit": True,
        "stage_counts": counts, "products": Product.objects.filter(is_active=True),
        "selected_product": selected_product,
    }
    return render(request, "funnel.html", ctx)


# --- Source Master ----------------------------------------------------------


@user_passes_test(_is_admin, login_url="/login")
def source_master(request):
    ctx = {
        **_base_ctx(request), "active": "sources",
        "sources": LeadSource.objects.all(),
    }
    return render(request, "source_master.html", ctx)


@user_passes_test(_is_admin, login_url="/login")
def products_page(request):
    ctx = {
        **_base_ctx(request), "active": "products",
        "products": Product.objects.all(),
    }
    return render(request, "products.html", ctx)


@user_passes_test(_is_admin, login_url="/login")
def masters_hub(request):
    ctx = {**_base_ctx(request), "active": "masters"}
    return render(request, "masters_hub.html", ctx)


@user_passes_test(_is_admin, login_url="/login")
def customer_profiles_page(request):
    ctx = {
        **_base_ctx(request), "active": "masters",
        "profiles": CustomerProfile.objects.all(),
    }
    return render(request, "customer_profiles.html", ctx)


# --- Students (Won leads) ---------------------------------------------------
@login_required
def students(request):
    qs = _lead_scope(request.user).select_related("stage", "owner", "product").filter(stage__is_won=True)
    search = request.GET.get("search", "").strip()
    product_obj = None
    product_id = request.GET.get("product")
    if product_id:
        try:
            product_obj = Product.objects.filter(pk=int(product_id)).first()
            qs = qs.filter(product_id=int(product_id))
        except (ValueError, TypeError):
            pass
    if search:
        qs = qs.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(phone__icontains=search))
    qs = qs.order_by("-converted_at", "-created_at")

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page", 1))
    page_range = paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)
    params = request.GET.copy()
    params.pop("page", None)
    querystring = params.urlencode()
    ctx = {
        **_base_ctx(request), "active": "students", "page_obj": page,
        "total": paginator.count, "search": search, "product_obj": product_obj,
        "page_range": page_range, "querystring": querystring,
    }
    return render(request, "students.html", ctx)


@login_required
def student_detail(request, pk):
    lead = get_object_or_404(
        _lead_scope(request.user).select_related("stage", "owner", "product"), pk=pk
    )
    ctx = {
        **_base_ctx(request), "active": "students", "lead": lead,
        "custom_fields": list((lead.custom_fields or {}).items()),
    }
    return render(request, "student_detail.html", ctx)


# --- Profile ----------------------------------------------------------------
@login_required
def profile(request):
    ctx = {**_base_ctx(request), "active": "profile"}
    return render(request, "profile.html", ctx)


@login_required
def profile_avatar(request):
    if request.method == "POST" and request.FILES.get("avatar"):
        f = request.FILES["avatar"]
        if f.content_type.startswith("image/") and f.size <= 5 * 1024 * 1024:
            request.user.avatar = f
            request.user.save(update_fields=["avatar"])
    return redirect("/profile")


# --- Campaigns (SMS/WhatsApp for team) ----------------------------------------
@user_passes_test(_is_admin, login_url="/login")
def campaigns_page(request):
    ctx = {**_base_ctx(request), "active": "campaigns"}
    return render(request, "campaigns.html", ctx)


@login_required
def campaigns_team_page(request):
    ctx = {**_base_ctx(request), "active": "campaigns"}
    return render(request, "campaigns_team.html", ctx)
