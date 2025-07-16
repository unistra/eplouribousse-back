import sentry_sdk


class CustomSentryTagsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set custom tags for Sentry
        if hasattr(request, "tenant"):
            tenant = request.tenant
            sentry_sdk.set_tags(
                {
                    "tenant.id": str(tenant.id),
                    "tenant.name": tenant.name,
                    "tenant.schema": tenant.schema_name,
                }
            )

        response = self.get_response(request)

        return response
