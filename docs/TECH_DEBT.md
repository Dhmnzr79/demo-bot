# Tech Debt

Открытый долг. Runtime: **`CURRENT_ARCHITECTURE.md`**. Ops / prod: **`MULTICLIENT.md`**.

---

## До prod (M5)

| Задача | Примечание |
|--------|------------|
| VPS + Caddy + wildcard `*.bot.artgents.ru` | один bot-сервис |
| Smoke 10–20 вопросов на клиента | цена, врач, контакты, lead |
| `allowed_origins` — реальные домены сайтов клиник | не только bot-поддомены |
| Контент nikadent / финализация cesi | `NOT_PROD.md` в pack |
| `demo_video.mp4` в demo `video_catalog.yaml` | placeholder |

---

## Runtime / код

| Задача | Направление | Phase |
|--------|-------------|-------|
| Карта маршрутов | `docs/ROUTING_MAP.md` | **2 ✓** |
| `app.py` большой | вынести `orchestration/` | **3** |
| Smoke на маршруты + legacy cleanup | evals + таблица legacy в ROUTING_MAP | **3** |
| Smoke runner ↔ orch_route (полное покрытие service_route) | `run_e2e_smoke._infer_route_from_response` | **3** |
| Legacy `classify_intent` + Resolver | evals → свести к Resolver | **3** |
| Golden routing per `client_id` | `evals/v5/` | **3** |
| `pending_followup_ref` / guide_router | после стабильного routing | **4** |

---

## Observability

| Задача | Направление |
|--------|-------------|
| Admin без PG для demo | норма (`features.yaml`) |
| JSONL + PG параллельно | см. `DASHBOARD.md` |

---

## Закрыто (не возвращать)

Multiclient M1–M4 локально: client packs, `data/{id}/`, `client_data_loader`, per-client session/SQLite, Host+Origin, leads email, admin token, legacy `md/` + `clients/default/` удалены.

При закрытии новой задачи — удалить строку из таблицы в PR.
