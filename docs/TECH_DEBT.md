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
| Smoke routing guards + `meta.service_route` | `evals/v5/e2e_smoke.json`, runner | **3 ✓** |
| `orchestration/route_guards.py` | pre-Resolver guards | **3 ✓** |
| `orchestration/ask_turn.py` + price/catalog/retrieval flows | post-Resolver | **3 ✓** |
| `pre_resolver_turn` + `resolver_turn` + `lead_flow` | pre-Resolver + Resolver | **3 ✓** |
| `finalize_turn.py`; slim `app.py` | dispatch остаётся в `app.py` | **3 ✓** |
| Legacy `classify_intent` только safety-net / `RESOLVER_OFF` | `resolver.resolve_with_fallback` | **3 ✓** |
| Smoke multiclient (`client_id` per case) | cesi, nikadent contacts | **3 ✓** |
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
