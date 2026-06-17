# PDF 知識庫 AI Agent — 企劃書

## 一句話說明

讓使用者用自然語言問問題，Agent 自動去搜尋 PDF 知識庫、彙整答案後回應，不需要手動關鍵字搜尋。

---

## 解決什麼問題

企業內部累積大量 PDF 文件（規章、說明書、報告等），員工需要查詢時只能：
1. 打開文件一頁一頁找
2. 用 Ctrl+F 搜尋關鍵字（只能完全比對，找不到同義詞）

**這個 Agent 解決的是「我知道這份資訊在某個 PDF 裡，但找不到在哪頁」的問題。**

--- 

## 技術選定理由

| 技術                        | 選定理由                                                                        |
| --------------------------- | ------------------------------------------------------------------------------- |
| **TypeScript + Bun**        | 必要要件。Bun 是 RAYVEN 標準 runtime，啟動快、無需複雜設定                      |
| **openAI API**              | 免費 tier 足夠（每日 1500 次），支援 Function Calling，無需信用卡               |
| **Hono**                    | 輕量 Web framework，與 Bun 相性最佳，10 行內可以啟動 server                     |
| **Python / Django（既有）** | 保留既有 RAG 後端的 embedding 模型（all-MiniLM-L6-v2）與 pgvector，不重複造輪子 |

---

## 系統架構

```
┌─────────────────────────────────────────────────────┐
│  瀏覽器                                              │
│  - 輸入問題                                          │
│  - 顯示 Agent 回答                                   │
└───────────────────┬─────────────────────────────────┘
                    │ HTTP POST /api/chat
┌───────────────────▼─────────────────────────────────┐
│  Hono Web Server（TypeScript / Bun）                 │
│  - 提供 HTML 頁面                                    │
│  - /api/chat endpoint                                │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Agent Loop                                     │ │
│  │  1. 收到使用者問題                               │ │
│  │  2. 送給 openAI（帶 tool 定義）                  │ │
│  │  3. openAI 決定要呼叫哪個 tool                   │ │
│  │  4. 執行 tool → 把結果回給 openAI                │ │
│  │  5. openAI 生成最終回答                          │ │
│  └─────────────────────────────────────────────────┘ │
└───────────────────┬─────────────────────────────────┘
                    │ HTTP（fetch）
┌───────────────────▼─────────────────────────────────┐
│  Django REST API（Python，既有後端）                  │
│  - POST /api/search/  → embedding + pgvector 搜尋    │
│  - GET  /api/documents/  → 文件列表                  │
└───────────────────┬─────────────────────────────────┘
                    │ ORM
┌───────────────────▼─────────────────────────────────┐
│  PostgreSQL + pgvector（Docker）                     │
└─────────────────────────────────────────────────────┘
```

---

## Agent 擁有的工具（Tools）

| 工具名稱                | 功能                                     | 何時使用                               |
| ----------------------- | ---------------------------------------- | -------------------------------------- |
| `search_knowledge_base` | 語義搜尋，回傳最相關的文章片段           | 使用者問「XXX 是什麼」「如何做 XXX」   |
| `list_documents`        | 列出知識庫中所有 PDF 文件                | 使用者問「有哪些資料」「知識庫有什麼」 |
| `get_document_detail`   | 取得特定文件的詳細資訊（狀態、chunk 數） | 使用者問特定文件                       |

---

## 想定使用場景

**誰：** 企業內部員工（HR、法務、業務等非工程師）

**何時：** 需要查找規章、契約範本、產品說明等內部文件時

**怎麼用：**

```
使用者：「試用期滿後，年休假怎麼計算？」

Agent：
  [呼叫 search_knowledge_base("試用期 年休假 計算")]
  [搜尋結果：員工手冊 第 3 章，第 12 條...]
  
  根據員工手冊第 12 條，試用期（3 個月）結束後，
  依照實際到職日比例計算當年度年休假天數。
  滿 1 年後適用正常年休制度（10 天起）。
  
  來源：員工手冊.pdf（第 23 頁）
```

---

## 目錄結構（預定）

```
agent/                    ← 新建 TypeScript 專案
  src/
    index.ts              ← 入口（啟動 Hono server）
    agent.ts              ← openAI Agent Loop
    tools.ts              ← tool 定義與執行邏輯
    mcp-server.ts         ← MCP Server（加分項）
  public/
    index.html            ← 聊天 UI（純 HTML，無 build 步驟）
  package.json
  tsconfig.json
  README.md
```

---

## 滿足的評分項

| 要件                      | 類型 | 說明                                   |
| ------------------------- | ---- | -------------------------------------- |
| TypeScript 實作           | 必要 | Bun + TypeScript                       |
| LLM Agent + Tool Use 循環 | 必要 | openAI Function Calling，自行實作 loop |
| Web UI                    | 必要 | Hono + 純 HTML                         |
| README 架構說明           | 必要 | 本文件基礎                             |
| MCP Server 自行實作       | 歡迎 | 同一套 tools 包裝為 MCP                |
| RAG 活用                  | 歡迎 | 既有 pgvector 語義搜尋                 |
| 思考過程 log              | 歡迎 | Tool Use 過程印出到 console            |

---

## 開發順序

```
Week 1
  Day 1  Django 加 REST API（search + list endpoints）
  Day 2  TypeScript 專案建立 + openAI 連線測試
  Day 3  Tools 實作（search / list / detail）
  Day 4  Agent Loop 實作（openAI Function Calling）
  Day 5  Hono Web Server + HTML UI
  Day 6  MCP Server（加分）
  Day 7  README + 整理 + Demo 準備
```
