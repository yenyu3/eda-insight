try:
    import vcdvcd
except ImportError:
    vcdvcd = None


def parse_vcd(vcd_path: str) -> dict:
    """
    解析 VCD 波形檔案，回傳可供前端與 AI 使用的時序資料。

    Returns:
        {
            "signals": ["clk", "reset", "count"],
            "timeline": {
                "clk": {"times": [0, 5, 10, ...], "values": [0, 1, 0, ...]},
            },
            "stats": {
                "sim_duration_ns": 200,
                "clock_period_ns": 10,
                "switching_activity": {"clk": 40},
                "parse_errors": [...]
            }
        }
    """
    if vcdvcd is None:
        raise ImportError("vcdvcd 套件未安裝，請執行 pip install vcdvcd")

    vcd = vcdvcd.VCDVCD(vcd_path)
    signal_names = _get_signal_names(vcd)
    timeline, parse_errors = _build_timeline(vcd)
    stats = _compute_stats(timeline, parse_errors)

    return {
        "signals": signal_names,
        "timeline": timeline,
        "stats": stats,
    }


def _get_signal_names(vcd) -> list[str]:
    names = []
    for ref in vcd.references_to_ids:
        names.append(_short_name(ref))
    return list(dict.fromkeys(names))


def _short_name(ref: str) -> str:
    """從完整 reference 取出短名稱，供顯示用。"""
    return ref.split(".")[-1]


def _build_timeline(vcd) -> tuple[dict, list[str]]:
    timeline = {}
    parse_errors = []

    for ref in vcd.references_to_ids:
        short_name = _short_name(ref)
        try:
            signal = vcd[ref]
            times = []
            values = []
            for time, value in signal.tv:
                times.append(int(time))
                values.append(_parse_value(value))
            timeline[short_name] = {"times": times, "values": values}
        except Exception as e:
            parse_errors.append(f"{ref}: {type(e).__name__}: {e}")

    return timeline, parse_errors


def _parse_value(raw_value):
    """
    將 VCD value 轉成較容易處理的值。

    支援：
    - 0 / 1
    - x / z / u（回傳字串）
    - binary vector（例如 b1010）
    - 其他格式則盡量保留原值
    """
    if isinstance(raw_value, int):
        return raw_value

    if not isinstance(raw_value, str):
        return None

    v = raw_value.strip().lower()

    if v in {"0", "1"}:
        return int(v)
    if v in {"x", "z", "u"}:
        return v

    if v.startswith("b"):
        bits = v[1:].strip()
        if set(bits) <= {"0", "1"}:
            try:
                return int(bits, 2)
            except ValueError:
                return bits
        return bits

    try:
        return int(v, 2)
    except ValueError:
        try:
            return int(v)
        except ValueError:
            return v


def _compute_stats(timeline: dict, parse_errors: list[str]) -> dict:
    max_time = 0
    switching_activity = {}
    clock_period_ns = None

    for sig, data in timeline.items():
        times = data["times"]
        values = data["values"]

        if times:
            max_time = max(max_time, times[-1])

        transitions = sum(
            1 for i in range(1, len(values)) if values[i] != values[i - 1]
        )
        switching_activity[sig] = transitions

        # 以多個 rising edge 的平均間距估算 clock period
        sig_lower = _short_name(sig).lower()
        if sig_lower == "clk" or sig_lower.endswith("_clk") or sig_lower.endswith("clk"):
            rising_edges = [
                times[i]
                for i in range(1, len(values))
                if values[i] == 1 and values[i - 1] == 0
            ]
            if len(rising_edges) >= 2:
                periods = [
                    rising_edges[i] - rising_edges[i - 1]
                    for i in range(1, len(rising_edges))
                ]
                if periods:
                    clock_period_ns = int(round(sum(periods) / len(periods)))

    return {
        "sim_duration_ns": max_time,
        "clock_period_ns": clock_period_ns,
        "switching_activity": switching_activity,
        "parse_errors": parse_errors,
    }
