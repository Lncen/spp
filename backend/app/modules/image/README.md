# 图片模块（image）

## 目录结构

```
modules/image/
├── api/                  # 接口层：权限校验、参数校验、响应
│   ├── images.py         # 图片接口
│   └── categories.py     # 分类管理接口
├── application/          # 应用服务：业务流程编排
│   ├── image_query.py    # 图片列表/详情
│   ├── image_upload.py   # 上传图片
│   ├── image_update.py   # 更新图片
│   ├── image_delete.py   # 删除图片
│   └── category_manage.py # 分类管理
├── domain/               # 领域规则：图片可见性、头像可用性
├── infrastructure/       # 外部交互：PIL 处理、文件存储
├── models/               # 数据模型：Image、ImageCategory
├── repositories/         # 数据访问
└── schemas/              # 请求/响应模型
```

## 核心规则

- 图片上传仅限超级管理员，普通用户暂不开放上传。
- 系统默认图片：超级管理员上传的图片，对所有用户可见。
- 普通用户图片列表 = 自己上传的图片 + 系统默认图片（超管上传）。
- 普通用户设置头像时，可选择自己上传的图片或系统默认头像。
- 图片分类由 `ImageCategory` 表驱动（种子数据：avatar/product/product_detail）。
