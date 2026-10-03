from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import base64
import os

from . import parser
from . import processor

app = FastAPI(title="ImageScope Hackathon API")
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
    name="static"
)

# Настройка шаблонов для раздачи GUI через GET /
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# --- Pydantic Модели (Требование ТЗ: структурированный JSON) ---
class AnalyzeRequest(BaseModel):
    filter_name: str = "default"
    max_images: int = 100

class ImageStats(BaseModel):
    width: int
    height: int
    aspect_ratio: float
    mean_brightness: float
    contrast: float
    avg_color_rgb: List[int]

class ImageResult(BaseModel):
    original_url: str
    original_base64: str
    processed_base64: str
    stats: ImageStats
    filters_applied: List[str]

class AnalyzeResponse(BaseModel):
    source_url: str
    filter_requested: str
    total_successful: int
    images: List[ImageResult]
    errors: List[Dict[str, str]]

# --- Эндпоинты ---
@app.get("/", response_class=HTMLResponse)
async def get_frontend(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "hackathon_imagescope"}

@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_images(req: AnalyzeRequest):
    target_url = "https://www.cybersport.ru/teams/cs2"
    
    # 1. Парсинг ссылок
    image_urls, parse_errors = parser.get_image_urls(target_url, max_images=100)
    if not image_urls:
        raise HTTPException(status_code=502, detail=f"Не удалось получить изображения. Ошибки: {parse_errors}")
        
    # 2. Скачивание (максимум req.max_images)
    downloaded_images, download_errors = parser.download_images(image_urls, max_download=req.max_images)
    all_errors = parse_errors + download_errors
    
    if not downloaded_images:
        raise HTTPException(status_code=500, detail="Не удалось загрузить ни одного корректного изображения")
        
    # 3. Обработка и формирование ответа
    final_images = []
    for img in downloaded_images:
        try:
            # Вызов модуля обработки
            proc_result = processor.process_image(img["data"], req.filter_name)
            
            final_images.append(ImageResult(
                original_url=img["url"],
                original_base64=f"data:{img['content_type']};base64,{base64.b64encode(img['data']).decode('utf-8')}",
                processed_base64=f"data:image/jpeg;base64,{base64.b64encode(proc_result['processed_bytes']).decode('utf-8')}",
                stats=ImageStats(**proc_result["stats"]),
                filters_applied=proc_result["filters_applied"]
            ))
        except Exception as e:
            all_errors.append({"url": img["url"], "error": f"Ошибка обработки: {str(e)}"})
            
    return AnalyzeResponse(
        source_url=target_url,
        filter_requested=req.filter_name,
        total_successful=len(final_images),
        images=final_images,
        errors=all_errors
    )

# Точка входа для запуска (Требование пользователя)
if __name__ == "__main__":
    import uvicorn
    # Запуск из корня проекта: uvicorn app.main:app --reload
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)