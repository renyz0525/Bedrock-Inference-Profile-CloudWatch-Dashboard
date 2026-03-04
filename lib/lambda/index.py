"""
Lambda handler for Bedrock Inference Profile Dashboard Custom Resource.
Used with CDK cr.Provider - returns dict instead of sending CFN response directly.
- Lists APPLICATION inference profiles from Bedrock
- Builds and deploys two CloudWatch dashboards (Detail + Comparison)
"""

import boto3
import json
import os

COLORS = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf']


# ─── Lambda Handler (cr.Provider format) ───

def handler(event, context):
    print(f"Event: {json.dumps(event)}")
    req_type = event['RequestType']
    props = event.get('ResourceProperties', {})
    detail_name = props.get('DetailDashboardName', 'BedrockInferenceProfile-Detail')
    comp_name = props.get('ComparisonDashboardName', 'BedrockInferenceProfile-Comparison')

    cw = boto3.client('cloudwatch')

    if req_type == 'Delete':
        try:
            cw.delete_dashboards(DashboardNames=[detail_name, comp_name])
            print(f"Deleted dashboards: {detail_name}, {comp_name}")
        except Exception as e:
            print(f"Delete warning: {e}")
        return {'Data': {'ProfileCount': '0'}}

    # ── List Application Inference Profiles ──
    bedrock = boto3.client('bedrock')
    profiles = []
    next_token = None

    while True:
        params = {'typeEquals': 'APPLICATION', 'maxResults': 100}
        if next_token:
            params['nextToken'] = next_token
        resp = bedrock.list_inference_profiles(**params)
        for p in resp.get('inferenceProfileSummaries', []):
            if p.get('status') == 'ACTIVE':
                profile_id = p['inferenceProfileId']
                short_id = profile_id.split('/')[-1] if '/' in profile_id else profile_id
                # Extract base model ID from first model ARN for pricing lookup
                base_model_id = ''
                models = p.get('models', [])
                if models:
                    model_arn = models[0].get('modelArn', '')
                    base_model_id = model_arn.split('/')[-1] if '/' in model_arn else ''
                profiles.append({
                    'name': p['inferenceProfileName'],
                    'id': short_id,
                    'arn': p.get('inferenceProfileArn', ''),
                    'baseModelId': base_model_id,
                })
        next_token = resp.get('nextToken')
        if not next_token:
            break

    print(f"Found {len(profiles)} active application inference profiles")
    for p in profiles:
        print(f"  - {p['name']} ({p['id']})")

    if not profiles:
        print("No application inference profiles found. Creating empty dashboards.")
        empty = {'widgets': [txt(0, 0, 24, 3,
            '# Bedrock Inference Profile Dashboard\n'
            'No application inference profiles found. '
            'Create an inference profile in Bedrock and redeploy this stack.')]}
        cw.put_dashboard(DashboardName=detail_name, DashboardBody=json.dumps(empty))
        cw.put_dashboard(DashboardName=comp_name, DashboardBody=json.dumps(empty))
        return {'Data': {'ProfileCount': '0'}}

    # ── Auto-resolve pricing via AWS Price List API ──
    manual_pricing = json.loads(props.get('Pricing', '{}'))
    period = int(props.get('Period', '300'))
    region = os.environ.get('AWS_REGION', 'us-east-1')
    pricing = resolve_pricing(bedrock, profiles, manual_pricing, region)

    # ── Build and put dashboards ──
    detail_body = build_detail_dashboard(profiles, period, region, pricing, detail_name, comp_name)
    comp_body = build_comparison_dashboard(profiles, period, region, pricing, detail_name, comp_name)

    cw.put_dashboard(DashboardName=detail_name, DashboardBody=json.dumps(detail_body))
    cw.put_dashboard(DashboardName=comp_name, DashboardBody=json.dumps(comp_body))

    profile_names = ', '.join(p['name'] for p in profiles)
    print(f"Dashboards updated: {detail_name}, {comp_name}")

    return {
        'Data': {
            'ProfileCount': str(len(profiles)),
            'ProfileNames': profile_names,
        }
    }


# ══════════════════════════════════════
# DETAIL DASHBOARD (with dropdown)
# ══════════════════════════════════════

def build_detail_dashboard(profiles, period, region, pricing, detail_name, comp_name):
    w = []
    y = 0

    variables = [{
        'type': 'property',
        'property': 'ModelId',
        'inputType': 'select',
        'id': 'inferenceProfile',
        'label': 'Inference Profile',
        'visible': True,
        'defaultValue': profiles[0]['id'],
        'values': [{'label': p['name'], 'value': p['id']} for p in profiles],
    }]

    w.append(txt(0, y, 24, 2,
        f'# Inference Profile - Detail View\n'
        f'Select a profile from the dropdown above. '
        f'For all profiles comparison, see the **{comp_name}** dashboard.'))
    y += 2

    has_cost = any(get_price(p, pricing) for p in profiles)

    # Token counts
    w.append({
        'type': 'metric', 'x': 0, 'y': y, 'width': 12 if has_cost else 24, 'height': 8,
        'properties': {
            'title': 'Input / Output Token Count',
            'view': 'timeSeries', 'stacked': False, 'region': region, 'period': period, 'stat': 'Sum',
            'metrics': [
                ['AWS/Bedrock', 'InputTokenCount', 'ModelId', '$inferenceProfile', {'label': 'Input Tokens', 'color': '#1f77b4'}],
                ['AWS/Bedrock', 'OutputTokenCount', 'ModelId', '$inferenceProfile', {'label': 'Output Tokens', 'color': '#ff7f0e', 'yAxis': 'right'}],
            ],
            'yAxis': {'left': {'label': 'Input', 'showUnits': False}, 'right': {'label': 'Output', 'showUnits': False}},
        },
    })

    if has_cost:
        priced = [p for p in profiles if get_price(p, pricing)]
        avg_in = sum(pricing.get(p['id'], {}).get('inputTokenPrice', 0) for p in priced) / len(priced)
        avg_out = sum(pricing.get(p['id'], {}).get('outputTokenPrice', 0) for p in priced) / len(priced)
        w.append({
            'type': 'metric', 'x': 12, 'y': y, 'width': 12, 'height': 8,
            'properties': {
                'title': 'Estimated Token Cost (USD)',
                'view': 'timeSeries', 'stacked': True, 'region': region, 'period': period,
                'metrics': [
                    ['AWS/Bedrock', 'InputTokenCount', 'ModelId', '$inferenceProfile', {'id': 'dI', 'stat': 'Sum', 'visible': False, 'period': period}],
                    ['AWS/Bedrock', 'OutputTokenCount', 'ModelId', '$inferenceProfile', {'id': 'dO', 'stat': 'Sum', 'visible': False, 'period': period}],
                    [{'expression': f'dI/1000*{avg_in}', 'label': 'Input Cost', 'id': 'dIC', 'color': '#1f77b4'}],
                    [{'expression': f'dO/1000*{avg_out}', 'label': 'Output Cost', 'id': 'dOC', 'color': '#ff7f0e'}],
                    [{'expression': f'dI/1000*{avg_in}+dO/1000*{avg_out}', 'label': 'Total', 'id': 'dTC', 'color': '#2ca02c'}],
                ],
                'yAxis': {'left': {'label': 'USD', 'showUnits': False}},
            },
        })
    y += 8

    # Single values
    sv_defs = [
        (0, 4, 'Invocations', 'SampleCount', 'Invocations'),
        (4, 4, 'Avg Latency', 'Average', 'InvocationLatency'),
        (8, 4, 'Min Latency', 'Minimum', 'InvocationLatency'),
        (12, 4, 'Max Latency', 'Maximum', 'InvocationLatency'),
        (16, 4, 'Client Errors', 'SampleCount', 'InvocationClientErrors'),
        (20, 4, 'Throttles', 'SampleCount', 'InvocationThrottles'),
    ]
    for sx, sw, title, stat, metric_name in sv_defs:
        w.append(sv(sx, y, sw, 4, title, region, period, stat,
                     [['AWS/Bedrock', metric_name, 'ModelId', '$inferenceProfile']]))
    y += 4

    # Token & Cost single values
    w.append(sv(0, y, 8, 4, 'Input Tokens', region, period, 'Sum',
                [['AWS/Bedrock', 'InputTokenCount', 'ModelId', '$inferenceProfile']]))
    w.append(sv(8, y, 8, 4, 'Output Tokens', region, period, 'Sum',
                [['AWS/Bedrock', 'OutputTokenCount', 'ModelId', '$inferenceProfile']]))
    if has_cost:
        priced_for_sv = [p for p in profiles if get_price(p, pricing)]
        avg_in_sv = sum(pricing.get(p['id'], {}).get('inputTokenPrice', 0) for p in priced_for_sv) / len(priced_for_sv)
        avg_out_sv = sum(pricing.get(p['id'], {}).get('outputTokenPrice', 0) for p in priced_for_sv) / len(priced_for_sv)
        w.append({
            'type': 'metric', 'x': 16, 'y': y, 'width': 8, 'height': 4,
            'properties': {
                'title': 'Est. Cost (USD)', 'view': 'singleValue', 'region': region, 'period': period,
                'setPeriodToTimeRange': True,
                'metrics': [
                    ['AWS/Bedrock', 'InputTokenCount', 'ModelId', '$inferenceProfile', {'id': 'svI', 'stat': 'Sum', 'visible': False}],
                    ['AWS/Bedrock', 'OutputTokenCount', 'ModelId', '$inferenceProfile', {'id': 'svO', 'stat': 'Sum', 'visible': False}],
                    [{'expression': f'svI/1000*{avg_in_sv}+svO/1000*{avg_out_sv}', 'label': 'Est. Cost', 'id': 'svC'}],
                ],
            },
        })
    y += 4

    # Latency distribution
    w.append({
        'type': 'metric', 'x': 0, 'y': y, 'width': 12, 'height': 6,
        'properties': {
            'title': 'Latency Distribution',
            'view': 'timeSeries', 'stacked': False, 'region': region, 'period': period,
            'metrics': [
                ['AWS/Bedrock', 'InvocationLatency', 'ModelId', '$inferenceProfile', {'stat': 'Average', 'label': 'Avg', 'color': '#1f77b4'}],
                ['...', {'stat': 'p50', 'label': 'p50', 'color': '#2ca02c'}],
                ['...', {'stat': 'p90', 'label': 'p90', 'color': '#ff7f0e'}],
                ['...', {'stat': 'p99', 'label': 'p99', 'color': '#d62728'}],
            ],
            'yAxis': {'left': {'label': 'ms', 'showUnits': False}},
        },
    })

    # Errors
    w.append({
        'type': 'metric', 'x': 12, 'y': y, 'width': 12, 'height': 6,
        'properties': {
            'title': 'Errors & Throttles',
            'view': 'timeSeries', 'stacked': False, 'region': region, 'period': period, 'stat': 'SampleCount',
            'metrics': [
                ['AWS/Bedrock', 'InvocationClientErrors', 'ModelId', '$inferenceProfile', {'label': 'Client Errors', 'color': '#ff7f0e'}],
                ['AWS/Bedrock', 'InvocationServerErrors', 'ModelId', '$inferenceProfile', {'label': 'Server Errors', 'color': '#d62728'}],
                ['AWS/Bedrock', 'InvocationThrottles', 'ModelId', '$inferenceProfile', {'label': 'Throttles', 'color': '#9467bd'}],
            ],
        },
    })
    y += 6

    return {'variables': variables, 'widgets': w, 'start': '-PT6H', 'periodOverride': 'inherit'}


# ══════════════════════════════════════
# COMPARISON DASHBOARD (no variable)
# ══════════════════════════════════════

def build_comparison_dashboard(profiles, period, region, pricing, detail_name, comp_name):
    w = []
    y = 0
    has_cost = any(get_price(p, pricing) for p in profiles)

    plist = ' | '.join(f"**{p['name']}** (`{p['id']}`)" for p in profiles)
    w.append(txt(0, y, 24, 2,
        f'# All Profiles - Comparison\n'
        f'{plist}  |  To filter by a single profile, see the **{detail_name}** dashboard.'))
    y += 2

    # ── Token Consumption ──
    w.append(txt(0, y, 24, 1, '## Token Consumption'))
    y += 1

    w.append(ts_all(0, y, 12, 8, 'Input Token Count', profiles, 'InputTokenCount', 'Sum', region, period))
    w.append(ts_all(12, y, 12, 8, 'Output Token Count', profiles, 'OutputTokenCount', 'Sum', region, period))
    y += 8

    # ── Performance ──
    w.append(txt(0, y, 24, 1, '## Performance'))
    y += 1

    w.append(ts_all(0, y, 12, 6, 'Invocation Count', profiles, 'Invocations', 'SampleCount', region, period))
    w.append(ts_all(12, y, 12, 6, 'Average Latency (ms)', profiles, 'InvocationLatency', 'Average', region, period,
                    yAxis={'left': {'label': 'ms', 'showUnits': False}}))
    y += 6

    # ── Cost ──
    if has_cost:
        w.append(txt(0, y, 24, 1, '## Cost Estimation'))
        y += 1

        cost_m, cost_e = [], []
        cum_m, cum_e, parts = [], [], []
        for i, p in enumerate(profiles):
            pr = get_price(p, pricing)
            if pr:
                ip, op = pr
                cost_m += [
                    ['AWS/Bedrock', 'InputTokenCount', 'ModelId', p['id'], {'id': f'aI{i}', 'stat': 'Sum', 'visible': False, 'period': period}],
                    ['AWS/Bedrock', 'OutputTokenCount', 'ModelId', p['id'], {'id': f'aO{i}', 'stat': 'Sum', 'visible': False, 'period': period}],
                ]
                cost_e.append([{'expression': f'aI{i}/1000*{ip}+aO{i}/1000*{op}', 'label': p['name'], 'id': f'aC{i}', 'color': COLORS[i % len(COLORS)]}])

                cum_m += [
                    ['AWS/Bedrock', 'InputTokenCount', 'ModelId', p['id'], {'id': f'cI{i}', 'stat': 'Sum', 'visible': False, 'period': period}],
                    ['AWS/Bedrock', 'OutputTokenCount', 'ModelId', p['id'], {'id': f'cO{i}', 'stat': 'Sum', 'visible': False, 'period': period}],
                ]
                expr = f'cI{i}/1000*{ip}+cO{i}/1000*{op}'
                cum_e.append([{'expression': f'RUNNING_SUM({expr})', 'label': p['name'], 'id': f'cc{i}', 'color': COLORS[i % len(COLORS)]}])
                parts.append(expr)

        if len(parts) > 1:
            cum_e.append([{'expression': f'RUNNING_SUM({"+".join(parts)})', 'label': 'Total', 'id': 'ccAll', 'color': '#000000'}])

        w.append({
            'type': 'metric', 'x': 0, 'y': y, 'width': 12, 'height': 8,
            'properties': {'title': 'Cost per Period (USD)', 'view': 'timeSeries', 'stacked': False,
                           'region': region, 'period': period, 'metrics': cost_m + cost_e,
                           'yAxis': {'left': {'label': 'USD', 'showUnits': False}}},
        })
        w.append({
            'type': 'metric', 'x': 12, 'y': y, 'width': 12, 'height': 8,
            'properties': {'title': 'Cumulative Cost (USD)', 'view': 'timeSeries', 'stacked': False,
                           'region': region, 'period': period, 'metrics': cum_m + cum_e,
                           'yAxis': {'left': {'label': 'USD', 'showUnits': False}}},
        })
        y += 8

    # ── Per-Profile Detail ──
    for p in profiles:
        y = profile_section(w, p, y, period, region, pricing)

    return {'widgets': w, 'start': '-PT6H', 'periodOverride': 'inherit'}


# ─── Per-Profile Section ───

def profile_section(w, p, start_y, period, region, pricing):
    y = start_y
    pid = p['id']
    pr = get_price(p, pricing)

    w.append(txt(0, y, 24, 1, f"## {p['name']}  `{pid}`"))
    y += 1

    w.append({
        'type': 'metric', 'x': 0, 'y': y, 'width': 12 if pr else 24, 'height': 7,
        'properties': {
            'title': f"{p['name']} - Token Count",
            'view': 'timeSeries', 'stacked': False, 'region': region, 'period': period, 'stat': 'Sum',
            'metrics': [
                ['AWS/Bedrock', 'InputTokenCount', 'ModelId', pid, {'label': 'Input', 'color': '#1f77b4'}],
                ['AWS/Bedrock', 'OutputTokenCount', 'ModelId', pid, {'label': 'Output', 'color': '#ff7f0e', 'yAxis': 'right'}],
            ],
            'yAxis': {'left': {'label': 'Input', 'showUnits': False}, 'right': {'label': 'Output', 'showUnits': False}},
        },
    })

    if pr:
        ip, op = pr
        s = f"x{pid[-5:]}"
        w.append({
            'type': 'metric', 'x': 12, 'y': y, 'width': 12, 'height': 7,
            'properties': {
                'title': f"{p['name']} - Cost (USD)",
                'view': 'timeSeries', 'stacked': True, 'region': region, 'period': period,
                'metrics': [
                    ['AWS/Bedrock', 'InputTokenCount', 'ModelId', pid, {'id': f'{s}I', 'stat': 'Sum', 'visible': False}],
                    ['AWS/Bedrock', 'OutputTokenCount', 'ModelId', pid, {'id': f'{s}O', 'stat': 'Sum', 'visible': False}],
                    [{'expression': f'{s}I/1000*{ip}', 'label': 'Input', 'id': f'{s}IC', 'color': '#1f77b4'}],
                    [{'expression': f'{s}O/1000*{op}', 'label': 'Output', 'id': f'{s}OC', 'color': '#ff7f0e'}],
                    [{'expression': f'{s}I/1000*{ip}+{s}O/1000*{op}', 'label': 'Total', 'id': f'{s}T', 'color': '#2ca02c'}],
                ],
                'yAxis': {'left': {'label': 'USD', 'showUnits': False}},
            },
        })
    y += 7

    # Latency + Errors
    w.append({
        'type': 'metric', 'x': 0, 'y': y, 'width': 12, 'height': 6,
        'properties': {
            'title': f"{p['name']} - Latency",
            'view': 'timeSeries', 'stacked': False, 'region': region, 'period': period,
            'metrics': [
                ['AWS/Bedrock', 'InvocationLatency', 'ModelId', pid, {'stat': 'Average', 'label': 'Avg', 'color': '#1f77b4'}],
                ['...', {'stat': 'p50', 'label': 'p50', 'color': '#2ca02c'}],
                ['...', {'stat': 'p90', 'label': 'p90', 'color': '#ff7f0e'}],
                ['...', {'stat': 'p99', 'label': 'p99', 'color': '#d62728'}],
            ],
            'yAxis': {'left': {'label': 'ms', 'showUnits': False}},
        },
    })

    w.append({
        'type': 'metric', 'x': 12, 'y': y, 'width': 12, 'height': 6,
        'properties': {
            'title': f"{p['name']} - Errors & Throttles",
            'view': 'timeSeries', 'stacked': False, 'region': region, 'period': period, 'stat': 'SampleCount',
            'metrics': [
                ['AWS/Bedrock', 'InvocationClientErrors', 'ModelId', pid, {'label': 'Client Errors', 'color': '#ff7f0e'}],
                ['AWS/Bedrock', 'InvocationServerErrors', 'ModelId', pid, {'label': 'Server Errors', 'color': '#d62728'}],
                ['AWS/Bedrock', 'InvocationThrottles', 'ModelId', pid, {'label': 'Throttles', 'color': '#9467bd'}],
            ],
        },
    })
    y += 6

    sv_defs = [
        (0, 'Invocations', 'SampleCount', 'Invocations'),
        (4, 'Avg Latency', 'Average', 'InvocationLatency'),
        (8, 'Min Latency', 'Minimum', 'InvocationLatency'),
        (12, 'Max Latency', 'Maximum', 'InvocationLatency'),
        (16, 'Client Errors', 'SampleCount', 'InvocationClientErrors'),
        (20, 'Throttles', 'SampleCount', 'InvocationThrottles'),
    ]
    for sx, title, stat, metric_name in sv_defs:
        w.append(sv(sx, y, 4, 3, title, region, period, stat,
                     [['AWS/Bedrock', metric_name, 'ModelId', pid]]))
    y += 3

    # Token & Cost single values
    w.append(sv(0, y, 8, 3, 'Input Tokens', region, period, 'Sum',
                [['AWS/Bedrock', 'InputTokenCount', 'ModelId', pid]]))
    w.append(sv(8, y, 8, 3, 'Output Tokens', region, period, 'Sum',
                [['AWS/Bedrock', 'OutputTokenCount', 'ModelId', pid]]))
    if pr:
        ip_sv, op_sv = pr
        s_sv = f"sv{pid[-5:]}"
        w.append({
            'type': 'metric', 'x': 16, 'y': y, 'width': 8, 'height': 3,
            'properties': {
                'title': 'Est. Cost (USD)', 'view': 'singleValue', 'region': region, 'period': period,
                'setPeriodToTimeRange': True,
                'metrics': [
                    ['AWS/Bedrock', 'InputTokenCount', 'ModelId', pid, {'id': f'{s_sv}I', 'stat': 'Sum', 'visible': False}],
                    ['AWS/Bedrock', 'OutputTokenCount', 'ModelId', pid, {'id': f'{s_sv}O', 'stat': 'Sum', 'visible': False}],
                    [{'expression': f'{s_sv}I/1000*{ip_sv}+{s_sv}O/1000*{op_sv}', 'label': 'Est. Cost', 'id': f'{s_sv}C'}],
                ],
            },
        })
    y += 3

    return y


# ─── Pricing Auto-Resolution ───

# Map from region code to AWS Pricing API location name
REGION_TO_LOCATION = {
    'us-east-1': 'US East (N. Virginia)', 'us-east-2': 'US East (Ohio)',
    'us-west-1': 'US West (N. California)', 'us-west-2': 'US West (Oregon)',
    'eu-west-1': 'EU (Ireland)', 'eu-west-2': 'EU (London)', 'eu-west-3': 'EU (Paris)',
    'eu-central-1': 'EU (Frankfurt)', 'eu-north-1': 'EU (Stockholm)',
    'ap-northeast-1': 'Asia Pacific (Tokyo)', 'ap-northeast-2': 'Asia Pacific (Seoul)',
    'ap-southeast-1': 'Asia Pacific (Singapore)', 'ap-southeast-2': 'Asia Pacific (Sydney)',
    'ap-south-1': 'Asia Pacific (Mumbai)', 'sa-east-1': 'South America (Sao Paulo)',
    'ca-central-1': 'Canada (Central)', 'me-south-1': 'Middle East (Bahrain)',
}

def resolve_pricing(bedrock, profiles, manual_pricing, region):
    """Auto-resolve per-1K-token pricing from AWS Price List API, with manual fallback."""
    pricing = {}
    location = REGION_TO_LOCATION.get(region, 'US East (N. Virginia)')

    # Collect unique base model IDs and resolve their friendly names
    model_id_to_name = {}
    for p in profiles:
        mid = p.get('baseModelId', '')
        if mid and mid not in model_id_to_name:
            try:
                fm = bedrock.get_foundation_model(modelIdentifier=mid)
                model_id_to_name[mid] = fm.get('modelDetails', {}).get('modelName', '')
            except Exception:
                model_id_to_name[mid] = ''

    # Query Price List API per model name
    pricing_client = boto3.client('pricing', region_name='us-east-1')
    model_name_to_prices = {}  # cache: model_name -> {input, output}

    for p in profiles:
        pid = p['id']

        # Manual override takes priority
        if pid in manual_pricing:
            pricing[pid] = manual_pricing[pid]
            print(f"  Pricing [{p['name']}]: manual override")
            continue

        mid = p.get('baseModelId', '')
        model_name = model_id_to_name.get(mid, '')
        if not model_name:
            print(f"  Pricing [{p['name']}]: no model name, skipping")
            continue

        # Check cache
        if model_name in model_name_to_prices:
            cached = model_name_to_prices[model_name]
            if cached:
                pricing[pid] = cached
                print(f"  Pricing [{p['name']}]: cached {cached}")
            continue

        # Query Price List API
        try:
            resp = pricing_client.get_products(
                ServiceCode='AmazonBedrock',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'model', 'Value': model_name},
                    {'Type': 'TERM_MATCH', 'Field': 'feature', 'Value': 'On-demand Inference'},
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': location},
                ],
            )
            input_price = None
            output_price = None
            for item_str in resp.get('PriceList', []):
                item = json.loads(item_str)
                itype = item['product']['attributes'].get('inferenceType', '')
                for terms in item.get('terms', {}).values():
                    for tv in terms.values():
                        for pv in tv.get('priceDimensions', {}).values():
                            usd = float(pv['pricePerUnit'].get('USD', '0'))
                            if itype == 'Input tokens':
                                input_price = usd
                            elif itype == 'Output tokens':
                                output_price = usd

            if input_price is not None and output_price is not None:
                prices = {'inputTokenPrice': input_price, 'outputTokenPrice': output_price}
                model_name_to_prices[model_name] = prices
                pricing[pid] = prices
                print(f"  Pricing [{p['name']}]: auto ({model_name}) in={input_price}, out={output_price}")
            else:
                model_name_to_prices[model_name] = None
                print(f"  Pricing [{p['name']}]: not found in Price List API for '{model_name}'")
        except Exception as e:
            model_name_to_prices[model_name] = None
            print(f"  Pricing [{p['name']}]: Price List API error: {e}")

    return pricing


# ─── Helpers ───

def get_price(p, pricing):
    """Returns (input_price, output_price) tuple or None."""
    pr = pricing.get(p['id'], {})
    ip = pr.get('inputTokenPrice')
    op = pr.get('outputTokenPrice')
    if ip is not None and op is not None:
        return (ip, op)
    return None

def txt(x, y, w, h, md):
    return {'type': 'text', 'x': x, 'y': y, 'width': w, 'height': h,
            'properties': {'markdown': md, 'background': 'transparent'}}

def sv(x, y, w, h, title, region, period, stat, metrics):
    return {'type': 'metric', 'x': x, 'y': y, 'width': w, 'height': h,
            'properties': {'title': title, 'view': 'singleValue', 'region': region,
                           'period': period, 'stat': stat, 'metrics': metrics,
                           'setPeriodToTimeRange': True}}

def ts_all(x, y, w, h, title, profiles, metric_name, stat, region, period, yAxis=None):
    widget = {
        'type': 'metric', 'x': x, 'y': y, 'width': w, 'height': h,
        'properties': {
            'title': title,
            'view': 'timeSeries', 'stacked': False, 'region': region, 'period': period, 'stat': stat,
            'metrics': [
                ['AWS/Bedrock', metric_name, 'ModelId', p['id'],
                 {'label': p['name'], 'color': COLORS[i % len(COLORS)]}]
                for i, p in enumerate(profiles)
            ],
        },
    }
    if yAxis:
        widget['properties']['yAxis'] = yAxis
    return widget
