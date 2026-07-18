"""Interview state machine tests — valid/invalid transitions, events."""
import pytest


class TestInterviewStateMachine:
    def test_state_machine_create_session(self):
        from src.interview_runtime import get_interview_state_machine, InterviewStage
        sm = get_interview_state_machine()

        state = sm.create_session("sess-sm-1", "technical")
        assert state.stage == InterviewStage.IDLE
        assert state.interview_type == "technical"

    def test_valid_transitions(self):
        from src.interview_runtime import get_interview_state_machine, InterviewStage
        sm = get_interview_state_machine()

        sm.create_session("sess-sm-2", "behavioral")

        assert sm.transition("sess-sm-2", InterviewStage.WELCOME)
        assert sm.transition("sess-sm-2", InterviewStage.INTRO)
        assert sm.transition("sess-sm-2", InterviewStage.QUESTION_DELIVERY)
        assert sm.transition("sess-sm-2", InterviewStage.USER_SPEAKING)

    def test_invalid_transition(self):
        from src.interview_runtime import get_interview_state_machine, InterviewStage
        sm = get_interview_state_machine()

        sm.create_session("sess-sm-3", "coding")

        # Cannot go from IDLE directly to EVALUATION
        result = sm.transition("sess-sm-3", InterviewStage.EVALUATION)
        assert result is False

    def test_pause_and_resume(self):
        from src.interview_runtime import get_interview_state_machine, InterviewStage
        sm = get_interview_state_machine()

        sm.create_session("sess-sm-4", "system_design")
        sm.transition("sess-sm-4", InterviewStage.WELCOME)
        sm.transition("sess-sm-4", InterviewStage.INTRO)
        sm.transition("sess-sm-4", InterviewStage.QUESTION_DELIVERY)

        # Pause
        paused = sm.pause("sess-sm-4")
        assert paused

        state = sm.get_state("sess-sm-4")
        assert state.stage == InterviewStage.PAUSED

        # Resume
        resumed = sm.resume("sess-sm-4")
        assert resumed

    def test_interrupt(self):
        from src.interview_runtime import get_interview_state_machine, InterviewStage
        sm = get_interview_state_machine()

        sm.create_session("sess-sm-5", "technical")
        sm.transition("sess-sm-5", InterviewStage.WELCOME)
        sm.transition("sess-sm-5", InterviewStage.QUESTION_DELIVERY)
        sm.transition("sess-sm-5", InterviewStage.USER_SPEAKING)

        interrupted = sm.interrupt("sess-sm-5")
        assert interrupted

        state = sm.get_state("sess-sm-5")
        assert state.stage == InterviewStage.INTERRUPTED
        assert state.interruption_count == 1

    def test_transition_history(self):
        from src.interview_runtime import get_interview_state_machine, InterviewStage
        sm = get_interview_state_machine()

        sm.create_session("sess-sm-6", "behavioral")
        sm.transition("sess-sm-6", InterviewStage.WELCOME)
        sm.transition("sess-sm-6", InterviewStage.INTRO)

        history = sm.get_transition_history("sess-sm-6")
        assert len(history) >= 3  # initial + 2 transitions
