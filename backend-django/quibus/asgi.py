"""ASGI config for Quibus LMS — HTTP + Channels WebSocket."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quibus.settings")

from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter

from crm.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(websocket_urlpatterns),
})
