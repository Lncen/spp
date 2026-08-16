# 数据备份模块

用于把关键业务数据导出为本地 JSON 压缩文件，并在数据丢失时执行合并恢复。

## 备份范围

- 用户：全部用户
- 钱包：全部钱包，不含钱包交易流水
- 订单：默认近 48 小时，按 `created_at` 过滤
- 订单参数：随订单一起导出
- 供应商：全部供应商

## 保存目录

默认读取环境变量 `BACKUP_DIR`，本地开发默认值为 `backend/backups`。
也可以在全局设置中修改 `backup_dir`，留空时使用环境变量。

## 接口

- `POST /api/v1/backups`：创建备份
- `GET /api/v1/backups`：备份列表
- `GET /api/v1/backups/{filename}/download`：下载备份
- `POST /api/v1/backups/{filename}/restore`：合并恢复
- `DELETE /api/v1/backups/{filename}`：删除备份
