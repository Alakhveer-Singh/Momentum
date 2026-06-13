"""WebSocket consumer: lead updates + per-user notifications, JWT-authenticated."""

import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _user_from_token(token: str):
    from .models import User

    try:
        payload = AccessToken(token)
    except TokenError:
        return None
    try:
        return User.objects.get(pk=payload["user_id"])
    except User.DoesNotExist:
        return None


class CrmConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        qs = parse_qs(self.scope["query_string"].decode())
        token = (qs.get("token") or [None])[0]
        self.user = await _user_from_token(token) if token else None
        if not self.user:
            await self.close()
            return
        self.groups_joined = ["leads", f"user.{self.user.id}"]
        for group in self.groups_joined:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        for group in getattr(self, "groups_joined", []):
            await self.channel_layer.group_discard(group, self.channel_name)

    # group_send type="lead.updated"
    async def lead_updated(self, event):
        await self.send(text_data=json.dumps({
            "event": "lead.updated",
            "action": event["action"],
            "lead": event["lead"],
        }))

    # group_send type="notification"
    async def notification(self, event):
        await self.send(text_data=json.dumps({
            "event": "notification",
            "payload": event["payload"],
        }))
