from django import template
from django.utils import timezone
from django.utils.dateparse import parse_datetime

register = template.Library()


@register.filter
def iso_to_dt(value):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.localtime(dt)
