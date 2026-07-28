# AfishaBot

Я разрабатываю Telegram Mini App и адаптивный сайт для поиска бесплатных офлайн-событий и людей по интересам на карте городов Дагестана.

Продуктовые решения и все существующие ADR согласованы. Сейчас я готовлю подробный архитектурный пакет G4 и backlog G5; production-реализация начнётся только после их подтверждения и моей отдельной однозначной команды.

Актуальные источники:

- [SOURCE_SPECIFICATION.md](SOURCE_SPECIFICATION.md) — полная неизменяемая Markdown-копия исходной спецификации 0.9;
- [CURRENT_SPECIFICATION_V1.md](CURRENT_SPECIFICATION_V1.md) — читаемый снимок действующих продуктовых и архитектурных правил v1.0;
- [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) — связь всех 28 пакетов исходных требований с текущими решениями;
- [PRODUCT_DECISIONS.md](PRODUCT_DECISIONS.md) — продуктовые правила `PD-001…PD-019`;
- [DECISIONS.md](DECISIONS.md) — актуальные архитектурные решения;
- [RISKS.md](RISKS.md) — риски и принятые остаточные риски;
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — порядок дальнейшей работы.

## Требования

- Python 3.14
- uv

## Установка

```bash
uv sync
```

Команды запуска и общей проверки будут добавлены после утверждения архитектурного skeleton.
