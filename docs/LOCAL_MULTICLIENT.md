# Локальный multiclient (demo / cesi / nikadent)

## Быстрый старт

1. Запустить бота: `python app.py`
2. Открыть: `http://127.0.0.1:9001/static/multiclient/index.html` (порт из `.env`)

## Postgres + admin (cesi / nikadent)

```bash
docker compose up -d postgres
```

В `.env`:

```env
BOT_PG_DSN=postgresql://bot:bot@localhost:5432/bot_events
```

Админка (отдельный терминал):

```bash
python admin_dashboard/app.py
```

Открыть: `http://127.0.0.1:9100/?client_id=cesi`

Таблицы создаются автоматически при первом событии (`pg_sink.py`).

## Заявки (cesi / nikadent)

**Почта получателей** — в git, по клиенту:

- `clients/cesi/lead_config.yaml` → `recipients`
- `clients/nikadent/lead_config.yaml` → `recipients`

**SMTP-сервер** — в `.env` (локально и на VPS свои значения):

```env
SMTP_HOST=mail.artgents.ru
SMTP_PORT=465
SMTP_USE_SSL=1
SMTP_USE_TLS=0
SMTP_USER=bot@artgents.ru
SMTP_PASSWORD=...   # пароль от ящика, только в .env
SMTP_FROM=bot@artgents.ru
```

Порт **465** — SSL (`SMTP_SSL`). Порт **587** — STARTTLS (`SMTP_USE_TLS=1`, `SMTP_USE_SSL=0`).

Без `SMTP_HOST` + `SMTP_FROM` заявка сохранится в Postgres (если PG включён), но письмо не уйдёт — в админке будет `email_smtp_not_configured`.

**Demo** — заявки не отправляются (`features.yaml`: `leads.enabled: false`, текст про демо в `clients/demo/tone.yaml`).

**Часы работы (cesi / nikadent):** `clients/{id}/clinic_policies.yaml` → блок `hours` (timezone + расписание по дням). Вне рабочего времени после заявки показывается `lead.submit_ok_after_hours` из `tone.yaml`.

## Конфиги клиента

| Файл | Назначение |
|------|------------|
| `clients/{id}/tone.yaml` | фразы lead / situation |
| `clients/{id}/ui.yaml` | guided menu, fallback-ответы |
| `clients/{id}/features.yaml` | leads, PG, consult_nudge |
| `clients/{id}/widget_config.json` | виджет + theme |

`client_id=default` в API мапится на пакет `demo`.

## Индекс базы знаний (M2 — обязательно после правок md)

Каждый клиент — свой индекс в `data/{id}/`:

```bash
python build_index.py --client all
# или по одному:
python build_index.py --client cesi
```

Нужен `OPENAI_API_KEY` в `.env`. Без индекса бот не найдёт ответы в md.

Сессии: `data/{id}/bot.db` (отдельно для demo / cesi / nikadent).

## API

- `GET /api/widget-config?client_id=demo` — конфиг embed-страниц
