# IPO Tracker

一个面向个人使用的美国 IPO 数据跟踪系统。

## 安装

### 1. 创建虚拟环境（推荐使用 conda）

```bash
conda create -n ipo_tracker python=3.11
conda activate ipo_tracker
```

或使用 venv：

```bash
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
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
- `data/ipo_tracker.db`：SQLite 数据库（含全部 5 张表）
- `data/raw/`：原始数据缓存目录
- `data/exports/`：CSV 导出目录

> **升级提示**：如果从第一阶段升级，建议先删除旧数据库再重新初始化：
> ```bash
> rm data/ipo_tracker.db
> python scripts/init_db.py
> ```

## 数据库表结构

| 表名 | 说明 |
|------|------|
| `issuers` | IPO 候选公司基本信息 |
| `filings` | SEC 提交文件记录 |
| `offerings` | 发行数据（定价、份额等） |
| `capitalization` | 资本化数据（流通股、浮动比率等） |
| `lockups` | 锁定期数据 |

## 项目结构

```
ipo_tracker/
├── app/
│   ├── config.py          # 配置（路径、数据库 URL、日志级别）
│   ├── db.py              # SQLAlchemy engine / SessionLocal / Base
│   ├── models.py          # 全部 SQLAlchemy 模型（5 张表）
│   ├── schemas.py         # Pydantic 读写 schema
│   ├── collectors/        # 数据采集器（待实现）
│   ├── parsers/           # 解析器（待实现）
│   ├── jobs/              # 定时任务（待实现）
│   └── utils/
│       └── logging.py     # get_logger(name) 工具函数
├── data/
│   ├── raw/               # 原始数据缓存
│   └── exports/           # 导出的 CSV 文件
├── scripts/
│   └── init_db.py         # 数据库初始化脚本
├── tests/
├── CHANGELOG.md
└── requirements.txt
```

## 手动填入 CIK（SEC filings 同步的前提）

`sync_sec_filings` 只处理 `issuers` 表中已有 `cik` 的公司。
用以下方式查询 CIK，再手动更新数据库：

```python
from app.collectors.sec import search_edgar_company
for hit in search_edgar_company("Reddit"):
    print(hit)
# {"cik": "0001713445", "name": "Reddit, Inc.", "ticker": "RDDT", "exchange": "NYSE"}
```

```sql
UPDATE issuers SET cik = '1713445' WHERE ticker = 'RDDT';
```

## 运行 SEC Filings 同步任务

```bash
conda activate ipo_tracker
python -m app.jobs.sync_sec_filings
```

输出示例：

```
Done — issuers=1  inserted=5  skipped=0  failed=0
```

## 运行 IPO 候选发现任务

```bash
conda activate ipo_tracker
python -m app.jobs.discover_candidates
```

输出示例：

```
Done — fetched=115  inserted=115  updated=0  skipped=0
```

> **首次运行或模型升级后**需重置数据库：
> ```bash
> rm data/ipo_tracker.db
> python scripts/init_db.py
> ```

## 运行 Lock-Up 解析任务

```bash
conda activate ipo_tracker
python -m app.jobs.parse_lockups
```

输出示例：

```
Done — issuers=1  parsed=1  skipped=0  failed=0
```

加 `--force` 强制重新解析已有记录：

```bash
python -m app.jobs.parse_lockups --force
```

## 当前进度

- [x] 第一阶段：项目骨架、配置、日志、数据库连接
- [x] 第二阶段：完整数据库模型层（5 张表 + Pydantic schemas）
- [x] 第三阶段：HTTP 工具层（缓存、重试、限速）
- [x] 第四阶段：SEC EDGAR 数据采集函数
- [x] 第五阶段：Nasdaq + NYSE 候选发现 job
- [x] 第六阶段：SEC filings 同步 job
- [x] 第七阶段：最佳 filing 选择器
- [x] 第八阶段：Prospectus 字段解析（offering + capitalization）
- [x] 第九阶段：Lock-up 解析（lockup_days、日期、staged unlock 检测）
- [ ] 后续阶段：CSV 导出报表、总入口脚本
