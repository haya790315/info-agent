# MCP Server 實施方案

## 背景與目標

目前要查詢 `rag_agent` 這個 pgvector 資料庫，必須每次手動拼接 `docker exec ... psql` 指令，
過程中需要試錯欄位名稱、等待權限確認，非常沒有效率。

**目標**：在專案內建立一個 MCP（Model Context Protocol）伺服器，讓 Claude Code 可以直接呼叫工具來讀寫資料庫，不需要手寫 SQL、不需要常駐 Django dev server。

---

## 選擇的方案：MCP 直連 Django ORM（方案 A）

### 核心架構

```
Claude Code
    │  MCP 工具呼叫（stdio）
    ▼
mcp_server.py
    │  django.setup() → 直接 import kb.models / kb.services
    ▼
Django ORM + 現有服務層
    │  SQL / pgvector CosineDistance
    ▼
PostgreSQL + pgvector（Docker 容器）
```

### 為什麼選方案 A，不選「先建 REST API 再包 MCP」（方案 B）

| 比較項目               | 方案 A（MCP 直連 ORM） | 方案 B（REST API + MCP）       |
| ---------------------- | ---------------------- | ------------------------------ |
| 需要常駐 Django server | ❌ 不需要               | ✅ 必須先 `make dev`            |
| 層數                   | 1 層                   | 2 層（HTTP + MCP）             |
| CSRF / 認證問題        | 不涉及                 | 需要處理                       |
| 複用現有服務層         | 直接 import 呼叫       | 需先寫 view 再呼叫             |
| 何時才值得用 B         | —                      | 前端或其他 HTTP 客戶端也需要時 |

---

## 需要修改 / 新增的檔案

### 1. `requirements.txt`（修改）
追加一行：
```
mcp
```

### 2. `mcp_server.py`（新增，專案根目錄）

負責以下事項：
- 設定 `DJANGO_SETTINGS_MODULE=rag_agent.settings`
- 呼叫 `django.setup()` 初始化 ORM
- 用 FastMCP 註冊下方的工具
- stdio 傳輸（由 Claude Code 按需啟動）
- 支援 `--selftest` 模式，不依賴 MCP 傳輸即可驗證工具是否正常

### 3. `.mcp.json`（新增，專案根目錄）

把伺服器登錄給 Claude Code：
```json
{
  "mcpServers": {
    "learn-rag-db": {
      "command": "uv",
      "args": [
        "run", "--directory",
        "/Users/ruyo.ko/works/practice-project/learn-rag",
        "python", "mcp_server.py"
      ],
      "env": {
        "DJANGO_SETTINGS_MODULE": "rag_agent.settings",
        "DB_PASSWORD": "postgres"
      }
    }
  }
}
```

---

## 工具清單

### 讀取工具

| 工具名稱          | 參數                                  | 說明                                                               | 複用的現有程式碼                             |
| ----------------- | ------------------------------------- | ------------------------------------------------------------------ | -------------------------------------------- |
| `list_documents`  | 無                                    | 列出所有文件（id / filename / status / chunk_count / uploaded_at） | `Document.objects.all()`                     |
| `get_document`    | `document_id`                         | 取得單篇詳情，含 error_message                                     | `Document.objects.get(pk=id)`                |
| `get_chunks`      | `document_id`, `limit=20`, `offset=0` | 分頁取得 chunk 正文                                                | `Chunk.objects.filter(document_id=id)`       |
| `semantic_search` | `query`, `top_k=5`                    | **核心功能**：語義搜尋，回傳最相似的 chunk + 所屬文件資訊          | `embedder.embed_one()` + `searcher.search()` |
| `database_stats`  | 無                                    | 文件數 / chunk 數 / 各狀態統計                                     | ORM 聚合                                     |

### 寫入工具

| 工具名稱          | 參數          | 說明                                                                                                                         | 複用的現有程式碼                           |
| ----------------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| `ingest_pdf`      | `file_path`   | 讀取 PDF → 抽取文字 → 分塊 → 向量化 → 寫入資料庫，完整複刻 UploadView 的狀態流轉（pending → processing → complete / failed） | `processor` + `embedder` + ORM bulk_create |
| `delete_document` | `document_id` | 級聯刪除文件及其所有 chunk，附確認防呆                                                                                       | `Document.objects.filter(pk=id).delete()`  |

---

## 關鍵技術細節

### Django 啟動順序
必須先 `django.setup()` 才能 import `kb.models`，否則會拋出 `AppRegistryNotReady`。

```python
import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rag_agent.settings")
django.setup()

# 這之後才能 import
from kb.models import Document, Chunk
from kb.services import embedder, searcher, processor
```

### 同步 ORM vs 非同步 MCP
FastMCP 會將同步函式丟到執行緒池執行，Django ORM 在執行緒池中是安全的。
若出現 `SynchronousOnlyOperation` 錯誤，設定環境變數 `DJANGO_ALLOW_ASYNC_UNSAFE=true` 即可解決。

### 嵌入模型只載入一次
[`embedder.py`](kb/services/embedder.py) 的 `_model` 是模組層級單例（模組載入時即初始化）。
MCP 伺服器是長駐程序，90MB 的模型只在**第一次呼叫**時載入，之後所有工具呼叫都共用同一個實例。

---

## 風險與注意事項

| 風險               | 說明                                                                | 對策                                           |
| ------------------ | ------------------------------------------------------------------- | ---------------------------------------------- |
| 寫入操作不可逆     | `delete_document` 會級聯刪除所有 chunk                              | 工具內加確認機制，刪除前先回傳文件資訊請求確認 |
| 首次呼叫較慢       | `semantic_search` / `ingest_pdf` 首次會花幾秒載入模型               | 屬正常現象，之後就快                           |
| `.mcp.json` 需重連 | 新增 `.mcp.json` 後，**需重開 / 重連 Claude Code 會話**工具才會出現 | 實施完成後提醒重連                             |
| 測試環境不涉及     | 現有測試用 SQLite（`test_settings.py`），MCP 走真實 pgvector        | 互不影響，MCP 無需修改測試設定                 |

---

## 驗收步驟

1. **自檢**：執行 `python mcp_server.py --selftest`，確認各工具能正常呼叫底層函式並回傳資料
2. **確認連線**：重連 Claude Code 後，用 `/mcp` 確認看到 `learn-rag-db` 已連線
3. **實測語義搜尋**：讓 Claude 呼叫 `semantic_search("React 経験")`，確認能命中 `コウルーヨウ(職歴書).pdf`
4. **實測讀取**：呼叫 `list_documents()` 和 `get_chunks(1)`，確認資料正確
5. **實測寫入**：用 `ingest_pdf` 上傳一份新 PDF，確認 status 流轉正常

---

## 實施順序

```
1. uv pip install mcp         → 確認版本，回填 requirements.txt
2. 撰寫 mcp_server.py         → 先實作讀取工具，--selftest 驗證通過
3. 追加寫入工具               → ingest_pdf / delete_document
4. 新增 .mcp.json             → 登錄給 Claude Code
5. 重連會話，實測全部工具
```
