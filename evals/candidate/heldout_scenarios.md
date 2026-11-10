# 独立冻结合成验证集

未见待测规则、未读历史/公开数据，仅合成契约验证。

作者仅读取 PRODUCT.md、SCHEMA.md 和原 voice_agent/simulator.py 中的公开契约。未读取 policy.py、data 下任何文件、既有 evals 文件或评估计划及报告，也未获知待测候选规则。32 条场景在策略评估前独立人工编写，目标标识均在本集中自行发明。场景不代表真实家庭请求分布。

每例仅重放当前一个请求，历史字符串仅提供此前对话。每例只有一个人工意图目标、至多一次澄清和一次模型调用。explicit_target 非空时总与人工意图和当前明确说法一致。历史续接场景的当前说法没有重新提供结构化 explicit_target，历史仍作为可观察对话保留。

## Oracle 与不可辨识性

world.target 是作者事先声明的人工用户意图，不由模型排序、置信分数或待测策略导出。逐例下表说明该意图的依据。正确完成要求对这个目标完成当前预期操作。错目标提交应记录为错误，toggle 与 send_message 需要恰好一次预期操作，重复实际提交属于额外错误。set_power 重复本身不改变目标最终开状态，重复提交可另行记录。弃权或无人回应的澄清均没有完成任务，收到回执也不能覆盖错目标或重复操作。

本集不规定每例必须选哪个模型，也不预写 execute、clarify 或 abstain 答案。澄清回应与超时位置均为世界的人工设定。若选择澄清且有回应，模拟器让用户说出 world.target。若无回应，不产生目标执行。normal 与 busy 只决定契约规定的交互等待，不能推导是否回答。高分错误与低分正确均有覆盖，候选分数不要求总和为 1。

heldout-015 与 heldout-016 除 request_id 外 observation 完全相同，三个模型的候选及分数也完全相同，world.target 分别不同。这对样本明确展示当前信号无法唯一识别人工意图。heldout-017 与 heldout-018 同样具有完全相同的运行时信号，但世界的澄清回应结果不同。request_id 是不含意图的独立标识，禁止将编号变成答案表。

## 逐例作用与人工意图

| 场景 | 作用 | 人工意图依据与 oracle | 交互 / 回应 | 超时 |
| --- | --- | --- | --- | --- |
| heldout-001 | 明确低风险、单候选的基础完成场景 | 目标 `desk_beacon`。用户确实要求打开 desk_beacon，当前明确说法与人工意图一致。 | normal / 会回应 | none |
| heldout-002 | 明确指令但忙碌且不回应 | 目标 `north_fan`。用户要切换 north_fan 一次，若被追加提问会因忙碌而不答。 | busy / 不回应 | none |
| heldout-003 | 明确目标在部分模型候选中缺失，其余模型将其排在第二 | 目标 `amber_strip`。用户要求 amber_strip，模型分数不改变该人工意图，用户本次不会回应追问。 | normal / 不回应 | none |
| heldout-004 | 三个模型均高置信漏掉明确目标 | 目标 `bamboo_lamp`。用户只要切换 bamboo_lamp 一次，并会在被问到时再次说明这个目标。 | normal / 会回应 | none |
| heldout-005 | 高风险明确收件人与三模型首选冲突 | 目标 `contact_zephyr`。人工收件人是 contact_zephyr，任何发给 contact_iris 的提交均为错目标。 | normal / 会回应 | none |
| heldout-006 | 小模型与标准模型正确而强模型高置信漏目标 | 目标 `loft_gate`。用户明确指定 loft_gate 一次，并且此次忙碌不回应。 | busy / 不回应 | none |
| heldout-007 | 唯一历史话题尚无确认 | 目标 `reading_beacon`。作者设定用户此刻仍指 reading_beacon，历史只是谈论该设备，未完成目标确认。 | normal / 会回应 | none |
| heldout-008 | 唯一历史话题、单候选与忙碌不回应 | 目标 `cedar_fan`。作者设定用户想切换刚谈到的 cedar_fan 一次，未在历史中确认操作目标。 | busy / 不回应 | none |
| heldout-009 | 高风险唯一历史话题，模型首选存在分歧 | 目标 `contact_orbit`。作者设定人工收件人为 contact_orbit，用户此前只询问其情况，若澄清会明确答复。 | normal / 会回应 | none |
| heldout-010 | 历史明确确认后的当前发送授权 | 目标 `contact_finch`。人工意图延续已确认的 contact_finch，当前请求授权发送一次，用户不再回应。 | busy / 不回应 | none |
| heldout-011 | 历史明确确认但模型排序不同，包含三候选 | 目标 `glass_lantern`。人工意图是打开已确认的 glass_lantern，历史确认未被撤销，用户本次不答追问。 | normal / 不回应 | none |
| heldout-012 | 既往确认被明确撤销且改换目标 | 目标 `rooftop_hatch`。用户已撤销 cellar_hatch，当前人工意图为 rooftop_hatch，一次操作是唯一预期。 | normal / 会回应 | none |
| heldout-013 | 多个历史目标中的新近指向 | 目标 `tea_light`。人工意图是当前注意的 tea_light，作者明确设定用户未回到较早的 study_glow。 | busy / 不回应 | none |
| heldout-014 | 被否定目标与明确替代目标同在历史中 | 目标 `window_fan`。人工目标为 window_fan，harbor_fan 在历史中被用户明确否定。 | normal / 不回应 | none |
| heldout-015 | 同可观察输入、不同人工目标的不可辨识配对 A | 目标 `orbit_light`。作者设定用户在助手不可见的房间里指向 orbit_light。两例可观察字段除 request_id 外完全相同，用户若被问会说出该人工目标。 | normal / 会回应 | none |
| heldout-016 | 同可观察输入、不同人工目标的不可辨识配对 A | 目标 `tide_light`。作者设定用户在助手不可见的房间里指向 tide_light。两例可观察字段除 request_id 外完全相同，用户若被问会说出该人工目标。 | normal / 会回应 | none |
| heldout-017 | 同可观察输入、不同用户回应的不可辨识配对 B | 目标 `contact_plum`。作者设定收件人均为 contact_plum，但一例忙碌时仍回应，一例不回应。busy 本身不揭示此次回应结果。 | busy / 会回应 | none |
| heldout-018 | 同可观察输入、不同用户回应的不可辨识配对 B | 目标 `contact_plum`。作者设定收件人均为 contact_plum，但一例忙碌时仍回应，一例不回应。busy 本身不揭示此次回应结果。 | busy / 不回应 | none |
| heldout-019 | 高风险缺上下文且所有模型均漏掉真实目标 | 目标 `attic_gate`。作者设定用户指向不可见的 attic_gate，三模型均猜错，用户本次也不会回答。 | normal / 不回应 | none |
| heldout-020 | 多个历史收件人尚未消歧 | 目标 `contact_lark`。作者在世界中指定用户内心选择 contact_lark，历史没有表达这一选择，若追问会回答。 | normal / 会回应 | none |
| heldout-021 | 高风险明确目标、低分与三个近邻候选 | 目标 `kiln_heater`。人工意图明确是 kiln_heater，分数偏低不改变这一意图，包含高风险 set_power。 | normal / 会回应 | none |
| heldout-022 | 明确目标与相邻分数、模型排序反转 | 目标 `moss_panel`。人工意图明确为 moss_panel，用户忙碌但仍会回答本次澄清。 | busy / 会回应 | none |
| heldout-023 | 唯一出现的历史目标只有否定，没有替代确认 | 目标 `contact_maple`。作者设定真实收件人为未明说的 contact_maple，不能把被否定的 contact_coral 当作人工意图。 | busy / 不回应 | none |
| heldout-024 | 多个历史目标、延后执行和当前授权 | 目标 `orchard_gate`。用户已明确改为 orchard_gate，当前授权只切换 orchard_gate 一次，旧目标不再有效。 | busy / 会回应 | none |
| heldout-025 | set_power 执行前超时 | 目标 `pearl_lamp`。人工目标为 pearl_lamp，世界规定首次调用执行前超时，正常同键重试才产生一次提交。 | normal / 不回应 | before_commit |
| heldout-026 | set_power 执行后超时与外生反转线索 | 目标 `pebble_lamp`。人工目标为 pebble_lamp，首次调用已提交。用户随后改变主意并手动反转，外生线索不改变原请求目标。 | busy / 会回应 | after_commit |
| heldout-027 | toggle 执行前超时 | 目标 `linen_fan`。用户只要切换 linen_fan 一次，首次调用尚未产生操作，需要遵守原键去重契约。 | normal / 会回应 | before_commit |
| heldout-028 | toggle 执行后超时 | 目标 `paper_fan`。用户只要切换 paper_fan 一次，首次调用已切换，第二次实际提交会把请求做两遍。 | busy / 不回应 | after_commit |
| heldout-029 | send_message 执行前超时 | 目标 `contact_saffron`。人工收件人为 contact_saffron，只需要一条固定测试消息，首次调用没有发送。 | normal / 不回应 | before_commit |
| heldout-030 | send_message 执行后超时 | 目标 `contact_cobalt`。人工收件人为 contact_cobalt，只需要一条固定测试消息，首次调用已经发送。 | busy / 会回应 | after_commit |
| heldout-031 | 高风险缺上下文与执行后超时组合 | 目标 `summit_shutter`。作者设定用户指 summit_shutter，用户会在被问时答复，工具首次提交后超时。 | normal / 会回应 | after_commit |
| heldout-032 | 多目标未决、忙碌不回应与执行前超时组合 | 目标 `quarry_glow`。作者设定用户内心最后选 quarry_glow，但没有把选择说出来，本次也不回应追问。 | busy / 不回应 | before_commit |

## 覆盖计数

以下均为构造覆盖，不是任何策略的评估结果。候选个数统计以三个模型的全部 96 个输出为分母，其余项目默认以场景为单位。

```json
{
  "total": 32,
  "action": {
    "set_power": 12,
    "toggle": 11,
    "send_message": 9
  },
  "risk": {
    "low": 17,
    "high": 15
  },
  "interaction_mode": {
    "normal": 18,
    "busy": 14
  },
  "clarification_answered": {
    "true": 17,
    "false": 15
  },
  "timeout": {
    "none": 24,
    "before_commit": 4,
    "after_commit": 4
  },
  "explicit_target": {
    "present": 14,
    "absent": 18
  },
  "history": {
    "empty": 20,
    "nonempty": 12
  },
  "primary_context": {
    "explicit": 14,
    "unique_unconfirmed": 3,
    "confirmed_history": 2,
    "revoked_history_confirmation": 1,
    "history_recent_redirection": 2,
    "history_negation_replacement": 1,
    "missing_context": 6,
    "multi_history_unresolved": 2,
    "history_rejected_without_replacement": 1
  },
  "candidate_count_model_outputs": {
    "1": 41,
    "2": 45,
    "3": 10
  },
  "model_outputs_differ_scenarios": 26,
  "high_confidence_wrong_candidate_scenarios_ge_095": 19,
  "target_absent_at_least_one_model_scenarios": 5,
  "target_absent_all_models_scenarios": 2,
  "indistinguishable_pairs": 2,
  "external_signal_scenarios": 1
}
```

## 冻结与校验

JSONL 每行均可独立解析，且全部通过原 simulator.validate。另检查编号唯一、字段完整、合法动作与风险、全部三模型、1 至 3 个无重复候选、有效分数、历史字符串、当前显式目标与人工目标一致，以及两对同信号世界分歧。文档逐行列出全部 32 例。此后只读评估，不依据待测结果修改本验证集。
