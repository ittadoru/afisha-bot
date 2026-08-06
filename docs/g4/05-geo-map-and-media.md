# G4 — география, карта и media

Статус: `ACCEPTED`. Документ объединяет прежние G4.15 и G4.18, а также
принятые media/storage границы.

## Географическая модель

PostGIS хранит event point как `geography(Point, 4326)` и использует
GiST-index. Публикация разрешена только внутри утверждённого polygon выбранного
города. Выбранная пользователем точка — источник истины; geocoder только
возвращает понятную подпись.

Canonical geo record содержит point, normalized address, street/city/region,
provider/place ID, locale, precision/confidence и canonical street ID/geometry.
Raw provider response не становится доменной моделью.

## Reverse geocoding

- Клиент двигает центральную marker; запрос начинается через 500 мс после
  `moveend`.
- Новый move отменяет ожидающий запрос; stale response игнорируется.
- Browser обращается только к backend; Nominatim закрыт.
- Общий deadline — 2,5 секунды, максимум один bounded retry.
- Private HMAC-keyed cache живёт не более 24 часов и не участвует в
  authorization.
- Provider outage не изменяет point, но блокирует публикацию, пока отсутствует
  обязательная безопасная address projection.

Nominatim использует региональный extract по bbox трёх городов (Махачкала,
Хасавюрт, Дербент) с запасом примерно 20 км вместо всего Дагестана (PD-021);
без flatnode. Перед публичным выпуском вручную проверяются реальные точки
трёх городов. URL/checksum extract задаются вне Git.

## Карта и projections

MapLibre получает style/tiles OpenFreeMap из конфигурации. Обязательны
attribution и list fallback. Public OSM tile server не используется.

Event marker приходит только из discovery projection:

- exact marker — только если caller имеет exact projection;
- street marker — стабильный anchor canonical street geometry; anchor —
  центроид (средняя точка) geometry, должен находиться внутри city boundary
  (PD-021);
- скрытая event point не участвует в расчёте street anchor;
- отсутствие валидной street geometry закрывает street-only публикацию.

Диаграмма: [выбор street anchor](diagrams/15-street-anchor-selection.mmd).

Exact и approximate marker различаются формой, подписью и screen-reader text,
не только цветом. Постоянная legend объясняет различие. Keyboard/touch/list
дают одинаково доступную карточку. Кластеризация не входит в MVP до измеримой
плотности.

Public map API принимает city + bbox/zoom и server limit. Пользовательская
геолокация и расстояние «Рядом со мной» не собираются.

## Provider boundaries

`MapProvider` возвращает только конфигурацию безопасного browser tile source.
`ReverseGeocodingProvider` принимает point/locale и возвращает canonical DTO
или typed timeout/unavailable/not-found/malformed failure. Domain не импортирует
provider SDK.

Смена tile/geocoder выполняется adapter/config без изменения domain contract.
Собственные vector tiles возвращаются в работу только по post-demand trigger и
на отдельном сервере.

## Media lifecycle

Media хранится в защищённой локальной директории за `MediaStorage` adapter.
PostgreSQL содержит metadata и attachment ID, но не binary. Volume доступен
только API, worker и будущему scoped backup process; прямой public file server
и object-storage emulator отсутствуют.

Pipeline:

1. создать короткоживущую upload session с owner/purpose/limits;
2. записать файл в quarantine под случайным именем;
3. проверить размер, declared/decoded type и pixel limit;
4. полностью decode, применить orientation/crop и re-encode;
5. удалить EXIF/metadata и original;
6. создать безопасный derivative: для единственной обязательной фотографии
   Event — `16:9`, для avatar — `256×256 WebP`;
7. moderation/owner use case переводит attachment в ready/rejected;
8. выдавать файл только через scoped application check.

Arbitrary remote URL не принимается. Filename, MIME и client metadata не
доверяются. Image bomb, malformed или неподдерживаемый файл удаляется и не
публикуется. В MVP Event принимает ровно одну фотографию; смена фотографии
проходит тот же pipeline и moderation path.

Attachment lifecycle и object-owner lifecycle согласуются фактами.
Idempotent cleanup удаляет orphan/quarantine/expired media. Off-server backup
provider и реальный backup job относятся к Slice 9.
