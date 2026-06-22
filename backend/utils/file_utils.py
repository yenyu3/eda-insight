"""utils/file_utils.py — 檔案處理工具函式。"""

import os


def is_testbench_filename(filename: str) -> bool:
    """依檔名慣例判斷是否為 testbench 檔案。"""
    name = filename.lower()
    return (
        name.endswith("_tb.v")
        or name.startswith("tb_")
        or "testbench" in name
        or name.endswith("_test.v")
    )


def find_verilog_files(directory: str) -> list[str]:
    """取得目錄下所有 .v 檔案的絕對路徑清單。"""
    return [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.endswith(".v")
    ]


def read_verilog_sources(run_dir: str) -> str:
    """讀取目錄下所有 .v 檔案，合併為帶有 file header 的字串。"""
    parts = []
    for fname in sorted(os.listdir(run_dir)):
        if not fname.endswith(".v"):
            continue
        path = os.path.join(run_dir, fname)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            parts.append(f"// File: {fname}\n{f.read()}")
    return "\n\n".join(parts)
