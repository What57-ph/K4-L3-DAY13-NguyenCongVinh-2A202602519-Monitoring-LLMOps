from __future__ import annotations

from contextlib import contextmanager

from app import agent as agent_module


class ManagedPrompt:
    name = "day13-chat"
    version = 7

    def compile(self, **variables: str) -> str:
        return (
            f"Feature={variables['feature']}\n"
            f"Docs={variables['docs']}\n"
            f"Question={variables['message']}"
        )


class RecordingObservation:
    def __init__(self, attributes: dict) -> None:
        self.attributes = attributes
        self.updates: list[dict] = []

    def update(self, **kwargs) -> None:
        self.updates.append(kwargs)


class RecordingClient:
    def __init__(self) -> None:
        self.prompt = ManagedPrompt()
        self.span_updates: list[dict] = []

    def get_prompt(self, name: str, **kwargs):
        return self.prompt

    def update_current_span(self, **kwargs) -> None:
        self.span_updates.append(kwargs)


def test_agent_creates_retrieval_and_generation_children(monkeypatch) -> None:
    client = RecordingClient()
    observations: list[RecordingObservation] = []
    propagated: list[dict] = []

    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    @contextmanager
    def record_attributes(**kwargs):
        propagated.append(kwargs)
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", record_attributes)

    @contextmanager
    def record_observation(_client, *, enabled: bool, **attributes):
        observation = RecordingObservation(attributes)
        observations.append(observation)
        yield observation

    monkeypatch.setattr(agent_module, "start_as_current_observation", record_observation)

    agent = agent_module.LabAgent(model="test-model")
    agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="student-01",
        feature="qa",
        session_id="session-01",
        message="Explain monitoring traces",
        correlation_id="req-12345678",
    )

    assert [observation.attributes["as_type"] for observation in observations] == [
        "retriever",
        "generation",
    ]
    assert observations[0].attributes["name"] == "retrieve-context"
    assert observations[1].attributes["name"] == "generate-response"
    assert observations[1].attributes["model"] == "test-model"
    generation_update = observations[1].updates[-1]
    assert generation_update["usage_details"]["input"] > 0
    assert generation_update["usage_details"]["output"] > 0
    assert generation_update["cost_details"]["total"] > 0
    assert propagated[0]["metadata"]["correlation_id"] == "req-12345678"
    assert client.span_updates[-1]["input"] == {"message": "Explain monitoring traces"}
    assert "answer" in client.span_updates[-1]["output"]
