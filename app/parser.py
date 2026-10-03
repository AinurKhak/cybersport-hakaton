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
    """Получает HTML, находит <img> и преобразует ссылки в абсолютные."""
    errors = []
    try:
        with httpx.Client(timeout=10.0, headers=HEADERS) as client:
            response = client.get(target_url)
            response.raise_for_status()
    except httpx.HTTPError as e:
        errors.append({"url": target_url, "error": f"Ошибка получения HTML: {str(e)}"})
        return [], errors

    soup = BeautifulSoup(response.text, 'html.parser')
    image_urls = []
    
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src')
        if src:
            absolute_url = urljoin(target_url, src)
            # Фильтруем data:image/svg+xml и прочие мусорные src
            if absolute_url.startswith('http'):
                image_urls.append(absolute_url)
                if len(image_urls) >= max_images:
                    break
                    
    return image_urls, errors

def download_images(image_urls: List[str], max_download: int = 10) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Скачивает изображения, пропуская повреждённые и собирая ошибки."""
    downloaded_images = []
    errors = []
    
    with httpx.Client(timeout=10.0, headers=HEADERS) as client:
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
                
    return downloaded_images, errors