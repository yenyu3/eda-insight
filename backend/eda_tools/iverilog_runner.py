import os
import shutil
import subprocess

DEFAULT_TIMEOUT_SEC = 60


def compile_verilog(
    run_dir: str,
    output_file: str = "sim.out",
) -> subprocess.CompletedProcess:
    """
    使用 iverilog 編譯 run_dir 下所有 .v 檔案。

    注意：
    - 目前會編譯目錄內所有 .v 檔案，包含 testbench
    - 若未來要區分 design / testbench，可在呼叫端先過濾檔案

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
        timeout=DEFAULT_TIMEOUT_SEC,
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
        timeout=DEFAULT_TIMEOUT_SEC,
        cwd=run_dir,
        env=tool_env(vvp_cmd),
    )


def resolve_tool(tool_name: str) -> str:
    """
    解析 EDA 工具的可執行檔路徑。

    搜尋順序：
    1. PATH
    2. Windows 常見安裝路徑（oss-cad-suite / chocolatey）

    Args:
        tool_name: 工具名稱，例如 iverilog、vvp

    Returns:
        工具可執行檔的完整路徑

    Raises:
        FileNotFoundError: 找不到工具時拋出
    """
    found = shutil.which(tool_name)
    if found:
        return found

    exe_name = f"{tool_name}.exe" if os.name == "nt" else tool_name
    candidates = []

    if os.name == "nt":
        # 常見 Windows 安裝位置
        candidates.extend([
            os.path.join("C:\\", "oss-cad-suite", "bin", exe_name),
            os.path.join("C:\\", "ProgramData", "chocolatey", "bin", exe_name),
        ])

    for path in candidates:
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        f"Cannot find '{tool_name}'. Please install it and ensure its bin directory is in PATH."
    )


def tool_env(tool_path: str) -> dict[str, str]:
    """
    建立工具執行所需的環境變數。

    目的：
    - 確保工具本體與其相依的動態函式庫能被找到
    - Windows 上對 oss-cad-suite 類安裝特別重要

    Args:
        tool_path: 工具可執行檔的完整路徑

    Returns:
        已補充 PATH 的環境變數 dict
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
