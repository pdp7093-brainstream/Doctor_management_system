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
