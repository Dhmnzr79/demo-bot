# Документация проекта

**Два слоя:** как работает код **сейчас** и куда идём **дальше**. Исторический архив V5 удалён из репо (копия у владельца).

| Слой | Файлы |
|------|--------|
| **План multiclient** | `MULTICLIENT.md` ← главный вектор |
| **Runtime сейчас** | `CURRENT_ARCHITECTURE.md` |
| **Дашборд / PG / admin** | `DASHBOARD.md` |
| **Общая очередность** | `ROADMAP.md` |
| **Долг** | `TECH_DEBT.md` |

Если код расходится с `CURRENT_ARCHITECTURE.md` — правим код **или** документ в том же PR.

---

## Обязательно читать (Cursor)

1. `README.md` (этот файл)
2. **`MULTICLIENT.md`** — изоляция demo / cesi / nikadent, M0–M6
3. `CURRENT_ARCHITECTURE.md` — фактический runtime до закрытия §4.1 MULTICLIENT
4. `ROADMAP.md`
5. `TECH_DEBT.md`
6. `DEPRECATED.md` (корень), `contracts/`, `core/routing.yaml`

---

## По задаче

| Задача | Документ |
|--------|----------|
| Multiclient, VPS, client pack | **`MULTICLIENT.md`** |
| Админка, Postgres, события | **`DASHBOARD.md`** |
| Маршрутизация | `ROUTING_MAP.md` |
| Виджет, стриминг, JSON ответа | `WIDGET_ANSWER_FORMAT.md` |
| Тон, UX, продукт | `PRODUCT_PRINCIPLES.md` |

---

## Evals

- Smoke: `evals/v5/run_e2e_smoke.py`
- Layer: `evals/v5/run_layer_eval.py`
