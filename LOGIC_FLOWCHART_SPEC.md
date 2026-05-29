# Logic Flowchart — 功能開發設計規格

> 版本：v1.0 | 2026-05-30
> 狀態：待實作
> 所屬功能區：Analysis 頁面 → Technical View

---

## 1. 功能定位

將 Verilog `always` block 的 if/else 邏輯自動轉換成**互動式流程圖**，讓非工程師（AE、SE、EDA PM）不需要看懂程式碼，也能理解電路的行為邏輯。

**輸入範例（counter_4bit.v）：**
```verilog
always @(posedge clk) begin
    if (reset)
        count <= 4'b0000;
    else if (enable)
        count <= count + 1;
end
```

**輸出：** 互動式流程圖，顯示每個 clock 觸發後，電路在不同條件下會做什麼。

**不依賴 AI**：全部基於靜態 Verilog 語法解析，不呼叫 Anthropic API。

---

## 2. 技術選型

| 項目 | 選擇 | 理由 |
|------|------|------|
| Flowchart 渲染 | `@xyflow/react` (ReactFlow v12) | 原生支援自訂 node 形狀、drag/zoom/pan、TypeScript 型別完整 |
| 自動排版 | `@dagrejs/dagre` | 計算 top-down DAG layout，ReactFlow 官方搭配方案 |
| Backend 解析 | Python `re` 模組 | 與現有 `verilog_parser.py` 保持一致，不加新套件 |

**新增 npm 套件（2個）：**
```
@xyflow/react
@dagrejs/dagre
```

---

## 3. 資料結構設計

### 3.1 Backend 輸出 JSON

`GET /api/result/<run_id>` 新增欄位 `flowchart`：

```json
{
  "always_blocks": [
    {
      "id": "ab_0",
      "trigger": "posedge clk",
      "trigger_type": "sequential",
      "nodes": [
        { "id": "ab_0_start",  "type": "trigger",  "label": "posedge clk"        },
        { "id": "ab_0_c0",     "type": "decision", "label": "reset"               },
        { "id": "ab_0_c0_yes", "type": "process",  "label": "count ← 0"          },
        { "id": "ab_0_c1",     "type": "decision", "label": "enable"              },
        { "id": "ab_0_c1_yes", "type": "process",  "label": "count ← count + 1"  },
        { "id": "ab_0_c1_no",  "type": "process",  "label": "(hold)"              }
      ],
      "edges": [
        { "id": "e0", "source": "ab_0_start",  "target": "ab_0_c0"              },
        { "id": "e1", "source": "ab_0_c0",     "target": "ab_0_c0_yes", "label": "YES" },
        { "id": "e2", "source": "ab_0_c0",     "target": "ab_0_c1",     "label": "NO"  },
        { "id": "e3", "source": "ab_0_c1",     "target": "ab_0_c1_yes", "label": "YES" },
        { "id": "e4", "source": "ab_0_c1",     "target": "ab_0_c1_no",  "label": "NO"  }
      ]
    }
  ],
  "assign_blocks": [
    {
      "id": "as_0",
      "output": "sum",
      "expression": "a + b"
    }
  ]
}
```

### 3.2 TypeScript 型別（新增至 `src/types/index.ts`）

```typescript
export type FlowNodeType = 'trigger' | 'decision' | 'process'

export interface FlowNode {
  id: string
  type: FlowNodeType
  label: string
}

export interface FlowEdge {
  id: string
  source: string
  target: string
  label?: string  // "YES" | "NO" | undefined
}

export interface AlwaysBlock {
  id: string
  trigger: string
  trigger_type: 'sequential' | 'combinational'
  nodes: FlowNode[]
  edges: FlowEdge[]
}

export interface AssignBlock {
  id: string
  output: string
  expression: string
}

export interface FlowchartData {
  always_blocks: AlwaysBlock[]
  assign_blocks: AssignBlock[]
}
```

`AnalysisResult` 介面新增一個 key：
```typescript
export interface AnalysisResult {
  // ...現有欄位不變...
  flowchart: FlowchartData | null
}
```

---

## 4. Backend 設計

### 4.1 新建 `backend/flowchart_extractor.py`

**對外 API：**
```python
def extract_flowchart(verilog_content: str) -> dict:
    """
    輸入 Verilog 原始碼，回傳 flowchart_data dict。
    不依賴外部工具，純 Python re 實作。
    """
```

**解析流程：**

```
verilog_content
    │
    ▼
_strip_comments()         ← 移除 // 和 /* */ 註解
    │
    ▼
_find_always_blocks()     ← regex 找出所有 always...end 區塊
    │
    ├─▶ 每個 always block
    │       │
    │       ▼
    │   _parse_trigger()  ← 取出 "posedge clk" / "*" 等觸發條件
    │       │
    │       ▼
    │   _parse_body()     ← 遞迴解析 if/else chain，回傳 (nodes, edges)
    │
    ▼
_find_assign_stmts()      ← 找 "assign out = expr;" 語句
    │
    ▼
回傳 { "always_blocks": [...], "assign_blocks": [...] }
```

**`_parse_body()` 遞迴邏輯（核心演算法）：**

```python
def _parse_body(body: str, prefix: str, counter: list) -> tuple[list, list, str]:
    """
    遞迴解析 always block body。
    counter 是 [int]，作為全域 id 計數器（mutable list pass-by-reference）。
    回傳 (nodes, edges, entry_node_id)。
    """
    body = body.strip().lstrip('begin').rstrip('end').strip()

    # Case 1: if (cond) ... [else if ...] [else ...]
    if_match = re.match(r'if\s*\((.+?)\)\s*(begin\b[\s\S]*?end\b|[^;]+;)\s*(.*)', body, re.DOTALL)
    if if_match:
        cond = if_match.group(1).strip()
        then_body = if_match.group(2)
        rest = if_match.group(3).strip()
        # 建立 decision node → 遞迴解析 then branch → 遞迴解析 else/else-if branch
        ...

    # Case 2: case (expr) ... endcase
    case_match = re.match(r'case\s*\((.+?)\)([\s\S]*?)endcase', body)
    if case_match:
        # 最多展開 4 個 case arm，超過合併為 "..." node
        ...

    # Case 3: assignment (count <= ...; 或 count = ...;)
    assign_match = re.match(r'(\w+)\s*(?:<=|=)\s*(.+?);', body.strip())
    if assign_match:
        ...

    # Fallback: 無法解析 → 顯示原始程式碼前 60 字元
    ...
```

**節點 id 命名規則：**
- Trigger：`ab_{block_idx}_start`
- Decision：`ab_{block_idx}_c{counter}`
- Process（YES branch）：`ab_{block_idx}_p{counter}_yes`
- Process（NO/else branch）：`ab_{block_idx}_p{counter}_no`
- Assign：`as_{assign_idx}`

### 4.2 修改 `backend/app.py`

在 `GET /api/result/<run_id>` 加入 `flowchart` 欄位，**即時計算**（不增加 DB 欄位）：

```python
from flowchart_extractor import extract_flowchart

@app.route("/api/result/<run_id>", methods=["GET"])
def get_result(run_id: str):
    run = db_manager.get_run(run_id)
    # ...現有邏輯...

    flowchart = None
    verilog_content = run.get("verilog_content")
    if verilog_content:
        try:
            flowchart = extract_flowchart(verilog_content)
        except Exception:
            flowchart = None

    return jsonify({
        # ...現有欄位...
        "flowchart": flowchart,
    })
```

> **不需要新增 DB 欄位**。flowchart 由 verilog_content 即時推導，解析時間 < 10ms。

---

## 5. Frontend 設計

### 5.1 視覺規格

本元件的設計語言**完全對齊**專案現有設計系統（Datadog/Grafana 工程感）：

#### Node 樣式

| Node Type | 用途 | 形狀 | 背景色 | 邊框色 | 文字色 | 字體 |
|-----------|------|------|--------|--------|--------|------|
| `trigger` | `always @(posedge clk)` 等觸發條件 | 圓角膠囊（`border-radius: 999px`） | `#378ADD` (blue) | `#2563eb` | `#ffffff` | Poppins 500 |
| `decision` | `if (cond)` 判斷條件 | 菱形（CSS rotate 45deg） | `rgba(239, 159, 39, 0.12)` | `#EF9F27` | `#0f1012` | Poppins 500 |
| `process` | Assignment（`count <= 0`） | 圓角矩形（`border-radius: 8px`） | `rgba(29, 158, 117, 0.1)` | `rgba(29, 158, 117, 0.4)` | `#0f1012` | Roboto mono 0.82rem |

> **設計原則**：Node 背景使用語意色的 10-12% 透明度，邊框使用語意色本體，與專案其他 card 的 `rgba(0,0,0,0.09)` 邊框風格一致，不突兀。

#### Edge 樣式

| Edge 類型 | 顏色 | 粗細 | Label 背景 |
|-----------|------|------|------------|
| 預設（無 label） | `#d1d5db` (gray-300) | 1.5px | — |
| YES branch | `#1D9E75` (emerald) | 1.5px | `rgba(29,158,117,0.08)` |
| NO branch | `#9ca3af` (gray-400) | 1.5px | `rgba(0,0,0,0.04)` |

Edge label 字體：Poppins 0.68rem，font-weight 600，letter-spacing 0.5px，全大寫。

#### Assign Block 區域

獨立 section，**不使用 ReactFlow**，用純 HTML card 排列：

```
┌ Combinational Logic ─────────────────────────┐
│  ┌──────────────────────┐  ┌────────────────┐ │
│  │  assign              │  │  assign        │ │
│  │  sum = a + b         │  │  out = sel?a:b │ │
│  └──────────────────────┘  └────────────────┘ │
└──────────────────────────────────────────────┘
```

樣式：`metric-card` class（`background: rgba(0,0,0,0.025)`, `border: 1px solid rgba(0,0,0,0.09)`, `border-radius: 12px`），左側加一條 3px emerald 色 left-border 作為視覺區分。

#### 容器樣式

- 容器高度：`420px`（固定高，ReactFlow 要求明確高度）
- 背景：`rgba(0,0,0,0.018)` （與 `goal-option` 背景一致）
- 邊框：`1px solid rgba(0,0,0,0.09)`
- 圓角：`12px`
- ReactFlow 內建控制列（zoom in/out、fit view）：保留，樣式覆寫為白色背景、`var(--soft-border-color)` 邊框

#### 多 always block Tab

有多個 always block 時，使用**現有的 `segmented` 元件**切換：

```
[ posedge clk ]  [ always * ]
```

Tab label 直接顯示 trigger 字串（如 `posedge clk`）。

### 5.2 元件結構

**新建 `frontend/src/components/LogicFlowchart.tsx`：**

```
LogicFlowchart (props: { data: FlowchartData | null })
├── 空狀態處理（data 為 null 或 always_blocks 為空）
├── Tab 選擇器（segmented，多 always block 才顯示）
├── ReactFlow 容器（高度 420px）
│   ├── TriggerNode（custom node）
│   ├── DiamondNode（custom node）
│   ├── ProcessNode（custom node）
│   └── LabeledEdge（custom edge，顯示 YES/NO label）
└── Assign Block Section（純 HTML，always_blocks 下方）
```

**DiamondNode 關鍵實作（CSS 旋轉法）：**

```tsx
// 外層正方形 rotate 45deg → 看起來是菱形
// 內層文字 rotate -45deg → 文字維持水平
function DiamondNode({ data }: { data: { label: string } }) {
  return (
    <>
      <Handle type="target" position={Position.Top} />
      <div style={{
        width: 88,
        height: 88,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transform: 'rotate(45deg)',
        background: 'rgba(239, 159, 39, 0.12)',
        border: '1.5px solid #EF9F27',
        borderRadius: 6,
      }}>
        <span style={{
          transform: 'rotate(-45deg)',
          fontSize: '0.75rem',
          fontFamily: 'var(--nav-font)',
          fontWeight: 600,
          color: '#0f1012',
          textAlign: 'center',
          maxWidth: 68,
          lineHeight: 1.3,
        }}>
          {data.label}
        </span>
      </div>
      <Handle type="source" position={Position.Bottom} id="yes" />
      <Handle type="source" position={Position.Right} id="no" />
    </>
  )
}
```

**dagre 排版函式：**

```typescript
import dagre from '@dagrejs/dagre'
import type { Node, Edge } from '@xyflow/react'

const NODE_WIDTH = { trigger: 160, decision: 88, process: 160 }
const NODE_HEIGHT = { trigger: 36, decision: 88, process: 44 }

function applyDagreLayout(nodes: Node[], edges: Edge[]): { nodes: Node[], edges: Edge[] } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'TB', ranksep: 56, nodesep: 36 })

  nodes.forEach((n) => {
    const type = n.type as keyof typeof NODE_WIDTH
    g.setNode(n.id, { width: NODE_WIDTH[type] ?? 140, height: NODE_HEIGHT[type] ?? 44 })
  })
  edges.forEach((e) => g.setEdge(e.source, e.target))

  dagre.layout(g)

  return {
    nodes: nodes.map((n) => {
      const pos = g.node(n.id)
      return { ...n, position: { x: pos.x - (NODE_WIDTH[n.type as keyof typeof NODE_WIDTH] ?? 140) / 2, y: pos.y } }
    }),
    edges,
  }
}
```

### 5.3 整合至 `Analysis.tsx`

在 Tech View 的 `Dependency Graph` section **下方**新增 Logic Flowchart section：

```tsx
{/* 現有 Dependency Graph section 保留不動 */}

{/* 新增 Logic Flowchart section */}
{isDone && (
  <section className="surface-card panel">
    <h2 className="panel-title">Logic Flowchart</h2>
    {result?.flowchart
      ? <LogicFlowchart data={result.flowchart} />
      : <p className="text-sm text-black/45">No flowchart data available for this design.</p>
    }
  </section>
)}
```

---

## 6. 解析能力邊界

| Verilog pattern | 處理方式 |
|-----------------|---------|
| `if / else if / else` chain | 完整支援，遞迴解析 |
| `case / casez` 語句 | 展開最多 4 個 case arm，超過合併為 `(n more cases...)` node |
| 巢狀 if（深度 > 4） | 第 5 層以下合併為單一 `[...]` process node |
| `assign` 語句 | 顯示為 Combinational Logic section，不進入 ReactFlow |
| `for` / `while` loop | 顯示為 `[loop: ...]` process node，不展開 |
| 複雜運算式（三元、位元運算） | 原始字串截斷至 48 字元後顯示，加 `...` |
| 多個 always block | Tab 切換顯示，最多 5 個 Tab（超過僅顯示前 5 個） |
| 解析完全失敗 | fallback 到 `{ "error": true, "message": "..." }`，前端顯示 inline error hint |

---

## 7. 空狀態規格

| 情境 | 顯示內容 |
|------|---------|
| pipeline 尚未完成 | 整個 section 不顯示（`isDone` 為 false） |
| 純組合邏輯設計（只有 assign，無 always） | 顯示 Combinational Logic section，ReactFlow 區域隱藏 |
| 完全空設計（無 always 也無 assign） | `text-sm text-black/45`：`"No logic blocks found in this design."` |
| 後端解析失敗 | `text-sm text-red-500`：`"Could not parse logic structure."` |

---

## 8. 修改檔案清單

| 動作 | 檔案 | 說明 |
|------|------|------|
| **新建** | `backend/flowchart_extractor.py` | Verilog always block 解析器 |
| **修改** | `backend/app.py` | `/api/result` 回傳加 `flowchart` key |
| **新建** | `frontend/src/components/LogicFlowchart.tsx` | ReactFlow 渲染元件 |
| **修改** | `frontend/src/types/index.ts` | 新增 `FlowchartData`、`AlwaysBlock`、`FlowNode`、`FlowEdge`、`AssignBlock` 型別；`AnalysisResult` 加 `flowchart` 欄位 |
| **修改** | `frontend/src/pages/Analysis.tsx` | Tech View 加入 Logic Flowchart section |
| **修改** | `frontend/package.json` | 加入 `@xyflow/react`、`@dagrejs/dagre` |

---

## 9. 實作順序

```
Step 1  npm install @xyflow/react @dagrejs/dagre
Step 2  types/index.ts — 新增 FlowchartData 等型別
Step 3  flowchart_extractor.py — 先跑通 counter_4bit.v 的 if/else 解析
Step 4  用 Python script 直接測試輸出 JSON（不啟動 Flask）
Step 5  app.py — result 端點加 flowchart key，curl 驗證回傳格式
Step 6  LogicFlowchart.tsx — 先用 hardcode JSON 驗證三種 node 樣式
Step 7  接上 dagre 排版，確認 layout 正確
Step 8  Analysis.tsx — 整合，接上真實 API 資料
Step 9  edge case 測試：adder_8bit.v（assign-only）、多模組設計
```

---

## 10. 未來擴充（MVP 完成後）

- **AI 標籤加強**：每個 decision node 的 condition 由 AI 翻譯成自然語言（`reset` → `Reset signal is high`）
- **FSM 偵測**：若解析到 `state`、`next_state` 等慣用命名，自動切換成 State Machine Diagram 視圖
- **Export**：下載 flowchart 為 SVG/PNG（ReactFlow 原生支援）

---

## 11. 再檢視筆記：正確性與受眾適配優化

> 檢視日期：2026-05-30
> 檢視角度：TA + 目標使用者（非 RTL 工程師），包含 AE、SE、EDA PM。

### 11.1 P0 - 正確性 / 信任度問題

1. **Flowchart 應使用完整上傳設計，而不是只使用 main file**
   - 目前 API 儲存的 `verilog_content` 來自被選為 main file 的檔案，但 `parse_verilog()` 使用的是所有上傳 `.v` 檔合併後的 `all_content`。
   - 風險：若使用者上傳多個 RTL 檔，module graph 與 parser result 可能反映全部檔案，但 Logic Flowchart 只反映其中一個檔案。
   - 建議：DB 儲存 `all_content`，或新增 `design_content` 欄位給所有衍生分析使用。Parser、Dependency Graph、Flowchart 應使用同一份 source text。

2. **不要只把省略資訊藏在 label 裡，應明確提供 truncation metadata**
   - 目前限制包含：最多 5 個 always block、case 最多顯示 4 個 branch、nested logic 深度限制、label 字數限制。
   - 風險：AE / SE / PM 可能以為圖是完整邏輯，而不知道它其實是摘要。
   - 建議 JSON 增加：
     ```json
     {
       "truncated": true,
       "truncation_reason": "case_arm_limit",
       "hidden_count": 5
     }
     ```
   - UI 建議在 graph title 或 collapsed node 旁顯示提示，例如：`摘要視圖：尚有 5 個分支未展開`。

3. **Sequence edge 要保留語意，避免誤導分支行為**
   - 目前 sequence parsing 可以把前一段 process 接到下一段 `case/if`，這對 `assignment -> case` 很有用。
   - 風險：在 nested if/else 場景中，若把多個 terminal branch 都接到下一段，視覺上可能暗示兩個分支都一定會繼續執行相同流程，但 RTL 語意未必如此。
   - 建議：edge 增加 metadata，例如 `kind: "sequence" | "branch" | "summary"`，並用較細或虛線呈現 sequence / summary edge。除非 parser 能確認後續 statement 對所有 branch 都成立，否則不要任意合併 branch exit。

4. **補強單行 if/else、巢狀 begin/end 的 regression tests**
   - 需要鎖住的模式：
     - `if (cond) a <= b; else a <= c;`
     - `if (cond) begin ... end else begin ... end`
     - `case (state)` branch 內含 `assignment + if`
     - assignment 內含 ternary operator，例如 `a <= sel ? b : c;`
   - 測試建議檢查 graph shape，不要依賴完整 JSON 順序，避免 layout 或 id 微調造成脆弱測試。

5. **支援 SystemVerilog always block，或明確標示不支援**
   - 常見 RTL 可能使用 `always_ff @(posedge clk)`、`always_comb`、`always_latch`。
   - 建議行為：
     - 支援解析 `always_ff`、`always_comb`、`always_latch`
     - 或在 UI 顯示 `目前尚未支援 SystemVerilog always_* block`，避免使用者以為沒有邏輯。

### 11.2 P1 - 針對 AE / SE / EDA PM 的可理解性優化

1. **在圖上方加入自然語言摘要**
   - 非工程師通常需要先知道「這段邏輯在做什麼」，再看 Verilog 層級的流程。
   - 範例：
     - `此 sequential block 由 clk 觸發。reset 時回到 IDLE；否則 FSM 會根據 baud_tick 在 START、DATA、STOP 狀態間前進。`
   - 可先用 rule-based 方式產生摘要，未來再升級成 AI explanation。

2. **在保留 RTL 原文的同時，加入比較友善的主標籤**
   - 目前 `case(state)`、`rst`、`baud_tick`、`bit_cnt == 3'd7` 很精準，但對 AE / SE / PM 偏硬。
   - 建議顯示格式：
     - 主標籤：`Reset 是否啟動？`
     - 副標籤：`rst`
     - 主標籤：`目前 FSM 狀態`
     - 副標籤：`case(state)`
   - 原始 RTL 仍要保留，方便工程師確認正確性。

3. **加入 legend 與 confidence indicator**
   - 建議 legend：
     - 藍色 pill = clock / trigger event
     - 黃色菱形 = condition 或 state branch
     - 綠色方塊 = signal update
     - 虛線 edge = summary 或 inferred continuation
   - 建議 confidence state：
     - `Complete`
     - `Summarized`
     - `Partial parse`
   - 目的：讓 PM / SE 知道這張圖是完整解析、摘要，還是部分解析，避免過度相信不完整圖。

4. **Tab 不只顯示 trigger，應顯示 block purpose**
   - 目前 tab 使用 `posedge clk`、`always @(*)`，當多個 block 有同樣 trigger 時不易辨識。
   - 建議 tab label：
     - `FSM: state register`
     - `Output decode`
     - `ALU operation select`
     - fallback：`Block 1 - posedge clk`
   - 可用 assigned signal、case expression、output port 來推測用途。

5. **每個 block 加上 signal impact summary**
   - 對 AE / SE / PM 而言，「哪些 signal 會被改變？」通常比完整控制流程更重要。
   - 建議 block metadata：
     ```json
     {
       "assigned_signals": ["state", "timer", "tx_busy"],
       "condition_signals": ["rst", "baud_tick", "tx_valid"],
       "block_role": "fsm"
     }
     ```
   - UI 可在 graph 上方顯示 chips：`Updates: state, timer`、`Controlled by: rst, baud_tick`。

### 11.3 P2 - 產品展示 / Demo 加分項

1. **FSM view 獨立成一種模式**
   - 如果偵測到 `case(state)` 與 `state <= NEXT_STATE` 這類 pattern，可額外產生 `state_diagram`。
   - 對非 RTL 使用者來說，State Diagram 通常比 procedural flowchart 更直覺，也很適合 demo。

2. **Click-to-source mapping**
   - node 增加 `source_line_start`、`source_line_end`。
   - UI 行為：點擊 flowchart node 時，在 side panel highlight 對應 Verilog 片段。
   - 好處：工程師可 audit，非工程師也能把圖和 source code 對起來。

3. **Export / share**
   - 支援 PNG / SVG 匯出。
   - AE / SE / PM 常需要把設計行為放進簡報、issue tracker 或客戶說明文件。

4. **大型設計的 search / filter**
   - 加入 signal name、block role、trigger type filter。
   - 範例：搜尋 `reset`，只顯示和 reset 行為相關的 block / node。

5. **清理 mojibake，統一 UTF-8 可讀文字**
   - 目前 `LOGIC_FLOWCHART_SPEC.md`、`backend/flowchart_extractor.py`、`frontend/src/components/LogicFlowchart.tsx` 中有部分中文在 PowerShell output 顯示為亂碼。
   - 不一定影響 runtime，但會影響 TA 閱讀、維護性與專案專業度。
   - 建議：將 spec 和程式註解重新整理為乾淨 UTF-8，可用中文或英文，但要一致且可讀。

### 11.4 建議驗收測試

Backend 最低 regression cases：

1. `counter_4bit.v`
   - 預期有 reset decision、enable decision、reset assignment、increment assignment。
2. `adder_8bit.v`
   - 預期沒有 always block，且有一個 `{cout, sum}` 的 assign block。
3. `alu_8bit.v`
   - 預期有 `case(op)`，且至少顯示 `OP_ADD`、`OP_SUB`、`OP_AND`、`OP_OR` branch label。
4. `traffic_light.v`
   - 預期有 `case(state)`，且 state branch 包含 `S_RED`、`S_GREEN`、`S_YELLOW`、`default`。
5. `uart_tx.v`
   - 預期 `baud_cnt` process 後面接 `case(state)`，且內層 decision 包含 `tx_valid`、`baud_tick`、`bit_cnt == 3'd7`。
6. inline if/else fixture
   - 預期產生一個 decision node，並有明確 YES / NO assignment branch。

Frontend 最低檢查：

1. case branch 不應出現 ReactFlow missing-handle warning。
2. 長 label 不應超出 decision diamond 或 process node。
3. 若 graph 是摘要或部分解析，UI 必須明確顯示 `Summarized` / `Partial parse` 類提示。
