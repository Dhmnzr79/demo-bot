# Roadmap

Краткий указатель. **Детали multiclient:** `MULTICLIENT.md` (M0–M6). **Runtime:** `CURRENT_ARCHITECTURE.md`.

---

## Сейчас: Multiclient (Phase M0–M6)

| Фаза | Содержание |
|------|------------|
| **M0** | Инвентаризация контента demo / cesi / nikadent |
| **M1** | `clients/{id}/`, client_runtime, doctors_lookup, Origin |
| **M2** | `data/{id}/`, client_data_loader, session per client |
| **M3** | `features.yaml`, `lead_config.yaml`, demo vs бой |
| **M4** | Postgres + admin локально |
| **M5** | Smoke, Caddy, VPS |
| **M6** | Docs sync, удаление legacy `md/`, `default/` |

---

## После M5

| Phase | Содержание |
|-------|------------|
| **Routing cleanup** | `ROUTING_MAP.md`, orchestration из `app.py` |
| **Evals** | Golden routing per `client_id` |
| **Guide layer** | `features.yaml` → guide_router |
| **Live consultant** | dialog_manager |
| **Platform** | n8n, Redis — только при необходимости |

---

## Docs cleanup ✅

- Удалены дубликаты и `docs/archive/`
- Канон: `README`, `MULTICLIENT`, `CURRENT_ARCHITECTURE`, `DASHBOARD`, `ROADMAP`, `TECH_DEBT`, `WIDGET_ANSWER_FORMAT`, `PRODUCT_PRINCIPLES`, `ROUTING_MAP`
