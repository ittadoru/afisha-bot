# Stage A — VPS и HTTPS

Статус: `ACCEPTED`. Все команды из этого документа выполняются только на
Ubuntu 24.04 VPS. Локальная машина используется для правок и Git-доставки.

## Публичная схема

- `podvval.xyz` обслуживает лендинг на `/` и текущую демонстрацию Mini App на
  `/app`;
- пользовательский API доступен под `/api`;
- `admin.podvval.xyz` получает тот же сертификат, но до реализации admin
  всегда отвечает `404`;
- host Nginx принимает только `80/443` и передаёт основной домен во внутренний
  Nginx на `127.0.0.1:8080`;
- PostgreSQL, Redis и служебные адреса наружу не публикуются.

## Подготовка сервера

1. Обновить Ubuntu и перезагрузить сервер, если обновилось ядро.
2. Установить Git, Docker Engine с Compose v2, Nginx, Certbot и UFW. Python и
   Node.js в host-систему для приложения не устанавливать.
3. Разрешить UFW только `OpenSSH`, `Nginx HTTP` и `Nginx HTTPS`.
4. Клонировать репозиторий в `/opt/afishabot`, проверить точный опубликованный
   commit и чистый checkout.
5. Передать игнорируемый `.env` отдельно, назначить владельца `root:root` и
   режим `600`. Значения файла не печатать в терминал или отчёт.

## Серверная проверка

В `/opt/afishabot`:

```bash
bash scripts/vps/preflight.sh
bash scripts/vps/verify_g6.sh
```

Gate должен выполняться на чистом checkout, чей `HEAD` совпадает с upstream.
При ошибке код исправляется локально, публикуется новый commit, а сервер снова
проверяет точный commit.

## Запуск Stage A

Для текущего MVP используется короткий сценарий развёртывания:

```bash
bash scripts/vps/deploy.sh
```

Он собирает только прикладные образы, один раз применяет миграции и запускает
`postgres`, `redis`, `api`, `bot`, `frontend` и `nginx`. Пустые `worker` и
`beat` находятся в профиле `jobs`; profiles `geo`, `geo-import` и `ops`
в обычный запуск не входят.

## Сертификат

До выпуска сертификата оба имени должны отвечать через публичный DNS:

- `podvval.xyz` → `194.5.65.112`;
- `admin.podvval.xyz` → `podvval.xyz`.

Сначала установить `deploy/host-nginx/podvval-bootstrap.conf`, создать
`/var/www/certbot` и проверить конфигурацию Nginx. Затем выпустить один
сертификат без изменения конфигурации:

```bash
certbot certonly --webroot --webroot-path /var/www/certbot \
  --email ittadoru@gmail.com --agree-tos --no-eff-email \
  -d podvval.xyz -d admin.podvval.xyz
```

После успешного выпуска заменить bootstrap-конфигурацию на
`deploy/host-nginx/podvval.conf`, проверить `nginx -t` и перечитать Nginx.
Для продления создать deploy hook, который выполняет `systemctl reload nginx`,
затем проверить `certbot renew --dry-run`.

## Приёмка

- HTTP обоих имён переводит на HTTPS;
- `/` показывает лендинг, `/app` открывается напрямую и после обновления;
- `admin.podvval.xyz` возвращает `404` по HTTPS;
- `/metrics` недоступен извне;
- снаружи открыты только `22`, `80`, `443`;
- `.env` имеет режим `600`, отсутствует в Git;
- после перезагрузки core-контейнеры возвращаются автоматически;
- пустые worker/beat, Nominatim и monitoring отсутствуют среди запущенных
  контейнеров.

После ручной проверки перезагрузки и `certbot renew --dry-run` выполнить:

```bash
bash scripts/vps/verify_stage_a.sh
```
