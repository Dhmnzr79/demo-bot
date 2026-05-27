# Правки демо-ветки (для переноса в боевой бот)

Краткий чеклист по изменениям с первого демо-пуша (`45b6aba` → `HEAD`).  
**Не включено:** цены, врачи, алиасы, массовые правки md-контента.

---

## 1. Персона и промпты генератора (`llm.py`)

- Имя консультанта: **Надежда** (в `BASE_SYSTEM`).
- Переписан **BASE_SYSTEM**: без лишней «заботы», ответ с сути, точные цифры из источника.
- Уточнён **GENERATOR_SINGLE_SOURCE_RULE** (роль контекста диалога).
- Расширен **EMPATHY_ADDON**: список запрещённых клише, короткая фраза → сразу суть.

---

## 2. Сценарий записи / lead flow

### Тексты (`app.py` → `TXT`)

- Старт записи и запрос телефона — **без** упоминания демо (обычный вежливый тон).
- Фраза про демо / CRM / почту — **только** после успешной отправки телефона (`lead_submit_ok`).
- После описания ситуации: «Спасибо, записала… передадим в клинику… Как к вам можно обращаться?»

### Логика (`flow_handlers.py`, `app.py`)

- **`resume_active_lead_flow`**: если в сессии активна запись, оркестратор не уводит в контент/guided (имя, телефон, подтверждение имени).
- Кнопка меню **«Хочу записаться»** → ref `lead:booking` → старт записи.
- Ingress и фильтр **obvious noise** **не срабатывают** во время активной записи (`collecting_name` / `phone` / `confirming_name`) и при `situation_pending` — иначе ломались «вася», номер телефона.
- Антиспам **burst / soft redirect** отключены, пока идёт активная запись.

---

## 3. Ingress и шаблоны клиники

- **`ingress_gate.py`**: пробел между номером телефона и срочным хвостом (`manual_contact` + `is_urgent`).
- **`clients/default/clinic_policies.yaml`**: шаблоны hard_stop / manual_contact (без правок md).

---

## 4. Guided-меню (неясный вопрос)

- Текст без «Понял.»: «Могу коротко подсказать… что для вас важнее?»
- **4 кнопки:** Стоимость имплантации, Больно ли ставить имплант?, Что будет на консультации?, Хочу записаться.
- Не показывается, если активна запись (см. п. 2).

---

## 5. Антиспам (`config.py`, `docs/BOT_PORTRAIT.md`)

- **`ANTI_SPAM_NO_INTENT_TURNS`**: дефолт **10 → 20** (ходы пользователя без `booking_intent_ever` → один мягкий редирект на консультацию).
- Burst по-прежнему: 6 сообщений за 120 сек (не меняли).

---

## 6. Виджет (`static/widget/`)

- **Лаунчер / welcome:** демо-карточка, стартовые подсказки, бренд, `botName: Надежда`.
- **Фазы «печатает»:** «Ищет в базе знаний…» только для контента/цен; для записи — сразу «Печатает ответ…» (эвристика + SSE `event: typing`).
- **Видео в чате:** inline player, кнопка «Посмотреть видео с врачом», каталог с API.
- **Стили:** фиолетовая палитра (#6952e8), typing, телефон в lead-step.
- **`widget-test.html`**: конфиг под демо.

---

## 7. Видео (backend)

- **`clients/default/video_catalog.yaml`** + **`core/video_catalog_loader.py`**
- **`app.py`**: `GET /api/video-catalog`, `GET /api/media/<key>` (прокси MP4, CORS).
- **`policy.py`**: `video` в ответе через `resolve_video_payload` (proxy URL), не голый `video_key`.

---

## 8. Стриминг ответа (`app.py`, `chunk_responder.py`, `static/widget/api.js`)

- SSE: первым идёт **`event: typing`** (`searching` | `writing`), затем `text_delta` / `ui` / `done`.
- Маршрут `service_reply` (запись, ingress, цены без стрима) — typing + ui без дельт.

---

## 9. Прочее по коду (по желанию в боевой)

- **`ux_builder.py`**: price clarify — альтернатива из `clinic_policies` (если переносите price-flow).
- **`evals/v5/`**: обновления smoke / ingress / arbiter golden под новое поведение.
- **`static/avatar.png`**: аватар виджета.

---

## Файлы «ядра» (куда смотреть в diff)

| Зона | Файлы |
|------|--------|
| Оркестрация / guided / антиспам | `app.py` |
| Запись | `flow_handlers.py` |
| Ingress | `ingress_gate.py` |
| Промпты | `llm.py` |
| Конфиг | `config.py` |
| Политики клиники | `clients/default/clinic_policies.yaml` |
| Видео | `core/video_catalog_loader.py`, `policy.py` |
| Виджет | `static/widget/widget.js`, `api.js`, `widget.css`, `widget-test.html` |
| SSE | `chunk_responder.py` |

---

*Документ для внутреннего переноса; не заменяет `git diff` и коммиты `444d3dc`, `0662bec`, `7069688`.*
