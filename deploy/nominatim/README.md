# Nominatim: адреса только для Дагестана

Nominatim работает внутри Docker и не публикует HTTP- или PostgreSQL-порты на
VPS. Backend обращается к нему по внутреннему адресу `http://nominatim:8080`.

Импорт выполняется один раз. Он скачивает extract Северо-Кавказского
федерального округа от Geofabrik, проверяет контрольную сумму, вырезает
Республику Дагестан по административной OSM relation `109876` и импортирует
только данные уровня `address`: населённые пункты, улицы и дома. POI,
Wikipedia, flatnode и автоматические OSM updates не используются.

## Требования

- Ubuntu 24.04 VPS с 6 GB RAM;
- уже установленные Docker Engine и Docker Compose;
- свободное место для исходного extract, временного extract Дагестана и базы;
- заполненный `NOMINATIM_PASSWORD` в закрытом `.env`;
- запуск из корня `/opt/afishabot` от root.

Установить единственные системные инструменты, необходимые для подготовки
файла:

```bash
apt-get update
apt-get install -y curl osmium-tool
```

Приложению не назначаются отдельные CPU или RAM limits. Во время первого
импорта сценарий останавливает API, bot, worker, beat, frontend и Nginx, чтобы
Nominatim мог использовать свободные ресурсы VPS.

## Первый импорт

Перед запуском проверить, что обычная база приложения сохранена и контейнеры
работают штатно. Затем выполнить:

```bash
cd /opt/afishabot
./scripts/vps/import_nominatim_dagestan.sh
```

Сценарий:

1. откажется работать, если успешный импорт уже отмечен или volume содержит
   Nominatim PostgreSQL;
2. скачает и проверит PBF;
3. вырежет Дагестан;
4. остановит необязательные сервисы;
5. запустит одноразовый `nominatim-import` и дождётся готовности;
6. проверит структуру базы и reverse lookup в Махачкале, Хасавюрте и Дербенте;
7. заменит import-контейнер обычным `nominatim` и вернёт приложение;
8. создаст игнорируемый Git маркер `var/nominatim/.import-complete`;
9. удалит загруженные и промежуточные PBF-файлы.

Импорт может идти долго и не должен прерываться закрытием SSH. Рекомендуемый
запуск через `tmux`:

```bash
apt-get install -y tmux
tmux new -s nominatim-import
cd /opt/afishabot
./scripts/vps/import_nominatim_dagestan.sh
```

Отсоединиться от сессии: `Ctrl+B`, затем `D`. Вернуться:

```bash
tmux attach -t nominatim-import
```

## Проверка после импорта

```bash
docker compose --profile geo ps
docker compose --profile geo logs --tail 100 nominatim
docker compose --profile geo exec -T nominatim \
  curl -fsS http://127.0.0.1:8080/status
```

Проверить три города:

```bash
docker compose --profile geo exec -T nominatim \
  curl -fsS 'http://127.0.0.1:8080/reverse?format=jsonv2&lat=42.9849&lon=47.5047'
docker compose --profile geo exec -T nominatim \
  curl -fsS 'http://127.0.0.1:8080/reverse?format=jsonv2&lat=43.2509&lon=46.5877'
docker compose --profile geo exec -T nominatim \
  curl -fsS 'http://127.0.0.1:8080/reverse?format=jsonv2&lat=42.0578&lon=48.2888'
```

Nominatim находит ближайший адрес, но не является проверкой разрешённой зоны.
Backend дополнительно сверяет координаты с административной границей выбранного
города. Поэтому точка вне Махачкалы, Хасавюрта или Дербента отклоняется до
сохранения события, даже если геокодер нашёл рядом какой-либо адрес.

Проверить, что порт не опубликован наружу:

```bash
docker compose --profile geo port nominatim 8080
```

Команда не должна вывести публичный адрес порта.

## Обычный запуск и перезагрузка

После первого успешного импорта `scripts/vps/deploy.sh` замечает локальный
маркер и запускает профиль `geo` вместе с приложением. У контейнера установлен
`restart: unless-stopped`, поэтому после перезагрузки VPS он поднимается без
повторного импорта.

Не запускайте `nominatim-import` вручную и не удаляйте volume
`nominatim_data`. Обычный сервис получает обязательное для Docker-образа имя
`PBF_PATH`, но при наличии внутреннего `import-finished` исходный файл повторно
не читает и импорт не запускает.

## Если первый импорт завершился ошибкой

Посмотреть причину:

```bash
docker compose --profile geo-import logs --tail 200 nominatim-import
docker compose --profile geo-import stop nominatim-import
```

Временные PBF-файлы при ошибке сохраняются в `var/nominatim`, чтобы не
скачивать их заново до диагностики. Сценарий никогда не перезаписывает уже
существующую базу Nominatim.

Если это был именно первый неудачный импорт, volume может содержать неполную
базу. Его удаление является отдельным разрушительным действием: перед повтором
нужно убедиться, что рабочей базы Nominatim ещё не было, остановить контейнер и
только затем вручную удалить соответствующий volume. Сценарий намеренно не
делает этого автоматически.

Ручное обновление OSM пока не реализовано. До отдельного этапа данные остаются
в состоянии на дату первого импорта.
