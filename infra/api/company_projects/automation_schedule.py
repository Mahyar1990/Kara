"""Small, portable schedule/input contract for project automations."""
import copy
import json
import math
import re
from uuid import uuid4

WEEKDAYS = ('sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat')
INPUT_TYPES = {'text-input': 'string', 'paragraph': 'string', 'select': 'string', 'number': 'number', 'checkbox': 'boolean'}


class AutomationError(ValueError):
    pass


def schedule_data(value):
    if not isinstance(value, dict):
        raise AutomationError('زمان‌بندی معتبر نیست.')
    frequency = value.get('frequency')
    visual = {}
    if frequency == 'hourly':
        minute = value.get('minute', 0)
        if type(minute) is not int or not 0 <= minute <= 59:
            raise AutomationError('دقیقه باید بین صفر و ۵۹ باشد.')
        visual['on_minute'] = minute
    elif frequency in {'daily', 'weekly', 'monthly'}:
        time = value.get('time')
        if not isinstance(time, str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', time):
            raise AutomationError('ساعت را به شکل ساعت و دقیقه وارد کنید.')
        hour, minute = map(int, time.split(':'))
        visual['time'] = f'{hour % 12 or 12}:{minute:02d} {"AM" if hour < 12 else "PM"}'
        if frequency == 'weekly':
            days = value.get('weekdays')
            if not isinstance(days, list) or not days or any(day not in WEEKDAYS for day in days):
                raise AutomationError('حداقل یک روز هفته را انتخاب کنید.')
            visual['weekdays'] = [day for day in WEEKDAYS if day in days]
        elif frequency == 'monthly':
            day = value.get('day')
            if type(day) is not int or not 1 <= day <= 31:
                raise AutomationError('روز ماه باید بین یک و ۳۱ باشد.')
            visual['monthly_days'] = [day]
    else:
        raise AutomationError('نوع زمان‌بندی معتبر نیست.')
    return dict(type='trigger-schedule', title='زمان‌بندی', desc='', mode='visual',
                frequency=frequency, visual_config=visual, timezone='Asia/Tehran')


def source_fields(graph):
    nodes = graph.get('nodes', [])
    starts = [node for node in nodes if node.get('data', {}).get('type') == 'start']
    if len(starts) != 1 or any(node.get('data', {}).get('type', '').startswith('trigger-') for node in nodes):
        raise AutomationError('فرایند مبنا باید یک شروع با ورودی کاربر داشته باشد. شروع‌های خودکار موجود را از همین فهرست مدیریت کنید.')
    fields = starts[0]['data'].get('variables', [])
    if any(field.get('type') not in INPUT_TYPES for field in fields):
        raise AutomationError('این فرایند ورودی فایل یا ورودی پشتیبانی‌نشده دارد. برای آن در صفحهٔ فرایند، شروع خودکار و دریافت داده تعریف کنید.')
    return starts[0], fields


def fixed_inputs(fields, values):
    if not isinstance(values, dict) or set(values) - {field['variable'] for field in fields}:
        raise AutomationError('ورودی‌های فرایند معتبر نیستند.')
    result = {}
    for field in fields:
        key, kind = field['variable'], field['type']
        value = values.get(key, field.get('default', '' if kind != 'checkbox' else False))
        if kind == 'number':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise AutomationError('برای ورودی عددی یک عدد معتبر وارد کنید.')
        elif kind == 'checkbox':
            if type(value) is not bool:
                raise AutomationError('ورودی انتخابی معتبر نیست.')
        elif not isinstance(value, str) or len(value) > min(field.get('max_length') or 48000, 48000):
            raise AutomationError('متن ورودی معتبر نیست یا طول آن بیش از حد مجاز است.')
        if field.get('required') and kind in {'text-input', 'paragraph', 'select'} and not value.strip():
            raise AutomationError('ورودی‌های الزامی فرایند را تکمیل کنید.')
        if kind == 'select' and value not in field.get('options', []) and (value or field.get('required')):
            raise AutomationError('یکی از گزینه‌های تعریف‌شدهٔ فرایند را انتخاب کنید.')
        result[key] = value
    if len(json.dumps(result, ensure_ascii=False)) > 100000:
        raise AutomationError('حجم ورودی‌های ثابت بیش از حد مجاز است.')
    return result


def scheduled_graph(graph, schedule, values):
    graph = copy.deepcopy(graph)
    start, fields = source_fields(graph)
    values = fixed_inputs(fields, values)
    node_id = f'company-schedule-{uuid4().hex[:16]}'
    # Keep the input node ID so every downstream variable selector stays valid.
    # JSON is data inside a quoted Python string, never executable user text.
    start['data'] = dict(type='code', title='ورودی‌های اتوماسیون', desc='', code_language='python3',
        variables=[], code=f'import json\n\ndef main() -> dict:\n    return json.loads({json.dumps(values, ensure_ascii=False)!r})\n',
        outputs={field['variable']: dict(type=INPUT_TYPES[field['type']], children=None) for field in fields})
    start['position'] = dict(x=300, y=0)
    for edge in graph.get('edges', []):
        if edge.get('source') == start['id']:
            edge.setdefault('data', {})['sourceType'] = 'code'
    trigger = dict(id=node_id, type='custom', position=dict(x=0, y=0), data=schedule_data(schedule))
    graph['nodes'].append(trigger)
    graph.setdefault('edges', []).append(dict(id=f'{node_id}-{start["id"]}', source=node_id,
        target=start['id'], sourceHandle='source', targetHandle='target', type='custom',
        data=dict(sourceType='trigger-schedule', targetType='code', isInIteration=False, isInLoop=False)))
    graph.pop('viewport', None)
    return graph, node_id
