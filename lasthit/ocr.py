"""Read text from a BGR numpy crop with the built-in Windows OCR engine."""
import asyncio

import cv2
import numpy as np
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter

_engine = OcrEngine.try_create_from_language(Language("en-US"))


async def _recognize(bgra: np.ndarray) -> str:
    h, w = bgra.shape[:2]
    writer = DataWriter()
    writer.write_bytes(bgra.tobytes())
    bmp = SoftwareBitmap.create_copy_from_buffer(
        writer.detach_buffer(), BitmapPixelFormat.BGRA8, w, h)
    return (await _engine.recognize_async(bmp)).text


def read_text(crop_bgr: np.ndarray, upscale: int = 4) -> str:
    big = cv2.resize(crop_bgr, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    bgra = cv2.cvtColor(big, cv2.COLOR_BGR2BGRA)
    return asyncio.run(_recognize(bgra))
