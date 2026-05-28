# EDA Insight

EDA Insight 是一個面向 EDA workflow 的 AI observability 平台。使用者可以上傳 Verilog 檔案，系統會執行解析、模擬、合成與 dependency 分析，並在前端儀表板中呈現 pipeline 狀態、log、波形、module graph、PPA 指標與 AI 輔助說明。

此專案由兩個主要部分組成：

- `backend/`: Flask API，負責檔案上傳、EDA pipeline、SQLite 紀錄與 AI 介接。
- `frontend/`: React + Vite 前端，負責上傳流程、分析頁、歷史紀錄與比較頁。

## 功能概覽

- 上傳一個或多個 `.v` Verilog 檔案。
- 解析 module、port、signal、lint issue 與 dependency graph。
- 使用 Icarus Verilog 執行 simulation，並解析 VCD waveform。
- 使用 Yosys 執行 synthesis，擷取 cell count 等合成資訊。
- 透過 SSE 串流顯示 AI insight。
- 保存分析紀錄，並支援兩次 run 的 PPA 比較。

## 環境需求

請先確認本機已安裝以下工具：

- Python 3.10 或以上
- Node.js 18 或以上
- npm
- Icarus Verilog: `iverilog`、`vvp`
- Yosys

在 Windows 上建議使用 OSS CAD Suite 安裝 Icarus Verilog 與 Yosys，並確認其 `bin` 目錄已加入 `PATH`。

可用以下指令檢查：

```powershell
python --version
node --version
npm --version
iverilog -V
yosys --version
```

## 專案結構

```text
eda-insight/
├─ backend/
│  ├─ app.py
│  ├─ workflow_engine.py
│  ├─ verilog_parser.py
│  ├─ vcd_parser.py
│  ├─ report_parser.py
│  ├─ dependency_analyzer.py
│  ├─ ai_engine.py
│  ├─ db_manager.py
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  ├─ package.json
│  └─ vite.config.ts
├─ sample_verilog/
│  ├─ counter_4bit.v
│  ├─ counter_tb.v
│  └─ adder_8bit.v
└─ README.md
```

## 安裝步驟

### 1. 安裝後端套件

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 設定後端環境變數

在 `backend/` 目錄下建立 `.env` 檔案：

```env
FLASK_PORT=5050
USE_MOCK_AI=true
USE_FIXED_PIPELINE=true
ANTHROPIC_API_KEY=your-key-here
```

說明：

- `FLASK_PORT=5050`: 前端 Vite proxy 目前會把 `/api` 轉發到 `http://localhost:5050`，因此後端建議固定使用 `5050`。
- `USE_MOCK_AI=true`: 使用 mock AI 輸出，不需要真實 API key，適合本機 demo。
- `USE_MOCK_AI=false`: 若要使用 Anthropic API，請填入有效的 `ANTHROPIC_API_KEY`。
- `USE_FIXED_PIPELINE=true`: 使用固定 pipeline: lint、simulate、synthesize。

`.env` 不應提交到 Git。

### 3. 安裝前端套件

開啟另一個 PowerShell：

```powershell
cd frontend
npm install
```

## 啟動專案

請使用兩個終端機分別啟動後端與前端。

### Terminal 1: 啟動 Flask 後端

```powershell
cd backend
.\venv\Scripts\activate
python app.py
```

成功後會看到類似輸出：

```text
Running on http://127.0.0.1:5050
```

### Terminal 2: 啟動 Vite 前端

```powershell
cd frontend
npm run dev
```

成功後開啟：

```text
http://127.0.0.1:5173
```

前端會透過 `frontend/vite.config.ts` 將 `/api` proxy 到後端 `http://localhost:5050`。

## 使用流程

1. 開啟 `http://127.0.0.1:5173`。
2. 在 Upload 頁面上傳 Verilog 檔案。
3. 可使用範例檔案：
   - `sample_verilog/counter_4bit.v`
   - `sample_verilog/counter_tb.v`
4. 上傳後開始分析。
5. 在 Analysis 頁查看 pipeline 狀態、log、波形、dependency graph、合成結果與 AI insight。
6. 在 History 頁查看過去執行紀錄。
7. 在 Compare 頁比較兩次 run 的 PPA 差異。

## API 快速檢查

後端啟動後，可用以下指令確認 API 是否正常：

```powershell
curl http://localhost:5050/api/history
```

預期會得到 JSON：

```json
{
  "runs": []
}
```

若已有執行紀錄，`runs` 會包含歷史資料。

## EDA 工具檢查

若 simulation 或 synthesis 失敗，先確認工具可以在終端機中被找到：

```powershell
where iverilog
where vvp
where yosys
```

也可以用範例檔案手動測試：

```powershell
cd sample_verilog
iverilog -o test.out -g2012 counter_4bit.v counter_tb.v
vvp test.out
yosys -p "read_verilog counter_4bit.v; synth; stat"
```

## 常用指令

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

重新安裝 Python 套件：

```powershell
cd backend
.\venv\Scripts\activate
pip install -r requirements.txt
```

## 常見問題

### 前端打不開或 API 沒有回應

確認兩個服務都已啟動：

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://localhost:5050`

並確認 `backend/.env` 有設定：

```env
FLASK_PORT=5050
```

### `ModuleNotFoundError`

代表 Python 套件尚未安裝或 virtual environment 尚未啟用：

```powershell
cd backend
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Simulation stage 失敗

通常是 `iverilog` 或 `vvp` 沒有安裝、沒有加入 `PATH`，或 Verilog/testbench 本身有語法錯誤。先用 `where iverilog`、`where vvp` 確認工具位置，再查看 Analysis 頁面的 log。

### Synthesis stage 失敗

通常是 `yosys` 沒有安裝、沒有加入 `PATH`，或 Verilog 不符合 Yosys 可合成語法。先用以下指令確認：

```powershell
yosys --version
```

### AI insight 沒有真實模型輸出

若 `USE_MOCK_AI=true`，系統會使用 mock response。若要連接 Anthropic API：

```env
USE_MOCK_AI=false
ANTHROPIC_API_KEY=sk-ant-...
```

設定後重新啟動後端。

## 資料與產物

執行過程會產生以下本機資料：

- `backend/eda_platform.db`: SQLite database。
- `backend/uploads/`: 上傳檔案與每次 run 的中間產物。
- `*.vcd`、`*.out`: simulation 產物。
- `frontend/dist/`: 前端 build 產物。

這些檔案已在 `.gitignore` 中排除，不應提交到版本控制。
