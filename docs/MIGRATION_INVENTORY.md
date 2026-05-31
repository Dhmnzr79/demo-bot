# M0 — инвентаризация и карта миграции

**Дата:** 2026-05-30  
**Фаза:** M0 (инвентаризация) + минимальный M1 (каркас client pack)  
**Runtime не менялся:** `app.py`, `retriever.py`, `session.py`, корневой `md/`, `clients/default/` — на месте.

---

## 1. Что найдено

### 1.1. Корневой `md/` — 47 файлов

Выдуманная демо-клиника (Москва, ул. Тверская; тел. +7 (495) 128-47-60). Все файлы **без** подпапки `client_id` — runtime читает их как общий корень.

| Группа | Файлы (кол-во) | Примеры |
|--------|----------------|---------|
| `clinic__info__*` | 6 | contacts, consultation, advantages, warranty, technology, payment_terms |
| `doctors__doctor__*` | 7 | overview, orlov, kuznetsov, morozova, grigoriev, fedorova, volkov |
| `implantation__*` | 23 | faq (7), info (7), pricing (3), service (6) |
| `treatment__service__*` | 3 | caries, pulpitis, teeth_treatment |
| `prosthetics__service__*` | 5 | veneers, crowns, dentures, … |
| `orthodontics__service__*` | 1 | aligners |
| `periodontology__service__*` | 1 | periodontitis |
| `extraction__service__*` | 1 | tooth_extraction |

**Маркеры «это demo»:** вымышленный адрес/врачи, demo-видео в `video_catalog.yaml`, текст заявки «это демо-бот» в `app.py`.

### 1.2. `clients/default/` — 4 файла

| Файл | Содержание |
|------|------------|
| `service_catalog.json` | 18 услуг (имплантация, протезирование, КТ, отбеливание, …) |
| `prices.json` | 18 price_key (от 3 000 ₽ КТ до 195 000 ₽ элайнеры) |
| `clinic_policies.yaml` | Тел. +7 (495) 128-47-60; нет детской/ОМС/ДМС; альтернатива брекеты→элайнеры |
| `video_catalog.yaml` | 1 видео `pain-doctor-explains` (S3 demo_video.mp4) |

Runtime сейчас резолвит `client_id=default` → эти файлы (`core/*_loader.py`).

### 1.3. `data/` — только перечень (не трогали)

| Файл | Назначение | Примечание |
|------|------------|------------|
| `corpus.jsonl` | 105 чанков индекса | все с `"client_id": "default"` |
| `embeddings.npy` | векторы corpus | общий индекс |
| `alias_rows.jsonl` | 1010 alias-строк | общий |
| `alias_embeddings.npy` | векторы aliases | общий |
| `demo-bot.db` (+ `-wal`, `-shm`) | SQLite сессий | один файл на процесс |

**Целевое (M2):** `data/demo/`, `data/cesi/`, `data/nikadent/` с отдельными corpus/embeddings/bot.db.

### 1.4. Контент cesi / nikadent в репозитории

**Не найден.** В git нет папок, md или json с реальными данными ЦЭСИ или НикаДент.  
`MULTICLIENT.md` указывает «контент cesi есть» — вероятно, **вне этого репо** (старый боевой бот / отдельный архив).

---

## 2. Карта миграции (куда что пойдёт)

### → `clients/demo/` (показ на artgents.ru)

| Источник | Что переносится | Когда |
|----------|-----------------|-------|
| `md/*.md` (47 файлов) | `clients/demo/md/` | Phase M1 (полный перенос) |
| `clients/default/service_catalog.json` | `clients/demo/service_catalog.json` | M1 |
| `clients/default/prices.json` | `clients/demo/prices.json` | M1 |
| `clients/default/clinic_policies.yaml` | `clients/demo/clinic_policies.yaml` | M1 |
| `clients/default/video_catalog.yaml` | `clients/demo/video_catalog.yaml` | M1 |
| `data/*` | `data/demo/*` | M2 + пересборка индекса |
| Тексты `app.py` TXT (demo) | уже в `clients/demo/tone.yaml` | M3 подключение в коде |

**Сейчас (M0+M1 scaffold):** каркас `clients/demo/` + конфиги; legacy **не удалён**, контент **ещё не скопирован**.

**`client_id`:** целевой `demo`. Сейчас runtime использует `default` — переименование в M1 вместе с `DEFAULT_CLIENT_ID`.

### → `clients/cesi/` (боевая клиника)

| Источник | Что переносится | Когда |
|----------|-----------------|-------|
| Контент старого боевого бота | md, catalog, prices, policies, video | M1 после получения от владельца |
| SMTP / тексты заявок | `lead_config.yaml`, `tone.yaml` | M3 |
| Сайт клиники | `widget_config.allowed_origins` | M1 |
| Бренд | `brand.yaml` | M1 |

**Не брать из demo:** адрес Тверская, вымышленные врачи, demo-видео, demo-текст заявки.

### → `clients/nikadent/` (контент скоро)

| Статус | Действие |
|--------|----------|
| Контента в репо нет | Каркас + конфиги-заглушки |
| md / catalog / prices | Заполнить, когда будут материалы от владельца |
| Индекс | `data/nikadent/` после M2 |

### Оставить без изменений (до cutover M6)

- `md/` (корень)
- `clients/default/`
- `data/` (корень)

---

## 3. Созданный каркас (M1 scaffold)

```text
clients/
  demo/          features.yaml, lead_config.yaml, widget_config.json, brand.yaml, tone.yaml, md/
  cesi/          … (те же конфиги, боевые defaults)
  nikadent/      … (заглушки null / REPLACE_*)
  _template/     … (копировать для новых клиник)
  default/       ← legacy, не тронут
```

Runtime **пока не читает** новые конфиги — подключение в M3 (`features.yaml`, `lead_config.yaml`, `tone.yaml`) и M1 §4.1 (`client_runtime`, Origin guard).

---

## 4. Вопросы к владельцу

### Demo

1. **Подтвердить:** весь текущий `md/` + `clients/default/` — это **только demo**, не ЦЭСИ?
2. **Домены embed (demo):** `artgents.ru` + `www` в `allowed_origins`; API на `demo.bot.artgents.ru` (`apiBase` в widget_config). ~~demo.artgents.ru~~ не используем.
3. **Демо на промо:** виджет остаётся с `client_id=demo` или временно `default` до cutover?
4. **Бренд demo:** оставляем фиолетовую палитру (#6952e8) и имя бота «Надежда»?

### ЦЭСИ (cesi)

5. **Где контент?** Путь к старому боевому боту / архиву md, prices, catalog (не в этом репо).
6. **Реальные контакты:** адрес, телефоны, WhatsApp, часы, метро/парковка — для `clinic__info__contacts.md` и `clinic_policies.yaml`.
7. **Врачи:** список `doctors__*.md` — ФИО, специализация, стаж, фото (если нужно в виджете).
8. **Цены и услуги:** актуальный `prices.json` + `service_catalog.json` или правим существующий demo-каркаталог?
9. **Политики:** детская стomatология, ОМС, ДМС, брекеты — что отличается от demo?
10. **Заявки:** email получателей, тема письма, нужен ли дубль в Postgres сразу?
11. **Сайт для embed:** URL клиники для `allowed_origins` (кроме `cesi.bot.artgents.ru`).
12. **Бренд:** hex-цвета, лого (URL или файл), имя бота в виджете.
13. **Видео:** есть ли ролики для `video_catalog.yaml`?

### НикаДент (nikadent)

14. **Срок контента:** когда ожидать md / prices / врачей?
15. **`client_id` финальный?** `nikadent` или другое имя для DNS?
16. **Те же вопросы, что для cesi** (контакты, заявки, бренд, сайт) — по мере готовности.

### Общее

17. **Третья клиника «на днях»:** имя `client_id` заранее?
18. **VPS / SMTP:** есть ли уже `.env` с SMTP для cesi или настраиваем с нуля в M4–M5?

---

## 5. Следующие шаги (не в этом PR)

| Phase | Работа |
|-------|--------|
| M1 | Копирование контента demo → `clients/demo/`; `core/client_runtime.py`; Host → client_id |
| M2 | `data/{id}/`, `client_data_loader`, client-aware `session.py` |
| M3 | Чтение `features.yaml` / `lead_config.yaml` / `tone.yaml` в runtime |
| M6 | Удаление `md/`, `clients/default/` после smoke |

---

## 6. Критерии готовности M0 + scaffold ✅

- [x] Инвентаризация `md/`, `clients/default/`, перечень `data/`
- [x] Карта миграции demo / cesi / nikadent
- [x] Каркас `clients/{demo,cesi,nikadent,_template}/` + конфиги
- [x] Runtime не изменён; legacy не удалён
- [x] Список вопросов к владельцу
