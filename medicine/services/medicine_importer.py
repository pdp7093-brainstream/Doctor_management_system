from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from medicine.models import Medicine, MedicineType, MedicineVariant


EXPECTED_HEADER_ROW = (
    'name, short_name, type, company, pack_size, unit, units_per_pack, '
    'cost_price, selling_price, packs, low_stock_alert, mfg_date, exp_date'
)
REQUIRED_HEADERS = ('name', 'short_name', 'pack_size', 'cost_price', 'selling_price')
_NO_DEFAULT = object()
HEADER_ALIASES = {
    'name': {'name', 'medicine', 'medicine name'},
    'short_name': {'short name', 'short', 'code'},
    'type': {'type', 'medicine type'},
    'company': {'company', 'manufacturer'},
    'pack_size': {'pack size', 'power', 'strength'},
    'unit': {'unit'},
    'units_per_pack': {'units per pack', 'unit per strip'},
    'cost_price': {'cost price'},
    'selling_price': {'selling price'},
    'packs': {'packs', 'total packs', 'strips', 'stock strips'},
    'low_stock_alert': {'low stock alert'},
    'mfg_date': {'mfg date'},
    'exp_date': {'exp date'},
}
UNIT_ALIASES = {
    key.casefold(): key
    for key, _label in MedicineVariant.UNIT_CHOICES
}
UNIT_ALIASES.update({
    label.casefold(): key for key, label in MedicineVariant.UNIT_CHOICES
})


class MissingRequiredHeaders(ValueError):
    def __init__(self, missing_headers):
        self.missing_headers = missing_headers
        super().__init__(
            f"Missing required columns: {', '.join(missing_headers)}. "
            f"Expected header row: {EXPECTED_HEADER_ROW}"
        )


def _openpyxl():
    try:
        from openpyxl import Workbook, load_workbook
    except ImportError as exc:
        raise ImproperlyConfigured(
            'Excel import requires openpyxl. Install project requirements and try again.'
        ) from exc
    return Workbook, load_workbook


def _normalize_header(value):
    return ' '.join(str(value or '').strip().casefold().replace('_', ' ').split())


def _header_indexes(header_row):
    alias_map = {
        alias: canonical
        for canonical, aliases in HEADER_ALIASES.items()
        for alias in aliases
    }
    indexes = {}
    for index, value in enumerate(header_row):
        canonical = alias_map.get(_normalize_header(value))
        if canonical and canonical not in indexes:
            indexes[canonical] = index
    missing = [header for header in REQUIRED_HEADERS if header not in indexes]
    if missing:
        raise MissingRequiredHeaders(missing)
    return indexes


def _cell_value(row, indexes, name):
    index = indexes.get(name)
    return row[index] if index is not None and index < len(row) else None


def _text(value):
    return str(value).strip() if value is not None else ''


def _parse_integer(value, field_name, default=_NO_DEFAULT, minimum=0):
    if value is None or _text(value) == '':
        if default is not _NO_DEFAULT:
            return default
        raise ValueError(f'{field_name} is required')
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        raise ValueError(f'{field_name} must be a valid number') from None
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f'{field_name} must be a valid whole number')
    number = int(number)
    if number < minimum:
        raise ValueError(f'{field_name} must be at least {minimum}')
    return number


def _parse_price(value, field_name):
    if value is None or _text(value) == '':
        raise ValueError(f'{field_name} is required')
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        raise ValueError(f'{field_name} must be a valid number') from None
    if not number.is_finite() or number < 0:
        raise ValueError(f'{field_name} must be a valid non-negative number')
    if field_name == 'selling_price' and number == 0:
        raise ValueError('selling price 0 is not allowed')
    return number.quantize(Decimal('0.01'))


def _parse_date(value, field_name):
    if value is None or _text(value) == '':
        return ''
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _text(value)
    for date_format in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f'bad date in {field_name}')


def _classify_row(row):
    errors = []
    warnings = []
    for required in ('name', 'short_name', 'pack_size'):
        if not row[required]:
            errors.append(f'missing field: {required}')

    for key in ('cost_price', 'selling_price'):
        try:
            row[key] = str(_parse_price(row[key], key))
        except ValueError as exc:
            errors.append(str(exc))

    for key, default, minimum in (
        ('units_per_pack', None, 1),
        ('packs', 0, 0),
        ('low_stock_alert', 10, 0),
    ):
        try:
            row[key] = _parse_integer(row[key], key, default=default, minimum=minimum)
        except ValueError as exc:
            errors.append(str(exc))

    raw_unit = row['unit']
    if raw_unit:
        row['unit'] = UNIT_ALIASES.get(raw_unit.casefold())
        if row['unit'] is None:
            errors.append(f'invalid unit: {raw_unit}')
    else:
        row['unit'] = 'piece'

    for key in ('mfg_date', 'exp_date'):
        try:
            row[key] = _parse_date(row[key], key)
        except ValueError as exc:
            errors.append(str(exc))

    if not errors:
        row['stock_units'] = (
            row['packs'] * row['units_per_pack']
            if row['units_per_pack'] is not None
            else row['packs']
        )
        cost_price = Decimal(row['cost_price'])
        selling_price = Decimal(row['selling_price'])
        if selling_price < cost_price:
            warnings.append('selling price < cost price')
        if row['exp_date'] and date.fromisoformat(row['exp_date']) < timezone.localdate():
            warnings.append('exp date in the past')

        medicine = Medicine.objects.filter(short_name__iexact=row['short_name']).first()
        if medicine:
            variant_exists = medicine.variants.filter(power=row['pack_size']).exists()
            row['status'] = 'Update existing' if variant_exists else 'New variant'
        else:
            row['status'] = 'New medicine'

        if row['type'] and not MedicineType.objects.filter(name__iexact=row['type']).exists():
            row['type_status'] = 'will be created'
        else:
            row['type_status'] = ''
    else:
        row['status'] = 'Error'
        row['stock_units'] = ''
        row['type_status'] = ''

    row['reason'] = '; '.join(errors + warnings)
    return row


def parse_medicine_excel(file):
    """Parse and validate a workbook without writing to the database."""
    _Workbook, load_workbook = _openpyxl()
    workbook = load_workbook(file, data_only=True, read_only=True)
    try:
        sheet = workbook.active
        iterator = sheet.iter_rows(values_only=True)
        header_row = next(iterator, ())
        indexes = _header_indexes(header_row)
        parsed_rows = []
        for row_number, values in enumerate(iterator, start=2):
            if not any(value is not None and _text(value) for value in values):
                continue
            row = {
                'row_num': row_number,
                'name': _text(_cell_value(values, indexes, 'name')),
                'short_name': _text(_cell_value(values, indexes, 'short_name')),
                'type': _text(_cell_value(values, indexes, 'type')),
                'company': _text(_cell_value(values, indexes, 'company')),
                'pack_size': _text(_cell_value(values, indexes, 'pack_size')),
                'unit': _text(_cell_value(values, indexes, 'unit')),
                'units_per_pack': _cell_value(values, indexes, 'units_per_pack'),
                'cost_price': _cell_value(values, indexes, 'cost_price'),
                'selling_price': _cell_value(values, indexes, 'selling_price'),
                'packs': _cell_value(values, indexes, 'packs'),
                'low_stock_alert': _cell_value(values, indexes, 'low_stock_alert'),
                'mfg_date': _cell_value(values, indexes, 'mfg_date'),
                'exp_date': _cell_value(values, indexes, 'exp_date'),
            }
            parsed_rows.append(_classify_row(row))
        return parsed_rows
    finally:
        workbook.close()


def import_medicine_rows(rows, stock_option='add'):
    """Import valid preview rows, isolating every row in its own savepoint."""
    success_count = 0
    error_rows = []
    for row in rows:
        if row.get('status') == 'Error':
            error_rows.append({**row, 'reason': row.get('reason') or 'Row has validation errors'})
            continue
        try:
            with transaction.atomic():
                medicine = Medicine.objects.filter(short_name__iexact=row['short_name']).first()
                type_obj = None
                if row.get('type'):
                    type_obj = MedicineType.objects.filter(name__iexact=row['type']).first()
                    if type_obj is None:
                        type_obj = MedicineType.objects.create(name=row['type'].title())

                if medicine is None:
                    medicine = Medicine.objects.create(
                        name=row['name'],
                        short_name=row['short_name'],
                        medicine_type=type_obj,
                        company=row['company'],
                        is_active=True,
                    )
                else:
                    medicine.name = row['name']
                    if type_obj is not None:
                        medicine.medicine_type = type_obj
                    if row['company']:
                        medicine.company = row['company']
                    medicine.save()

                variant = medicine.variants.filter(power=row['pack_size']).first()
                units_per_pack = row['units_per_pack']
                packs = row['packs']
                stock_units = packs * units_per_pack if units_per_pack is not None else packs
                if variant is None:
                    MedicineVariant.objects.create(
                        medicine=medicine,
                        power=row['pack_size'],
                        cost_price=Decimal(row['cost_price']),
                        selling_price=Decimal(row['selling_price']),
                        stock=stock_units,
                        unit=row['unit'],
                        unit_per_strip=units_per_pack,
                        low_stock_alert=row['low_stock_alert'],
                        mfg_date=date.fromisoformat(row['mfg_date']) if row['mfg_date'] else None,
                        exp_date=date.fromisoformat(row['exp_date']) if row['exp_date'] else None,
                    )
                else:
                    if stock_option == 'add':
                        variant.stock += stock_units
                    elif stock_option == 'replace':
                        variant.stock = stock_units
                    elif stock_option != 'keep':
                        raise ValueError('Invalid stock option')
                    variant.cost_price = Decimal(row['cost_price'])
                    variant.selling_price = Decimal(row['selling_price'])
                    variant.unit = row['unit']
                    variant.unit_per_strip = units_per_pack
                    variant.low_stock_alert = row['low_stock_alert']
                    variant.mfg_date = date.fromisoformat(row['mfg_date']) if row['mfg_date'] else None
                    variant.exp_date = date.fromisoformat(row['exp_date']) if row['exp_date'] else None
                    variant.save()
            success_count += 1
        except Exception as exc:
            error_rows.append({**row, 'status': 'Error', 'reason': str(exc)})
    return {'success_count': success_count, 'error_rows': error_rows, 'total': len(rows)}


def generate_sample_excel():
    Workbook, _load_workbook = _openpyxl()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Medicines'
    sheet.append(EXPECTED_HEADER_ROW.split(', '))
    sheet.append(['Ashwagandha Churna', 'ASH-CH', 'Churna', 'Ayur Herbs', '100 gm', 'jar', 1, 80, 120, 5, 10, '01/01/2026', '01/01/2028'])
    sheet.append(['Triphala Vati', 'TRI-VA', 'Vati / Gutika', 'Herbal Care', '60 tablets', 'bottle', 60, 45, 70, 3, 10, '15/02/2026', '15/02/2028'])
    sheet.append(['Mahanarayan Taila', 'MAH-TA', 'Taila (Oil)', 'Ayur Herbs', '200 ml', 'bottle', 1, 110, 160, 4, 10, '10/03/2026', '10/03/2028'])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def generate_error_excel(error_rows):
    Workbook, _load_workbook = _openpyxl()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Import Errors'
    headers = EXPECTED_HEADER_ROW.split(', ')
    sheet.append(['row_num', *headers, 'Reason'])
    for row in error_rows:
        sheet.append([
            row.get('row_num', ''),
            row.get('name', ''),
            row.get('short_name', ''),
            row.get('type', ''),
            row.get('company', ''),
            row.get('pack_size', ''),
            row.get('unit', ''),
            row.get('units_per_pack', ''),
            row.get('cost_price', ''),
            row.get('selling_price', ''),
            row.get('packs', ''),
            row.get('low_stock_alert', ''),
            row.get('mfg_date', ''),
            row.get('exp_date', ''),
            row.get('reason', ''),
        ])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()