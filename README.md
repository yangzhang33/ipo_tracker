# IPO Tracker

一个面向个人使用的美国 IPO 数据跟踪系统。

## 安装

### 1. 创建虚拟环境

```bash
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python scripts/init_db.py
```

这将创建：
- SQLite 数据库文件
- `data/raw/` 目录（用于存储原始数据）
- `data/exports/` 目录（用于存储导出的 CSV 文件）

## 项目结构

```
ipo_tracker/
├── app/
│   ├── config.py          # 配置文件
│   ├── db.py             # 数据库连接
│   ├── models.py         # SQLAlchemy 模型
│   ├── schemas.py        # Pydantic 模式
│   ├── collectors/       # 数据收集器
│   ├── parsers/          # 数据解析器
│   ├── jobs/             # 定时任务
│   └── utils/            # 工具函数
├── data/
│   ├── raw/              # 原始数据缓存
│   └── exports/          # 导出的 CSV 文件
├── scripts/
│   └── init_db.py        # 数据库初始化脚本
└── tests/                # 测试文件
```

## 使用

当前版本为第一阶段实现，仅包含基础项目骨架。后续版本将添加：
- SEC 数据抓取功能
- IPO 数据解析功能
- 自动化报表生成功能