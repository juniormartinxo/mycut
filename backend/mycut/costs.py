"""Token and credit usage per project. Values are API list-price equivalents, not what a subscription bills."""
import json
from .agent_models import MODEL_ID

PRICES_SOURCE = 'https://developers.openai.com/api/docs/pricing'
# US$ per 1M tokens, Standard tier, short context; checked on 2026-10-14.
DEFAULTS = {
    'usd_brl': 5.0096,  # PTAX de venda do Banco Central em 13/10/2026.
    'elevenlabs_usd_per_1k_credits': None,
    'checked_at': '2026-10-14',
    'models': {
        'gpt-6-astra': {'input': 10.0, 'cache_read': 1.0, 'output': 50.0},
        'gpt-6.1-sol': {'input': 2.0, 'cache_read': .1, 'output': 10.0},
        'gpt-6-sol': {'input': 2.0, 'cache_read': .2, 'output': 10.0},
        'gpt-6-luna': {'input': .1, 'cache_read': .01, 'output': .5},
        'gpt-5.6-sol': {'input': 4.0, 'cache_read': .4, 'output': 20.0},
        'gpt-5.6-terra': {'input': 2.0, 'cache_read': .2, 'output': 12.0},
        'gpt-5.6-luna': {'input': .2, 'cache_read': .02, 'output': 1.2},
    },
}
FIELDS = ('input', 'cache_read', 'cache_write', 'output', 'reasoning', 'web_searches')


def count(value):
    return value if type(value) is int and value >= 0 else 0


def extract(provider, requested_model, stdout):
    """Usage from the CLI envelope only; model-authored text is never read as metadata."""
    entries = []
    if provider == 'codex':
        totals = dict.fromkeys(('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
                                'output_tokens', 'reasoning_output_tokens'), 0)
        seen = False
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get('type') == 'turn.completed' and isinstance(event.get('usage'), dict):
                seen = True
                for key in totals:
                    totals[key] += count(event['usage'].get(key))
        if seen:
            # OpenAI counts cached and cache-write tokens inside input, and reasoning inside output.
            cached, written = totals['cached_input_tokens'], totals['cache_write_input_tokens']
            entries.append({'model': requested_model, 'input': max(0, totals['input_tokens']-cached-written),
                            'cache_read': cached, 'cache_write': written, 'output': totals['output_tokens'],
                            'reasoning': totals['reasoning_output_tokens'], 'web_searches': 0, 'cost_usd': None})
        return entries
    try:
        envelope = json.loads(stdout)
        usage = envelope.get('modelUsage')
    except (ValueError, AttributeError):
        return []
    if not isinstance(usage, dict):
        return []
    reasoning = count((envelope.get('usage') or {}).get('reasoning_tokens')) if len(usage) == 1 else 0
    for model, stats in usage.items():
        if not isinstance(stats, dict) or not MODEL_ID.fullmatch(model):
            continue
        cost = stats.get('costUSD')
        entries.append({'model': model, 'input': count(stats.get('inputTokens')),
                        'cache_read': count(stats.get('cacheReadInputTokens')),
                        'cache_write': count(stats.get('cacheCreationInputTokens')),
                        'output': count(stats.get('outputTokens')),
                        'reasoning': count(stats.get('thinkingTokens')) or reasoning,
                        'web_searches': count(stats.get('webSearchRequests')),
                        'cost_usd': float(cost) if isinstance(cost, (int, float)) and cost >= 0 else None})
    return entries


def priced(entry, pricing):
    """Returns (usd, source). The CLI's own figure wins; otherwise the editable table."""
    if entry.get('cost_usd') is not None:
        return entry['cost_usd'], 'cli'
    price = pricing['models'].get(entry.get('model') or '')
    if not price:
        return None, None
    usd = ((entry['input']+entry['cache_write'])*price['input'] + entry['cache_read']*price['cache_read']
           + entry['output']*price['output']) / 1_000_000
    return usd, 'tabela'


def empty_total():
    return {**dict.fromkeys(FIELDS, 0), 'credits': 0, 'usd': 0.0, 'unpriced': 0}


def add(total, line):
    for key in FIELDS:
        total[key] += line.get(key) or 0
    total['credits'] += line.get('credits') or 0
    if line['usd'] is None:
        total['unpriced'] += 1
    else:
        total['usd'] += line['usd']


def summary(jobs, rows, pricing, running=()):
    """Itemize by version, step, attempt and model. `running` lists jobs whose calls may still settle."""
    by_job = {}
    for row in rows:
        by_job.setdefault(row['job_id'], []).append(row)
    total, versions = empty_total(), []
    for job in jobs:
        calls, job_total = [], empty_total()
        for row in by_job.get(job['id'], []):
            state = row['state']
            if state == 'running' and job['id'] not in running:
                state = 'interrupted'
            base = {'step': row['step'], 'attempt': row['attempt'], 'provider': row['provider'],
                    'requested_model': row['requested_model'], 'state': state, 'created_at': row['created_at']}
            if row['provider'] == 'elevenlabs':
                credits = row['credits']
                rate = pricing.get('elevenlabs_usd_per_1k_credits')
                line = {**base, 'model': row['requested_model'], **dict.fromkeys(FIELDS, 0), 'credits': credits,
                        'credits_estimated': bool(row['credits_estimated']),
                        'usd': credits*rate/1000 if credits is not None and rate is not None else None,
                        'cost_source': 'plano' if credits is not None and rate is not None else None}
                calls.append(line)
                add(job_total, line)
                continue
            entries = json.loads(row['entries'])
            if not entries:
                line = {**base, 'model': row['requested_model'], **dict.fromkeys(FIELDS, 0), 'credits': None,
                        'usd': None, 'cost_source': None, 'unreported': True}
                calls.append(line)
                if state not in ('running',):
                    job_total['unpriced'] += 1
                continue
            for entry in entries:
                usd, source = priced(entry, pricing)
                line = {**base, **{k: entry[k] for k in FIELDS}, 'model': entry['model'], 'credits': None,
                        'usd': usd, 'cost_source': source}
                calls.append(line)
                add(job_total, line)
        recorded = bool(calls) or job['kind'] == 'render'
        versions.append({'id': job['id'], 'kind': job['kind'], 'state': job['state'], 'created_at': job['created_at'],
                         'recorded': recorded, 'calls': calls, 'total': job_total})
        for key in (*FIELDS, 'credits', 'usd', 'unpriced'):
            total[key] += job_total[key]
    return {'total': total, 'versions': versions, 'usd_brl': pricing.get('usd_brl'),
            'checked_at': pricing.get('checked_at'), 'source': PRICES_SOURCE}


def settle(usage_id):
    """Close a call from the runner's answer; safe to repeat and to run after a killed production."""
    from . import bridge, store
    answer = bridge.response(usage_id)
    if answer is not None:
        store.usage_finish(usage_id, 'failed' if answer.get('error') else 'succeeded', answer.get('usage') or [])


def project(project_id, pricing):
    from . import store
    rows = store.usage_rows(project_id)
    pending = [row['id'] for row in rows if row['state'] == 'running' and row['provider'] != 'elevenlabs']
    for usage_id in pending:
        settle(usage_id)
    if pending:
        rows = store.usage_rows(project_id)
    jobs = store.jobs(project_id)
    running = {job['id'] for job in jobs if job['state'] in ('queued', 'running')}
    return summary(jobs, rows, pricing, running)
