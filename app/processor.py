import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
import io
from typing import Dict, Any, List

def process_image(image_bytes: bytes, filter_name: str) -> Dict[str, Any]:
    """
    Выполняет обязательные требования ТЗ:
    1. Статистика NumPy (размеры, яркость, контраст, средний цвет)
    2. Преобразование NumPy (массивные операции, например, инверсия или сепия)
    3. Свёртка PyTorch (conv2d с ядром, например, Sobel или резкость)
    """
    # 1. Загрузка и преобразование в RGB массив
    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    img_np = np.array(img)
    
    h, w, c = img_np.shape
    aspect_ratio = round(w / h, 2) if h > 0 else 0.0
    
    # Статистика NumPy (яркость и контраст)
    grayscale_np = np.mean(img_np, axis=2)
    mean_brightness = float(np.mean(grayscale_np))
    contrast = float(np.std(grayscale_np))
    avg_color = [int(np.mean(img_np[:, :, i])) for i in range(3)]
    
    stats = {
        "width": w,
        "height": h,
        "aspect_ratio": aspect_ratio,
        "mean_brightness": round(mean_brightness, 2),
        "contrast": round(contrast, 2),
        "avg_color_rgb": avg_color
    }
    
    filters_applied = []
    processed_np = img_np.copy()
    
    # 2. Преобразование NumPy (операции над массивами, не просто PIL метод)
    if filter_name.lower() in ["invert", "invert_numpy"]:
        processed_np = 255 - processed_np  # Инверсия каналов массивом
        filters_applied.append("invert_numpy")
    else:
        # По умолчанию: ручная конвертация в grayscale через dot product (массивная операция)
        coefficients = np.array([0.2989, 0.5870, 0.1140])
        gray_manual = np.dot(processed_np[..., :3], coefficients).astype(np.uint8)
        processed_np = np.stack((gray_manual,)*3, axis=-1)
        filters_applied.append("grayscale_numpy_manual")

    # 3. Свёртка PyTorch (обязательно: C x H x W тензор и F.conv2d)
    # Преобразуем в тензор и меняем форму на (1, C, H, W) для batch
    img_tensor = torch.from_numpy(processed_np).float().permute(2, 0, 1).unsqueeze(0) / 255.0
    
    # Ядро свёртки (например, повышение резкости / unsharp mask или Sobel)
    # Используем ядро резкости 3x3
    kernel = torch.tensor([[
        [[ 0, -1,  0],
         [-1,  5, -1],
         [ 0, -1,  0]]
    ]], dtype=torch.float32) # Форма: (out_channels=1, in_channels=1, kH=3, kW=3)
    
    # Для простоты применяем к первому каналу (или можно сделать поканально, но для демо хватит одного)
    # Если изображение цветное, применим ядро к каждому каналу через groups=3 или усредним.
    # Для гарантированной работы сделаем свёртку на grayscale версии для PyTorch шага:
    gray_tensor = torch.mean(img_tensor, dim=1, keepdim=True) # (1, 1, H, W)
    
    # Применяем conv2d (padding=1 чтобы сохранить размер)
    with torch.no_grad():
        convolved = F.conv2d(gray_tensor, kernel, padding=1)
    
    # Нормализуем результат обратно в [0, 1]
    convolved = torch.clamp(convolved, 0.0, 1.0)
    
    # Преобразуем обратно в изображение (H, W, C)
    result_np = (convolved.squeeze().numpy() * 255).astype(np.uint8)
    # Делаем его 3-канальным для сохранения в JPEG/PNG
    result_img = Image.fromarray(np.stack((result_np,)*3, axis=-1))
    
    filters_applied.append("sharpen_pytorch_conv2d")
    
    # Сохраняем в байты для отправки на фронтенд
    output_bytes = io.BytesIO()
    result_img.save(output_bytes, format="JPEG")
    
    return {
        "stats": stats,
        "processed_bytes": output_bytes.getvalue(),
        "filters_applied": filters_applied
    }