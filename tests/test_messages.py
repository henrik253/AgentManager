import pytest

from agent_manager.messages import parse_client_message, validate_prompt_submission


def test_parse_client_message_requires_json_object():
    with pytest.raises(ValueError, match="JSON object"):
        parse_client_message("[]")


def test_validate_prompt_submission_accepts_prompt_and_routing_hints():
    submission = validate_prompt_submission(
        {
            "type": "prompt.submit",
            "prompt": "Fix the tests",
            "backend": "codex",
            "model": "default",
        }
    )

    assert submission == {
        "prompt": "Fix the tests",
        "backend": "codex",
        "model": "default",
        "workspace": None,
    }


def test_validate_prompt_submission_rejects_empty_prompt():
    with pytest.raises(ValueError, match="non-empty prompt"):
        validate_prompt_submission({"type": "prompt.submit", "prompt": "   "})


def test_validate_prompt_submission_accepts_workspace_hints():
    submission = validate_prompt_submission(
        {
            "type": "prompt.submit",
            "prompt": "Start task B",
            "workspace": {
                "mode": "create_worktree",
                "branch": "agent-task/task-b",
            },
        }
    )

    assert submission["workspace"] == {
        "mode": "create_worktree",
        "branch": "agent-task/task-b",
        "worktree_path": None,
    }
