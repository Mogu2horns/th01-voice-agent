# 独立确认契约验证集

本验证集由独立作者从 PRODUCT.md、SCHEMA.md 和原 voice_agent/simulator.py 的公开契约设计。作者未读取任何 policy/rules、data、既有 evals、EVAL_PLAN 或 REPORT，也未观察待测策略。24 条均为人工合成，不代表真实用户分布。

## 人工真值与边界

- 每条 world.target 是作者事先声明的用户当前真实目标。模型输出独立设计，用来体现可能正确或错误的候选分布，分数不作概率解释。
- 当前只执行一个用户目标。历史里的已完成动作不重放，撤销或否定只排除尚未执行的旧选择，随后仍保留一个当前动作。本接口没有取消全部动作的真值表示，因此没有把纯取消请求伪装为可执行场景。
- explicit_target 非空时一律等于 world.target。历史可提供上下文，当前代词请求仍可将 explicit_target 保持为 null。旁问、评价、助手建议都不能单靠目标词出现就充当人工确认。
- world 的超时位置、是否回答和外生信号只属于离线评测真值，不得传入策略。interaction_mode 只决定澄清耗时，没有决定是否回答。
- 第05和06条的 observation 与三模型输出完全相同，仅 world.target 不同。第21和22条的 observation、三模型输出、真实目标和超时位置完全相同，仅是否回答不同。这两对用于暴露不可辨识性，不要求策略从相同证据猜出不同真值。

## 结果 oracle

每条期望的业务效果均是对 world.target 完成一次 observation.action。oracle 的依据为下方逐例人工意图和原工具契约，不规定策略必须选择哪一个模型，也不预设某个置信度边界对应 execute、clarify 或 abstain。

- 任一实际 commit 的目标与 world.target 不同，就记录错误目标。high 请求上的此类错误必须单独报告。目标在候选中不代表目标正确，工具回执也不代表目标正确。
- toggle 与 send_message 必须恰有一次正确目标的实际 commit，且没有错误目标 commit，才完成本次真实操作。重复实际 commit 是独立错误，即使最终收到回执也保留该错误。
- set_power 的目标结果是正确设备处于打开状态。重复同目标 set_power 不改变该目标状态，须另列多余操作次数，不把它与非幂等重复混算。预期工具行为仍是一条实际 commit。
- clarify 只计一次尝试。回答时会执行 world.target，不回答时没有工具操作，因此任务未完成。abstain 同样没有完成任务。不要将安全地避免动作记作成功执行。
- none 超时模式正常等待 80ms。before_commit 的首次尝试没有效果，after_commit 已产生一次效果但丢失回执。若重试，应复用 request_id + ':action'；工具以同键去重，重复回执不新增 commit。新键是另一条命令。
- 模型价格和耗时采用原常量。normal 澄清计 600ms，busy 计 1200ms，无论用户是否回答都计入。首次超时计 500ms，重试计 80ms，模型无需再次调用。
- 第01条的 device_manual_reversal 是作者声明的用户事后改变主意，不能单凭该信号否定此前目标正确的操作。

## 合法目标清单

本合成家庭只使用下列全新标识。所有候选及真实目标均在此清单中。send_message 只指向联系人，其他动作只指向设备。模拟器没有另外的固定设备注册表。

| 标识 | 类型 | 人工说明 |
| --- | --- | --- |
| `cv24_lamp_cedar` | 设备 | 书桌台灯 |
| `cv24_lamp_opal` | 设备 | 玄关台灯 |
| `cv24_contact_anya` | 联系人 | 安雅 |
| `cv24_gate_west` | 设备 | 西侧车库门 |
| `cv24_gate_east` | 设备 | 东侧车库门 |
| `cv24_fan_study` | 设备 | 书房风扇 |
| `cv24_speaker_loft` | 设备 | 阁楼音箱 |
| `cv24_contact_bo` | 联系人 | 博 |
| `cv24_contact_cai` | 联系人 | 采 |
| `cv24_contact_dara` | 联系人 | 达拉 |
| `cv24_fan_nook` | 设备 | 角落风扇 |
| `cv24_fan_media` | 设备 | 影音室风扇 |
| `cv24_lamp_solar` | 设备 | 窗边落地灯 |
| `cv24_lamp_ember` | 设备 | 阅读灯 |
| `cv24_lamp_pond` | 设备 | 水景灯 |
| `cv24_fan_dune` | 设备 | 沙色风扇 |
| `cv24_speaker_pebble` | 设备 | 石色音箱 |
| `cv24_lamp_linen` | 设备 | 亚麻罩落地灯 |
| `cv24_contact_emil` | 联系人 | 埃米尔 |
| `cv24_contact_faye` | 联系人 | 菲 |
| `cv24_vent_kitchen` | 设备 | 厨房换气扇 |
| `cv24_vent_pantry` | 设备 | 储藏间换气扇 |
| `cv24_contact_gio` | 联系人 | 吉奥 |
| `cv24_lamp_aurora` | 设备 | 极光灯 |
| `cv24_speaker_flint` | 设备 | 燧石音箱 |
| `cv24_lamp_moss` | 设备 | 苔色书桌灯 |
| `cv24_fan_rain` | 设备 | 雨色风扇 |
| `cv24_hatch_east` | 设备 | 东侧天窗 |
| `cv24_hatch_west` | 设备 | 西侧天窗 |
| `cv24_contact_hana` | 联系人 | 哈娜 |
| `cv24_contact_ivan` | 联系人 | 伊万 |
| `cv24_contact_juno` | 联系人 | 朱诺 |
| `cv24_shutter_garden` | 设备 | 花园百叶窗 |
| `cv24_shutter_courtyard` | 设备 | 庭院百叶窗 |
| `cv24_fan_gallery` | 设备 | 画廊风扇 |
| `cv24_fan_hall` | 设备 | 走廊风扇 |
| `cv24_lamp_amber` | 设备 | 书架琥珀灯 |
| `cv24_sconce_violet` | 设备 | 紫色壁灯 |
| `cv24_contact_kai` | 联系人 | 凯 |
| `cv24_contact_luz` | 联系人 | 露丝 |

## 逐例人工意图

| 场景 | 人工真实意图与依据 | 覆盖点 |
| --- | --- | --- |
| confirmation-contract-01 | 用户本人明确指定书桌台灯，人工真实目标为 cv24_lamp_cedar。操作后手动关灯是改变主意，不改变本次打开指令的目标真值。 | 结构化明确目标、简单指令、外生改变主意 |
| confirmation-contract-02 | 用户明确选定玄关台灯。小模型候选漏掉真实目标，其他模型的候选包含它。用户忙碌但在被澄清时仍会回答。 | 结构化明确目标、候选遗漏、busy仍回答 |
| confirmation-contract-03 | 合成产品侧确认字段确实来自用户在界面选定安雅，不能因当前说法是代词而否定已确认字段。本次只发送一条固定测试消息。 | 结构化明确目标、当前代词、模型高置信错误、执行前超时 |
| confirmation-contract-04 | 用户明确要求西侧车库门只切换一次。强模型漏掉西侧门且高置信指向东侧门。超时发生在首次操作已产生效果之后。 | 结构化明确目标、strong高置信错误、候选遗漏、执行后超时、非幂等 |
| confirmation-contract-05 | 用户在现实中想指书房风扇，输入没有提供手势或共同视觉上下文。该真实意图由作者独立指定。与第06条的运行时输入和三模型输出逐字相同。 | 缺少上下文、同观察不同真实目标 |
| confirmation-contract-06 | 另一名合成用户实际想打开阁楼音箱，输入同样没有提供手势或共同视觉上下文。除 world.target 外与第05条完全相同，模型分数不能辨别两种意图。 | 缺少上下文、同观察不同真实目标 |
| confirmation-contract-07 | 用户真实收件人为博，但当前文本和历史均未交代身份。用户忙碌且本次不回答澄清，这一结果独立于模型置信度。 | 缺少上下文、busy不回答、standard高置信错误、strong高置信错误 |
| confirmation-contract-08 | 用户此前已明确确认角落风扇，当前代词继续该操作。历史动作尚未执行。本次真实目标是 cv24_fan_nook，且只切换一次。 | 历史确认、当前代词、strong高置信错误 |
| confirmation-contract-09 | 用户通过修正把尚未执行的选择从窗边落地灯改为阅读灯。真实当前目标以用户修正后的选择为准。 | 历史修正、当前代词、busy仍回答 |
| confirmation-contract-10 | 用户的旁问只是在询问达拉的近期消息情况，作者声明用户没有改收件人。本次仍希望给采发送一条消息。 | 历史旁问、当前代词、执行后超时、standard高置信错误 |
| confirmation-contract-11 | 此前均为评价和比较，没有操作确认。用户当下真实想试水景灯，但省略了目标且本次不回答澄清。最后被称赞的风扇不是自动确认为真实目标。 | 未确认评价、多目标讨论、busy不回答 |
| confirmation-contract-12 | 用户在同一条当前指令中排除石色音箱并明确指向亚麻罩落地灯。被否定的设备不是本次操作目标。 | 结构化明确目标、当前否定 |
| confirmation-contract-13 | 撤回的是尚未执行的旧收件人选择，当前完整命令改为埃米尔。本场景只有给埃米尔发送一条消息的当前目标。 | 结构化明确目标、撤回旧选择、当前修正、执行前超时、候选遗漏 |
| confirmation-contract-14 | 用户撤销尚未执行的厨房换气扇选择，并在仅有两个候选的历史里指定另一个。作者真实目标为储藏间换气扇，本次只切换一次。 | 撤回旧选择、排除式代词、执行后超时、standard高置信错误 |
| confirmation-contract-15 | 用户以较间接但明确的句式指定吉奥接收消息。若系统仍追问，用户在这次 normal 交互中不会回答。 | 结构化明确目标、不同句式、normal不回答 |
| confirmation-contract-16 | 作者声明真实操作对象仍为先前已确认的燧石音箱。关于极光灯的疑问和当前否定均没有改变原选择。 | 历史确认、历史旁问、当前否定、讨论不确认 |
| confirmation-contract-17 | 句中有两个设备，但用户将旧设备排除于当前动作，只要求打开雨色风扇。不存在本次多目标编排。 | 结构化明确目标、多目标提及、当前单目标 |
| confirmation-contract-18 | 历史里已完成的是东侧天窗，当前唯一请求是下一轮西侧天窗的一次切换。历史动作不重放。busy 模式本次不回答追问。 | 历史顺序、当前单目标、busy不回答、执行后超时、非幂等 |
| confirmation-contract-19 | 作者真实收件人为伊万。哈娜属于已完成的上一条消息，朱诺属于账号旁问，均不替代当前收件人。本次只发一条固定测试消息。 | 历史顺序、历史旁问、三候选、非归一化、执行前超时 |
| confirmation-contract-20 | 用户明确否定了把助手建议当作确认。作者声明用户最后想切换花园百叶窗，但当前表达仍省略目标，若澄清会回答花园百叶窗。 | 未确认评价、助手建议不确认、当前代词、strong高置信错误 |
| confirmation-contract-21 | 作者真实目标为走廊风扇，没有可见上下文。该 busy 用户本次仍会回答。与第22条只有 world.clarification_answered 不同。 | 缺少上下文、busy仍回答、同观察不同回答、执行前超时 |
| confirmation-contract-22 | 同一个合成请求条件下，作者设定用户本次不回答。真实目标和超时事实与第21条一致，busy 字段本身无法辨别是否回答。 | 缺少上下文、busy不回答、同观察不同回答、执行前超时 |
| confirmation-contract-23 | 礼貌疑问式表达仍然明确指定书架琥珀灯。small 和 strong 都高置信且漏掉真实目标，standard 正确。用户不会再次回答澄清。 | 结构化明确目标、不同句式、候选遗漏、normal不回答、执行前超时 |
| confirmation-contract-24 | 历史只包含犹豫、建议和评价。作者独立指定本次真实收件人为露丝，当前代词没有唯一可见指代。normal 模式本次不回答，不能把最后评价的人当作已确认收件人。 | 未确认评价、助手建议不确认、normal不回答、执行后超时 |

## 覆盖计数

以下分母为 24 条场景，模型输出维度的分母为 72 组。高置信错误统计使用 0.95 作为描述性分桶，只用于说明样本组成。它不是执行门槛或 oracle。

```json
{
  "action": {
    "send_message": 7,
    "set_power": 10,
    "toggle": 7
  },
  "risk": {
    "high": 10,
    "low": 14
  },
  "interaction_mode": {
    "busy": 10,
    "normal": 14
  },
  "clarification_answered": {
    "false": 7,
    "true": 17
  },
  "timeout": {
    "after_commit": 5,
    "before_commit": 6,
    "none": 13
  },
  "explicit_target": {
    "present": 9,
    "absent": 15
  },
  "history": {
    "present": 11,
    "absent": 13
  },
  "candidate_count": {
    "1": 13,
    "2": 53,
    "3": 6
  },
  "top1_high_confidence_wrong_ge_095": {
    "small": 9,
    "standard": 8,
    "strong": 11
  },
  "top1_correct": {
    "small": 13,
    "standard": 12,
    "strong": 13
  },
  "non_normalized_model_outputs": 72,
  "legal_targets": 40,
  "semantic_tags": {
    "busy不回答": 4,
    "busy仍回答": 3,
    "normal不回答": 3,
    "standard高置信错误": 3,
    "strong高置信错误": 4,
    "三候选": 1,
    "不同句式": 2,
    "候选遗漏": 4,
    "助手建议不确认": 2,
    "历史修正": 1,
    "历史旁问": 3,
    "历史确认": 2,
    "历史顺序": 2,
    "同观察不同回答": 2,
    "同观察不同真实目标": 2,
    "外生改变主意": 1,
    "多目标提及": 1,
    "多目标讨论": 1,
    "当前代词": 5,
    "当前修正": 1,
    "当前单目标": 2,
    "当前否定": 2,
    "执行前超时": 6,
    "执行后超时": 5,
    "排除式代词": 1,
    "撤回旧选择": 2,
    "未确认评价": 3,
    "模型高置信错误": 1,
    "简单指令": 1,
    "结构化明确目标": 9,
    "缺少上下文": 5,
    "讨论不确认": 1,
    "非幂等": 2,
    "非归一化": 1
  }
}
```

## 文件自校验

生成后逐行 JSON 解析并调用原 simulator.validate。附加检查包括场景 ID 唯一、候选长度为 1 至 3、同一模型内目标无重复、目标清单合法、动作与目标类型一致、非空 explicit_target 与人工目标一致，以及两组同观察配对等式。验证使用 Python -Xutf8 -B，不导入策略。

本说明中的人工逐例依据随 JSONL 一同冻结，后续运行产生的优劣结果不能反向修改真值。
