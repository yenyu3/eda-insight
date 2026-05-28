# EDA Workflow Intelligence Platform — CLAUDE.md

> 這是給 Claude Code 讀取的主要專案規格文件。開始任何開發工作前，請完整讀完此文件。

---

## 專案概述

**專案名稱：** EDA Workflow Intelligence Platform
**定位：** 給 EDA 產業非開發者角色（AE、SE、EDA PM）的 AI-first Workflow Observability Platform。讓使用者不需要讀懂 EDA log，也能理解 workflow 狀態、掌握設計風險、做出工程決策。

**核心價值主張：** 解決現有 EDA 工具鏈的「黑盒問題」——使用者上傳一段 Verilog 程式碼，系統自動執行完整 EDA pipeline，並以 AI 分析結果、互動視覺化儀表板呈現，全程不需要使用者懂任何 EDA 工具指令。

**Python 在本專案的角色：** Python 是整個系統的核心語言，負責 EDA 工具控制、資料解析、AI 分析引擎、全部業務邏輯與 API 服務。React 前端僅負責視覺呈現，所有資料處理與分析邏輯均在 Python 後端完成。

---

## 技術架構

### 三層架構

```
Layer 3 — 展示層 (React)
  React 18 + Vite, Tailwind CSS, react-plotly.js, D3.js
  React Router v6, TanStack Query, Framer Motion

Layer 2 — 分析層 (Python 核心)
  Flask API Server, Anthropic Claude API
  pandas, networkx, re, json, SQLite

Layer 1 — 執行層 (Python 控制)
  subprocess → Icarus Verilog, Yosys
  vcdvcd, re
```

### 專案目錄結構

```
eda-workflow-platform/
├── CLAUDE.md                  # 本文件
├── backend/                   # Python 後端（核心）
│   ├── app.py                 # Flask 主程式，所有 API 端點
│   ├── workflow_engine.py     # EDA 工具執行控制器
│   ├── verilog_parser.py      # Verilog 靜態分析器
│   ├── vcd_parser.py          # 波形資料解析
│   ├── report_parser.py       # 合成報告解析
│   ├── dependency_analyzer.py # Module 依賴關係分析
│   ├── ai_engine.py           # Anthropic API 封裝
│   ├── db_manager.py          # SQLite 資料庫管理
│   ├── requirements.txt       # Python 套件清單
│   └── uploads/               # 暫存上傳的 .v 檔案
│       └── runs/              # 每次執行的輸出目錄
├── frontend/                  # React 前端（呈現層）
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Upload.jsx
│   │   │   ├── Analysis.jsx
│   │   │   ├── History.jsx
│   │   │   └── Compare.jsx
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   ├── WorkflowPipeline.jsx
│   │   │   ├── WaveformChart.jsx
│   │   │   ├── DependencyGraph.jsx
│   │   │   ├── MetricCard.jsx
│   │   │   ├── RiskPanel.jsx
│   │   │   ├── AIInsightPanel.jsx
│   │   │   └── LogViewer.jsx
│   │   ├── hooks/
│   │   │   ├── useRunStatus.js
│   │   │   └── useSSEStream.js
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── sample_verilog/            # 測試用的 Verilog 範例電路
    ├── counter_4bit.v
    ├── adder_8bit.v
    └── counter_tb.v           # testbench
```

---

## Python 後端模組規格

### app.py — Flask API Server

所有端點前綴為 `/api`，回傳格式一律為 JSON，並啟用 `flask-cors` 允許 Vite dev server（`localhost:5173`）跨來源請求。

| 端點 | 方法 | 功能 |
|------|------|------|
| `POST /api/upload` | POST | 接收 .v 檔案，呼叫 `verilog_parser.py`，回傳 module 結構 JSON |
| `POST /api/run` | POST | 觸發固定 EDA pipeline（lint → simulate → synthesize），background thread 執行，回傳 `run_id`；進階版本接入 `workflow_planner` 動態選步驟 |
| `GET /api/status/<run_id>` | GET | 回傳各 stage 即時狀態（pending/running/done/error），供前端 polling |
| `GET /api/stream/<run_id>` | GET (SSE) | Server-Sent Events，串流推送 AI 分析文字 |
| `GET /api/result/<run_id>` | GET | 回傳完整結果：波形 JSON、PPA 指標、dependency graph、AI 摘要 |
| `GET /api/history` | GET | 從 SQLite 讀取所有執行歷史，回傳版本清單 |
| `POST /api/compare` | POST | 接收兩個 `run_id`，回傳 PPA 差異比較資料 |

**SSE 實作注意事項：**
- 使用 `flask` 的 `Response` 搭配 `stream_with_context` 實作 SSE
- Content-Type 設為 `text/event-stream`
- 每個事件格式：`data: <json_string>\n\n`
- 前端使用 `EventSource` API 接收

### workflow_engine.py — EDA 工具執行控制器

**設計策略（兩個版本）：**
- **MVP 版本（先實作）：** 固定完整 pipeline — lint → simulate → synthesize，不依賴 AI 動態決定，確保期末 Demo 穩定
- **進階版本（MVP 完成後）：** 接收 `ai_engine.workflow_planner()` 回傳的 JSON 步驟清單，動態決定本次執行哪些工具；後端加 fallback — 若 AI 回傳格式有誤，自動退回固定完整 pipeline

**MVP 核心邏輯（固定版）：**
1. 固定依序執行：verilog_parser → iverilog → vvp → yosys
2. 每個 stage 完成後更新 SQLite 的狀態欄位
3. 失敗時自動觸發 `ai_engine.debug_advisor()`

**subprocess 呼叫範例：**
```python
# 模擬
result = subprocess.run(
    ['iverilog', '-o', 'sim.out', verilog_file],
    capture_output=True, text=True, timeout=60
)

# 執行模擬產生 VCD
result = subprocess.run(
    ['vvp', 'sim.out'],
    capture_output=True, text=True, timeout=60
)

# 合成
result = subprocess.run(
    ['yosys', '-p', f'read_verilog {verilog_file}; synth; write_json out.json; stat'],
    capture_output=True, text=True, timeout=120
)
```

**重要：** 務必設 `timeout`，避免無窮等待。捕獲 `stdout` 和 `stderr` 兩者。

### verilog_parser.py — Verilog 靜態分析器

使用 `re` 模組解析，**不呼叫任何外部工具**，純 Python 實作。

需要萃取：
- `module` 名稱與 port 列表（`input`/`output`/`inout`，含位元寬度）
- `wire`/`reg` 訊號宣告
- `always`/`assign` 區塊（區分時序與組合邏輯）
- `module instantiation`（子模組名稱與實例名稱）
- 基本 Lint 問題（`blocking`/`non-blocking` 混用、未使用訊號）

輸出格式（Python dict → JSON）：
```json
{
  "modules": [
    {
      "name": "counter_4bit",
      "ports": [
        {"name": "clk", "direction": "input", "width": 1},
        {"name": "count", "direction": "output", "width": 4}
      ],
      "signals": ["clk", "reset", "count"],
      "logic_type": "sequential",
      "instantiations": ["clk_divider"]
    }
  ],
  "lint_issues": [
    {"type": "unused_wire", "signal": "n3", "line": 15}
  ]
}
```

### vcd_parser.py — 波形資料處理

使用 `vcdvcd` 套件讀取，`pandas` 整理後輸出 Plotly 格式。

輸出格式：
```json
{
  "signals": ["clk", "reset", "count"],
  "timeline": {
    "clk":   {"times": [0, 5, 10, ...], "values": [0, 1, 0, ...]},
    "reset": {"times": [0, 20],         "values": [1, 0]},
    "count": {"times": [0, 10, 20, ...], "values": [0, 1, 2, ...]}
  },
  "stats": {
    "sim_duration_ns": 200,
    "clock_period_ns": 10,
    "switching_activity": {"clk": 40, "count": 15}
  }
}
```

### report_parser.py — Yosys 合成報告解析

使用 `re` 解析 Yosys `stat` 指令輸出的文字報告。

需萃取的關鍵指標：
- `Number of cells` → `cell_count`
- `Number of wires` → `wire_count`
- `Estimated number of transistors` → `transistor_count`
- `$_DFF_*` 計數 → flip-flop 數量
- Critical path delay（若 Yosys 有輸出）

輸出格式：
```json
{
  "cell_count": 47,
  "wire_count": 32,
  "flip_flop_count": 4,
  "critical_path_ns": 2.3,
  "slack_ns": 1.7,
  "area_estimate": "medium"
}
```

**注意：** Yosys 免費版不一定輸出完整時序資訊，`critical_path_ns` 和 `slack_ns` 若無法萃取則設為 `null` 而非造假數字。

### dependency_analyzer.py — Module 依賴分析

使用 `networkx` 建立有向無環圖（DAG）。

```python
import networkx as nx

def build_dag(parser_result: dict) -> dict:
    G = nx.DiGraph()
    for module in parser_result["modules"]:
        G.add_node(module["name"])
        for inst in module["instantiations"]:
            G.add_edge(module["name"], inst)
    
    # Critical path = 最長路徑
    critical_path = nx.dag_longest_path(G)
    
    # 輸出 D3.js 格式
    return {
        "nodes": [{"id": n, "in_degree": G.in_degree(n)} for n in G.nodes],
        "links": [{"source": u, "target": v} for u, v in G.edges],
        "critical_path": critical_path,
        "topological_order": list(nx.topological_sort(G))
    }
```

### ai_engine.py — AI 分析引擎

使用 `anthropic` SDK，模型固定使用 `claude-sonnet-4-20250514`，`max_tokens=1024`。

**AI workflow 設計說明：**
- MVP 不實作 `workflow_planner`，pipeline 由 `workflow_engine.py` 固定執行
- MVP 完成後，才實作 `workflow_planner` 作為進階功能
- `workflow_planner` 的設計重點：AI 只能從三個預定義選項選擇，不能自由發揮，後端永遠有 fallback

**六個功能模組：**

#### 1. verilog_insight（MVP 必做）
```python
# 輸入：verilog_parser 的解析結果 JSON
# 輸出：電路功能說明、複雜度評估（自然語言，streaming）
PROMPT = """
你是 EDA 領域的技術顧問。根據以下 Verilog 解析結果，用繁體中文說明：
1. 這個電路的功能是什麼
2. 電路複雜度評估（module 數量、port 數量）
3. 有哪些潛在問題需要注意
請用清楚易懂的語言，讓非電路工程師也能理解。
Verilog 解析結果：{parser_result}
"""
```

#### 2. workflow_planner（進階功能，MVP 完成後再做）
```python
# 輸入：verilog_insight 結果 + 使用者選擇的分析目標
# 輸出：JSON 步驟清單（嚴格限制選項範圍）
PROMPT = """
你是 EDA workflow 規劃專家。根據以下資訊，決定這次要執行哪些分析步驟。
steps 只能從 ["lint", "simulate", "synthesize"] 中選擇，可以選一個或多個。
回傳純 JSON，不要任何 markdown 或說明文字：
{
  "steps": ["simulate", "synthesize"],
  "reason": "時序邏輯電路建議先模擬驗證功能，再合成評估面積"
}
電路資訊：{verilog_insight}
使用者目標：{user_goals}
"""
# 重要：解析 AI 回傳時必須做 validation
# 若 steps 包含非預定義選項 or 解析失敗 → fallback 到 ["simulate", "synthesize"]
VALID_STEPS = {"lint", "simulate", "synthesize"}
```

#### 3. log_insight（MVP 必做）
- 輸入：Icarus Verilog / Yosys 完整 stdout log 文字
- 輸出：重要事件清單、warning 分類、結構化摘要

#### 4. debug_advisor（MVP 必做）
- 輸入：stderr 錯誤訊息 + 原始 Verilog 程式碼
- 輸出：錯誤類型、問題行號、具體修正建議
- **此功能使用 streaming**，讓使用者即時看到診斷過程

#### 5. risk_analyzer（MVP 必做）
- 輸入：合成指標（來自 `report_parser`）+ 波形統計（來自 `vcd_parser`）
- 輸出：`{"timing_risk": 2.5, "area_risk": 4.0, "function_risk": 1.0, "summary": "..."}`
- 分數範圍 0-10，越高越危險

#### 6. bottleneck_detector（MVP 必做）
- 輸入：dependency graph DAG + critical path
- 輸出：瓶頸節點識別、影響範圍說明、優化建議

**Streaming 實作：**
```python
def stream_analysis(self, prompt: str):
    with self.client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for text in stream.text_stream:
            yield text
```

**JSON 輸出解析注意：**
- 要求 AI 只回傳 JSON 時，在 prompt 中明確寫「回傳純 JSON，不要 markdown backtick」
- 解析前先用 `text.strip().lstrip("```json").rstrip("```").strip()` 清除可能的 fence

### db_manager.py — SQLite 資料庫管理

使用 Python 標準函式庫 `sqlite3`，資料庫檔案存在 `backend/eda_platform.db`。

**資料表設計：**
```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',  -- pending/running/done/error
    verilog_content TEXT,
    parser_result TEXT,    -- JSON string
    workflow_plan TEXT,    -- JSON string
    sim_result TEXT,       -- JSON string
    synthesis_result TEXT, -- JSON string
    dependency_graph TEXT, -- JSON string
    ai_summary TEXT,
    ppa_cell_count INTEGER,
    ppa_critical_path_ns REAL,
    ppa_slack_ns REAL
);

CREATE TABLE stage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    stage TEXT,
    status TEXT,
    log_output TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
```

---

## Flask API 端點詳細規格

### POST /api/upload
```json
// Request: multipart/form-data
// Response:
{
  "run_id": "uuid-string",
  "filename": "counter_4bit.v",
  "parser_result": { /* verilog_parser 輸出 */ },
  "preview": "module counter_4bit(\n  input clk..."
}
```

### POST /api/run
```json
// Request:
{"run_id": "uuid-string", "goals": ["simulate", "synthesize"]}
// Response: 202 Accepted
{"run_id": "uuid-string", "status": "started"}
```
**注意：** 這個端點要用 `threading.Thread` 在背景執行 pipeline，不能 block HTTP response。

### GET /api/status/<run_id>
```json
{
  "run_id": "uuid-string",
  "overall": "running",
  "stages": [
    {"name": "verilog_parse",  "status": "done",    "duration_ms": 45},
    {"name": "ai_plan",        "status": "done",    "duration_ms": 820},
    {"name": "simulation",     "status": "done",    "duration_ms": 1240},
    {"name": "synthesis",      "status": "running", "duration_ms": null},
    {"name": "dep_analysis",   "status": "pending", "duration_ms": null},
    {"name": "ai_report",      "status": "pending", "duration_ms": null}
  ]
}
```

### GET /api/result/<run_id>
```json
{
  "run_id": "uuid-string",
  "filename": "counter_4bit.v",
  "parser_result": { /* ... */ },
  "waveform": { /* vcd_parser 輸出 */ },
  "synthesis": { /* report_parser 輸出 */ },
  "dependency_graph": { /* nodes, links, critical_path */ },
  "ai_summary": "此電路功能驗證完全通過...",
  "risk_scores": {"timing": 2.5, "area": 4.0, "function": 1.0},
  "lint_issues": [{ "type": "unused_wire", "signal": "n3" }]
}
```

### POST /api/compare
```json
// Request:
{"run_id_a": "uuid-a", "run_id_b": "uuid-b"}
// Response:
{
  "version_a": {"filename": "v1.v", "cell_count": 47, "critical_path_ns": 2.3, "slack_ns": 1.7},
  "version_b": {"filename": "v2.v", "cell_count": 39, "critical_path_ns": 2.7, "slack_ns": 1.3},
  "diff": {
    "cell_count": {"delta": -8, "pct": -17.0, "better": true},
    "critical_path_ns": {"delta": 0.4, "pct": 17.4, "better": false},
    "slack_ns": {"delta": -0.4, "better": false}
  },
  "ai_tradeoff": "版本 B 面積縮減 17%，但關鍵路徑退步 0.4ns..."
}
```

---

## React 前端規格

### 頁面路由

| 頁面 | 路由 | 主要功能 |
|------|------|---------|
| Upload | `/` | 檔案上傳、AI 預覽、分析目標選擇 |
| Analysis | `/analysis/:runId` | Pipeline 狀態 + 完整結果儀表板（同一頁面，執行完後切換） |
| History | `/history` | 執行記錄列表，可點入查看或加入比較 |
| Compare | `/compare` | 版本並排比較 |

### 關鍵元件說明

**WorkflowPipeline.jsx**
- 六個 stage 的垂直列表
- 每個 stage：左側狀態指示燈（`done`=綠、`running`=藍閃、`pending`=灰）
- 執行中使用 `Framer Motion` 做閃爍動畫
- 每 2 秒 polling `GET /api/status/<runId>`（用 TanStack Query `refetchInterval`）

**WaveformChart.jsx**
- 使用 `react-plotly.js`
- X 軸為時間（ns），Y 軸為訊號值（0/1 或多位元）
- 每個訊號一條線，顏色固定（clk=藍、reset=綠、多位元=橘）
- 支援框選縮放、hover tooltip

**DependencyGraph.jsx**
- 使用 `D3.js` force-directed graph
- 節點為圓角矩形，顏色依層級區分（root=藍、mid=綠、leaf=紫）
- Critical path 節點加粗邊框
- 可拖曳節點、hover 顯示 module 詳情 tooltip

**AIInsightPanel.jsx**
- 使用 `EventSource` 連接 `GET /api/stream/<runId>`
- 文字逐字 append 到 state，呈現打字機效果
- 末端顯示閃爍游標（CSS animation）

**LogViewer.jsx**
- 固定高度區塊，overflow scroll
- 根據 log 內容套用語意顏色：
  - `[✓]` 或 `Passed` → 綠色
  - `Warning` → 橘色
  - `Error` / `error` → 紅色
  - 其他 → 灰色

### 前端 API 呼叫規範

使用 **TanStack Query** 管理所有 API 呼叫：

```javascript
// 範例：polling 執行狀態
const { data: status } = useQuery({
  queryKey: ['run-status', runId],
  queryFn: () => fetch(`/api/status/${runId}`).then(r => r.json()),
  refetchInterval: (data) => data?.overall === 'running' ? 2000 : false,
  enabled: !!runId,
})
```

開發時 Vite proxy 設定（`vite.config.js`）：
```javascript
server: {
  proxy: {
    '/api': 'http://localhost:5000'
  }
}
```

---

## UI 設計規範

### 設計風格

參考 Datadog / Grafana 的 Observability Platform 視覺語言。扁平、乾淨、工程感。**避免過於消費性 app 的圓潤風格。**

### 色彩語意系統

| 狀態 | 顏色 hex | Tailwind class | 使用情境 |
|------|----------|----------------|---------|
| 成功 / 通過 / 改善 | `#1D9E75` | `text-emerald-600` | 模擬通過、Slack 正值、指標改善 |
| 執行中 / 資訊 | `#378ADD` | `text-blue-500` | Running stage、AI 串流游標 |
| 警告 / 需注意 | `#EF9F27` | `text-amber-500` | Warning badge、Risk 中等 |
| 錯誤 / 退步 | `#E24B4A` | `text-red-500` | Error log、Slack 負值、指標退步 |
| 中性 / 待執行 | `#888780` | `text-gray-500` | Pending stage、次要文字 |

### 元件尺寸規範

- **Navbar 高度：** 40px，固定在頂部
- **Card：** 白色背景、`border border-gray-200`、`rounded-xl`、`p-3`
- **MetricCard：** `bg-gray-50`（無邊框）、`rounded-lg`、`p-3`
- **Badge / Chip：** `rounded-full`、`text-xs`、`px-2 py-0.5`
- **Workflow Stage 列：** 高度 36px，左側 8px 圓形指示燈

### 雙層資訊架構

Analysis 結果頁的頂部有兩個切換 Chip：

- **技術數字層：** 合成指標、波形圖、Dependency Graph（給 AE 使用）
- **AI 決策摘要層：** 自然語言分析、風險評分卡、優化建議（給 PM / SE）

兩層使用 React state 切換顯示，非真正的頁面跳轉。

---

## 開發環境設置

### Prerequisites

```bash
# Python 3.10+
python --version

# Node.js 18+
node --version

# EDA 工具（macOS 範例）
brew install icarus-verilog
brew install yosys

# EDA 工具（Ubuntu/Debian）
sudo apt-get install iverilog
sudo apt-get install yosys
```

### 後端安裝與啟動

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 設定環境變數
export ANTHROPIC_API_KEY="your-key-here"

# 啟動
python app.py
# Flask 跑在 http://localhost:5000
```

**requirements.txt 內容：**
```
flask==3.0.0
flask-cors==4.0.0
anthropic==0.25.0
pandas==2.2.0
networkx==3.2.0
vcdvcd==2.0.0
python-dotenv==1.0.0
```

### 前端安裝與啟動

```bash
cd frontend
npm install
npm run dev
# Vite 跑在 http://localhost:5173
```

### 驗證 EDA 工具是否可用

```bash
# 測試 Icarus Verilog
echo "module test; endmodule" > test.v
iverilog -o test.out test.v
echo $?  # 應該輸出 0

# 測試 Yosys
yosys -p "read_verilog test.v; stat"
```

---

## 開發準則

### Python 後端準則

1. **模組獨立性：** 每個 `.py` 模組應能獨立測試，不依賴其他模組的副作用
2. **統一錯誤格式：** 所有 API 端點的錯誤回應使用 `{"error": "message", "code": "ERROR_CODE"}`
3. **subprocess 安全：** 永遠使用 list 形式（`['iverilog', '-o', ...]`），不用 `shell=True`
4. **timeout 必填：** 所有 `subprocess.run()` 都要設 `timeout` 參數，避免掛死
5. **AI 回傳 JSON 解析：** 要做 try/except，AI 偶爾會回傳不符格式的內容
6. **run_id 使用 UUID：** `import uuid; run_id = str(uuid.uuid4())`
7. **暫存檔路徑：** 每個 run 建立獨立子目錄 `uploads/runs/<run_id>/`，執行結束後保留供查詢
8. **不要硬寫 API key：** 從環境變數讀取，`os.environ.get("ANTHROPIC_API_KEY")`
9. **Pipeline 背景執行：** `POST /api/run` 用 `threading.Thread` 執行，不 block response

### React 前端準則

1. **API 狀態統一用 TanStack Query 管理，** 不要自己手寫 `useState` + `useEffect` 做 fetch
2. **SSE 連線用 `useSSEStream.js` custom hook 封裝，** 統一管理連線開關
3. **顏色統一用 Tailwind class，** 不要 inline style 硬寫 hex（除了 Plotly / D3 的 config 物件）
4. **D3.js 整合進 React：** 用 `useRef` 取得 DOM 節點，在 `useEffect` 裡初始化 D3，記得在 cleanup 函式移除監聽器
5. **Plotly 用 `react-plotly.js`，** 不要直接操作 `Plotly` global

### AI Prompt 設計準則

1. **要求 JSON 輸出時，** 永遠加上「回傳純 JSON，不要任何 markdown backtick 或說明文字」
2. **給 AI 的 EDA 資料先做摘要，** 不要把幾百行 log 全塞進去——只取重要部分，`max 2000 chars`
3. **prompt 用 f-string 組合，** 但 JSON 部分用 `json.dumps()` 序列化，不要手工拼字串
4. **Streaming 端點中不要做 heavy computation，** AI streaming 期間後端只做 yield，解析工作在 streaming 結束後做

### 一般開發準則

1. **先讓 Python pipeline 跑通，再做前端** — 後端跑通才有意義的資料可以視覺化
2. **用 sample_verilog/ 裡的範例電路開發測試，** 確保 parser 能正確處理再接真實上傳
3. **SQLite 每次 app 啟動時自動建表（`CREATE TABLE IF NOT EXISTS`），** 不要要求手動初始化
4. **前後端分離，** 後端只回 JSON，不 render HTML（除了 SSE 的 text/event-stream）

---

## 開發步驟（建議順序）

### Phase 1 — Python Pipeline 骨架（Week 1）

**目標：** 讓一個 Verilog 檔案走完完整 pipeline，不需要前端，用 `curl` 或 Python script 測試。

**Step 1.1：** 建立專案目錄結構，設置 virtual environment，安裝 requirements.txt

**Step 1.2：** 實作 `verilog_parser.py`
- 先用 `sample_verilog/counter_4bit.v` 測試
- 確認能正確萃取 module name、ports、instantiations
- 寫一個 `if __name__ == "__main__":` 區塊直接測試

**Step 1.3：** 確認 Icarus Verilog 可用，實作 `workflow_engine.py` 的 simulate 部分
- `subprocess.run(['iverilog', ...])` → 確認能編譯
- `subprocess.run(['vvp', ...])` → 確認能產生 `.vcd` 檔

**Step 1.4：** 實作 `vcd_parser.py`
- 用 `vcdvcd` 讀取上一步產生的 `.vcd`
- 確認能取出訊號名稱與時序資料

**Step 1.5：** 確認 Yosys 可用，實作 `workflow_engine.py` 的 synthesize 部分
- 執行 `yosys` stat 指令 → 確認能取得 cell count

**Step 1.6：** 實作 `report_parser.py`
- 用 `re` 解析 Yosys 輸出，取出 cell count 等指標

**Step 1.7：** 實作 `dependency_analyzer.py`
- 用 `verilog_parser` 的結果建立 networkx DAG
- 確認 `topological_sort` 和 `dag_longest_path` 可用

**Step 1.8：** 實作 `db_manager.py`
- 建立 SQLite 資料表
- 測試 CRUD 操作

**Step 1.9：** 實作 `app.py` 基礎版本
- `POST /api/upload` → 呼叫 `verilog_parser`
- `POST /api/run` → 執行完整 pipeline（同步版，先不做背景執行）
- `GET /api/result/<run_id>` → 回傳結果
- 用 `curl` 測試這三個端點

### Phase 2 — AI 分析引擎（Week 2）

**Step 2.1：** 設定 `ANTHROPIC_API_KEY`，測試 `anthropic` SDK 基本呼叫

**Step 2.2：** 實作 `ai_engine.py` — `verilog_insight()`（串流版本）
- 確認 streaming 輸出正常，前端 SSE 能接到

**Step 2.3：** 實作 `ai_engine.py` — `debug_advisor()`
- 測試：故意傳一個有 syntax error 的 Verilog，確認 AI 能給出修正建議

**Step 2.4：** 實作 `ai_engine.py` — `log_insight()` 和 `risk_analyzer()`

**Step 2.5：** 實作 `ai_engine.py` — `bottleneck_detector()`

**Step 2.6：** 實作 Flask SSE 串流端點 `GET /api/stream/<run_id>`
- 讓 `ai_engine` 的 streaming 輸出透過 SSE 推送

**Step 2.7：** 將 `/api/run` 改為背景執行（`threading.Thread`）
- 實作 `GET /api/status/<run_id>` 端點
- 測試 polling 機制

**Step 2.8：** 實作 `GET /api/history` 和 `POST /api/compare`

**Step 2.9（進階，MVP 完成後）：** 實作 `ai_engine.py` — `workflow_planner()`
- 確認能回傳有效 JSON（加 validation 和 fallback 錯誤處理）
- 整合進 `/api/run`，加入 `USE_FIXED_PIPELINE` 環境變數開關切換

### Phase 3 — React 前端（Week 3）

**Step 3.1：** 初始化 Vite + React 專案，安裝所有 npm 套件，設定 Tailwind CSS 和 Vite proxy

**Step 3.2：** 實作 `Navbar.jsx` 和 React Router 四頁路由骨架

**Step 3.3：** 實作 `Upload.jsx`
- 拖曳上傳區（可先用 `<input type="file">`）
- 上傳後顯示 AI 預解析結果卡

**Step 3.4：** 實作 `WorkflowPipeline.jsx`
- 六個 stage 靜態版本，確認樣式
- 接上 TanStack Query polling `GET /api/status`

**Step 3.5：** 實作 `LogViewer.jsx` 和 `AIInsightPanel.jsx`（SSE 串流）

**Step 3.6：** 實作 `WaveformChart.jsx`（react-plotly.js）

**Step 3.7：** 實作 `DependencyGraph.jsx`（D3.js）

**Step 3.8：** 實作 `MetricCard.jsx` 和 `RiskPanel.jsx`

**Step 3.9：** 組合 `Analysis.jsx`（pipeline 狀態 + 完整儀表板切換）

**Step 3.10：** 實作 `History.jsx` 和 `Compare.jsx`

**Step 3.11：** 加上 Framer Motion 動畫，調整整體 UI/UX，準備 Demo

---

## 範例 Verilog 電路（測試用）

以下是 `sample_verilog/counter_4bit.v` 的內容，用來開發測試：

```verilog
module counter_4bit (
    input clk,
    input reset,
    input enable,
    output reg [3:0] count
);

always @(posedge clk) begin
    if (reset)
        count <= 4'b0000;
    else if (enable)
        count <= count + 1;
end

endmodule
```

對應 testbench `sample_verilog/counter_tb.v`：

```verilog
module counter_tb;
    reg clk, reset, enable;
    wire [3:0] count;

    counter_4bit uut (
        .clk(clk),
        .reset(reset),
        .enable(enable),
        .count(count)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    initial begin
        $dumpfile("counter.vcd");
        $dumpvars(0, counter_tb);
        reset = 1; enable = 0;
        #20 reset = 0; enable = 1;
        #100;
        $finish;
    end
endmodule
```

---

## 常見問題與注意事項

### Yosys 輸出格式

Yosys 的 `stat` 指令輸出格式可能因版本略有不同，建議用以下方式萃取 cell count：

```python
import re

def parse_cell_count(yosys_output: str) -> int:
    # 匹配 "Number of cells: 47" 這種格式
    match = re.search(r'Number of cells:\s+(\d+)', yosys_output)
    if match:
        return int(match.group(1))
    return 0
```

### VCD 檔案可能沒有 dumpvars

若使用者的 Verilog testbench 沒有 `$dumpfile` 和 `$dumpvars`，模擬不會產生 VCD。`workflow_engine.py` 需要：
1. 先用 `verilog_parser.py` 判斷是否有 testbench 模組
2. 若沒有，自動生成一個基礎 testbench 並加入 dumpfile 指令
3. 若有，檢查是否有 `$dumpfile`，沒有則在輸出中提示使用者

### Anthropic API Rate Limit

開發測試時避免每次存檔都自動觸發 AI 分析，建議：
- 開發 Phase 1 時先用 mock AI 回傳（硬寫假 JSON）
- Phase 2 再接真實 API
- 可加一個環境變數 `USE_MOCK_AI=true` 切換

### Windows 相容性

若在 Windows 開發，`subprocess` 呼叫 EDA 工具需注意：
- 路徑使用 `os.path.join()` 而非 hardcode `/`
- 建議使用 WSL2 開發，避免 Windows 路徑問題

---

*文件版本：v2.0 | 2025 年 6 月*
*對應規劃書版本：v5.0*
