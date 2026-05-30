# Tech Debt

Активный долг. План работ: **`MULTICLIENT.md`**. Runtime: **`CURRENT_ARCHITECTURE.md`**.

---

## Multiclient (блокер изоляции)

| Проблема | Направление |
|----------|-------------|
| Корневой `md/` + `clients/default/` | M1: только `clients/{id}/` |
| Один `DATA_DIR` / corpus | M2: `client_data_loader` |
| Один `SQLITE_PATH` | M2: `session.py` → `data/{id}/bot.db` |
| `doctors_lookup` → корневой `md/` | M1 |
| Нет Origin guard на `/ask` | M1 |
| Lead stub hardcoded | M3: `lead_config.yaml` |

---

## Runtime / код

| Проблема | Направление |
|----------|-------------|
| `app.py` большой | Routing cleanup после M5 |
| Legacy `classify_intent` + Resolver | evals → свести |
| `enqueue_lead` не вызывается | M3 prod lead |
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
