from rest_framework import pagination


class PageNumberPagination(pagination.PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 1000

    def get_next_link(self) -> int | None:
        return self.page.next_page_number() if self.page.has_next() else None

    def get_previous_link(self) -> int | None:
        return self.page.previous_page_number() if self.page.has_previous() else None

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "example": 123,
                },
                "next": {
                    "type": "integer",
                    "nullable": True,
                    "example": 4,
                },
                "previous": {
                    "type": "integer",
                    "nullable": True,
                    "example": 2,
                },
                "results": schema,
            },
        }
