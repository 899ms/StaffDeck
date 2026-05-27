from app.core.skill_runtime import SkillRuntime
from app.db.models import ChatSession
from app.session.session_schema import RouterDecision


def test_suspend_and_restore_skill_stack():
    session = ChatSession(
        id="session_test",
        tenant_id="tenant_demo",
        active_skill_id="repair_ticket",
        active_step_id="collect_repair_info",
        slots_json={"asset_id": "EQ-9"},
    )
    runtime = SkillRuntime()

    runtime.apply_decision(
        session,
        RouterDecision(
            decision="suspend_current_and_start_new_skill",
            target_skill_id="visitor_badge",
            target_step_id="collect_visit_info",
        ),
    )

    assert session.active_skill_id == "visitor_badge"
    assert session.active_step_id == "collect_visit_info"
    assert session.slots_json == {}
    assert session.skill_stack_json[0]["skill_id"] == "repair_ticket"

    runtime.apply_decision(session, RouterDecision(decision="exit_current_skill"))

    assert session.active_skill_id == "repair_ticket"
    assert session.active_step_id == "collect_repair_info"
    assert session.slots_json == {"asset_id": "EQ-9"}


def test_related_question_restores_after_answer():
    session = ChatSession(
        id="session_test",
        tenant_id="tenant_demo",
        active_skill_id="repair_ticket",
        active_step_id="collect_repair_info",
    )
    runtime = SkillRuntime()

    runtime.apply_decision(
        session,
        RouterDecision(
            decision="answer_related_question_then_resume",
            target_skill_id="repair_ticket",
            target_step_id="answer_warranty_policy",
            should_resume_after_answer=True,
        ),
    )
    assert session.active_step_id == "answer_warranty_policy"
    assert session.resume_after_answer_json == {
        "skill_id": "repair_ticket",
        "step_id": "collect_repair_info",
    }

    runtime.finish_interrupt_response(session)

    assert session.active_step_id == "collect_repair_info"
    assert session.resume_after_answer_json is None
