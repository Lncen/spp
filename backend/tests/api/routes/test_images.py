"""图片模块：API 路由测试"""
import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.utils.image import create_test_image_bytes


def test_upload_image(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """上传合法 JPEG 图片应返回图片信息"""
    image_bytes = create_test_image_bytes()
    response = client.post(
        f"{settings.API_V1_STR}/images/upload",
        headers=superuser_token_headers,
        files={"file": ("test.jpg", image_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["filename"] == "test.jpg"
    assert content["width"] == 100
    assert content["height"] == 100
    assert content["file_size"] > 0
    assert "id" in content
    assert "url" in content
    assert content["url"].startswith("/uploads/")
    assert content["url"].endswith(".webp")


def test_upload_duplicate_image(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """上传相同内容的图片应返回已存在的记录（SHA256 去重）"""
    image_bytes = create_test_image_bytes()
    response1 = client.post(
        f"{settings.API_V1_STR}/images/upload",
        headers=superuser_token_headers,
        files={"file": ("first.jpg", image_bytes, "image/jpeg")},
    )
    assert response1.status_code == 200
    id1 = response1.json()["id"]

    response2 = client.post(
        f"{settings.API_V1_STR}/images/upload",
        headers=superuser_token_headers,
        files={"file": ("second.jpg", image_bytes, "image/jpeg")},
    )
    assert response2.status_code == 200
    content2 = response2.json()
    assert content2["id"] == id1
    assert content2["filename"] == "first.jpg"


def test_upload_invalid_extension(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """上传不支持的格式应返回 400"""
    response = client.post(
        f"{settings.API_V1_STR}/images/upload",
        headers=superuser_token_headers,
        files={"file": ("test.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400
    content = response.json()
    assert "detail" in content
    assert "格式" in content["detail"]


def test_upload_empty_file(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """上传空文件应返回 400"""
    response = client.post(
        f"{settings.API_V1_STR}/images/upload",
        headers=superuser_token_headers,
        files={"file": ("empty.jpg", b"", "image/jpeg")},
    )
    assert response.status_code == 400
    content = response.json()
    assert "detail" in content


def test_read_images(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """获取图片列表应返回列表与计数"""
    # 先上传一张图确保列表非空
    image_bytes = create_test_image_bytes()
    client.post(
        f"{settings.API_V1_STR}/images/upload",
        headers=superuser_token_headers,
        files={"file": ("list_test.jpg", image_bytes, "image/jpeg")},
    )
    response = client.get(
        f"{settings.API_V1_STR}/images/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert "count" in content
    assert content["count"] > 0
    assert len(content["data"]) > 0
    for img in content["data"]:
        assert "url" in img
        assert "id" in img


def test_read_image(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """根据 ID 获取图片应返回图片信息"""
    image_bytes = create_test_image_bytes()
    upload_resp = client.post(
        f"{settings.API_V1_STR}/images/upload",
        headers=superuser_token_headers,
        files={"file": ("get_test.jpg", image_bytes, "image/jpeg")},
    )
    image_id = upload_resp.json()["id"]

    response = client.get(
        f"{settings.API_V1_STR}/images/{image_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == image_id
    assert content["filename"] == "get_test.jpg"
    assert "url" in content


def test_read_image_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """获取不存在的图片应返回 404"""
    response = client.get(
        f"{settings.API_V1_STR}/images/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "图片不存在"


def test_read_image_not_enough_permissions(
    client: TestClient, superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    """普通用户访问他人的图片应返回 403"""
    image_bytes = create_test_image_bytes()
    upload_resp = client.post(
        f"{settings.API_V1_STR}/images/upload",
        headers=superuser_token_headers,
        files={"file": ("owner_test.jpg", image_bytes, "image/jpeg")},
    )
    image_id = upload_resp.json()["id"]

    response = client.get(
        f"{settings.API_V1_STR}/images/{image_id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "权限不足"


def test_delete_image(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """删除图片应返回成功消息"""
    image_bytes = create_test_image_bytes()
    upload_resp = client.post(
        f"{settings.API_V1_STR}/images/upload",
        headers=superuser_token_headers,
        files={"file": ("del_test.jpg", image_bytes, "image/jpeg")},
    )
    image_id = upload_resp.json()["id"]

    response = client.delete(
        f"{settings.API_V1_STR}/images/{image_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "图片已删除"


def test_delete_image_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """删除不存在的图片应返回 404"""
    response = client.delete(
        f"{settings.API_V1_STR}/images/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "图片不存在"


def test_delete_image_not_enough_permissions(
    client: TestClient, superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    """普通用户删除他人的图片应返回 403"""
    image_bytes = create_test_image_bytes()
    upload_resp = client.post(
        f"{settings.API_V1_STR}/images/upload",
        headers=superuser_token_headers,
        files={"file": ("del_owner_test.jpg", image_bytes, "image/jpeg")},
    )
    image_id = upload_resp.json()["id"]

    response = client.delete(
        f"{settings.API_V1_STR}/images/{image_id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    content = response.json()
    assert content["detail"] == "权限不足"
