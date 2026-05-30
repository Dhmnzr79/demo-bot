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

## Конфиги клиента

| Файл | Назначение |
|------|------------|
| `clients/{id}/tone.yaml` | фразы lead / situation |
| `clients/{id}/ui.yaml` | guided menu, fallback-ответы |
| `clients/{id}/features.yaml` | leads, PG, consult_nudge |
| `clients/{id}/widget_config.json` | виджет + theme |

`client_id=default` в API мапится на пакет `demo`.

## API

- `GET /api/widget-config?client_id=demo` — конфиг embed-страниц
