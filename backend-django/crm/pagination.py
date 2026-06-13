from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class LaravelStylePagination(PageNumberPagination):
    """Mirrors Laravel's paginator JSON so the existing React frontend works unchanged."""

    page_size = 25
    page_size_query_param = "per_page"
    max_page_size = 200

    def get_paginated_response(self, data):
        page = self.page
        per_page = self.get_page_size(self.request)
        count = page.paginator.count
        current = page.number
        start = (current - 1) * per_page
        return Response(
            {
                "data": data,
                "current_page": current,
                "last_page": page.paginator.num_pages,
                "per_page": per_page,
                "total": count,
                "from": start + 1 if count else None,
                "to": start + len(data) if count else None,
            }
        )
