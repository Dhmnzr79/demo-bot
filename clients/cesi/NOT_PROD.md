# NOT PROD — контент ЦЭСИ

**Статус:** временная копия demo-контента. **Не деплоить на боевой VPS** без замены маркеров ниже.

## Что ещё demo / вымышленное

| Маркер | Где | Заменить на |
|--------|-----|-------------|
| ул. Тверская, 12 | `md/clinic__info__contacts.md` | реальный адрес ЦЭСИ |
| +7 (495) 128-47-60 | contacts, `clinic_policies.yaml` | телефон ЦЭСИ |
| Врачи (Орлов, Кузнецов, …) | `md/doctors__doctor__*.md` | врачи ЦЭСИ |
| `demo_video.mp4` | `video_catalog.yaml` | видео ЦЭСИ или убрать |
| «бесплатная консультация» | md, fallback в коде | политика ЦЭСИ |

## Перед prod

1. Правки в `clients/cesi/md/`, prices, policies.
2. Пересборка `data/cesi/` (Phase M2).
3. `lead_config.yaml` — реальный email.
4. `widget_config.json` — `allowed_origins` сайта клиники.
5. Smoke 5–10 вопросов на стенде cesi.

См. также `docs/MIGRATION_INVENTORY.md`.
