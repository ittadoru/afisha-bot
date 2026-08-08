from afishabot.modules.communication.application.telegram_dispatch import (
    KIND_ICONS,
    _compose_text,
    _open_button,
)


def test_compose_text_combines_icon_title_and_body() -> None:
    items = [
        {
            "id": "a",
            "kind": "event_cancelled",
            "title": "Событие отменено",
            "body": "Проверить детали.",
        },
        {
            "id": "b",
            "kind": "looking_post.answer",
            "title": "Вам ответили",
            "body": "Прочитать ответ.",
        },
    ]
    text = _compose_text(items)
    assert text.startswith("🚫 Событие отменено\nПроверить детали.")  # noqa: RUF001
    assert "\n\n" in text
    second = text.split("\n\n", 1)[1]
    assert second.startswith("💬 Вам ответили\nПрочитать ответ.")  # noqa: RUF001


def test_unknown_kind_falls_back_to_megaphone() -> None:
    text = _compose_text(
        [{"id": "c", "kind": "mystery_kind", "title": "X", "body": "Y"}]
    )
    assert text.startswith("📣")


def test_missing_mini_app_url_yields_no_button() -> None:
    settings = type("Fake", (), {"afisha_mini_app_url": None})()
    assert _open_button(settings) is None


def test_open_button_uses_mini_app_url() -> None:
    url = "https://t.me/afisha_test_bot/app"
    settings = type("Fake", (), {"afisha_mini_app_url": url})()
    button = _open_button(settings)
    assert button is not None
    assert button.inline_keyboard[0][0].url == url


def test_kind_icons_cover_all_existing_kinds() -> None:
    existing_kinds = {
        "event_cancelled",
        "event_participation_excluded",
        "waitlist_promoted",
        "event_approved",
        "event_rejected",
        "event_changed",
        "looking_post.question",
        "looking_post.answer",
    }
    assert existing_kinds <= set(KIND_ICONS)
