from uuid import UUID


class QueryParamMixin:
    TRUE_VALUES = ("true", "1", "yes", "y")
    FALSE_VALUES = ("false", "0", "no", "n")

    def get_bool(self, request, param_name, default: bool = False) -> bool:
        """
        Helper method to get a boolean value from query parameters.
        """
        value = request.query_params.get(param_name, None).lower()
        if value in self.TRUE_VALUES:
            return True
        if value in self.FALSE_VALUES:
            return False
        return default

    def get_int(self, request, param_name, default: int = None) -> int | None:
        """
        Helper method to get an integer value from query parameters.
        """
        value = request.query_params.get(param_name, None)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def get_uuid(self, request, param_name, default=None) -> UUID | None:
        """
        Helper method to get a UUID value from query parameters.
        """
        value = request.query_params.get(param_name, None)
        if value is None:
            return default
        try:
            from uuid import UUID

            value = UUID(value)
            return value  # Assuming the value is already in UUID format
        except ValueError:
            return default
