# 新浪财经研报采集（sina_stock_finance）

基于 [Crawlo](https://github.com/crawl-coder/Crawlo) 的分布式爬虫，采集
新浪财经最新滚动研究报告（列表页 + 详情页正文），支持单机与多 Worker
分布式运行，数据入库 MySQL。

## 功能特性

- **列表页采集**：新浪财经研报列表（`vReport_List/kind/lastest`），212 页全量
- **详情页正文**：提取研报标题、类型、机构、研究员、发布日期、正文全文
- **分布式运行**：Redis Stream + Consumer Group，多 Worker 并行消费、崩溃任务自动回收
- **批量入库**：MySQLPipeline 批量写入（batch_size=500），`uk_url` 唯一键防重复
- **断点安全**：Redis 去重指纹跨运行持久化，重启不重抓

## 环境要求

- Python 3.10+（Crawlo 要求）
- MySQL 8.0（入库）
- Redis 7+（分布式模式）

## 安装

```bash
# 1. 创建虚拟环境并激活
conda create -n crawlo python=3.10 -y
conda activate crawlo

# 2. 安装依赖
pip install -r requirements.txt

# 3. 建库建表
mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS crawlo_deployer CHARACTER SET utf8mb4;"
mysql -uroot -p crawlo_deployer < sql/schema.sql
```

> 国内网络可用镜像加速：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 配置

### 运行模式切换（settings.py）

项目的运行模式由 `settings.py` 顶部的 `CrawloConfig.xxx()` 工厂决定，
支持三种模式，按需切换（改一行配置即可）：

| 模式 | 工厂方法 | 队列 | 去重 | 依赖 | 适用场景 |
|---|---|---|---|---|---|
| **单机** | `CrawloConfig.standalone()` | 内存 memory | MemoryFilter | 无 | 本地调试、小规模采集 |
| **分布式** | `CrawloConfig.distributed()` | Redis Stream | AioRedisFilter | Redis | 多 Worker 并行、长任务 |
| **自动** | `CrawloConfig.auto()` | 运行时探测 | 自动 | Redis 可选 | 单机/分布式自动切换 |

#### 单机模式

```python
config = CrawloConfig.standalone(
    project_name='sina_stock_finance',
    concurrency=8,
    download_delay=1.0,
)
```

内存队列，无需 Redis。运行：

```bash
python run.py
```

> 注意：单机模式每次运行去重指纹在内存中，重启后会重新抓取（无跨运行去重）。

#### 分布式模式（当前默认）

```python
config = CrawloConfig.distributed(
    project_name='sina_stock_finance',
    concurrency=8,
    download_delay=1.0,
)
```

Redis Stream 队列 + 多 Worker 并行，需要 Redis 运行。运行：

```bash
python run_distributed.py            # 默认 5 Worker
python run_distributed.py --workers 10
```

> 分布式模式默认 `CONCURRENCY=16`、`DISTRIBUTED_WORKER_IDLE_TIMEOUT=120`；
> 本项目的 `concurrency=8` 显式覆盖了并发，`idle_timeout` 在下方单独调为 600。

#### 自动模式（推荐新手）

```python
config = CrawloConfig.auto(
    project_name='sina_stock_finance',
    concurrency=8,
    download_delay=1.0,
)
```

运行时探测 Redis：可用 → 分布式队列；不可用 → 单机内存队列。
适合"本地单机、生产分布式"的部署形态，代码不用改。

### 数据库（`sina_stock_finance/settings.py`）

按实际环境修改 MySQL 连接与 Redis 地址：

```python
MYSQL_HOST = '127.0.0.1'
MYSQL_PORT = 3306
MYSQL_USER = 'crawlo'
MYSQL_PASSWORD = 'crawlo123'
MYSQL_DB = 'crawlo_deployer'
MYSQL_TABLE = 'sina_stock_finance'

REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
```

> MySQL 冲突策略默认 `MYSQL_INSERT_IGNORE=True`（重复 URL 跳过），配合
> `uk_url` 唯一键保证幂等入库。如需覆盖更新，改用 `MYSQL_UPDATE_COLUMNS`。

### 爬取范围（`sina_stock_finance/spiders/stock_finance.py`）

```python
MAX_PAGES = 212   # 最大页数；可用环境变量 STOCK_MAX_PAGES 覆盖（冒烟用）
```

### 分布式空闲退出阈值

```python
DISTRIBUTED_WORKER_IDLE_TIMEOUT = 600   # 长任务建议 600s，防止翻页间隙误退出
```

## 运行

### 单机模式

```bash
python run.py
```

### 分布式模式（推荐）

```bash
# 默认 5 个 Worker
python run_distributed.py

# 指定 Worker 数
python run_distributed.py --workers 10

# 冒烟测试（限 2 页）
python run_distributed.py --workers 5 --pages 2
```

首次/复跑前建议清空 Redis 指纹，避免 start URL 被上次运行的去重指纹判重：

```bash
redis-cli -n 0 FLUSHDB
```

## 日志

- 每个 Worker 使用框架默认文件日志：`logs/sina_stock_finance_*.log`
  （文件名带启动时间戳，可与 Worker 对应）；
- 单机运行同样写入 `logs/` 目录；
- 日志级别在 `settings.py` 的 `LOG_LEVEL` 调整。

## 数据表

见 [sql/schema.sql](sql/schema.sql)，核心字段：

| 字段 | 说明 |
|---|---|
| `title` | 研报标题 |
| `url` | 详情页地址（唯一键，幂等入库） |
| `report_type` | 报告类型（宏观/行业/公司/策略等） |
| `pub_date` | 发布日期 |
| `org_name` | 研究机构 |
| `researchers` | 研究员 |
| `content` | 正文全文 |

## 项目结构

```text
sina_stock_finance/
├── crawlo.cfg                    # Crawlo 项目配置（settings 模块路径）
├── run.py                        # 单机运行入口
├── run_distributed.py            # 分布式多 Worker 启动脚本
├── requirements.txt              # 依赖清单
├── sql/schema.sql                # MySQL 建表脚本
├── logs/                         # 运行日志
└── sina_stock_finance/
    ├── settings.py               # 项目配置（MySQL/Redis/日志）
    ├── items.py                  # 数据模型
    ├── pipelines.py              # 数据管道
    ├── middlewares.py            # 中间件（模板）
    └── spiders/stock_finance.py  # 爬虫：列表页 + 详情页
```

## 分布式设计要点

- **列表页批量推送**：`start_requests` 一次性入队全部列表页，Worker 并行消费，
  避免串行翻页限制并行度；
- **种子锁**：仅 Leader Worker 生成起始请求，其余跳过（防重复入队）；
- **投递语义**：at-least-once（至少一次），重复由 `uk_url` 唯一键 + MySQL
  INSERT IGNORE 兜底；
- **崩溃回收**：Worker 异常退出后，未 ACK 任务由 XCLAIM 自动重投。

## 常见问题

| 问题 | 处理 |
|---|---|
| 0 产出、Filtered 1 duplicate | Redis 残留指纹 → `redis-cli FLUSHDB` 后重跑 |
| 提前退出（只爬几页） | `DISTRIBUTED_WORKER_IDLE_TIMEOUT` 太短 → 调大（建议 600） |
| MySQL 连接失败 | 检查 `MYSQL_*` 配置与 `asyncmy` 是否安装 |
| 分布式 0 Worker 启动 | 确认 Redis 运行（`redis-cli ping`） |
