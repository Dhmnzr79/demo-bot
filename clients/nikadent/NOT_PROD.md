# NOT PROD — контент НикаДент

**Статус:** временная копия demo-контента. **Не деплоить на боевой VPS** без замены маркеров ниже.

## Что ещё demo / вымышленное

| Маркер | Где | Заменить на |
|--------|-----|-------------|
| ул. Тверская, 12 | `md/clinic__info__contacts.md` | реальный адрес НикаДент |
| +7 (495) 128-47-60 | contacts, `clinic_policies.yaml` | телефон клиники |
| Врачи (Орлов, Кузнецов, …) | `md/doctors__doctor__*.md` | врачи НикаДент |
| `demo_video.mp4` | `video_catalog.yaml` | видео клиники или убрать |
| «бесплатная консультация» | md, fallback в коде | политика клиники |

## Перед prod

1. Правки в `clients/nikadent/md/`, prices, policies.
2. Пересборка `data/nikadent/` (Phase M2).
3. `lead_config.yaml` — реальный email.
4. `widget_config.json` — `allowed_origins` сайта клиники.
5. Smoke 5–10 вопросов на стенде nikadent.

См. также `docs/MIGRATION_INVENTORY.md`.
