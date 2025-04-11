import uuid
from functools import partial

from django.db import models

UUIDPrimaryKeyField = partial(models.UUIDField, primary_key=True, default=uuid.uuid4, editable=False)
CreatedAtField = partial(models.DateTimeField, auto_now_add=True, editable=False)
UpdatedAtField = partial(models.DateTimeField, auto_now=True)
