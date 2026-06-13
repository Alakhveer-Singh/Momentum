"""Helpers to push events over Channels (matches the Laravel broadcast payloads)."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_lead(lead, action: str) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        "leads",
        {
            "type": "lead.updated",
            "action": action,
            "lead": {
                "id": lead.id,
                "full_name": lead.full_name,
                "company": lead.company,
                "stage_id": lead.stage_id,
                "stage": lead.stage.name if lead.stage_id else None,
                "score": lead.score,
                "owner_id": lead.owner_id,
            },
        },
    )


def notify_user(user, payload: dict) -> None:
    """Persist a notification row and push it to the user's private channel."""
    from .models import Notification

    Notification.objects.create(user=user, data=payload)
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"user.{user.id}",
        {"type": "notification", "payload": payload},
    )
