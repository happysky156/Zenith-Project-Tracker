好，我们直接把它落成 **Streamlit 项目目录结构 + 页面文件拆分 + 数据表实现方案**。

先给结论：

**这套系统在 Streamlit 里要用“多页面 + 服务层 + 外部数据库”的结构。**
原因很明确：`st.session_state` 适合保存单个用户会话里的临时状态，并能跨页面保留，但用户刷新页面会重置成新会话；而 Community Cloud 也不保证本地文件存储持久化，所以真实项目数据不能只放在本地 Excel / 本地 SQLite 里。数据库连接这类全局资源则适合用 `st.cache_resource` 管理。([Streamlit 文档][1])

---

# 一、推荐的总目录结构

```text
project_tracker/
│
├─ app.py
├─ requirements.txt
├─ README.md
├─ .streamlit/
│  ├─ config.toml
│  └─ secrets.toml
│
├─ pages/
│  ├─ 1_Import_Center.py
│  ├─ 2_Sales_Board.py
│  ├─ 3_Operation_Board.py
│  ├─ 4_Project_Detail.py
│  ├─ 5_Meeting_Mode.py
│  └─ 6_Settings.py
│
├─ core/
│  ├─ constants.py
│  ├─ dictionaries.py
│  ├─ permissions.py
│  ├─ state.py
│  └─ routing.py
│
├─ database/
│  ├─ connection.py
│  ├─ schema.py
│  ├─ migrations.py
│  ├─ repositories/
│  │  ├─ project_repo.py
│  │  ├─ event_repo.py
│  │  ├─ meeting_repo.py
│  │  ├─ import_repo.py
│  │  └─ dictionary_repo.py
│  └─ adapters/
│     ├─ postgres_adapter.py
│     └─ sqlite_adapter.py
│
├─ services/
│  ├─ import_service.py
│  ├─ project_service.py
│  ├─ event_service.py
│  ├─ meeting_service.py
│  ├─ button_service.py
│  ├─ summary_service.py
│  └─ validation_service.py
│
├─ ui/
│  ├─ components/
│  │  ├─ filters.py
│  │  ├─ project_table.py
│  │  ├─ project_card.py
│  │  ├─ action_buttons.py
│  │  ├─ status_badges.py
│  │  ├─ meeting_card.py
│  │  └─ forms.py
│  ├─ layouts/
│  │  ├─ page_header.py
│  │  ├─ sidebar.py
│  │  └─ metric_strip.py
│  └─ helpers/
│     ├─ formatters.py
│     └─ messages.py
│
├─ domain/
│  ├─ models/
│  │  ├─ project.py
│  │  ├─ event_log.py
│  │  ├─ meeting_snapshot.py
│  │  └─ import_batch.py
│  └─ enums/
│     ├─ phase.py
│     ├─ health.py
│     ├─ result.py
│     ├─ request_type.py
│     └─ people.py
│
├─ utils/
│  ├─ dates.py
│  ├─ ids.py
│  ├─ excel.py
│  ├─ text_templates.py
│  └─ logger.py
│
├─ sql/
│  ├─ 001_init.sql
│  ├─ 002_indexes.sql
│  └─ 003_seed_dictionaries.sql
│
└─ tests/
   ├─ test_import.py
   ├─ test_buttons.py
   ├─ test_meeting_pool.py
   └─ test_round_logic.py
```

---

# 二、为什么这样拆

这套拆法的核心思想是：

## 1）`pages/` 只负责页面，不负责业务规则

页面文件应该尽量薄。
它们负责：

* 显示筛选器
* 调用服务层
* 显示表格和按钮
* 接收用户点击

它们**不应该**直接写 SQL，也不应该在页面里写一堆状态更新规则。

---

## 2）`services/` 负责业务逻辑

真正复杂的逻辑都放这里，比如：

* 导入时按 `project_id` 做 upsert
* `Quote Revised` 自动 `quote_round + 1`
* `Need Decision` 自动联动 `request_type = Decision`
* Meeting Pool 自动筛选
* `Reviewed No Change` 只更新 review 时间，不改业务状态

这样以后你改规则时，不需要去每个页面文件里找。

---

## 3）`database/` 负责持久化

项目真实数据要持久保存，不能依赖 `st.session_state`，因为 Session State 是单个用户会话级别，刷新页面会重置；Community Cloud 也不保证本地文件长期存在，所以生产环境必须用外部数据库。([Streamlit 文档][1])

---

## 4）`ui/components/` 负责复用组件

例如：

* 项目表格
* 状态标签
* 高频按钮组
* 会议卡片

这样 Sales Board 和 Operation Board 能共享很多 UI。

---

# 三、页面文件最终拆分

---

## `app.py`

这是入口文件。

### 作用

* 加载全局配置
* 初始化数据库连接
* 初始化全局 Session State
* 渲染顶层导航

如果你用新版导航，`st.navigation` 的入口文件本身就像一个路由框架，每次 rerun 都会先执行它。([Streamlit 文档][2])

### 不应该做的事

* 不直接写项目业务逻辑
* 不直接处理按钮更新

---

## `pages/1_Import_Center.py`

### 作用

* 上传 Excel
* 字段映射
* Project ID 校验
* 预览新增 / 更新结果
* 确认导入

### 依赖服务

* `import_service.py`
* `validation_service.py`

### 页面只做什么

* 拿文件
* 显示校验结果
* 触发导入

---

## `pages/2_Sales_Board.py`

### 作用

* 看所有 Sales 项目
* 筛选
* 点高频 Sales 按钮
* 手动加入 Meeting Pool

### 依赖服务

* `project_service.py`
* `button_service.py`
* `meeting_service.py`

### 组件

* `filters.py`
* `project_table.py`
* `action_buttons.py`

---

## `pages/3_Operation_Board.py`

### 作用

* 看所有 Operation 项目
* 筛选风险项目
* 点高频 Operation 按钮

### 依赖服务

* 同 Sales Board，但按钮字典不同

---

## `pages/4_Project_Detail.py`

### 作用

* 查看单项目当前状态
* 看时间线
* 看轮次变化
* 看请求层
* 执行低频动作

### 为什么单独拆页

因为复杂项目一定要有一个“真相页”，否则 Board 页面会越来越重。

---

## `pages/5_Meeting_Mode.py`

### 作用

* 自动生成本周会议池
* Team View / Boss View
* 点周会按钮
* 生成 meeting snapshot

### 依赖服务

* `meeting_service.py`
* `summary_service.py`

### 这是最关键的页面

它最后是替代你现在手工整理周会表的核心。

---

## `pages/6_Settings.py`

### 作用

* 管人员名单
* 管字典
* 管阈值
* 管会议规则

第一版可以做轻。
先只允许设置：

* Due Soon 天数
* Review 超期天数
* 固定字典展示

---

# 四、`core/` 层怎么用

---

## `core/constants.py`

放全局常量，例如：

* 默认分页大小
* 默认 Due Soon 天数
* 默认 Review 超期天数
* 默认主页面标题

---

## `core/dictionaries.py`

放固定字典：

* Sales Phase
* Operation Phase
* Health Status
* Result Status
* Request Type
* People List
* 首页高频按钮列表

---

## `core/state.py`

只负责 **会话级临时状态**，不负责真实项目数据。

适合放：

* 当前选中的 project_id
* 当前筛选条件
* 当前是否打开确认弹窗
* 当前 Boss View / Team View
* 当前导入文件的临时预览数据

不适合放：

* 项目最终状态
* event log
* meeting snapshot

因为这些必须持久化。([Streamlit 文档][1])

---

# 五、数据库实现方案

这里我给你一个最稳的方案：

## 开发环境

本地可以先用 **SQLite**

## 部署环境

Streamlit Cloud 上用 **PostgreSQL / Supabase Postgres**

原因是：

* 本地开发方便
* 云端要持久，不能依赖本地文件
* 外部数据库才适合多人共享、长期保留状态数据。([Streamlit 文档][3])

也就是说：

**代码层做数据库适配器，开发用 SQLite，部署切 Postgres。**

---

## 推荐数据库连接方式

### `database/connection.py`

负责：

* 读取 `.streamlit/secrets.toml`
* 初始化数据库连接
* 返回统一 session / connection

### 推荐做法

把数据库连接作为资源缓存，而不是每次页面 rerun 都重连。
Streamlit 官方建议全局资源用 `st.cache_resource`。([Streamlit 文档][4])

---

# 六、数据表最终落地方案

你前面确认的三张核心表，落地时我建议扩成五张：

---

## 1）`projects`

当前状态主表。
每个 `project_id` 只保留一条当前记录。

### 作用

回答：
**这个项目现在是什么状态。**

### 建议字段分组

* 身份字段
* 当前状态字段
* 轮次字段
* 人员字段
* 会议字段
* 请求层字段
* 时间字段

---

## 2）`event_logs`

每点一次按钮，插入一条。

### 作用

回答：
**这个项目是怎么变成现在这样的。**

### 为什么必须单独有

因为你们项目会反复报价、反复送样、反复改文件。
只看主表是看不出来过程的。

---

## 3）`meeting_snapshots`

每次正式周会保存一份快照。

### 作用

回答：
**这个项目在某一周会议上，当时是什么状态。**

### 为什么不只看 event_logs

因为会议是一个“当时状态”的集合，不只是单按钮动作。

---

## 4）`import_batches`

这个表我建议加。

### 作用

记录每次导入：

* 导入文件名
* 导入时间
* 导入人
* 新增多少
* 更新多少
* 失败多少

### 价值

后面你排查“这周为什么多了这些项目”会很好用。

---

## 5）`dictionary_settings`

第一版可以很轻。

### 作用

存：

* Due Soon 天数
* Review 过期天数
* 页面默认排序规则

人员名单和状态字典第一版也可以先写死在代码里，等第二版再搬进数据库。

---

# 七、推荐的主键、索引和约束

这部分很重要，后面性能和稳定性都靠它。

## `projects`

* 主键：`project_id`
* 索引：

  * `track_type`
  * `phase`
  * `health_status`
  * `current_owner`
  * `target_date`
  * `review_this_week`

## `event_logs`

* 主键：`event_id`
* 外键：`project_id -> projects.project_id`
* 索引：

  * `project_id`
  * `event_time DESC`
  * `event_type`

## `meeting_snapshots`

* 主键：`snapshot_id`
* 索引：

  * `meeting_week`
  * `project_id`
  * `health_status`

## `import_batches`

* 主键：`batch_id`
* 索引：

  * `import_time DESC`

---

# 八、Repository 层怎么拆

我建议一个表一个 repo，不要把所有 SQL 写进一个大文件里。

---

## `project_repo.py`

负责：

* 按 ID 查项目
* 列表筛选
* upsert 基础字段
* 更新当前状态字段

---

## `event_repo.py`

负责：

* 写 event log
* 查某项目时间线
* 查最近事件

---

## `meeting_repo.py`

负责：

* 写快照
* 按周查会议项目
* 查项目历史会议记录

---

## `import_repo.py`

负责：

* 写 import batch
* 记录导入结果

---

# 九、Service 层怎么拆

这里是真正重要的。

---

## `import_service.py`

负责：

* 解析上传 Excel
* 做字段映射
* 校验 Project ID
* 按 `project_id` 分成“新建/更新”
* 调用 repo 完成导入
* 生成导入报告

### 特别规则

没有 `project_id` 的行，直接拦住，不允许导入。
你已经把这条定死了，这里必须作为硬规则。

---

## `project_service.py`

负责：

* 列表筛选
* 项目详情读取
* 计算衍生字段
* 统一格式化给页面用的数据

例如：

* `days_since_status_update`
* `days_since_review`
* 是否高风险
* 是否显示红色 badge

---

## `button_service.py`

这是整个系统最关键的服务之一。

### 负责

* 接收按钮动作
* 判断这个动作属于哪类
* 更新 `projects`
* 写 `event_logs`
* 联动 round / request / meeting pool

例如：

* `Quote Revised` -> `quote_round + 1`
* `Need Decision` -> `health_status = Need Decision` + `request_type = Decision`
* `Reviewed No Change` -> 只改 review 时间

所有按钮逻辑都放这里，不要散落在页面文件里。

---

## `meeting_service.py`

负责：

* 自动筛选 Meeting Pool
* 生成 Team View / Boss View
* 保存 meeting snapshots
* 处理周会按钮

---

## `summary_service.py`

负责：

* 生成老板版摘要
* 生成团队版摘要
* 生成会议导出文本

第一版可以先只做简单文本拼装，不用 AI。

---

## `validation_service.py`

负责：

* 导入校验
* Project ID 唯一性校验
* 字典值合法性校验
* 必填字段校验

---

# 十、UI 组件层怎么拆

这样写，后面页面会清爽很多。

---

## `ui/components/filters.py`

统一所有页面的筛选条。
例如：

* owner 下拉
* phase 下拉
* health 下拉
* 高优先级勾选
* review_this_week 勾选

---

## `ui/components/project_table.py`

统一渲染项目列表。
Sales 和 Operation 可以传不同列配置。

---

## `ui/components/action_buttons.py`

统一渲染按钮组。
根据页面和 track_type 自动切换按钮集合。

---

## `ui/components/status_badges.py`

专门负责：

* phase badge
* health badge
* result badge
* pattern flag badge

这样颜色和显示逻辑都集中。

---

## `ui/components/meeting_card.py`

Meeting Mode 专用。
因为会议页显示的信息密度更高，建议单独做。

---

# 十一、Session State 的正确使用范围

这个要说清楚，不然后面很容易把它用过头。

## 只放临时 UI 状态

例如：

* 当前筛选器值
* 当前选中项目 ID
* 当前打开的 tab
* 当前确认弹窗状态
* 当前导入预览 DataFrame

## 不放持久业务数据

例如：

* 项目当前 phase
* round
* owner
* event log
* meeting snapshot

因为这些必须多人共享，且刷新后仍存在；Session State 只适合单用户会话内的临时状态，刷新后会重置。([Streamlit 文档][1])

---

# 十二、缓存建议

## 用 `st.cache_resource`

缓存：

* 数据库连接
* 字典加载器
* 可能后续会接的 AI 客户端

官方建议这类全局资源用 `st.cache_resource`，但共享资源要注意线程安全。([Streamlit 文档][4])

## 谨慎用 `st.cache_data`

适合缓存：

* 只读字典
* 不经常变的配置表
* 非实时统计结果

不建议直接缓存：

* 高频变动的项目列表
* 当前会议池
* 当前按钮点击后的实时状态

因为这个系统的数据变动很频繁，缓存太重会让你看到旧数据。

---

# 十三、导入文件实现建议

Streamlit 的 `st.file_uploader` 默认单文件大小限制是 200 MB；上传文件在后端内存中，不是持久存到磁盘，所以导入逻辑应当“上传后立即解析并入库”，不要把它当成长期存储。([Streamlit 文档][5])

所以导入页的实现原则是：

* 上传 Excel
* 立即解析
* 立即校验
* 立即导入数据库
* 可选地只记录导入批次，不必保存原文件

---

# 十四、MVP 版本的实际落地方案

我建议你现在就按下面这套来实施。

## 本地开发

* Python + Streamlit
* SQLite
* SQLAlchemy 或轻量 repository 封装
* Excel 导入先用 pandas

## 云端部署

* Streamlit Community Cloud
* 外部 Postgres
* `.streamlit/secrets.toml` 存数据库连接
* `st.cache_resource` 缓存连接资源。([Streamlit 文档][6])

---

# 十五、最简执行版目录

如果你想第一版先别拆太细，也可以先用这个“轻量但不乱”的版本：

```text
project_tracker/
├─ app.py
├─ pages/
│  ├─ 1_Import_Center.py
│  ├─ 2_Sales_Board.py
│  ├─ 3_Operation_Board.py
│  ├─ 4_Project_Detail.py
│  └─ 5_Meeting_Mode.py
├─ services/
│  ├─ import_service.py
│  ├─ button_service.py
│  ├─ meeting_service.py
│  └─ project_service.py
├─ database/
│  ├─ connection.py
│  ├─ schema.py
│  └─ repositories.py
├─ ui/
│  ├─ action_buttons.py
│  ├─ project_table.py
│  └─ filters.py
├─ core/
│  ├─ dictionaries.py
│  └─ state.py
└─ utils/
   ├─ excel.py
   ├─ dates.py
   └─ logger.py
```

这个版本已经足够开始写 MVP 了。
后面代码多了，再拆 repo 和 model 也来得及。

---

# 十六、最终建议

你这套系统最稳的技术路线可以压缩成一句话：

**前端用 Streamlit 多页面，页面只做展示和点击；业务逻辑放 services；真实数据放外部数据库；`project_id` 作为唯一主键；Session State 只保留临时 UI 状态，不承担项目持久化。**

下一步最合适的是直接进入：
**数据库 schema 草案 + 首批页面的数据流 + Streamlit 第一版代码骨架。**

[1]: https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state?utm_source=chatgpt.com "Session State - Streamlit Docs"
[2]: https://docs.streamlit.io/develop/api-reference/navigation/st.navigation?utm_source=chatgpt.com "st.navigation - Streamlit Docs"
[3]: https://docs.streamlit.io/develop/concepts/connections/connecting-to-data?utm_source=chatgpt.com "Connecting to data - Streamlit Docs"
[4]: https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource?utm_source=chatgpt.com "st.cache_resource - Streamlit Docs"
[5]: https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader?utm_source=chatgpt.com "st.file_uploader - Streamlit Docs"
[6]: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app?utm_source=chatgpt.com "Prep and deploy your app on Community Cloud"
