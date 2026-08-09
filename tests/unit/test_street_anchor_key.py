from afishabot.modules.discovery.application.street_anchors import street_key


def test_street_key_removes_russian_street_prefix_and_normalizes_yo() -> None:
    assert street_key("  ул.  Тотурбиёва ") == "тотурбиева"
    assert street_key("улица Тотурбиева") == "тотурбиева"
