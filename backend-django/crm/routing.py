from django.urls import path

from .consumers import CrmConsumer

websocket_urlpatterns = [
    path("ws/crm", CrmConsumer.as_asgi()),
]
