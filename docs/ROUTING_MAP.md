# Карта маршрутизации

**Статус:** черновик Phase 0; детализация — Phase 2 (Routing Cleanup).  
**Парный документ:** `CURRENT_ARCHITECTURE.md`.

Цель: один документ «куда уходит вопрос» без чтения всего `app.py`.

---

## Порядок проверок (сверху вниз)

| # | Условие | Куда | Модуль |
|---|---------|------|--------|
| 1 | `cta_action`, situation, lead active | Сценарный ответ | `flow_handlers` |
| 2 | Booking intent | Booking / redirect | `flow_handlers` |
| 3 | `ref` в теле | Chunk по ref | `retriever.get_chunk_by_ref` |
| 4 | Пустой / duplicate / anti-spam | Service payload | `app.py` |
| 5 | «Да» / lead / situation pending | Не retrieval | `flow_handlers` |
| 6 | Короткое продолжение + `current_doc_id` | `#korotko` | `app.py` |
| 7 | Resolver или `classify_intent` | `effective_intent` | `resolver` / `llm` |
| 8 | Contacts overlay | Contacts chunk | `app.py` + `retrieve` |
| 9 | A3 `route_source` | doctor / catalog / price | `source_routing` |
| 10 | Иначе | Retrieval + arbiter | `query_selector`, `arbiter` |

---

## Intent → ветка

| Intent / сигнал | Источник | Примечание |
|-----------------|----------|------------|
| contacts | MD chunk `clinic__info__contacts` | topk retrieve + pick |
| price_lookup | `prices.json` / price ref | `select_price_service_route` |
| price_concern | `concern_ref` или generic payload | |
| doctor | `doctors_lookup` | cards / overview / doc ref |
| catalog facts | `service_catalog` без MD | facts card |
| catalog md | `md_entry_ref` | приоритетный ref |
| content / retrieval fallback | RAG + rerank (+ arbiter) | topic scope опционально |

---

## Env / флаги

| Переменная | Эффект |
|------------|--------|
| `RESOLVER_OFF=1` | Только `classify_intent`, Resolver в shadow |

---

## TODO (Phase 2)

- [ ] Таблица legacy vs Resolver для каждой ветки
- [ ] Примеры запросов → `source` + `ref` + `service_id`
- [x] Список DEPRECATED — `DEPRECATED.md` (корень)
- [ ] Golden-ссылки на `evals/v5/`

**Не добавлять сюда guide_router до Phase 4.**
