import httpx
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging
from typing import List, Dict, Any, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Расширенные заголовки для имитации реального браузера
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Connection": "close"  # Избегаем зависаний на полузакрытых keep-alive сокетах CDN
}


def human_delay(min_sec: float = 0.2, max_sec: float = 1.0) -> None:
    """
    Имитирует поведение человека: случайная пауза между запросами.
    Помогает обойти антибот-защиту и снижает нагрузку на CDN.
    """
    time.sleep(random.uniform(min_sec, max_sec))


def get_image_urls(target_url: str, max_images: int = 100) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Получает HTML с пагинацией, находит <img>, фильтрует мусор и дубликаты.
    Реализует:
    - повторные попытки (retry) при сбоях сети;
    - грациозную деградацию (не падает, если часть страниц недоступна);
    - имитацию человеческого поведения (random delay).
    """
    errors = []
    image_urls = []
    page = 1

    # Умные таймауты: каждая фаза запроса имеет свой лимит
    timeout = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0)

    with httpx.Client(timeout=timeout, headers=HEADERS, follow_redirects=True) as client:
        while len(image_urls) < max_images:
            current_url = f"{target_url}?page={page}" if page > 1 else target_url

            # === Retry-логика: 3 попытки загрузить страницу ===
            response = None
            for attempt in range(3):
                try:
                    response = client.get(current_url)
                    response.raise_for_status()
                    break  # Успех — выходим из цикла попыток
                except httpx.HTTPError as e:
                    logger.warning(f"Попытка {attempt + 1}/3 для {current_url}: {e}")
                    if attempt == 2:
                        # Дружелюбное сообщение вместо технического "incomplete chunked read"
                        errors.append({
                            "url": current_url,
                            "error": "Не удалось загрузить часть страниц источника. Анализ выполнен по доступным изображениям."
                        })

            # Graceful degradation: если страница не загрузилась — прерываем пагинацию,
            # но сохраняем уже собранные данные
            if response is None:
                logger.info(
                    f"Прерывание пагинации на странице {page} из-за ошибок сети. "
                    f"Используем собранные данные ({len(image_urls)} шт.)."
                )
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            new_images_found = 0

            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if not src:
                    continue

                absolute_url = urljoin(current_url, src)

                # === ГЛАВНАЯ ФИЛЬТРАЦИЯ ===
                # 1. Берём только логотипы команд (отсекаем Яндекс.Метрику, баннеры, иконки)
                if "/images/team-list-logo/" not in absolute_url:
                    continue
                # 2. Исключаем SVG — Pillow их не открывает как обычные картинки
                if absolute_url.lower().endswith(".svg"):
                    continue

                # === ДЕДУПЛИКАЦИЯ ===
                if absolute_url not in image_urls:
                    image_urls.append(absolute_url)
                    new_images_found += 1

                if len(image_urls) >= max_images:
                    break
# Если на странице не нашли ни одной новой подходящей картинки — пагинация закончилась
            if new_images_found == 0:
                logger.info(f"Больше новых изображений не найдено после страницы {page}.")
                break

            # === ЧЕЛОВЕЧЕСКАЯ ПАУЗА перед следующей страницей ===
            if len(image_urls) < max_images:
                human_delay(0.5, 2.0)

            page += 1

    logger.info(f"Итого успешно собрано {len(image_urls)} уникальных ссылок на логотипы.")
    return image_urls, errors


def download_images(image_urls: List[str], max_download: int = 10) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Скачивает изображения, пропуская повреждённые и собирая ошибки.
    Не падает при единичных сбоях — возвращает то, что успел загрузить.
    """
    downloaded_images = []
    errors = []

    timeout = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0)

    with httpx.Client(timeout=timeout, headers=HEADERS, follow_redirects=True) as client:
        for url in image_urls[:max_download]:
            try:
                response = client.get(url)
                response.raise_for_status()

                content_type = response.headers.get('content-type', '').lower()
                if not content_type.startswith('image/'):
                    errors.append({"url": url, "error": "Неверный формат файла"})
                    continue

                image_data = response.content
                if not image_data or len(image_data) < 100:
                    errors.append({"url": url, "error": "Файл слишком мал или пуст"})
                    continue

                downloaded_images.append({
                    "url": url,
                    "data": image_data,
                    "content_type": content_type
                })

                # Небольшая пауза между скачиваниями, чтобы не нагружать CDN
                human_delay(0.2, 0.7)

            except httpx.HTTPError:
                # Не засоряем логи пользователя техническими деталями
                errors.append({"url": url, "error": "Ошибка загрузки изображения"})
                continue

    logger.info(
        f"Успешно загружено {len(downloaded_images)} "
        f"из {min(len(image_urls), max_download)} запрошенных."
    )
    return downloaded_images, errors