# 会员权益补偿与配送改派处理备忘

这份文档给客服和运营同学做处理参考。用户可能不会按固定格式描述问题，常见说法包括“黑卡券没到账”“活动赠品少了”“说好今天到但物流没动”“地址临时要改”“我不要退款，先补权益”等。

先判断用户当前到底要处理哪一类事情：

- 会员权益、券、积分、赠品、等级权益发放异常，走权益核对与补偿。
- 配送承诺、地址改派、期望送达时间变化，走仓配改派评估。
- 用户同时提到权益和配送时，先确认会影响当前履约的部分，再把另一件事保留为后续任务。
- 用户只是在问规则或口径时，先查知识依据，不要直接承诺补偿。

## 会员权益核对

如果用户说权益没到账、少发、补券、黑卡礼、积分、赠品等，需要先把用户身份和订单确认清楚。可以用用户 ID、订单号、会员等级、权益类型和活动批次去查一遍权益差异。

可参考的核对入口是 POST http://127.0.0.1:8000/api/mock/member/benefit-reconcile。

请求参数：

user_id：用户 ID 或会员身份标识，必填。

order_id：订单号，必填。

member_level：会员等级，可选，例如 normal、gold、black。

benefit_type：权益类型，可选，例如 coupon、points、gift。

benefit_campaign_id：活动批次，可选。

可以先按这个样例核对：用户 user_demo，订单 A12345，会员等级 black，权益类型 coupon，活动批次 vip_2026_midyear。实际处理时，从用户当前消息、历史会话和记忆里拼请求字段。

返回结果里重点看：found、eligible、expected_benefits、delivered_benefits、missing_benefits、difference_reason、recommended_action、can_auto_compensate。只要能说明差异和下一步即可，不要把所有字段都机械复述给用户。

若 can_auto_compensate 为 true，可以告诉用户会进入补发或补偿；若 false，要说明需要复核或转人工。若 found 为 false，先核对订单号和用户身份，不要编造权益。

## 配送改派评估

用户要求改地址、改时间、提前送、晚点送、指定配送方式，或者说承诺没兑现时，需要评估是否可以改派。这个动作不等于直接改派，先判断可行性和风险。

可参考的评估入口是 POST http://127.0.0.1:8000/api/mock/fulfillment/reroute-plan。

请求参数大致包括：

order_id：订单号，必填。

address：新的收货地址或地址片段。

expected_delivery_time：用户希望送达的时间。

delivery_priority：配送优先级，可选，例如 normal、urgent。

package_type：包裹类型，可选，例如 standard、fresh、fragile。

样例：订单 A12345，地址“上海市浦东新区测试路 88 号”，希望 2026-06-18 18:00 前送达，优先级 urgent，包裹 standard。实际处理时也要从当前会话中抽字段，不要照抄样例。

返回后看是否 can_reroute、plan_id、risk_level、estimated_delivery_window、extra_cost、recommended_action。如果无法改派，给出原因和替代建议；如果可改派，先向用户确认会产生的变化，不要直接替用户提交。

## 补偿与闭环

权益补偿或配送改派都会影响用户预期。回复时保持三件事：

1. 已确认的信息是什么。
2. 系统核对或评估后的结果是什么。
3. 下一步需要用户确认、等待复核，还是可以继续执行。

如果用户同时提出多个诉求，不要把所有诉求挤成一个步骤。先处理当前最阻塞的事项，把另一个事项作为后续任务。
