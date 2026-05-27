# Skill Card Schema

```json
{
  "skill_id": "after_sales_refund",
  "name": "售后退款流程",
  "version": "1.0.0",
  "business_domain": "after_sales",
  "description": "处理用户退款、退货、取消订单等诉求。",
  "trigger_intents": ["退款", "退货"],
  "user_utterance_examples": ["我想退货"],
  "goal": ["确认用户退款诉求"],
  "required_info": ["order_id"],
  "steps": [
    {
      "step_id": "collect_order_info",
      "name": "收集订单信息",
      "instruction": "如果用户未提供订单号，询问订单号。",
      "expected_user_info": ["order_id"],
      "allowed_actions": ["ask_user", "call_tool:order.query"]
    }
  ],
  "interruption_policy": {
    "related_question": "可以临时回答，回答后回到当前流程。"
  },
  "response_rules": ["不要承诺一定能退款。"]
}
```
