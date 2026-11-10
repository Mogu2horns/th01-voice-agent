"""Current production policies: safe high-risk handling and basic routing already work."""
from voice_agent.rules import action_override, model_override


def select_model(request):
    override = model_override(request)
    if override is not None:
        return override
    if request['risk'] == 'high' and request['explicit_target'] is None:
        return 'small'
    if request['explicit_target']:
        return 'standard'
    if request['history']:
        return 'strong'
    return 'standard'


def choose_action(request, prediction):
    override = action_override(request, prediction)
    if override is not None:
        return override
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
