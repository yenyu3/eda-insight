import os


def is_testbench_filename(filename: str) -> bool:
    """依檔名慣例判斷是否為 testbench 檔案。

    注意：
    - 這是經驗式規則，不保證 100% 正確
    - 目前支援常見命名：
      *_tb.v、tb_*、*testbench*、*_test.v
    """
    name = filename.lower()
    return (
        name.endswith("_tb.v")
        or name.startswith("tb_")
        or "testbench" in name
        or name.endswith("_test.v")
    )


def find_verilog_files(directory: str) -> list[str]:
    """取得目錄下所有 .v 檔案的路徑清單。

    注意：
    - 回傳的是 os.path.join(directory, filename) 的結果
    - 若 directory 是相對路徑，回傳值也會是相對路徑
    """
    return [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.endswith(".v")
    ]


def read_verilog_sources(run_dir: str, exclude_testbench: bool = False) -> str:
    """讀取目錄下所有 .v 檔案，合併為帶有 file header 的字串。

    Args:
        run_dir: Verilog 檔案所在目錄
        exclude_testbench: 是否排除 testbench 檔案

    Returns:
        合併後的 Verilog 文字
    """
    parts = []

    for fname in sorted(os.listdir(run_dir)):
        if not fname.endswith(".v"):
            continue
        if exclude_testbench and is_testbench_filename(fname):
            continue

        path = os.path.join(run_dir, fname)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            parts.append(f"// File: {fname}\n{f.read()}")

    return "\n\n".join(parts)
