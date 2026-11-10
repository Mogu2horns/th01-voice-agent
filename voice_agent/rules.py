"""Bounded dialogue rules using request evidence and dynamic candidate targets."""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ReferenceFeatures:
    has_reference: bool
    target: str | None
    rule: str
    evidence: str


REFERENCE = re.compile(
    r"那个|这个|那[盏台扇]|这[盏台扇]|刚才|之前|先前|定好的|改好的|"
    r"前一个|后一个|第一个|第二个|前者|后者|"
    r"(?:打开|关闭|切换|启动|操作|控制|执行|发送给|发给|给|开|关)[它他她]|"
    r"(?:^|[，,。.!！?？\s])[它他她](?:的|$|[，,。.!！?？\s])"
)
CURRENT_CANCEL = re.compile(
    r"(?:不要|别|暂不|先不|不再)\s*(?:打开|关闭|切换|启动|操作|执行|发送|选|用)|"
    r"取消|撤销|算了|不确定|没(?:有)?决定"
)
USER = re.compile(r"^\s*(?:用户|user)\s*[:：]\s*(.*)$", re.IGNORECASE)
CLAUSES = re.compile(r"([^，,。.!！?？;；]+)([?？]?)")
CHOICE = re.compile(
    r"(?:(?:我(?:决定|想|要)?|请|那就|现在|待会儿|等下|稍后)\s*)?"
    r"(?P<verb>先选|选择|选|换成|改成|改为|就用|用)\s*(?P<target>[\w-]+)"
)
QUESTION = re.compile(r"(?:吗|呢|么)$|能否|是否|可否|能不能|可不可以|顺便问|问下|请问")
UNCERTAIN = re.compile(r"如果|可能|也许|或者|还是|不确定|没(?:有)?决定|没选好")
INVALIDATE = re.compile(r"^(?:不对|取消.*|撤销.*|算了.*|(?:不要|别|不)(?:选|换|用).*)$")
DEFER = re.compile(r"(?:先|还|暂时|暂)?(?:别|不要|不)(?:执行|操作|发送|打开|启动)")
NEUTRAL = re.compile(r"好的?|知道了|明白|记下了|谢谢|等我确认|先等等")
PAIR = re.compile(r"(?P<first>[\w-]+?)\s*(?:和|与|、)\s*(?P<second>[\w-]+?)")
PAIR_PREFIX = re.compile(r"(?:我)?(?:在)?考虑\s*(.*)")
PAIR_SUFFIX = re.compile(r"(.*?)(?:都可能要用|都可能|都能用|都可用|都可以)")
FIRST = re.compile(r"前一个|第一个|前者")
SECOND = re.compile(r"后一个|第二个|后者")


def _pair(clause):
    prefix = PAIR_PREFIX.fullmatch(clause)
    suffix = PAIR_SUFFIX.fullmatch(clause)
    if prefix is None and suffix is None:
        return None
    text = prefix.group(1) if prefix is not None else suffix.group(1)
    match = PAIR.fullmatch(text)
    if match is None or match["first"] == match["second"]:
        return None
    return (match["first"], match["second"])


def extract_reference(request):
    """Recognize explicit user choices, corrections, and a two-item reference."""
    text = request["text"]
    if REFERENCE.search(text) is None:
        return ReferenceFeatures(False, None, "no_reference", "")
    if CURRENT_CANCEL.search(text):
        return ReferenceFeatures(True, None, "unresolved", text)

    target = None
    rule = "unresolved"
    evidence = text
    options = None
    for message in request["history"]:
        user = USER.fullmatch(message)
        if user is None:
            continue
        for match in CLAUSES.finditer(user.group(1)):
            clause = match.group(1).strip()
            if match.group(2) or QUESTION.search(clause):
                continue
            pair = _pair(clause)
            if pair is not None:
                target, rule, options, evidence = None, "unresolved", pair, clause
                continue
            if INVALIDATE.fullmatch(clause) or UNCERTAIN.search(clause):
                target, rule, options, evidence = None, "unresolved", None, clause
                continue
            choice = CHOICE.fullmatch(clause)
            if choice is not None:
                target = choice["target"]
                rule = "correction" if choice["verb"] in ("换成", "改成", "改为") else "selection"
                options, evidence = None, clause
                continue
            if not (DEFER.fullmatch(clause) or NEUTRAL.fullmatch(clause)):
                target, rule, options, evidence = None, "unsupported", None, clause

    if rule == "unsupported":
        return ReferenceFeatures(True, None, rule, evidence)
    first = FIRST.search(text) is not None
    second = SECOND.search(text) is not None
    if first or second:
        if options is not None and first != second:
            return ReferenceFeatures(True, options[0 if first else 1], "ordinal", evidence)
        return ReferenceFeatures(True, None, "unresolved", evidence)
    return ReferenceFeatures(True, target, rule, evidence)


def model_override(request):
    """Return a pre-prediction route, or defer to the original router."""
    if request["risk"] != "low" or request["explicit_target"] is not None:
        return None
    reference = extract_reference(request)
    if not reference.has_reference or reference.rule == "unsupported":
        return None
    return "standard" if reference.target is not None else "small"


def action_override(
    request, prediction, *, correction=True, selection=True,
    ordinal=True, ambiguity_guard=True,
):
    """Apply an enabled evidence rule, or defer to the original action policy."""
    if request["risk"] != "low" or request["explicit_target"] is not None:
        return None
    reference = extract_reference(request)
    if not reference.has_reference or reference.rule == "unsupported":
        return None
    if reference.target is None:
        return {"kind": "clarify"} if ambiguity_guard else None
    enabled = {"correction": correction, "selection": selection, "ordinal": ordinal}
    if not enabled[reference.rule]:
        return None
    targets = {candidate["target"] for candidate in prediction["candidates"]}
    if reference.target in targets:
        return {"kind": "execute", "target": reference.target}
    return {"kind": "clarify"}
