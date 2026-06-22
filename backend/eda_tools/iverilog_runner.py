"""
eda_tools/iverilog_runner.py — Icarus Verilog 工具呼叫封裝

負責 iverilog 編譯與 vvp 模擬的 subprocess 呼叫，
以及 EDA 工具路徑解析（支援 Windows oss-cad-suite）。
"""

import os
import shutil
import subprocess


def compile_verilog(
    run_dir: str,
    output_file: str = "sim.out",
) -> subprocess.CompletedProcess:
    """
    使用 iverilog 編譯 run_dir 下所有 .v 檔案。

    Args:
        run_dir: 包含 .v 檔案的目錄路徑
        output_file: 編譯輸出檔案名稱（相對於 run_dir）

    Returns:
        subprocess.CompletedProcess（呼叫端自行判斷 returncode）
    """
    verilog_filenames = sorted(f for f in os.listdir(run_dir) if f.endswith(".v"))
    iverilog_cmd = resolve_tool("iverilog")
    return subprocess.run(
        [iverilog_cmd, "-o", output_file, "-g2012"] + verilog_filenames,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=run_dir,
        env=tool_env(iverilog_cmd),
    )


def run_simulation(
    run_dir: str,
    sim_file: str = "sim.out",
) -> subprocess.CompletedProcess:
    """
    使用 vvp 執行已編譯的模擬二進位。

    Args:
        run_dir: 工作目錄
        sim_file: 編譯輸出的二進位檔名（相對於 run_dir）

    Returns:
        subprocess.CompletedProcess
    """
    vvp_cmd = resolve_tool("vvp")
    return subprocess.run(
        [vvp_cmd, sim_file],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=run_dir,
        env=tool_env(vvp_cmd),
    )


def resolve_tool(tool_name: str) -> str:
    """
    解析 EDA 工具的可執行檔路徑。
    優先使用 PATH，其次嘗試 Windows 常見安裝路徑（oss-cad-suite）。
    """
    found = shutil.which(tool_name)
    if found:
        return found

    exe_name = f"{tool_name}.exe" if os.name == "nt" else tool_name
    candidates = []
    if os.name == "nt":
        candidates.extend([
            os.path.join("C:\\", "oss-cad-suite", "bin", exe_name),
            os.path.join("C:\\", "ProgramData", "chocolatey", "bin", exe_name),
        ])

    for path in candidates:
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        f"{tool_name} not found. Install it or add its bin directory to PATH."
    )


def tool_env(tool_path: str) -> dict[str, str]:
    """
    建立帶有工具 lib 目錄前置的環境變數 dict，
    確保動態連結函式庫能被正確找到（Windows 特別需要）。
    """
    env = os.environ.copy()
    tool_dir = os.path.dirname(tool_path)
    suite_root = os.path.dirname(tool_dir)
    suite_lib = os.path.join(suite_root, "lib")
    current_path = env.get("PATH", "")
    path_parts = [p for p in current_path.split(os.pathsep) if p]
    prepend = [
        p for p in (tool_dir, suite_lib)
        if p and os.path.exists(p) and p not in path_parts
    ]
    if prepend:
        env["PATH"] = os.pathsep.join(prepend + ([current_path] if current_path else []))
    return env
