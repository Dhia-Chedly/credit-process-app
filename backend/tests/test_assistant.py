import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.assistant.services import AssistantAnswer, answer_question
from apps.assistant.tools import TOOL_DEFINITIONS, ToolResult


@pytest.fixture
def operator() -> User:
    return User.objects.create_user(username="assistant-operator", password="test-password")


@pytest.mark.django_db
def test_assistant_requires_authentication() -> None:
    response = APIClient().post(
        reverse("assistant:messages"),
        {"message": "Résume le portefeuille."},
        format="json",
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_assistant_returns_a_structured_answer(operator: User) -> None:
    client = APIClient()
    client.force_authenticate(operator)
    expected = AssistantAnswer(
        answer="Le portefeuille contient 12 demandes.",
        sources=[{"type": "analytics", "label": "Vue d'ensemble"}],
        links=[{"label": "Ouvrir", "url": "/"}],
        suggestions=["Comparer les agences"],
    )

    with patch("apps.assistant.views.answer_question", return_value=expected) as mocked:
        response = client.post(
            reverse("assistant:messages"),
            {
                "message": "Résume le portefeuille.",
                "history": [{"role": "assistant", "content": "Bonjour"}],
            },
            format="json",
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": expected.answer,
        "sources": expected.sources,
        "links": expected.links,
        "suggestions": expected.suggestions,
    }
    mocked.assert_called_once_with(
        message="Résume le portefeuille.",
        history=[{"role": "assistant", "content": "Bonjour"}],
        user=operator,
    )


@pytest.mark.django_db
def test_assistant_rejects_excessive_history(operator: User) -> None:
    client = APIClient()
    client.force_authenticate(operator)

    response = client.post(
        reverse("assistant:messages"),
        {
            "message": "Résume le portefeuille.",
            "history": [{"role": "user", "content": "Question"}] * 7,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "history" in response.json()


def test_every_assistant_tool_uses_a_closed_strict_schema() -> None:
    for tool in TOOL_DEFINITIONS:
        assert tool["strict"] is True
        parameters = tool["parameters"]
        assert isinstance(parameters, dict)
        assert parameters["additionalProperties"] is False
        assert set(parameters["required"]) == set(parameters["properties"])


def test_answer_question_executes_model_selected_read_only_tool(settings: object) -> None:
    settings.OPENAI_MODEL = "test-model"  # type: ignore[attr-defined]
    function_call = SimpleNamespace(
        type="function_call",
        name="get_portfolio_summary",
        arguments=json.dumps({"date_from": None, "date_to": None, "agency_names": None}),
        call_id="call-1",
    )
    first_response = SimpleNamespace(output=[function_call], output_text="")
    final_response = SimpleNamespace(output=[], output_text="Le portefeuille contient 12 demandes.")
    client = MagicMock()
    client.responses.create.side_effect = [first_response, final_response]
    tool_result = ToolResult(
        data={"summary": {"total_requests": 12}},
        sources=[{"type": "analytics", "label": "Vue d'ensemble"}],
        links=[{"label": "Ouvrir", "url": "/"}],
    )

    with (
        patch("apps.assistant.services._client", return_value=client),
        patch("apps.assistant.services.execute_tool", return_value=tool_result) as execute,
    ):
        answer = answer_question(message="Combien de demandes ?", history=[], user=object())

    assert answer.answer == "Le portefeuille contient 12 demandes."
    assert answer.sources == tool_result.sources
    assert answer.links == tool_result.links
    execute.assert_called_once()
    second_input = client.responses.create.call_args_list[1].kwargs["input"]
    assert second_input[-1]["type"] == "function_call_output"
    assert second_input[-1]["call_id"] == "call-1"
