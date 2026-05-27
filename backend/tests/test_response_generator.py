from app.core.response_generator import ResponseGenerator
from app.db.models import ChatSession
from app.llm.client import LLMClient
from app.session.session_schema import RouterDecision, StepAgentResult
from app.tools.tool_schema import ToolResult


def test_clarify_does_not_leak_internal_router_prompt():
    session = ChatSession(
        id="session_test",
        tenant_id="tenant_demo",
        active_skill_id="repair_ticket",
        active_step_id="collect_repair_info",
    )
    decision = RouterDecision(
        decision="clarify",
        clarification_question="请提供当前用户消息、会话状态、技能进度及可用技能列表，以便进行准确的路由决策。",
    )
    step_result = StepAgentResult(reply="好的，请描述一下设备问题，我会继续为您处理。")

    reply = ResponseGenerator().generate(
        message="我想报修设备",
        session=session,
        skill=None,
        router_decision=decision,
        step_result=step_result,
        tool_result=None,
        model_config=None,  # type: ignore[arg-type]
    )

    assert reply == step_result.reply
    assert "技能进度" not in reply
    assert "路由" not in reply


def test_tool_result_reply_is_model_driven(monkeypatch):
    def fake_init(self, model_config):  # noqa: ANN001
        return None

    def fake_generate_text(self, system_prompt, payload):  # noqa: ANN001
        assert payload["tool_result"]["tool_name"] == "ticket.create"
        return "已创建报修工单 T-100，工程师会尽快联系您。"

    monkeypatch.setattr(LLMClient, "__init__", fake_init)
    monkeypatch.setattr(LLMClient, "generate_text", fake_generate_text)

    reply = ResponseGenerator().generate(
        message="设备坏了",
        session=ChatSession(id="session_test", tenant_id="tenant_demo"),
        skill=None,
        router_decision=RouterDecision(decision="continue_current_skill"),
        step_result=StepAgentResult(),
        tool_result=ToolResult(
            tool_name="ticket.create",
            success=True,
            data={"ticket_id": "T-100", "status": "created"},
        ),
        model_config=None,  # type: ignore[arg-type]
    )

    assert reply == "已创建报修工单 T-100，工程师会尽快联系您。"
