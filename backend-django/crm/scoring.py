"""Lead scoring: source quality + stage progression + engagement + profile completeness (0-100)."""

SOURCE_WEIGHTS = {
    "referral": 25,
    "web_form": 20,
    "linkedin": 15,
    "google_ads": 12,
    "facebook_ads": 10,
    "cold_call": 5,
    "manual": 5,
}

STAGE_WEIGHTS = {
    "new": 0,
    "contacted": 10,
    "qualified": 25,
    "negotiating": 35,
    "won": 40,
    "lost": 0,
}

ACTIVITY_WEIGHTS = {"meeting": 8, "call": 5, "email": 3, "note": 1}
ENGAGEMENT_CAP = 30


def calculate(lead) -> int:
    score = SOURCE_WEIGHTS.get(lead.source, 5)
    score += STAGE_WEIGHTS.get(lead.stage.slug, 0)

    engagement = sum(ACTIVITY_WEIGHTS.get(a.type, 0) for a in lead.activities.all())
    score += min(engagement, ENGAGEMENT_CAP)

    score += sum(1 for f in (lead.email, lead.phone, lead.company) if f)
    if lead.value and lead.value > 0:
        score += 2

    return min(score, 100)


def recalculate(lead) -> None:
    lead.score = calculate(lead)
    lead.save(update_fields=["score"])
