from unittest.mock import MagicMock

import pytest
import uvicorn

from afishabot import main


def test_console_entrypoint_starts_only_the_api_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = MagicMock()
    monkeypatch.setattr(uvicorn, "run", run)

    main.run()

    run.assert_called_once_with(
        "afishabot.main:app",
        host="0.0.0.0",
        port=8000,
    )
