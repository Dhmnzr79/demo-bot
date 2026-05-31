# Tech Debt

Активный долг. План работ: **`MULTICLIENT.md`**. Runtime: **`CURRENT_ARCHITECTURE.md`**.

---

## Multiclient (блокер изоляции)

| Проблема | Направление |
|----------|-------------|
| Корневой `md/` + `clients/default/` | ~~удалено~~ только `clients/{id}/` |
| Один `DATA_DIR` / corpus | ~~done~~ `core/client_data_loader.py` → `data/{id}/` |
| Один `SQLITE_PATH` | ~~done~~ `session.py` → `data/{id}/bot.db` |
| `doctors_lookup` → корневой `md/` | ~~done~~ `clients/{id}/md/` |
| Нет Origin guard на `/ask` | ~~M1~~ `core/origin_guard.py`; prod: `origin_required` без Origin/Referer |
| Lead stub hardcoded | ~~M3~~ email + `lead_config.yaml` (`core/lead_email.py`) |
| Legacy `_startup_check` → `data/` | ~~done~~ `core/startup_check.py` per `data/{id}/` |
| `BASE_SYSTEM` / «бесплатная» в коде | ~~done~~ `core/llm_system_prompt.py` + `features.messaging.free_consultation` |
| Host → `client_id` | ~~done~~ `core/client_host.py` (prod: поддомен `*.bot.*`) |
| Legacy `/dashboard` в prod | ~~done~~ 404; использовать `admin_dashboard/` |

**Контент перед prod (ещё вручную):** `demo_video.mp4` в `video_catalog.yaml`; `allowed_origins` — домены сайтов клиник; персонализация `starterPrompts`.


---

## Runtime / код

| Проблема | Направление |
|----------|-------------|
| `app.py` большой | Routing cleanup после M5 |
| Legacy `classify_intent` + Resolver | evals → свести |
| `enqueue_lead` не вызывается | ~~M3~~ PG + email в `lead_service` |
| Нет `pending_followup_ref` | Guide phase |

---

## Качество

| Проблема | Направление |
|----------|-------------|
| Нет golden routing per client | Phase evals после M5 |
| Evals частично (`evals/v5/`) | расширить по `client_id` |

---

## Observability

| Проблема | Направление |
|----------|-------------|
| Admin требует PG — demo без | `features.yaml` |
| JSONL + PG параллельно | норма, см. `DASHBOARD.md` |

При закрытии — удалить строку из таблицы в PR.
