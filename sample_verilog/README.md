# Sample Verilog 測試集

這個資料夾提供一組可直接在 **VeriFlow Insight** 中使用的 Verilog 測試檔。範例從簡單組合邏輯到 FSM、UART、版本比較與故意錯誤案例都有，主要用來測試：

- 上傳流程、Verilog 靜態解析與 lint 檢查
- Icarus Verilog simulation 與 waveform 顯示
- Yosys synthesis 與基本資源統計
- Flowchart / dependency graph 顯示
- History、Compare 與 AI 分析摘要
- 錯誤偵測與 log 解讀

---

## 1. 資料夾包含什麼？

每個範例都放在獨立資料夾中。大多數範例包含：

- **Design file**：主要 Verilog 設計，例如 `counter_4bit.v`
- **Testbench**：模擬用測試檔，通常以 `_tb.v` 結尾，例如 `counter_4bit_tb.v`

如果只想看 parser、lint、synthesis、flowchart 或 dependency graph，可以只上傳 design file。

如果想測完整 pipeline，尤其是 simulation 與 waveform，通常需要 **design file + testbench 一起上傳**。

---

## 2. 如何使用

### 方法一：測單一設計檔

只想測靜態分析、合成、flowchart 或 dependency graph 時，可以只上傳 design file，例如：

- `01_adder_8bit/adder_8bit.v`
- `10_incomplete_assign/incomplete_assign.v`
- `11_bad_style_mix/bad_style_mix.v`

### 方法二：測完整流程

想看到 simulation、waveform、Analysis 頁面完整結果、AI summary 或 Compare 結果時，請同時上傳 design file 與對應 testbench，例如：

- `02_counter_4bit/counter_4bit.v` + `02_counter_4bit/counter_4bit_tb.v`
- `03_alu_8bit_v1/alu_8bit_v1.v` + `03_alu_8bit_v1/alu_8bit_v1_tb.v`
- `05_traffic_light_fsm/traffic_light.v` + `05_traffic_light_fsm/traffic_light_tb.v`

### 在平台中操作

1. 開啟 VeriFlow Insight。
2. 進入 **Upload** 頁面。
3. 點選檔案選擇器。
4. 同時選取一個或多個 `.v` 檔。
5. 按下 **Run Analysis**。
6. 前往 **Analysis** 頁面查看結果。

---

## 3. 檔案命名規則

為了讓平台比較容易辨識，建議使用以下命名規則：

- Design file：`xxx.v`
- Testbench：`xxx_tb.v`
- 版本比較：`xxx_v1.v`、`xxx_v2.v`
- 錯誤案例：使用清楚的名稱，例如 `broken_adder_8bit.v`

VeriFlow Insight 會優先把非 `_tb.v` 的檔案視為主要 design file。simulation 時，系統會編譯同一個 run 中上傳的所有 `.v` 檔案。

---

## 4. 測試案例總覽

| 資料夾                   | 類型                 | 檔案                                              | 適合測試                                                      |
| ------------------------ | -------------------- | ------------------------------------------------- | ------------------------------------------------------------- |
| `01_adder_8bit/`         | 純組合邏輯           | `adder_8bit.v`, `adder_8bit_tb.v`                 | assign、combinational analysis、基本 synthesis、簡單 waveform |
| `02_counter_4bit/`       | 時序電路             | `counter_4bit.v`, `counter_4bit_tb.v`             | reset、enable、clocked logic、完整 pipeline                   |
| `03_alu_8bit_v1/`        | 組合 + 時序混合      | `alu_8bit_v1.v`, `alu_8bit_v1_tb.v`               | case 分支、暫存器、mixed logic、Compare                       |
| `04_alu_8bit_v2/`        | 同功能不同實作       | `alu_8bit_v2.v`, `alu_8bit_v2_tb.v`               | 與 v1 比較 synthesis/resource 差異                            |
| `05_traffic_light_fsm/`  | FSM                  | `traffic_light.v`, `traffic_light_tb.v`           | state transition、flowchart、FSM 分析                         |
| `06_uart_tx/`            | 協定控制器           | `uart_tx.v`, `uart_tx_tb.v`                       | parameter、baud counter、多狀態控制流程                       |
| `07_pulse_stretcher_v1/` | 同功能版本 1         | `pulse_stretcher_v1.v`, `pulse_stretcher_v1_tb.v` | counter-based pulse stretcher、Compare                        |
| `08_pulse_stretcher_v2/` | 同功能版本 2         | `pulse_stretcher_v2.v`, `pulse_stretcher_v2_tb.v` | shift-register-based pulse stretcher、Compare                 |
| `09_broken_adder/`       | 故意錯誤案例         | `broken_adder_8bit.v`, `broken_adder_8bit_tb.v`   | simulation error、LogViewer、AI 錯誤解讀                      |
| `10_incomplete_assign/`  | 潛在 latch 風險      | `incomplete_assign.v`                             | incomplete assignment、lint / 靜態分析                        |
| `11_bad_style_mix/`      | 混合風格 / lint 測試 | `bad_style_mix.v`                                 | unused wire、混合時序/組合寫法、AI summary                    |

---

## 5. 每組測試案例說明

### `01_adder_8bit/`

8-bit adder，包含 carry in 與 carry out。適合確認系統是否能正確解析最基本的組合邏輯，也可以透過 testbench 看簡單 waveform。

你可以觀察到：

- 合成結果很小
- `assign` 與 combinational logic 解析
- 即使只上傳 design file，也可以測 parser 與 synthesis

### `02_counter_4bit/`

4-bit counter，包含 `rst_n`、`en` 與 `count`。這是最推薦第一個使用的完整流程範例。

你可以觀察到：

- reset 時 `count` 歸零
- enable 為 1 時才計數
- waveform 中可看到 `count` 隨 clock 變化

### `03_alu_8bit_v1/`

ALU 版本 1，使用 `alu_tmp` 做 combinational 暫存，再把結果 register 到輸出。

你可以觀察到：

- 多種運算結果
- `zero`、`carry` 旗標變化
- mixed logic 分析摘要
- 與 `04_alu_8bit_v2/` 的 Compare 差異

### `04_alu_8bit_v2/`

ALU 版本 2，將 `next_value` 與 `logic_value` 拆開。功能接近 v1，但內部寫法不同。

你可以觀察到：

- 與 v1 功能相似
- synthesis/resource 統計可能不同
- Compare 頁面可用來解讀兩種 RTL 寫法差異

### `05_traffic_light_fsm/`

交通燈 FSM，包含 red、green、yellow 狀態，以及 timer / phase_len 控制。

你可以觀察到：

- 紅燈、綠燈、黃燈輪流亮起
- state 依 timer 與 phase_len 轉換
- 適合檢查 flowchart 與 FSM 分析結果

### `06_uart_tx/`

UART transmitter，包含 parameter、baud counter、bit counter、shift register 與多狀態控制流程。

你可以觀察到：

- `tx` 顯示 UART frame 行為
- `tx_busy` 在發送期間為 1
- 比 counter / adder 更完整的 control path 與 data path

### `07_pulse_stretcher_v1/`

Pulse stretcher 版本 1，使用 counter 讓短 pulse 維持多個 clock cycle。

你可以觀察到：

- 輸入一個短 pulse，輸出會被拉長
- counter-based 實作
- 適合與 `08_pulse_stretcher_v2/` 做 Compare

### `08_pulse_stretcher_v2/`

Pulse stretcher 版本 2，使用 shift register 與 reduction OR 產生延長後的 pulse。

你可以觀察到：

- 與 v1 功能相近
- 內部結構不同
- 合成與結構結果應與 v1 有差異

### `09_broken_adder/`

故意寫錯的 adder。`broken_adder_8bit.v` 把加法寫成 `a + b - 1`，testbench 預期 `15 + 1 = 16`，因此 simulation 會觸發 `$fatal`。

你可以觀察到：

- 程式可能可以編譯
- simulation 會失敗
- pipeline 應在 simulation 階段回報錯誤
- LogViewer 與 AI summary 可用來解讀失敗原因

### `10_incomplete_assign/`

只有 design file，沒有 testbench。這個範例的 `always @(*)` 沒有完整 else 分支，可能造成 latch。

你可以觀察到：

- incomplete assignment 風險
- lint / parser / AI 對潛在 latch 的說明
- 不適合作為 waveform demo

### `11_bad_style_mix/`

只有 design file，沒有 testbench。這個範例包含 unused wire，並混合 sequential 與 combinational 寫法。

你可以觀察到：

- 未使用訊號
- 混合風格與可疑 RTL 寫法
- lint 與 AI summary 是否指出問題

---

## 6. Compare 功能怎麼測？

Compare 功能建議使用兩組相近但實作不同的設計。

### 組合 A：Pulse stretcher

- Run A：`07_pulse_stretcher_v1/pulse_stretcher_v1.v` + `07_pulse_stretcher_v1/pulse_stretcher_v1_tb.v`
- Run B：`08_pulse_stretcher_v2/pulse_stretcher_v2.v` + `08_pulse_stretcher_v2/pulse_stretcher_v2_tb.v`

觀察重點：

- counter-based 與 shift-register-based 實作差異
- cell count、wire count、flip-flop count
- simulation 是否都通過

### 組合 B：ALU

- Run A：`03_alu_8bit_v1/alu_8bit_v1.v` + `03_alu_8bit_v1/alu_8bit_v1_tb.v`
- Run B：`04_alu_8bit_v2/alu_8bit_v2.v` + `04_alu_8bit_v2/alu_8bit_v2_tb.v`

觀察重點：

- 兩種 RTL 寫法是否產生不同 synthesis 結果
- warning 數量
- cell / wire / flip-flop 差異
- AI tradeoff 說明

---

## 7. 錯誤案例怎麼看？

`09_broken_adder/` 是預期會失敗的範例。它的 testbench 會在檢查結果時呼叫 `$fatal`，因此：

- 編譯可能成功
- simulation 會失敗
- pipeline 顯示 simulation error 是正常現象

如果系統能在 Analysis 頁顯示錯誤、LogViewer 顯示 `$fatal`，並在 AI summary 中說明可能原因，就代表錯誤偵測流程有正常運作。

---

## 8. 如果結果不如預期

### 沒有 waveform

常見原因：

1. 沒有同時上傳 testbench。
2. testbench 沒有 `$dumpfile` 或 `$dumpvars`。
3. simulation 沒有成功執行。
4. testbench 沒有正確 instantiate design module。
5. 上傳的檔案不是同一組 design/testbench。

### Synthesis 指標是 0 或 unknown

常見原因：

- Yosys 沒有正確安裝。
- Yosys 不在 PATH 中。
- Verilog 語法不被 Yosys 接受。
- 只上傳 testbench，沒有真正的 design file。
- top module 推測與預期不同。

### Compare 沒有足夠資料

常見原因：

- 兩個 run 尚未完成 analysis。
- 其中一個 run 沒有執行 synthesis 或 simulation。
- 其中一個 run 是錯誤案例，可比較的指標較少。

---

## 9. 建議測試順序

如果是第一次使用，建議依照下列順序測試：

### 第一輪：最簡單

1. `01_adder_8bit/`
2. `02_counter_4bit/`

### 第二輪：中等複雜

3. `03_alu_8bit_v1/`
4. `05_traffic_light_fsm/`

### 第三輪：較完整

5. `06_uart_tx/`

### 第四輪：Compare

6. `07_pulse_stretcher_v1/` vs `08_pulse_stretcher_v2/`
7. `03_alu_8bit_v1/` vs `04_alu_8bit_v2/`

### 第五輪：錯誤與邊界

8. `09_broken_adder/`
9. `10_incomplete_assign/`
10. `11_bad_style_mix/`

---

## 10. 給非開發者的操作提醒

- 看到檔案名稱中有 `_tb.v`，通常表示它是 testbench。
- 上傳時，design file 與 testbench 建議一起選。
- 如果只有分析結果但沒有 waveform，通常代表 testbench 沒有上傳或沒有成功執行。
- 如果看不懂結果，先檢查是否有 error、warning、waveform 與 AI summary。
- `09_broken_adder/` 是故意失敗的範例，看到 simulation error 是正常的。

---

## 11. 維護與新增案例

如果之後要新增案例，建議遵守以下規則：

- Design file 使用 `.v`。
- Testbench 名稱加 `_tb.v`。
- 版本比較用 `_v1.v`、`_v2.v`。
- 錯誤案例名稱可以加 `broken_`，或使用清楚描述錯誤的名稱。
- 測試檔盡量保持簡單、可讀、可重現。
- 新增範例資料夾時，請同步更新這份 README。

---

## 12. 注意事項與回報問題

注意事項：

- `_tb.v` 是 testbench，不是 synthesis 目標。
- `10_incomplete_assign/` 與 `11_bad_style_mix/` 沒有 testbench，主要用於 lint/style 分析。
- Yosys-only flow 不一定提供 timing data，因此 `critical_path_ns` 與 `slack_ns` 可能是空值。
- 合成數字可能因工具版本或環境略有差異，這是正常的。
