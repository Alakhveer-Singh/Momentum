from django import template

register = template.Library()


def _indian_group(n: int) -> str:
    s = str(abs(int(n)))
    if len(s) <= 3:
        head, tail = s, ""
    else:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        parts.insert(0, head)
        head = ",".join(parts)
    out = f"{head},{tail}" if tail and len(s) > 3 else (head if not tail else head)
    return ("-" if n < 0 else "") + out


@register.filter
def inr(value):
    try:
        return "₹" + _indian_group(round(float(value)))
    except (TypeError, ValueError):
        return "₹0"


@register.filter
def pretty(value):
    """source/enum slug -> 'Web form'."""
    return str(value).replace("_", " ").capitalize() if value else ""


_ACT_ICON = {
    "call": "phone", "email": "mail", "meeting": "users", "note": "file-text",
    "stage_change": "git-branch", "task": "check-square", "system": "settings",
}


@register.filter
def activity_icon(value):
    return _ACT_ICON.get(value, "circle-dot")


@register.filter
def get(d, key):
    try:
        return d.get(key, "")
    except AttributeError:
        return ""
