"""Current production policies: safe high-risk handling and basic routing already work."""
def select_model(request):
    if (
        request['risk'] == 'low'
        and request['explicit_target'] is None
        and not request['history']
        and request.get('interaction_mode', 'normal') in ('normal', 'busy')
    ):
        return 'small'
    if request['risk'] == 'high' and request['explicit_target'] is None:
        return 'small'
    if request['explicit_target']:
        return 'standard'
    if request['history']:
        return 'strong'
    return 'standard'


def choose_action(request, prediction):
    ranked = sorted(prediction['candidates'], key=lambda c: c['confidence'], reverse=True)
    if request['risk'] == 'high' and request['explicit_target'] is None:
        return {'kind': 'clarify'}
    explicit = request['explicit_target']
    if explicit:
        if any(c['target'] == explicit for c in ranked):
            return {'kind': 'execute', 'target': explicit}
        return {'kind': 'clarify'}
    top = ranked[0]
    margin = top['confidence'] - (ranked[1]['confidence'] if len(ranked) > 1 else 0)
    if top['confidence'] >= .8 and margin >= .4:
        return {'kind': 'execute', 'target': top['target']}
    return {'kind': 'clarify'}


def retry_key(request, timeout):
    return timeout['original_key']
