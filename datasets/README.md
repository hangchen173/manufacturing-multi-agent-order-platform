# Datasets

标准数据目录，统一管理公开数据集、自建数据集和共享参考数据。

## 目录结构

```text
datasets/
├── public/
│   ├── xfund_zh/
│   │   ├── raw/          # 原始下载包或解压后的原始文件
│   │   └── processed/    # 清洗、抽样、格式统一后的文件
│   ├── cord/
│   │   ├── raw/
│   │   └── processed/
│   ├── sroie/
│   │   ├── raw/
│   │   └── processed/
│   └── docvqa/
│       ├── raw/
│       └── processed/
├── self_built/
│   ├── orders_raw/
│   │   ├── pdf/          # 自建 PDF 订单
│   │   └── image/        # 自建图片/扫描件订单
│   ├── annotations/      # 自建数据标注文件
│   └── manifests/        # 自建样本清单
└── shared/
    ├── material_master/  # 共享物料主数据、SKU 对照表
    └── reference_docs/   # 合法公开参考文档、模板来源说明
```

## 使用约定

### 公开数据集

- `raw/` 只放原始下载内容，不做手工修改。
- `processed/` 放抽样结果、重命名结果、统一格式后的文件。

### 自建数据集

- `orders_raw/pdf/` 放原始导出的订单 PDF。
- `orders_raw/image/` 放拍照件、扫描件、增强后的图片版本。
- `annotations/` 放与样本一一对应的 JSON 标注。
- `manifests/` 放 CSV 清单，用于记录样本来源、质量标签、标注状态。

### 共享数据

- `material_master/` 放标准物料库、SKU 映射表。
- `reference_docs/` 放公开来源样本说明、模板设计参考说明，不建议直接混放测试数据。

## 命名建议

- 样本文件：`order_0001.pdf`、`order_0002.jpg`
- 标注文件：`order_0001.json`
- manifest：`self_built_orders_manifest.csv`

## 注意事项

- 不要把来源不明或未脱敏的真实业务数据直接放进仓库。
- 不要在 `raw/` 目录直接覆盖原始文件。
- 如果公开数据集 license 有限制，请在对应数据集目录下单独放一个 `LICENSE_NOTE.md` 记录来源与使用边界。
