# DEPRECATED — не использовать в новом коде

Краткий реестр устаревших путей и функций. Детали runtime: `docs/CURRENT_ARCHITECTURE.md`. Целевая схема: `docs/MULTICLIENT.md`.

**Правило:** не вызывать из нового кода; не копировать паттерн. При правках рядом — оставить комментарий `# DEPRECATED — see DEPRECATED.md`.

---

## Функции (замены)

| Символ | Замена | Статус |
|--------|--------|--------|
| `llm.classify_handoff_filter` | `ingress_gate.classify_ingress()` | legacy, не расширять |
| `llm.classify_intent` | `resolver.resolve()` (+ `RESOLVER_OFF=1` → shadow) | legacy safety-net |
| `query_selector.select_catalog_content_route` | `source_routing.route_source` (A3) | legacy, не расширять |

---

## Пути и конфиг (удалено / не использовать)

| Устаревшее | Статус |
|------------|--------|
| Корневой `md/` | **удалено** — только `clients/{id}/md/` |
| `clients/default/` | **удалено** — alias API `default` → pack `demo` |
| `data/corpus.jsonl`, `data/alias_*`, `data/demo-bot.db` | **удалено** — `data/{id}/` |
| `config.SQLITE_PATH` / общий `DATA_DIR` | не для runtime; сессии в `data/{id}/bot.db` |
| Fallback default → корневой md | **запрещено** |

---

## Документы

| Устаревшее | Замена |
|------------|--------|
| `work_info/widget.md` | `docs/WIDGET_ANSWER_FORMAT.md` |
| `docs/archive/*`, ARCHITECTURE V5 | `docs/MULTICLIENT.md`, `docs/CURRENT_ARCHITECTURE.md` |

При удалении deprecated-символа — убрать строку из этой таблицы в том же PR.
