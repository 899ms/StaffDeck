from __future__ import annotations

from app.db.models import ChatSession, utc_now
from app.session.session_schema import RouterDecision


class SkillRuntime:
    def apply_decision(self, session: ChatSession, decision: RouterDecision) -> ChatSession:
        current_frame = {
            "skill_id": session.active_skill_id,
            "step_id": session.active_step_id,
            "slots": session.slots_json or {},
            "summary": session.summary,
            "last_agent_question": session.last_agent_question,
        }

        if decision.decision == "start_skill":
            session.active_skill_id = decision.target_skill_id
            session.active_step_id = decision.target_step_id
            session.slots_json = {}
            session.resume_after_answer_json = None

        elif decision.decision in {"continue_current_skill", "jump_within_current_skill"}:
            if decision.target_step_id:
                session.active_step_id = decision.target_step_id

        elif decision.decision in {
            "answer_related_question_then_resume",
            "answer_chitchat_then_resume",
        }:
            if session.active_skill_id and session.active_step_id:
                session.resume_after_answer_json = {
                    "skill_id": session.active_skill_id,
                    "step_id": session.active_step_id,
                }
            if decision.target_skill_id:
                session.active_skill_id = decision.target_skill_id
            if decision.target_step_id:
                session.active_step_id = decision.target_step_id

        elif decision.decision == "suspend_current_and_start_new_skill":
            stack = list(session.skill_stack_json or [])
            target_frame = None
            for index in range(len(stack) - 1, -1, -1):
                if stack[index].get("skill_id") == decision.target_skill_id:
                    target_frame = stack.pop(index)
                    break
            if current_frame["skill_id"]:
                stack.append(current_frame)
            session.skill_stack_json = stack
            if target_frame:
                session.active_skill_id = target_frame.get("skill_id")
                session.active_step_id = target_frame.get("step_id") or decision.target_step_id
                session.slots_json = target_frame.get("slots") or {}
                session.summary = target_frame.get("summary")
                session.last_agent_question = target_frame.get("last_agent_question")
            else:
                session.active_skill_id = decision.target_skill_id
                session.active_step_id = decision.target_step_id
                session.slots_json = {}
            session.resume_after_answer_json = None

        elif decision.decision == "exit_current_skill":
            stack = list(session.skill_stack_json or [])
            if stack:
                frame = stack.pop()
                session.skill_stack_json = stack
                session.active_skill_id = frame.get("skill_id")
                session.active_step_id = frame.get("step_id")
                session.slots_json = frame.get("slots") or {}
                session.summary = frame.get("summary")
                session.last_agent_question = frame.get("last_agent_question")
            else:
                session.active_skill_id = None
                session.active_step_id = None
                session.slots_json = {}
                session.resume_after_answer_json = None

        elif decision.decision == "handoff_human":
            session.status = "handoff"

        session.updated_at = utc_now()
        return session

    def complete_current_skill(self, session: ChatSession) -> ChatSession:
        stack = list(session.skill_stack_json or [])
        if stack:
            frame = stack.pop()
            session.skill_stack_json = stack
            session.active_skill_id = frame.get("skill_id")
            session.active_step_id = frame.get("step_id")
            session.slots_json = frame.get("slots") or {}
            session.summary = frame.get("summary")
            session.last_agent_question = frame.get("last_agent_question")
        else:
            session.active_skill_id = None
            session.active_step_id = None
            session.slots_json = {}
            session.resume_after_answer_json = None
        session.updated_at = utc_now()
        return session

    def finish_interrupt_response(self, session: ChatSession) -> ChatSession:
        resume = session.resume_after_answer_json
        if resume:
            session.active_skill_id = resume.get("skill_id")
            session.active_step_id = resume.get("step_id")
            session.resume_after_answer_json = None
            session.updated_at = utc_now()
        return session
