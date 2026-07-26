from io import BytesIO

from PIL import Image as PILImage


def create_test_image_bytes(
    *,
    width: int = 100,
    height: int = 100,
    format: str = "JPEG",
    color: tuple[int, int, int] = (255, 0, 0),
) -> bytes:
    """创建测试用图片字节数据"""
    img = PILImage.new("RGB", (width, height), color=color)
    buf = BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()
