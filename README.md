# VeriFlow Insight

VeriFlow Insight 是一個面向 EDA 產業非開發者角色的 AI-first Workflow Observability Platform，主要服務 AE、SE、EDA PM 等需要理解設計流程與風險、但不一定直接撰寫工具腳本或閱讀大量 EDA log 的使用者。使用者只要上傳 Verilog 程式碼，系統就會自動執行完整 EDA pipeline，並透過 AI 分析結果與互動式視覺化儀表板呈現 workflow 狀態、設計風險與工程決策線索。

[Live Demo](https://drive.google.com/file/d/13HH7IjGilpuVEDFrNM3KG7JgeTEpLWx1/view?usp=sharing)

### 系統定位

本系統定位為 **AI-first Workflow Observability Platform for EDA**。不是完整商用 EDA 工具，也不是單純的語法檢查器，而是一個為 EDA 產業非開發者角色設計的工作流觀測平台：讓使用者不需要讀懂 EDA log 或工具指令，也能理解 workflow 狀態、掌握設計風險，並做出工程決策。

- 對 Verilog 原始碼做 module、port、signal、logic type 與 instantiation 解析。
- 透過 heuristic lint 找出部分可疑訊號或風格問題。
- 使用 Icarus Verilog 編譯並執行 testbench，擷取 simulation 狀態與 VCD 統計資訊。
- 使用 Yosys synthesis，取得 cell count、wire count、flip-flop count 與面積等級估計。
- 建立 module dependency graph 與 flowchart，輔助理解設計結構。
- 將每次分析保存為 run，可在 History 查詢，也可在 Compare 比較兩次分析結果。
- 使用 AI provider 或 mock AI 產生 log insight、risk score、bottleneck analysis 與 compare tradeoff。

### 價值主張

VeriFlow Insight 的核心價值主張是解決現有 EDA 工具鏈的「黑盒問題」。把分散的 EDA 指令、log、波形與合成數據整理成一個連續的觀測流程：使用者上傳一段 Verilog 程式碼後，系統自動完成解析、lint、simulation、synthesis、dependency analysis 與 AI report，並以互動視覺化儀表板呈現結果。整個過程不要求使用者懂任何 EDA 工具指令，也能快速比較不同 Verilog 版本的結構、simulation 狀態、synthesis 指標與設計風險。

### Python 在本專案的角色

Python 是整個系統的核心語言，負責 EDA 工具控制、資料解析、AI 分析引擎、全部業務邏輯與 API 服務：

- 使用 Flask 提供 REST API 與 Server-Sent Events。
- 管理上傳檔案、run 目錄、SQLite 資料庫與 stage logs。
- 呼叫 Icarus Verilog 的 `iverilog`、`vvp` 與 Yosys 的 `yosys`。
- 解析 Verilog、VCD、Yosys JSON/report，並轉成前端可視化資料。
- 管理 pipeline stage，包括 parse、lint、simulation、dependency、synthesis、AI report。
- 封裝 Anthropic Claude 或 Google Gemini API，並提供 mock AI 模式讓沒有 API key 的環境也能 demo。

## 功能

- 多檔 `.v` 上傳：可同時上傳 design file 與 testbench。
- Verilog 靜態解析：module、port、signal、logic type、module instantiation。
- Lint 檢查：目前以 heuristic 方式偵測部分 unused wire/reg 類型問題。
- Simulation：使用 Icarus Verilog 編譯所有上傳的 `.v`，再用 `vvp` 執行。
- Waveform 統計：讀取 simulation 產生的 VCD，供前端顯示波形資訊。
- Synthesis：使用 Yosys 讀取 design files，輸出 synthesis JSON 並解析 PPA 類指標。
- Dependency graph 與 flowchart：呈現 RTL module 關係與控制流程摘要。
- AI insight：產生 log 摘要、risk score、bottleneck analysis 與版本比較文字。
- History：保存每次 run 的狀態與主要指標。
- Compare：比較兩個 run 的 simulation、warning、cell、wire、flip-flop 等差異。

## 技術架構

```text
eda-insight/
├─ backend/
│  ├─ app.py                         # Flask application factory 與健康檢查
│  ├─ config.py                      # port、CORS、AI provider、pipeline 與資料路徑設定
│  ├─ db_manager.py                  # SQLite runs 與 stage_logs 管理
│  ├─ requirements.txt               # Python 套件
│  ├─ routes/
│  │  ├─ upload.py                   # upload、run、status、delete run
│  │  ├─ analysis.py                 # result、logs
│  │  ├─ history.py                  # history
│  │  ├─ compare.py                  # compare
│  │  └─ ai.py                       # SSE AI stream
│  ├─ services/
│  │  ├─ workflow_service.py         # pipeline orchestration
│  │  ├─ parser_service.py           # parse 與 flowchart stage
│  │  ├─ lint_service.py             # lint stage
│  │  ├─ simulation_service.py       # simulation stage
│  │  ├─ synthesis_service.py        # synthesis stage
│  │  └─ ai_service.py               # Anthropic/Gemini/mock AI wrapper
│  ├─ eda_tools/
│  │  ├─ verilog_parser.py           # Verilog parser
│  │  ├─ iverilog_runner.py          # iverilog/vvp subprocess wrapper
│  │  ├─ yosys_runner.py             # Yosys subprocess wrapper 與 report parser
│  │  ├─ vcd_parser.py               # VCD parser
│  │  └─ flowchart_extractor.py      # flowchart extraction
│  └─ utils/                         # file、log、json、graph helpers
├─ frontend/
│  ├─ package.json                   # React/Vite scripts 與前端依賴
│  ├─ vite.config.ts                 # Vite dev server 與 /api proxy
│  └─ src/
│     ├─ App.tsx                     # routes: Upload, Analysis, History, Compare
│     ├─ pages/                      # page views
│     ├─ components/                 # pipeline、waveform、graph、log、AI panels
│     ├─ hooks/                      # run status polling 與 SSE stream
│     └─ types/                      # TypeScript shared types
├─ sample_verilog/
│  ├─ 01_adder_8bit/
│  ├─ 02_counter_4bit/
│  ├─ 03_alu_8bit_v1/
│  ├─ 04_alu_8bit_v2/
│  ├─ 05_traffic_light_fsm/
│  ├─ 06_uart_tx/
│  ├─ 07_pulse_stretcher_v1/
│  ├─ 08_pulse_stretcher_v2/
│  ├─ 09_broken_adder/
│  ├─ 10_incomplete_assign/
│  └─ 11_bad_style_mix/
└─ README.md
```

## 執行需求

### 必要環境

- Python 3.10 以上
- Node.js 18 以上
- npm
- Icarus Verilog：需要 `iverilog` 與 `vvp`
- Yosys：需要 `yosys`

Windows 使用者可以透過 OSS CAD Suite 安裝 Icarus Verilog 與 Yosys。後端也會嘗試尋找以下常見路徑：

- `C:\oss-cad-suite\bin`
- `C:\ProgramData\chocolatey\bin`

確認工具是否可用：

```powershell
python --version
node --version
npm --version
iverilog -V
vvp -V
yosys --version
```

## 後端設定與執行

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

建立 `backend/.env`。如果只是 demo 或本機測試，可以使用 mock AI，不需要 API key：

```env
FLASK_PORT=5050
FLASK_DEBUG=1
CORS_ORIGINS=http://localhost:5173
USE_FIXED_PIPELINE=true
USE_MOCK_AI=true
AI_PROVIDER=anthropic
```

啟動後端：

```powershell
cd backend
.\venv\Scripts\activate
python app.py
```

預設 API server：

```text
http://localhost:5050
```

健康檢查：

```powershell
curl http://localhost:5050/
```

## AI Provider 與 API Key

AI 功能是可選的。沒有 API key 時，建議設定：

```env
USE_MOCK_AI=true
```

若要使用 Anthropic：

```env
USE_MOCK_AI=false
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-anthropic-key
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

若要使用 Gemini：

```env
USE_MOCK_AI=false
AI_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-2.5-flash
```

其他可用環境變數：

```env
MAX_TOKENS=1024
USE_FIXED_PIPELINE=true
```

## 前端設定與執行

```powershell
cd frontend
npm install
npm run dev
```

預設前端網址：

```text
http://127.0.0.1:5173
```

`frontend/vite.config.ts` 會把 `/api` proxy 到：

```text
http://localhost:5050
```

因此本機開發時請同時啟動後端與前端。

## 使用流程

1. 開啟 `http://127.0.0.1:5173`。
2. 在 Upload 頁面上傳一個或多個 `.v` 檔案。
3. 如果要看到 simulation 與 waveform，請同時上傳 design file 與 testbench。
4. 按下 Run Analysis。
5. 到 Analysis 頁面查看 pipeline stage、logs、waveform、synthesis metrics、dependency graph、flowchart 與 AI insight。
6. 到 History 頁面查看過去 run。
7. 到 Compare 頁面選擇兩個 run，比較 simulation、warning 與 synthesis 指標。

建議從以下範例開始：

- `sample_verilog/02_counter_4bit/counter_4bit.v`
- `sample_verilog/02_counter_4bit/counter_4bit_tb.v`

Compare demo 可使用：

- `sample_verilog/07_pulse_stretcher_v1/`
- `sample_verilog/08_pulse_stretcher_v2/`
- `sample_verilog/03_alu_8bit_v1/`
- `sample_verilog/04_alu_8bit_v2/`

錯誤與 lint demo 可使用：

- `sample_verilog/09_broken_adder/`
- `sample_verilog/10_incomplete_assign/`
- `sample_verilog/11_bad_style_mix/`

## 資料檔與產生檔案

本專案不需要預先準備資料庫檔。第一次啟動後端時，系統會自動建立 SQLite database 與必要資料夾。

會自動產生的檔案與資料夾：

- `backend/eda_platform.db`：SQLite database。
- `backend/uploads/runs/`：每次上傳的 Verilog run 目錄。
- `backend/logs/`：後端 log 相關輸出目錄。
- `backend/reports/`：report 相關輸出目錄。
- `*.vcd`：simulation waveform。
- `*.out`：Icarus Verilog 編譯輸出。
- `frontend/dist/`：前端 production build。

這些檔案大多已在 `.gitignore` 中排除。

## 開發與檢查指令

前端 type check：

```powershell
cd frontend
npm run typecheck
```

前端 production build：

```powershell
cd frontend
npm run build
```

後端目前沒有完整 pytest test suite，僅有部分工具測試檔。可先用以下方式檢查後端是否能啟動：

```powershell
cd backend
.\venv\Scripts\activate
python app.py
```

## 常見問題

### 前端連不到後端

確認兩個服務都已啟動：

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://localhost:5050`

並確認 `backend/.env` 與 `frontend/vite.config.ts` 使用相同的後端 port，預設為 `5050`。

### `iverilog`、`vvp` 或 `yosys` 找不到

請確認 EDA 工具已安裝，且 `bin` 目錄在 PATH 中：

```powershell
where iverilog
where vvp
where yosys
```

Windows 若使用 OSS CAD Suite，常見路徑是：

```text
C:\oss-cad-suite\bin
```

### Analysis 沒有 waveform

通常是以下原因：

- 沒有上傳 testbench。
- testbench 沒有產生 `$dumpfile` 與 `$dumpvars`。
- simulation 編譯或執行失敗。
- testbench 沒有正確 instantiate design module。

### Synthesis 指標為 0 或 unknown

可能原因：

- Yosys 沒有安裝或不在 PATH。
- design file 有語法問題。
- 上傳的檔案只有 testbench，沒有可 synthesis 的 design module。
- top module 推測不符合預期。

### AI insight 沒有真實模型回覆

如果 `USE_MOCK_AI=true`，系統會使用 mock 回覆，這是正常行為。若要使用真實模型，請設定 `USE_MOCK_AI=false` 並提供對應 provider 的 API key。
