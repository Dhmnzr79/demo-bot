# Документация

| Документ | Зачем |
|----------|--------|
| **`CURRENT_ARCHITECTURE.md`** | Как бот работает **сейчас** (runtime, модули, пайплайн) |
| **`MULTICLIENT.md`** | Client pack, домены, VPS, локальный запуск, prod-критерии |
| **`ROUTING_MAP.md`** | Куда уходит вопрос (маршруты до retrieval) |
| **`WIDGET_ANSWER_FORMAT.md`** | Контракт текста ответа для виджета |
| **`DASHBOARD.md`** | Admin, Postgres, события, cost |
| **`TECH_DEBT.md`** | Открытый долг и следующие шаги |

Корень репо: `DEPRECATED.md`, `contracts/`, `core/routing.yaml`.

**Правило:** код и `CURRENT_ARCHITECTURE.md` не расходятся — правим вместе в одном PR.

---

## Cursor (обязательно)

1. `README.md` → `CURRENT_ARCHITECTURE.md` → `MULTICLIENT.md` → `TECH_DEBT.md`
2. Задача по UI: `WIDGET_ANSWER_FORMAT.md`
3. Задача по admin/PG: `DASHBOARD.md`
4. Задача по маршрутам: `ROUTING_MAP.md`

---

## Evals

- Smoke: `evals/v5/run_e2e_smoke.py`
- Layer: `evals/v5/run_layer_eval.py`
