from app.logging_config import JsonlFileProcessor, scrub_event
from app import logging_config


def test_pii_scrubber_handles_nested_and_top_level_values() -> None:
    event = scrub_event(
        None,
        "error",
        {
            "detail": "student@vinuni.edu.vn",
            "payload": ["0901234567", {"cccd": "001234567890"}],
        },
    )

    assert "student@vinuni.edu.vn" not in str(event)
    assert "0901234567" not in str(event)
    assert "001234567890" not in str(event)


def test_pii_scrubber_runs_before_file_writer_and_json_renderer() -> None:
    logging_config.configure_logging()
    processors = logging_config.structlog.get_config()["processors"]
    scrub_index = processors.index(logging_config.scrub_event)
    file_index = next(
        index
        for index, processor in enumerate(processors)
        if isinstance(processor, JsonlFileProcessor)
    )
    renderer_index = next(
        index
        for index, processor in enumerate(processors)
        if isinstance(processor, logging_config.structlog.processors.JSONRenderer)
    )

    assert scrub_index < file_index < renderer_index
