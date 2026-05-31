# Мультиклиентность — план внедрения

**Статус:** канон multiclient (реализовано локально M1–M4; prod — M5).  
**Runtime:** `CURRENT_ARCHITECTURE.md`.  
**Долг:** `TECH_DEBT.md`.

---

## 1. Решение в одном абзаце

**Один движок, один репозиторий, много строго изолированных клиентских пакетов.**

Demo, ЦЭСИ, НикаДент и следующие клиники — **не отдельные боты и не отдельные ветки git**, а разные `client_id` с собственными данными. Demo — клиент с выключенными заявками и демо-текстами. Боевые клиники — клиенты с заявками, админкой и своим контентом.

Старый боевой бот используется **только как источник контента и интеграций** (md, цены, SMTP), не как вторая кодовая база.

---

## 2. Главные правила (нерушимые)

1. **Общий только код** — Python, виджет, routing, evals runner.
2. **Всё клиентское — в `clients/{client_id}/` и `data/{client_id}/`.**
3. **Бот ищет ответы только внутри текущего `client_id`.**
4. **Никакого fallback** из `cesi` в `demo`, из `nikadent` в `default`, из корневого `md/` в клиента.
5. **Индекс (corpus + embeddings + aliases) собирается отдельно** для каждого клиента.
6. **Сессии (SQLite) — отдельный `bot.db`** на клиента в `data/{client_id}/` (через client-aware слой, §4.1).
7. **Заявки, админка, guide-router, demo-режим** — через конфиг клиента (`features.yaml`, `lead_config.yaml`), не через `if client_id == ...` в коде.
8. **Секреты** (OpenAI, SMTP, пароли админки) — только в `.env` на сервере, не в git.

Изоляция в коде: `core/client_runtime.py`, `core/client_data_loader.py`, client-aware `session.py` — см. `CURRENT_ARCHITECTURE.md`.

---

## 3. Клиенты (текущий список)

| `client_id` | Назначение | Статус |
|-------------|------------|--------|
| `demo` | Показ заказчикам на artgents.ru | есть |
| `cesi` | ЦЭСИ | контент есть |
| `nikadent` | НикаДент | контент скоро |
| *(TBD)* | Третья клиника | возможно на днях |

Имена **финальные** — они же в DNS, админке и git. Не использовать абстрактные `clinic-a`.

---

## 4. Структура репозитория (целевая)

```text
clients/
  demo/
    md/                      # вся база знаний demo
    service_catalog.json
    prices.json
    clinic_policies.yaml
    video_catalog.yaml
    widget_config.json       # embed, allowed_origins, тексты виджета
    brand.yaml               # цвета, лого (или ссылка на CSS vars)
    tone.yaml                # тон LLM, тексты lead/situation
    features.yaml            # что включено у этого клиента
    lead_config.yaml         # demo_stub | email | webhook

  cesi/
    md/
    service_catalog.json
    prices.json
    clinic_policies.yaml
    video_catalog.yaml
    widget_config.json
    brand.yaml
    tone.yaml
    features.yaml
    lead_config.yaml

  nikadent/
    ...

data/
  demo/
    corpus.jsonl
    embeddings.npy
    alias_rows.jsonl
    alias_embeddings.npy
    bot.db                   # SQLite сессий

  cesi/
    ...

  nikadent/
    ...
```

### Что в каждом файле (кратко)

| Файл | Содержимое |
|------|------------|
| `md/` | FAQ, услуги, врачи (`doctors__*.md`), контакты, цены-объяснения |
| `service_catalog.json` | Услуги, aliases, `md_entry_ref`, `price_key` |
| `prices.json` | Цифры для price_lookup |
| `clinic_policies.yaml` | «Нет детской», «нет ОМС», альтернативы услуг |
| `video_catalog.yaml` | Ключи видео для виджета |
| `widget_config.json` | Приветствие, teaser, **`allowed_origins`** (whitelist для проверки на сервере) |
| `brand.yaml` | Палитра виджета, лого URL |
| `tone.yaml` | Системный промпт, тексты lead/situation |
| `features.yaml` | `leads: false`, `admin: false`, `guide_router: false`, … |
| `lead_config.yaml` | Режим доставки, email получателей, webhook URL (позже) |

**Врачи:** только в `clients/{client_id}/md/` (файлы `doctors__*.md`), без отдельного `doctors.json`.

### 4.1. Client-aware runtime ✅

Реализовано в коде:

| Модуль | Поведение |
|--------|-----------|
| `core/client_runtime.py` | пути pack md, `data/{id}/`, sqlite |
| `core/client_data_loader.py` | corpus, embeddings, alias_* per client |
| `session.py` | `data/{id}/bot.db` |
| `meta_loader.py` | только `clients/{id}/md/` |
| `retriever.py` | loader текущего клиента |
| `doctors_lookup.py` | `clients/{id}/md/doctors__*.md` |
| `core/client_host.py` | Host `*.bot.*` → `client_id` (prod) |
| `core/origin_guard.py` | Origin/Referer vs `allowed_origins` |

Legacy удалён: корневой `md/`, `clients/default/`, общий `data/corpus.jsonl`.

---

## 5. Пример `features.yaml`

```yaml
# clients/demo/features.yaml
leads:
  enabled: false
  mode: demo_stub          # показывает flow, заявка никуда не уходит

admin:
  enabled: false             # demo не в боевой админке

postgres_events:
  enabled: false             # опционально: отдельная demo-БД

guide_router:
  enabled: false

ingress:
  strict: true
```

```yaml
# clients/cesi/features.yaml
leads:
  enabled: true
  mode: email                # или file, webhook — см. lead_config.yaml

admin:
  enabled: true

postgres_events:
  enabled: true

guide_router:
  enabled: false             # см. TECH_DEBT.md
```

---

## 6. Пример `lead_config.yaml`

```yaml
# clients/cesi/lead_config.yaml
delivery: email
recipients:
  - admin@clinic.example
subject_template: "Заявка с бота ЦЭСИ"
store_in_postgres: true
```

```yaml
# clients/demo/lead_config.yaml
delivery: demo_stub
success_message_key: demo_lead_ok   # текст из tone.yaml
```

---

## 7. Домены и `client_id`

```text
artgents.ru (обычный хостинг, не VPS)
  промо-лендинг + embed виджета demo
  Origin в allowed_origins demo; API → demo.bot.artgents.ru

demo.bot.artgents.ru (VPS, wildcard *.bot.artgents.ru)
  client_id = demo  (Host → client_id)
  leads off, PG опционально

cesi.bot.artgents.ru
  client_id = cesi

nikadent.bot.artgents.ru
  client_id = nikadent

*.bot.artgents.ru
  wildcard DNS/TLS — для 30–40 клиентов

admin.bot.artgents.ru
  admin_dashboard (только боевые client_id)
```

**Правило:** API бота живёт только на **`{client_id}.bot.artgents.ru`**. Host **однозначно** задаёт `client_id` в prod (`core/client_host.py`). Лендинг клиники / artgents.ru — отдельный сайт; виджет ходит на API своего bot-поддомена.

**Demo:** страница на `artgents.ru` грузит конфиг с `https://demo.bot.artgents.ru/api/widget-config` (`clients/demo/widget_config.json` → `apiBase`). Локально `static/multiclient/demo.html` сбрасывает `apiBase` на same-origin.

**Не использовать** `demo.artgents.ru` как API-host — в коде нет mapping без сегмента `.bot.`, на prod будет 403.

**Embed и бюджет OpenAI:** список `allowed_origins` в `widget_config.json` — только конфиг. Защита работает, если **сервер на `/ask` и `/lead` проверяет `Origin` / `Referer` (и при необходимости согласованность с Host)** по этому списку и отклоняет запросы с чужих сайтов. Одного поля в JSON недостаточно.

---

## 8. Инфраструктура на VPS (3–4 клиента, без Redis/n8n)

**Reverse proxy:** **Caddy** (единый выбор в этом проекте) — HTTPS и wildcard `*.bot.artgents.ru` с меньшей возней, чем ручной Nginx + certbot. Rate limit — на Caddy и/или в боте.

Минимальный состав:

| Компонент | Назначение |
|-----------|------------|
| **Caddy** | TLS, wildcard `*.bot.artgents.ru`, прокси на bot и admin |
| **1× bot (gunicorn)** | Один сервис на все поддомены; Host → `client_id`; см. workers ниже |
| **PostgreSQL** | `bot_events`, `leads` — с колонкой `client_id` |
| **admin_dashboard** | `:9100`, `ADMIN_DASHBOARD_TOKEN` |
| **`.env` на сервере** | Секреты, `BOT_PG_DSN`, OpenAI |

**Workers (gunicorn):**

- **Старт (3–4 клиента, низкая нагрузка):** `-w 1` — ок при client-aware SQLite (§4.1).
- **Не обещать `-w 1` навсегда** для 30–40 клиентов: после стабильного §4.1 можно поднять workers или второй инстанс; долгосрочно сессии в PG снимают привязку к одному SQLite-файлу на worker.

**Не нужно сейчас:** Redis, n8n, отдельный CRM. Webhook в `lead_config.yaml` — задел на потом.

**Масштаб 30–40 клиентов (архитектурно):** тот же wildcard + **один bot-сервис** возможен, если изоляция данных через `data/{id}/` и §4.1 закрыты. Это не значит «один worker на всё время» — только «не 40 отдельных процессов на 40 клиник».

```text
                    ┌──────────────────┐
  artgents.ru       │                  │     (embed → demo.bot…)
  demo.bot...       │   bot :8000      │──► data/demo/, data/cesi/, …
  cesi.bot...       │   (один код)     │
  nikadent.bot...   │                  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
  admin.bot...      │  PostgreSQL      │
                    │  admin :9100     │
                    └──────────────────┘
```

---

## 9. Безопасность

| Угроза | Мера |
|--------|------|
| Спам / DDoS на `/ask` | Caddy rate limit + лимиты в боте (`RATE_LIMIT_*`) |
| Перегрузка VPS | Лимит длины вопроса; caps OpenAI; workers по нагрузке (§8) |
| Подбор пароля админки | Сильный token; HTTPS; по желанию IP allowlist |
| Чужой сайт жжёт OpenAI | **Сервер:** проверка `Origin`/`Referer` по `widget_config.allowed_origins` на `/ask` |
| Утечка контента клиники А в Б | Строгий `client_id` + нет fallback + отдельный индекс |
| Утечка диалогов | PG и SQLite с `client_id`; телефоны redacted в логах |
| Debug на prod | `APP_ENV=prod`, debug-роуты 404 |
| Секреты в git | Только `.env.example` без значений |

---

## 10. Статус фаз

| Фаза | Статус | Комментарий |
|------|--------|-------------|
| **M0** | ✅ | инвентаризация (архив удалён) |
| **M1** | ✅ | client packs, runtime paths, Host, Origin |
| **M2** | ✅ | `data/{id}/`, loader, session, build_index |
| **M3** | ✅ | features, lead_config, tone, demo vs бой |
| **M4** | ✅ локально | Postgres + admin_dashboard |
| **M5** | ⏳ | VPS, Caddy, prod smoke |
| **M6** | ✅ | legacy удалён, docs sync |

**После M5 (не блокер запуска):** routing cleanup (`ROUTING_MAP`), guide_router, webhook CRM — см. `TECH_DEBT.md`.

---

## 10.1. Локальная разработка

**Бот:** `python app.py` → `http://127.0.0.1:9001/static/multiclient/index.html` (порт из `.env`).

**Postgres + admin (cesi / nikadent):**

```bash
docker compose up -d postgres
python admin_dashboard/app.py   # :9100
```

`.env`: `BOT_PG_DSN=postgresql://bot:bot@localhost:5432/bot_events`

**Индекс** (после правок md):

```bash
python build_index.py --client all
# или: python build_index.py --client cesi
```

**Заявки:** получатели в `clients/{id}/lead_config.yaml`; SMTP в `.env`. Demo — `leads.enabled: false`.

**API alias:** `client_id=default` в запросе → pack `demo`.

---

## 10.2. Старый чеклист фаз (архив)

<details>
<summary>M0–M6 детальный список (исторический)</summary>

### Phase M0 — Инвентаризация

- [x] Список md, json, yaml по demo / cesi / nikadent
- [x] Карта миграции demo / cesi / nikadent

### Phase M1 — Структура + runtime

- [x] `clients/{demo,cesi,nikadent}/`
- [x] `core/client_runtime.py`, meta_loader, doctors_lookup
- [x] Host → client_id; Origin guard

### Phase M2 — Индекс и сессии

- [x] `client_data_loader`, retriever, `build_index --client`
- [x] `session.py` → `data/{id}/bot.db`
- [x] Удалён общий `data/corpus.jsonl`

### Phase M3 — Demo vs бой

- [x] lead_service + features + lead_config + tone

### Phase M4 — Админка

- [x] Postgres локально, admin_dashboard

### Phase M5 — Prod

- [ ] Caddy + wildcard + HTTPS
- [ ] Деплой + smoke на VPS

### Phase M6 — Legacy

- [x] Удалены корневой `md/`, `clients/default/`
- [x] Docs sync

</details>

---

## 11. Критерии готовности («можно в prod»)

1. Правка md **только** в `clients/cesi/md/` → пересборка **только** `data/cesi/` → nikadent **не меняется**.
2. Запрос с `client_id=nikadent` **никогда** не возвращает doc_id из cesi (smoke).
3. Demo: заявка с телефоном → `demo_stub`, нет записи в `leads` PG.
4. CESI: заявка → email и/или строка в PG, видна в admin.
5. Admin: фильтр по `client_id`, HTTPS + token.
6. Нет legacy-путей (`md/`, `clients/default/`, общий corpus) в репо и runtime.
7. Client-aware loader, session, doctors, meta — без fallback на чужой pack.
8. Запрос `/ask` с чужим `Origin` → отказ (prod, если origin не в `allowed_origins`).

---

## 12. Что сознательно откладываем

| Отложено | Почему можно | Как добавить потом |
|----------|--------------|-------------------|
| Redis | 3–40 клиентов на VPS без очередей | кеш / rate limit |
| n8n | заявки через email/webhook достаточно | webhook в `lead_config.yaml` |
| Отдельный CRM | не блокер | тот же webhook |
| SaaS-биллинг | не нужен на 4 клиники | `clients/{id}/plan.yaml` |
| guide_router | после стабильного routing | `features.yaml` |

---

## 13. Риски

| Риск | Митигация |
|------|-----------|
| Забыли пересобрать индекс после md | CLI + чеклист в PR |
| Остался fallback на `default` | grep + smoke + удаление корневого md |
| Demo случайно шлёт лиды | `features.yaml` + smoke |
| Конкурент embed без origin | enforce Origin на сервере + `allowed_origins` |
| Папки разложены, код старый | §11 п.7; smoke врачей и retrieval |
| Один SQLite на всех в одном процессе | `session.py` client-aware (§4.1) |
| Два источника правды (старый бой + новый) | freeze старого боя после cutover cesi |

---

## 14. Следующие шаги (код)

См. **`TECH_DEBT.md`**: VPS (M5), routing cleanup, guide_router, evals per client.

---

## 15. Чеклист для владельца (не программист)

При правке контента **ЦЭСИ**:

1. Открыть только `clients/cesi/md/` и `clients/cesi/prices.json` (и catalog при необходимости).
2. **Не трогать** `clients/nikadent/`, `clients/demo/`, папки `data/`.
3. После правок — попросить «пересобрать индекс для cesi» (одна команда у разработчика).
4. Проверить 3–5 вопросов на стенде cesi.

При добавлении **новой клиники**:

1. Скопировать каркас `clients/_template/` → `clients/newclinic/`.
2. Заполнить контент.
3. Собрать индекс `data/newclinic/`.
4. DNS: `newclinic.bot.artgents.ru`.
5. Smoke + включить в admin.

---

*Документ создан по согласованному решению: один движок, изолированные пакеты, wildcard DNS, Postgres для боевой админки.*
