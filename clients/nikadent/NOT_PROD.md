# NOT PROD — контент НикаДент

**Статус:** временная копия demo-контента. **Не деплоить на боевой VPS** без замены маркеров ниже.

## Что ещё demo / вымышленное

| Маркер | Где | Заменить на |
|--------|-----|-------------|
| Описания врачей (черновик) | `md/doctors__doctor__*.md` | финальные тексты и фото |
| `demo_video.mp4` | `video_catalog.yaml` | видео клиники или убрать |
| «бесплатная консультация» | md, fallback в коде | политика клиники |

## Перед prod

1. Правки в `clients/nikadent/md/`, prices, policies.
2. Пересборка `data/nikadent/` (Phase M2).
3. `lead_config.yaml` — реальный email.
4. `widget_config.json` — `allowed_origins` сайта клиники.
5. Smoke 5–10 вопросов на стенде nikadent.

См. `docs/MULTICLIENT.md` §15 и `docs/TECH_DEBT.md`.
