# 路由定向场景与预期依据

18条场景均为本次独立人工构造，结构遵守原SCHEMA，目标名称、请求、候选、真实目标、超时和回应条件均由本次设定。未改动原data。world.target表达本次设定的用户意图，模型候选用于模拟可能的模型输出。它们用于检验主张和暴露边界，不能据其比例估计线上发生率。

正常设备操作的oracle为对world.target执行请求action。set_power重复设开仍能完成目标，重复开销单列。toggle和send_message要求恰好一次。明确目标是已确认信息，不能因候选缺失而执行另一个目标。澄清回应由人工设定，回应后给出真实目标，无回应则没有操作。

| 场景ID | 构造目的与oracle依据 | 预期行为或代价 |
|---|---|---|
| normal_shared_clarify | 用户真实目标为window_light，模型均不确定，用户会回应 | 三方案均澄清并完成。基线930ms，A/B为780ms |
| normal_single_candidate | 新目标entry_light，三模型只有一个0.9分候选且与意图一致 | 正确执行一次，基线330ms，A/B为180ms |
| small_confident_wrong | 用户想操作reading_light，small高置信猜side_light，standard正确 | A/B会错目标但仍有回执。必须识别为退化，构成成本路由的适用边界 |
| explicit_missing_answered | 明确herb_light，但standard候选只有hall_lamp，用户回答 | 三方案均选择standard并澄清，正确完成，930ms |
| explicit_missing_unanswered | 同上，用户不回应 | 不执行，850ms，计入未完成 |
| busy_extra_clarify_answered | busy用户想操作desk_strip，small不确定，standard正确且确定 | A与基线330ms直接完成，B澄清后1380ms完成，额外等待1050ms |
| busy_extra_clarify_unanswered | 同上，但用户不回应 | A与基线正确完成，B为1300ms且未完成，暴露完成质量代价 |
| high_ambiguous_answered | 高风险给contact_mina发消息，small猜错contact_ren，用户回应 | 三方案均澄清后给正确联系人发一次，780ms |
| high_ambiguous_unanswered | 同上，用户不回应 | 三方案均不执行，700ms |
| history_requires_strong | 历史明确约定ceiling_light，只有strong正确解读 | 三方案均选strong并正确执行，780ms |
| threshold_at_boundary | 新目标balcony_light，首分0.8、间隔0.4，两分数和为1.2 | 现有执行规则直接执行，验证分数不要求归一化 |
| threshold_below_score | 首分0.79、间隔0.69，用户回应 | 现有执行规则澄清并完成 |
| threshold_below_margin | 首分0.81、间隔0.39，用户不回应 | 现有执行规则澄清且不执行 |
| timeout_before_message | 明确给contact_rui发消息，执行前超时 | 原键重试后恰好发送一次，830ms |
| timeout_after_toggle | 明确切换garden_gate，执行后超时 | 重试去重，恰好切换一次，830ms |
| indistinguishable_east | 用户真实目标east_lamp，观测和候选与下一场景相同 | 三方案执行east_lamp，完成 |
| indistinguishable_west | 用户真实目标west_lamp，只有评测真值与上一场景不同 | 三方案仍执行east_lamp，错误。运行时信号无法区分两者 |
| legacy_mode_missing | 省略interaction_mode的旧结构，用户回应 | A/B按normal路由，模拟器按normal收取澄清等待 |

不可辨识场景的request_id仅为独立请求的幂等标识，除该标识外，两条observation相同。策略不能利用此标识记忆答案。

测试还在副本中构造重复操作、错误action、主动放弃和执行前超时不重试，用来独立检查质量统计的判定。此类构造仅用于指标单元测试，原始场景和执行器保持各自可重放。
