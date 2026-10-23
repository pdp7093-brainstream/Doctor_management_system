from django import template
from decimal import Decimal
import re

register = template.Library()

ONES = [
    '', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
    'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
    'Seventeen', 'Eighteen', 'Nineteen'
]
TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

def _two_digits(n):
    if n < 20:
        return ONES[n]
    tens = TENS[n // 10]
    ones = ONES[n % 10]
    return f"{tens} {ones}".strip()

def _three_digits(n):
    hundreds = n // 100
    rest = n % 100
    res = []
    if hundreds:
        res.append(f"{ONES[hundreds]} Hundred")
    if rest:
        res.append(_two_digits(rest))
    return " ".join(res)

def number_to_words_indian(num):
    try:
        val = Decimal(str(num))
    except Exception:
        return ""
    
    integer_part = int(abs(val))
    paise = int(round((abs(val) - integer_part) * 100))

    if integer_part == 0 and paise == 0:
        return "Rupees Zero Only"

    crores = integer_part // 10000000
    rem = integer_part % 10000000
    lakhs = rem // 100000
    rem = rem % 100000
    thousands = rem // 1000
    hundreds = rem % 1000

    parts = []
    if crores:
        parts.append(f"{_two_digits(crores)} Crore")
    if lakhs:
        parts.append(f"{_two_digits(lakhs)} Lakh")
    if thousands:
        parts.append(f"{_two_digits(thousands)} Thousand")
    if hundreds:
        parts.append(_three_digits(hundreds))

    words = " ".join(parts).strip()
    result = f"Rupees {words}" if words else "Rupees"
    if paise:
        result += f" and {_two_digits(paise)} Paise"
    result += " Only"
    return re.sub(r'\s+', ' ', result).strip()

@register.filter(name='num_to_words')
def num_to_words(value):
    if value is None:
        return ""
    return number_to_words_indian(value)

@register.filter(name='clean_address')
def clean_address(val):
    if not val:
        return ""
    # Ensure a space after commas if missing
    return re.sub(r',(?!\s)', ', ', str(val)).strip()

@register.filter(name='doctor_display_name')
def doctor_display_name(visit, request_user=None):
    name = ""
    if visit and getattr(visit, 'doctor', None):
        doc = visit.doctor
        user = getattr(doc, 'user', None)
        if user:
            name = (user.get_full_name() or "").strip() or (getattr(user, 'first_name', '') or "").strip()
    if not name and request_user:
        name = (request_user.get_full_name() or "").strip() or (getattr(request_user, 'first_name', '') or "").strip()
    
    if not name:
        return "—"
    
    # Prefix "Dr." only if the name doesn't already start with Dr
    if re.match(r'^Dr\.?\s+', name, re.IGNORECASE):
        return name
    return f"Dr. {name}"
