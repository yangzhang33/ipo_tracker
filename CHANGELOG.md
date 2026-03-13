# Changelog

## [Step 3] - 2026-03-11 — 基础工具层

### 新增文件

#### `app/utils/http.py`
- **新增** `get_text(url, headers, use_cache) -> str`
  - 支持超时（`HTTP_TIMEOUT`）、自动重试（tenacity，最多 `HTTP_MAX_RETRIES` 次）
  - 重试条件：`httpx.TimeoutException` / `httpx.NetworkError`；HTTP 4xx/5xx 不重试
  - 重试等待：指数退避，2 ~ 15 秒
  - 支持限速（`HTTP_RATE_LIMIT_DELAY`），模块级时间戳跨调用生效
  - 缓存路径：`data/raw/cache/<sha256前24位>.txt`
- **新增** `get_json(url, headers, use_cache) -> dict`
  - 与 `get_text` 相同的重试/限速/缓存机制
  - 缓存路径：`data/raw/cache/<sha256前24位>.json`，序列化时保留非 ASCII
- **新增** `_fetch(url, headers)` — 内部重试装饰器封装，不暴露给外部；自动注入 `SEC_USER_AGENT` 作为默认 `User-Agent`，调用方传入的 headers 可覆盖

#### `app/utils/text.py`
- **新增** `normalize_whitespace(text) -> str`
  - 将任意连续空白折叠为单个空格，首尾裁剪
- **新增** `strip_html_to_text(html) -> str`
  - 使用 selectolax 解析 HTML，移除 `<script>` / `<style>` / `<head>`
  - 块级元素用换行分隔，保留段落结构
  - 连续 3+ 空行折叠为 2 行
- **新增** `find_section(text, section_titles) -> str | None`
  - 按 section_titles 优先级顺序进行大小写不敏感子串搜索
  - 匹配后返回最多 8000 字符，遇到下一个段落边界（全大写/首字母大写短行）提前截断
  - 未匹配返回 None

#### `app/utils/dates.py`
- **新增** `parse_date(value) -> date | None`
  - 基于 python-dateutil，支持 ISO、US long form 等多种格式
  - 解析失败返回 None，不抛异常
- **新增** `add_days(value, days) -> str | None`
  - 对 parse_date 结果加 N 个日历天，返回 ISO 字符串
  - 源字符串不可解析时返回 None
- **新增** `today_str() -> str`
  - 返回当天 ISO 日期字符串（YYYY-MM-DD）

### 修改文件

#### `app/config.py`
- 新增 `CACHE_DIR` property → `data/raw/cache/`
- 新增 `HTTP_TIMEOUT: float = 30.0`
- 新增 `HTTP_RATE_LIMIT_DELAY: float = 1.0`
- 新增 `HTTP_MAX_RETRIES: int = 3`
- 新增 `SEC_USER_AGENT: str`（默认 `"ipo-tracker research@example.com"`，可通过 `.env` 覆盖）

#### `requirements.txt`
- 新增 `httpx>=0.27.0`
- 新增 `tenacity>=8.2.0`
- 新增 `selectolax>=0.3.17`
- 新增 `lxml>=5.0.0`
- 新增 `truststore>=0.9.0`（修复 macOS conda 环境 SSL 证书验证失败问题）

### 不变文件
- `app/models.py` / `app/schemas.py` / `app/db.py` — 无需修改
- `scripts/init_db.py` — 无需修改（缓存目录按需由 http.py 自动创建）

---

## [Step 2] - 2026-03-11 — 数据库模型层

### 修改文件

#### `app/models.py`
- **重构** `Issuer` 模型：
  - `created_at` / `updated_at` 类型从 `DateTime` 改为 `Text`，与规格文档一致（时间字段统一用字符串）
  - 移除 `String(N)` 长度限制，改为 `Text`（SQLite 不强制列宽）
  - 新增 `filings` / `offerings` / `capitalizations` / `lockups` 四个 `relationship`，级联删除子记录
- **新增** `Filing` 模型（`filings` 表）：
  - 字段：`issuer_id`、`accession_no`、`form_type`、`filing_date`、`primary_doc_url`、`filing_index_url`、`is_parsed`、`created_at`
  - `UNIQUE(issuer_id, accession_no, form_type)` 约束，防止重复写入
  - 与 `Issuer`、`Offering`、`Capitalization`、`Lockup` 建立双向 relationship
- **新增** `Offering` 模型（`offerings` 表）：
  - 完整发行字段：价格区间、发行价、定价日、份额明细、greenshow、bookrunners 等
  - `bookrunners` 以分号分隔字符串存储
- **新增** `Capitalization` 模型（`capitalization` 表）：
  - 字段：`shares_outstanding_pre/post_ipo`、`free_float_at_ipo`、`float_ratio`、`fully_diluted_shares`
- **新增** `Lockup` 模型（`lockups` 表）：
  - 字段：`lockup_days`、`lockup_start/end_date`、`is_staged_unlock`、`unlock_notes`、`unlock_shares_estimate`、`confidence`

#### `app/schemas.py`
- **重构** 全部 schema，统一命名为 `XxxCreate` / `XxxRead` 格式
- **保留** `IssuerCreate`；将原 `Issuer` read schema 重命名为 `IssuerRead`
- **新增** `FilingCreate` / `FilingRead`
- **新增** `OfferingCreate` / `OfferingRead`
- **新增** `CapitalizationCreate` / `CapitalizationRead`
- **新增** `LockupCreate` / `LockupRead`
- 时间字段类型改为 `Optional[str]`，与模型层保持一致
- 移除 `IssuerUpdate`（当前阶段未使用，后续按需恢复）

#### `README.md`
- 更新安装说明，增加 conda 环境示例
- 增加升级提示（从 Step 1 升级需删除旧 DB）
- 增加数据库表结构说明
- 更新当前进度列表

#### `CHANGELOG.md`（新增）
- 新增本文件，记录各阶段变更

### 不变文件
- `app/config.py` — 无需修改
- `app/db.py` — 无需修改
- `scripts/init_db.py` — 无需修改（`create_all` 自动感知新模型）
- `app/utils/logging.py` — 无需修改
- `requirements.txt` — 无需修改

---

## [Step 1] - 2026-03-10 — 工程骨架

### 新增文件
- `requirements.txt`
- `README.md`
- `app/__init__.py`
- `app/config.py` — pydantic-settings 配置类，含路径和日志级别
- `app/db.py` — SQLAlchemy engine、SessionLocal、Base、get_db()
- `app/models.py` — 最小 `Issuer` 占位模型
- `app/schemas.py` — 最小 `IssuerCreate` / `IssuerRead` 占位 schema
- `app/collectors/__init__.py`
- `app/parsers/__init__.py`
- `app/jobs/__init__.py`
- `app/utils/__init__.py`
- `app/utils/logging.py` — `get_logger(name)` 工具函数
- `scripts/init_db.py` — 创建目录 + `Base.metadata.create_all`
- `tests/__init__.py`
