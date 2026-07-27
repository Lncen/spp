"""图片分类管理：API 路由测试"""
import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.modules.image.service import get_category_by_name
from tests.utils.image import create_test_image_bytes


def _list_categories_url() -> str:
    return f"{settings.API_V1_STR}/image-categories/"


class TestReadCategories:
    """获取分类列表"""

    def test_list_categories(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """获取分类列表应返回所有默认分类"""
        response = client.get(
            _list_categories_url(),
            headers=superuser_token_headers,
        )
        assert response.status_code == 200
        content = response.json()
        assert "data" in content
        assert "count" in content
        assert content["count"] >= 3
        names = [c["name"] for c in content["data"]]
        assert "avatar" in names
        assert "product" in names
        assert "product_detail" in names

    def test_list_categories_normal_user(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """普通用户不能获取分类列表"""
        response = client.get(
            _list_categories_url(),
            headers=normal_user_token_headers,
        )
        assert response.status_code == 403

    def test_list_categories_unauthenticated(
        self, client: TestClient
    ) -> None:
        """未认证用户无法获取分类列表"""
        response = client.get(_list_categories_url())
        assert response.status_code == 403


class TestReadCategoryOptions:
    """获取分类选项列表"""

    def test_options(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """分类选项应返回 name 列表"""
        response = client.get(
            f"{settings.API_V1_STR}/image-categories/options",
            headers=superuser_token_headers,
        )
        assert response.status_code == 200
        content = response.json()
        assert isinstance(content, list)
        assert len(content) >= 3
        for item in content:
            assert "avatar" in content


class TestReadCategory:
    """获取单个分类"""

    def test_get_category(
        self, client: TestClient, superuser_token_headers: dict[str, str],
        db,
    ) -> None:
        """根据 ID 获取分类应返回分类信息"""
        category = get_category_by_name(session=db, name="avatar")
        assert category is not None

        response = client.get(
            f"{settings.API_V1_STR}/image-categories/{category.id}",
            headers=superuser_token_headers,
        )
        assert response.status_code == 200
        content = response.json()
        assert content["name"] == "avatar"

        assert "image_count" in content
        assert "id" in content

    def test_get_category_not_found(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """获取不存在的分类应返回 404"""
        response = client.get(
            f"{settings.API_V1_STR}/image-categories/{uuid.uuid4()}",
            headers=superuser_token_headers,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "分类不存在"


class TestCreateCategory:
    """创建分类"""

    CREATE_URL = _list_categories_url()

    def test_create_category(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """管理员可以创建分类"""
        response = client.post(
            self.CREATE_URL,
            headers=superuser_token_headers,
            json={
                "name": "banner",

                "description": "横幅广告图片",
                "sort_order": 10,
                "icon": "image",
            },
        )
        assert response.status_code == 201
        content = response.json()
        assert content["name"] == "banner"

        assert content["icon"] == "image"

        # 清理
        client.delete(
            f"{settings.API_V1_STR}/image-categories/{content['id']}",
            headers=superuser_token_headers,
        )

    def test_create_category_duplicate_name(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """重复 name 应返回 409"""
        # 先创建
        resp = client.post(
            self.CREATE_URL,
            headers=superuser_token_headers,
            json={"name": "temp_cat", "description": "临时"},
        )
        assert resp.status_code == 201
        cat_id = resp.json()["id"]

        # 重复创建
        resp2 = client.post(
            self.CREATE_URL,
            headers=superuser_token_headers,
            json={"name": "temp_cat", "description": "临时"},
        )
        assert resp2.status_code == 409
        assert "已存在" in resp2.json()["detail"]

        # 清理
        client.delete(
            f"{settings.API_V1_STR}/image-categories/{cat_id}",
            headers=superuser_token_headers,
        )

    def test_create_category_normal_user(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """普通用户不能创建分类"""
        response = client.post(
            self.CREATE_URL,
            headers=normal_user_token_headers,
            json={"name": "test", "description": "测试"},
        )
        assert response.status_code == 403

    def test_create_category_invalid_name(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """name 格式非法应返回 422"""
        response = client.post(
            self.CREATE_URL,
            headers=superuser_token_headers,
            json={"name": "Invalid Name!", "description": "测试"},
        )
        assert response.status_code == 422


class TestUpdateCategory:
    """更新分类"""

    def test_update_category(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """管理员可以更新分类"""
        # 先创建
        resp = client.post(
            _list_categories_url(),
            headers=superuser_token_headers,
            json={"name": "upd_cat", "description": "更新前"},
        )
        cat_id = resp.json()["id"]

        # 更新 description
        response = client.patch(
            f"{settings.API_V1_STR}/image-categories/{cat_id}",
            headers=superuser_token_headers,
            json={"description": "更新后"},
        )
        assert response.status_code == 200
        content = response.json()
        assert content["description"] == "更新后"

        # 清理
        client.delete(
            f"{settings.API_V1_STR}/image-categories/{cat_id}",
            headers=superuser_token_headers,
        )

    def test_update_category_not_found(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """更新不存在的分类应返回 404"""
        response = client.patch(
            f"{settings.API_V1_STR}/image-categories/{uuid.uuid4()}",
            headers=superuser_token_headers,
            json={"description": "新名称"},
        )
        assert response.status_code == 404

    def test_update_category_normal_user(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """普通用户不能更新分类"""
        response = client.patch(
            f"{settings.API_V1_STR}/image-categories/{uuid.uuid4()}",
            headers=normal_user_token_headers,
            json={"description": "新名称"},
        )
        assert response.status_code == 403


class TestDeleteCategory:
    """删除分类"""

    def test_delete_category(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """管理员可以删除未被引用的分类"""
        resp = client.post(
            _list_categories_url(),
            headers=superuser_token_headers,
            json={"name": "del_cat"},
        )
        cat_id = resp.json()["id"]

        response = client.delete(
            f"{settings.API_V1_STR}/image-categories/{cat_id}",
            headers=superuser_token_headers,
        )
        assert response.status_code == 200
        assert response.json()["message"] == "分类已删除"

    def test_delete_category_with_references(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """分类下有图片引用时拒绝删除"""
        # 确保 avatar 分类存在
        resp = client.post(
            f"{settings.API_V1_STR}/images/upload",
            headers=superuser_token_headers,
            files={"file": ("cat_ref.jpg", create_test_image_bytes(), "image/jpeg")},
            params={"category": "avatar"},
        )
        assert resp.status_code == 200

        # 尝试删除 avatar 分类（有图片引用）
        list_resp = client.get(
            _list_categories_url(),
            headers=superuser_token_headers,
        )
        categories = list_resp.json()["data"]
        avatar_cat = next(c for c in categories if c["name"] == "avatar")

        response = client.delete(
            f"{settings.API_V1_STR}/image-categories/{avatar_cat['id']}",
            headers=superuser_token_headers,
        )
        assert response.status_code == 400
        assert "图片" in response.json()["detail"]

    def test_delete_category_not_found(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """删除不存在的分类应返回 400"""
        response = client.delete(
            f"{settings.API_V1_STR}/image-categories/{uuid.uuid4()}",
            headers=superuser_token_headers,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "分类不存在"

    def test_delete_category_normal_user(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ) -> None:
        """普通用户不能删除分类"""
        response = client.delete(
            f"{settings.API_V1_STR}/image-categories/{uuid.uuid4()}",
            headers=normal_user_token_headers,
        )
        assert response.status_code == 403


class TestUploadWithCategory:
    """上传图片时使用分类"""

    def test_upload_with_valid_category(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """使用有效分类上传图片应成功"""
        image_bytes = create_test_image_bytes()
        response = client.post(
            f"{settings.API_V1_STR}/images/upload",
            headers=superuser_token_headers,
            files={"file": ("cat_test.jpg", image_bytes, "image/jpeg")},
            params={"category": "product"},
        )
        assert response.status_code == 200
        content = response.json()
        assert content["category"] == "product"

    def test_upload_with_invalid_category(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """使用不存在的分类上传图片应返回 400"""
        image_bytes = create_test_image_bytes()
        response = client.post(
            f"{settings.API_V1_STR}/images/upload",
            headers=superuser_token_headers,
            files={"file": ("bad_cat.jpg", image_bytes, "image/jpeg")},
            params={"category": "nonexistent_category"},
        )
        assert response.status_code == 400
        assert "不存在" in response.json()["detail"]

    def test_filter_by_category(
        self, client: TestClient, superuser_token_headers: dict[str, str]
    ) -> None:
        """分类筛选应正确过滤图片"""
        # 上传两张不同分类的图片
        img1 = create_test_image_bytes()
        client.post(
            f"{settings.API_V1_STR}/images/upload",
            headers=superuser_token_headers,
            files={"file": ("avatar_img.jpg", img1, "image/jpeg")},
            params={"category": "avatar"},
        )
        img2 = create_test_image_bytes(color=(0, 255, 0))
        client.post(
            f"{settings.API_V1_STR}/images/upload",
            headers=superuser_token_headers,
            files={"file": ("product_img.jpg", img2, "image/jpeg")},
            params={"category": "product"},
        )

        # 按 avatar 筛选
        resp = client.get(
            f"{settings.API_V1_STR}/images/?category=avatar",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 200
        for img in resp.json()["data"]:
            assert img["category"] == "avatar"
