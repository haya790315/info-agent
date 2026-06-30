# Research / Discovery Log — duplicate-upload-replace

## 发现范围（Discovery Scope）

类型：**扩展（Extension）** — 在现有 PDF 上传流程（`UploadView`）上集成「同名即替换」行为。采用轻量发现，聚焦集成点与现有模式。

## 现状调查（Investigations）

### 1. 当前上传流程
- 来源：[knowledge_base/views.py:30-94](knowledge_base/views.py#L30-L94) `UploadView.post`
- 行为：始终 `Document.objects.create(...)`（[views.py:46](knowledge_base/views.py#L46)）→ 同名文件必产生重复 Document。
- 处理顺序（关键）：
  1. 读取 `pdf_bytes`
  2. **先**创建 Document、`status=processing`、**先保存原本 PDF**（[views.py:53](knowledge_base/views.py#L53)）
  3. 再抽取文本、分块、嵌入
  4. `transaction.atomic()` 内 `bulk_create` chunks + 更新 doc
  5. 失败 → 记录 `error_message`、`status=failed`
- **含义**：现有「先存记录/文件再抽取」对新建是合理的（图像型 PDF 也保留原本）；但对**替换不安全**——若先改动既有 doc 再抽取失败，会破坏旧数据。替换路径必须把易失败步骤（抽取/嵌入）放在任何破坏性写入之前。

### 2. 数据模型
- 来源：[knowledge_base/models.py](knowledge_base/models.py)
- `Document.filename` 为 `CharField`，**无 unique 约束**；历史数据可能已存在多个同名记录（实测库中已有 `コウルーヨウ(職歴書).pdf` 等单份，但模型层不阻止重复）。
- `Chunk.document` 外键 `on_delete=CASCADE`（[models.py:82-86](knowledge_base/models.py#L82-L86)）→ 删除 Document 会级联删除其 Chunk。
- `file = FileField(upload_to=pdfs/<category>/<filename>)`（[models.py:10-13](knowledge_base/models.py#L10-L13)）→ 物理文件按种别分目录；种别变更会改变存储路径。Django FileField **不会自动删除**旧物理文件。

### 3. 反馈机制
- `django.contrib.messages` 中间件与 context processor 已在 [config/settings.py](config/settings.py) 启用，但**代码中尚无任何 messages 使用**，模板也未渲染 messages。
- 当前成功/失败仅通过跳转到详情页 + `document.status` 体现。

### 4. 表单与种别
- [knowledge_base/forms.py](knowledge_base/forms.py) `UploadForm` 校验 PDF 类型/大小；`category` 可空。
- `processor.chunk_config_for_category` / `extract_text` / `split_into_chunks` 为现成可复用流程。

## 架构决策（Design Decisions）

| 决策 | 选择 | 理由 |
|------|------|------|
| 同名判定 | 仅 `filename` | 用户确认；不纳入 category |
| 替换方式 | 复用 Document 行、删旧 chunk、重建 | 用户确认；保持 document id 稳定，外部引用不失效 |
| 失败安全 | 抽取/嵌入在破坏性写入之前；破坏性写入用 `transaction.atomic()` 包裹 | 满足 Req 3：失败时旧数据完好、无中间不一致可见状态 |
| 失败原因提示 | 用 messages 闪现，**不**把 `error_message` 写入既有 doc | 满足 Req 3.3「提示失败原因」同时满足 Req 3.1「不做部分更新」 |
| 旧物理文件 | 替换成功后显式删除旧文件再保存新文件 | 避免孤儿/陈旧文件；种别变更导致路径变化时尤其必要 |
| 历史多重复记录 | 选定一个 doc 作为替换目标，删除其余同名 doc（级联其 chunk） | 满足 Req 1.4「替换后该文件名仅对应一个有效文档」 |
| 是否加 DB unique 约束 | **不加** | 既有重复数据会使迁移失败；改由应用逻辑保证单一性，避免破坏性 schema 变更 |
| 反馈实现 | 启用 `django.contrib.messages` 并在 base 模板渲染 | 中间件已就绪，零新依赖 |

## 综合（Synthesis）

- **复用而非新建**：替换路径与新建路径共享同一套「抽取→分块→嵌入」逻辑；差异仅在持久化阶段（新建 = create；替换 = 复用行 + 重建 chunk + 换文件）。将易失败的纯计算部分提取为可共享步骤，持久化分支化。
- **构建 vs 采纳**：反馈采纳 Django 内建 messages 框架（已配置），不自造提示机制。
- **简化**：不引入版本历史、不加唯一约束、不处理严格并发锁——均列入 Out of Boundary，保持最小变更。

## 风险（Risks）

- **文件 I/O 非事务性**：`FileField` 的物理文件写入/删除不在 DB 事务内。缓解：把文件操作放在事务块内的最后一步，且在抽取/嵌入成功之后；本项目为本地文件系统、单机，残留风险可接受。
- **并发同名上传**：两个请求同时替换同名文件可能产生竞态。已在 Out of Boundary 声明不做严格锁；单一性为尽力而为。
