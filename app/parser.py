import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging
from typing import List, Dict, Any, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_image_urls(target_url: str, max_images: int = 100) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Получает HTML с пагинацией, находит <img>, фильтрует мусор и дубликаты.
    """
    errors = []
    image_urls = []
    page = 1
    
    # follow_redirects=True решает проблему 302 Moved
    with httpx.Client(timeout=10.0, headers=HEADERS, follow_redirects=True) as client:
        while len(image_urls) < max_images:
            # Формируем URL: первая страница без параметра, остальные с ?page=N
            current_url = f"{target_url}?page={page}" if page > 1 else target_url
            
            try:
                response = client.get(current_url)
                response.raise_for_status()
            except httpx.HTTPError as e:
                errors.append({"url": current_url, "error": f"Ошибка получения HTML: {str(e)}"})
                break # Если страница не грузится (например, 404), дальше идти бессмысленно
            
            soup = BeautifulSoup(response.text, 'html.parser')
            new_images_found = 0
            
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if not src:
                    continue
                    
                absolute_url = urljoin(current_url, src)
                
                # === ГЛАВНАЯ ФИЛЬТРАЦИЯ ===
                # 1. Берем только логотипы команд
                if "/images/team-list-logo/" not in absolute_url:
                    continue
                # 2. Исключаем SVG, которые ломают Pillow
                if absolute_url.lower().endswith(".svg"):
                    continue
                
                # === ДЕДУПЛИКАЦИЯ ===
                if absolute_url not in image_urls:
                    image_urls.append(absolute_url)
                    new_images_found += 1
                    
                # Если набрали нужное количество, выходим из цикла img
                if len(image_urls) >= max_images:
                    break
            
            # Если на текущей странице не нашли ни одной новой подходящей картинки, 
            # значит, пагинация закончилась или фильтр слишком строгий. Останавливаемся.
            if new_images_found == 0:
                logger.info(f"Больше новых изображений не найдено после страницы {page}.")
                break
                
            page += 1
            
    logger.info(f"Успешно собрано {len(image_urls)} уникальных ссылок на логотипы.")
    return image_urls, errors


def download_images(image_urls: List[str], max_download: int = 10) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Скачивает изображения, пропуская повреждённые и собирая ошибки.
    """
    downloaded_images = []
    errors = []
    
    # follow_redirects=True и здесь, на случай редиректов на CDN
    with httpx.Client(timeout=10.0, headers=HEADERS, follow_redirects=True) as client:
        for url in image_urls[:max_download]:
            try:
                response = client.get(url)
                response.raise_for_status()
                
                content_type = response.headers.get('content-type', '').lower()
                if not content_type.startswith('image/'):
                    errors.append({"url": url, "error": "Неверный Content-Type (не изображение)"})
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
            except httpx.HTTPError as e:
                errors.append({"url": url, "error": str(e)})
                continue
                
    logger.info(f"Успешно загружено {len(downloaded_images)} из {min(len(image_urls), max_download)} запрошенных.")
    return downloaded_images, errors