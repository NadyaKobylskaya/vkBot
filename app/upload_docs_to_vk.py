"""
Загрузка картинок как ФОТО VK и обновление image_path в БД.

Отличие от upload_docs_to_vk.py:
  Старый скрипт использовал docs.getUploadServer — он НЕ работает
  с токеном группы (error_code 27).

  Этот скрипт использует photos.getMessagesUploadServer →
  photos.saveMessagesPhoto — работает с групповым токеном ✅

Как работает:
  1. Находит в БД задания с локальными путями к картинкам
  2. Загружает каждый файл через photos API
  3. Обновляет image_path в БД на "photo{owner_id}_{photo_id}" формат
  4. Повторный запуск — пропускает уже загруженные

Запуск: из папки VK_BOT2.0/
    python upload_photos_to_vk.py
"""

import asyncio
import aiosqlite
import aiohttp
import ssl
import os

from app.config import VK_TOKEN

# ── НАСТРОЙКИ ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "app", "bot_database.db")

try:
    import sys; sys.path.insert(0, os.path.join(BASE_DIR, "app"))
    from config import VK_TOKEN, GROUP_ID
except ImportError:
    VK_TOKEN = "vk1.a.ТВОЙ_ТОКЕН"
    GROUP_ID = 123456789

VK_API = "https://api.vk.com/method"
VK_VER = "5.131"


ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# ── VK API ────────────────────────────────────────────────────────────────────

async def vk_call(session: aiohttp.ClientSession, method: str, params: dict) -> dict:
    params.update({"access_token": VK_TOKEN, "v": VK_VER})
    async with session.post(f"{VK_API}/{method}", data=params) as resp:
        result = await resp.json(content_type=None)
    if "error" in result:
        raise RuntimeError(f"VK API error {method}: {result['error']}")
    return result["response"]


async def upload_photo(session: aiohttp.ClientSession, file_path: str) -> str:
    abs_path = (
        os.path.join(BASE_DIR, file_path)
        if not os.path.isabs(file_path)
        else file_path
    )
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Файл не найден: {abs_path}")

    # Шаг 1: URL для загрузки на стену группы
    upload_info = await vk_call(session, "photos.getWallUploadServer", {
        "group_id": GROUP_ID,
    })
    upload_url = upload_info["upload_url"]

    # Шаг 2: загружаем файл
    with open(abs_path, "rb") as f:
        form = aiohttp.FormData()
        form.add_field(
            "photo", f,
            filename=os.path.basename(abs_path),
            content_type="image/png"
        )
        async with session.post(upload_url, data=form, ssl=ssl_ctx) as resp:
            upload_result = await resp.json(content_type=None)

    if "photo" not in upload_result or upload_result["photo"] == "[]":
        raise RuntimeError(f"Ошибка загрузки: {upload_result}")

    # Шаг 3: сохраняем фото в альбом группы
    save_result = await vk_call(session, "photos.saveWallPhoto", {
        "group_id": GROUP_ID,
        "photo":    upload_result["photo"],
        "server":   upload_result["server"],
        "hash":     upload_result["hash"],
    })

    if not save_result:
        raise RuntimeError("photos.saveWallPhoto вернул пустой ответ")

    photo = save_result[0]
    return f"photo{photo['owner_id']}_{photo['id']}"


# ── ОСНОВНАЯ ЛОГИКА ────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  Загрузка картинок в VK (photos API)")
    print("=" * 60)

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            # Задания с локальными путями
            cursor = await db.execute("""
                SELECT id, task_number, topic, image_path
                FROM tasks
                WHERE image_path IS NOT NULL
                  AND image_path NOT LIKE 'doc%'
                  AND image_path NOT LIKE 'photo%'
                  AND image_path NOT LIKE 'http%'
                ORDER BY task_number, id
            """)
            rows = await cursor.fetchall()

            if not rows:
                print("✅ Все картинки уже загружены в VK.")
                return

            print(f"Найдено заданий с локальными картинками: {len(rows)}\n")

            # Кэш: локальный_путь → vk_attachment
            cache: dict[str, str] = {}
            updated = 0
            errors  = 0
            skipped = 0

            for i, row in enumerate(rows, 1):
                task_id    = row["id"]
                image_path = row["image_path"]
                topic      = row["topic"]
                task_num   = row["task_number"]

                paths = [p.strip() for p in image_path.split("|")]
                new_parts = []
                changed = False

                for path in paths:
                    # Уже VK — не трогаем
                    if path.startswith("doc") or path.startswith("photo") or path.startswith("http"):
                        new_parts.append(path)
                        continue

                    # Из кэша
                    if path in cache:
                        new_parts.append(cache[path])
                        changed = True
                        continue

                    # Загружаем
                    print(f"  [{i}/{len(rows)}] {os.path.basename(path)}", end=" ... ", flush=True)

                    try:
                        attachment = await upload_photo(session, path)
                        cache[path] = attachment
                        new_parts.append(attachment)
                        changed = True
                        print(f"✅ {attachment}")
                        await asyncio.sleep(0.35)  # пауза чтобы не превысить лимит VK API
                    except FileNotFoundError:
                        print(f"⚠️  файл не найден, пропускаю")
                        new_parts.append(path)
                        skipped += 1
                    except Exception as e:
                        print(f"❌ {e}")
                        new_parts.append(path)
                        errors += 1

                # Обновляем БД
                if changed:
                    new_image_path = "|".join(new_parts)
                    await db.execute(
                        "UPDATE tasks SET image_path = ? WHERE id = ?",
                        (new_image_path, task_id)
                    )
                    updated += 1

                # Сохраняем каждые 50 записей
                if i % 50 == 0:
                    await db.commit()
                    print(f"\n  💾 Сохранено {i}/{len(rows)} записей...\n")

            await db.commit()

            print()
            print("=" * 60)
            print(f"  Загружено уникальных файлов : {len(cache)}")
            print(f"  Обновлено записей в БД      : {updated}")
            if skipped:
                print(f"  ⚠️  Файлов не найдено        : {skipped}")
            if errors:
                print(f"  ❌ Ошибок загрузки           : {errors}")
            print("=" * 60)

            # Итоговая статистика
            cursor = await db.execute("""
                SELECT
                  SUM(CASE WHEN image_path LIKE 'photo%' OR image_path LIKE 'doc%' THEN 1 ELSE 0 END) as vk,
                  SUM(CASE WHEN image_path NOT LIKE 'photo%'
                                AND image_path NOT LIKE 'doc%'
                                AND image_path NOT LIKE 'http%'
                                AND image_path IS NOT NULL THEN 1 ELSE 0 END) as local
                FROM tasks
            """)
            stat = await cursor.fetchone()
            print(f"\n  Итого в БД:")
            print(f"    ✅ Загружено в VK : {stat['vk']} заданий")
            print(f"    💻 Локальных путей: {stat['local']} заданий")
            if stat['local'] == 0:
                print("\n  🎉 Все картинки загружены!")
            else:
                print(f"\n  ⚠️  Осталось загрузить: {stat['local']} файлов")
                print(f"     Запусти скрипт ещё раз — он продолжит с места остановки.")


asyncio.run(main())