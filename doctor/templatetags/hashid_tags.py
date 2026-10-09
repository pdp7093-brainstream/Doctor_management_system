from django import template
from .. import hashid

register = template.Library()


@register.filter(name='hid')
def hid(value):
    """Template filter to convert numeric id to short hash string."""
    try:
        return hashid.encode_id(int(value))
    except Exception:
        return ''


@register.filter(name='format_working_days')
def format_working_days(value):
    """Format saved weekday codes as capitalized day names."""
    if not value:
        return ''

    labels = {
        'mon': 'Mon', 'tue': 'Tue', 'wed': 'Wed', 'thu': 'Thu',
        'fri': 'Fri', 'sat': 'Sat', 'sun': 'Sun'
    }
    days = [labels.get(day.strip().lower()) for day in value.split(',')]
    return ', '.join(day for day in days if day)
