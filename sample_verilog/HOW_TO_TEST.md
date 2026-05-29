# Sample Verilog 測試說明

本資料夾提供五個測試電路，複雜度由簡到繁。每個電路都附帶 testbench，可直接上傳至 EDA Insight 平台進行完整分析。

---

## 電路清單與複雜度

| 設計檔案 | Testbench | 電路類型 | 預估 Cell 數 |
|---------|-----------|---------|------------|
| `adder_8bit.v` | _(無，純組合邏輯)_ | 組合邏輯 | ~5 |
| `counter_4bit.v` | `counter_tb.v` | 時序 / 單模組 | ~10 |
| `alu_8bit.v` | `alu_8bit_tb.v` | 組合 + 時序 | ~30–50 |
| `traffic_light.v` | `traffic_light_tb.v` | 有限狀態機 (FSM) | ~40–60 |
| `uart_tx.v` | `uart_tx_tb.v` | 協定控制器 / 多暫存器 | ~60–100 |

---

## 如何上傳測試

### 步驟

1. 開啟 EDA Insight（`http://localhost:5173`）
2. 點選 **Upload** 頁面
3. 同時選取設計檔 + testbench（按住 Ctrl 或 Shift 多選）
4. 點擊 **Run Analysis**
5. 跳轉至 Analysis 頁面，等待 Pipeline 全部變綠
6. 切換 **Technical** / **AI Review** 查看結果

### 注意事項

- `adder_8bit.v` 沒有 testbench，可單獨上傳；系統會執行合成但**不會產生波形**
- 其餘四個設計請**一定要同時上傳設計檔和對應 testbench**，否則模擬無法產生 VCD 波形
- 兩個檔案的欄位名稱都是 `file`，平台支援一次選取多個 `.v` 上傳

---

## 各電路說明

### 1. `adder_8bit.v` — 8-bit 進位加法器

**功能：** 純組合邏輯，計算 `a + b + cin`，輸出 8-bit `sum` 與進位 `cout`

**分析重點：**
- Cell Count 應極少（約 5 個），無 Flip-Flop
- 波形：無（沒有 testbench）
- 適合確認組合邏輯合成結果

---

### 2. `counter_4bit.v` + `counter_tb.v` — 4-bit 同步計數器

**功能：** 帶同步 reset 與 enable 控制的 4-bit 計數器

**分析重點：**
- Cell Count ≈ 10，Flip-Flop ≈ 4（對應 4-bit 暫存器）
- 波形：`count` 從 0 開始遞增，前 20 ns 有 reset，之後 enable 拉高開始計數
- AI Review 應識別為時序電路、同步重置設計

---

### 3. `alu_8bit.v` + `alu_8bit_tb.v` — 8-bit 算術邏輯單元

**功能：** 支援 8 種運算（ADD / SUB / AND / OR / XOR / NOT / SHL / SHR），結果暫存於 D flip-flop，輸出 zero flag 與 carry

**電路特色：**
- **雙 always block**：一個組合（計算 `alu_out`），一個時序（暫存結果）
- 合成後 Cell 數明顯多於 counter_4bit

**分析重點：**
- Cell Count 預計 30–50
- Flip-Flop = 10（8-bit result + zero + carry_out）
- 波形：依序測試 ADD、SUB、AND、OR、XOR、NOT、SHL、SHR 各一次，可看到 result 每 10 ns 變化一次
- `carry_out` 在 `a=200, b=100` 的 ADD 操作時應為 1（200+100=300 > 255）
- `zero` 在最後 `a=0, b=0, op=ADD` 時應為 1

**testbench 操作序列（各 10 ns）：**
```
ADD  10+20=30        → result=0x1E, carry=0, zero=0
ADD  200+100=300     → result=0x2C, carry=1, zero=0
SUB  50-20=30        → result=0x1E, carry=0, zero=0
AND  0xFF & 0x0F     → result=0x0F, carry=0, zero=0
OR   0xF0 | 0x0F     → result=0xFF, carry=0, zero=0
XOR  0xAA ^ 0x55     → result=0xFF, carry=0, zero=0
NOT  ~0xAA           → result=0x55, carry=0, zero=0
SHL  0x01 << 1       → result=0x02, carry=0, zero=0
SHR  0x80 >> 1       → result=0x40, carry=0, zero=0
ADD  0+0             → result=0x00, carry=0, zero=1
```

---

### 4. `traffic_light.v` + `traffic_light_tb.v` — 交通號誌 FSM

**功能：** Moore FSM 實現三相交通號誌（紅→綠→黃→紅），phase_len 可動態調整

**電路特色：**
- 三個 state（RED / GREEN / YELLOW）+ 計時器 counter
- `phase_len` 控制紅燈與綠燈持續時間，黃燈固定 3 個 clock
- 典型的 Moore FSM：輸出只由 state 決定，不受輸入影響

**狀態轉移：**
```
RED (phase_len cycles) → GREEN (phase_len cycles) → YELLOW (3 cycles) → RED ...
```

**分析重點：**
- Cell Count 預計 40–60，Flip-Flop ≈ 6（2-bit state + 4-bit timer）
- 波形：red/green/yellow 三條訊號輪流為 1，可清楚看出 FSM 狀態轉換
- testbench 先以 `phase_len=5` 跑 3 個完整週期，後改為 `phase_len=8` 測試重新配置
- Dependency Graph：只有單一模組（traffic_light_tb → traffic_light）
- AI Review 應識別為 Moore FSM，並說明各狀態轉移條件

---

### 5. `uart_tx.v` + `uart_tx_tb.v` — UART 發送器

**功能：** 標準 8N1 UART 發送（1 start bit + 8 data bits LSB-first + 1 stop bit）

**電路特色：**
- `BAUD_DIV` 參數控制 baud rate（testbench 覆寫為 4，實際應用設為 5208 for 9600 baud @ 50 MHz）
- 4 個狀態：IDLE → START → DATA → STOP
- 多個計數器：`baud_cnt`（baud 計時）、`bit_cnt`（bit 索引）、`shift_reg`（移位暫存器）

**Frame 格式（BAUD_DIV=4，10 ns clock）：**
```
tx: ‾‾‾|_____|D0|D1|D2|D3|D4|D5|D6|D7|‾‾‾‾‾
        Start  ← 8 data bits LSB first →  Stop
        (40ns)      (8 × 40ns = 320ns)   (40ns)
Total frame = 400 ns per byte
```

**分析重點：**
- Cell Count 預計 60–100（最複雜的測試電路）
- Flip-Flop ≈ 28（2-bit state + 16-bit baud_cnt + 8-bit shift_reg + 3-bit bit_cnt + tx + tx_busy）
- 波形：`tx` 訊號會顯示 UART frame，可看到 start bit 拉低 → 8 個 data bit → stop bit 拉高
- testbench 依序發送 4 個 byte：`0x48`('H')、`0x69`('i')、`0x00`、`0xFF`
- `tx_busy` 訊號在發送期間為高，每個 byte 完成後短暫回到低
- AI Review 應識別為 UART 協定控制器，說明移位暫存器設計與狀態機邏輯

---

## 預期分析結果摘要

| 設計 | Cell Count | FF Count | Area | 波形訊號數 |
|------|-----------|----------|------|---------|
| adder_8bit | ~5 | 0 | small | 無 |
| counter_4bit | ~10 | 4 | small | 4 |
| alu_8bit | ~30–50 | 10 | small | 5 |
| traffic_light | ~40–60 | 6 | small | 5 |
| uart_tx | ~60–100 | ~28 | small–medium | 4 |

> **注意：** Cell Count 因 Yosys 版本與合成策略不同會有差異；Critical Path / Slack 在 Yosys 免費版中顯示 N/A 屬正常現象。

---

## 常見問題

**Q：上傳後波形是空白的？**
A：請確認有同時上傳 testbench（`_tb.v` 結尾），且 testbench 內有 `$dumpfile` 與 `$dumpvars` 宣告。

**Q：Synthesis Metrics 全部顯示 0？**
A：通常是 Yosys 未正確安裝或不在 PATH 中。請確認 `yosys --version` 能正常執行。

**Q：AI Report 永遠顯示 pending？**
A：AI Report 的串流分析在你切換到 **AI Review** 頁籤時才觸發，pending 是正常初始狀態，切換後約數秒出現文字。
