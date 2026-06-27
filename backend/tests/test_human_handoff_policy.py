from app.core.agent_loop import AgentLoop
from app.session.slot_policy import strip_router_generated_message_slots


def test_handoff_requires_structured_step_declaration():
    loop = AgentLoop.__new__(AgentLoop)

    assert loop._step_declares_human_handoff({"allowed_actions": ["answer_user", "handoff_human"]})
    assert loop._step_declares_human_handoff({"type": "handoff"})
    assert loop._step_declares_human_handoff({"handoff": {"enabled": True}})

    assert not loop._step_declares_human_handoff({"description": "用户要求转人工时请转人工"})
    assert not loop._step_declares_human_handoff({"name": "转人工确认"})
    assert not loop._step_declares_human_handoff({"allowed_actions": ["answer_user", "continue_flow"]})


def test_router_generated_message_slots_are_not_persisted():
    cleaned = strip_router_generated_message_slots(
        {
            "message_content": "模型改写后的用户消息",
            "user_message": "另一个改写版本",
            "current_message": "当前输入摘要",
            "product_id": "A1",
            "quantity": 1,
        }
    )

    assert cleaned == {"product_id": "A1", "quantity": 1}
