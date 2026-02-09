"""
System monitoring module: CPU, memory, GPU snapshots.

Usage:
  python -m python.sysmon snapshot
"""

import subprocess
import sys

from python.protocol import emit_result, emit_error


def get_snapshot() -> dict:
    """Get current system resource usage snapshot."""
    result = {
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "memory_used_gb": 0.0,
        "memory_total_gb": 0.0,
        "gpu_percent": 0.0,
    }

    # Try psutil first
    try:
        import psutil
        result["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        result["memory_percent"] = mem.percent
        result["memory_used_gb"] = round(mem.used / (1024**3), 1)
        result["memory_total_gb"] = round(mem.total / (1024**3), 1)
    except ImportError:
        # Fallback: use macOS commands
        try:
            # CPU via top
            proc = subprocess.run(
                ["top", "-l", "1", "-n", "0", "-stats", "cpu"],
                capture_output=True, text=True, timeout=5,
            )
            for line in proc.stdout.split("\n"):
                if "CPU usage" in line:
                    import re
                    m = re.search(r"(\d+\.?\d*)% user.*?(\d+\.?\d*)% sys", line)
                    if m:
                        result["cpu_percent"] = float(m.group(1)) + float(m.group(2))
                    break
        except Exception:
            pass

        try:
            # Memory via vm_stat
            proc = subprocess.run(
                ["vm_stat"],
                capture_output=True, text=True, timeout=5,
            )
            import re
            pages = {}
            for line in proc.stdout.split("\n"):
                m = re.match(r"(.+?):\s+(\d+)", line)
                if m:
                    pages[m.group(1).strip()] = int(m.group(2))

            page_size = 16384  # Default macOS page size
            active = pages.get("Pages active", 0) * page_size
            wired = pages.get("Pages wired down", 0) * page_size
            compressed = pages.get("Pages occupied by compressor", 0) * page_size
            used = active + wired + compressed

            # Get total memory
            proc2 = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            )
            total = int(proc2.stdout.strip())

            result["memory_used_gb"] = round(used / (1024**3), 1)
            result["memory_total_gb"] = round(total / (1024**3), 1)
            result["memory_percent"] = round((used / total) * 100, 1)
        except Exception:
            pass

    # GPU usage (macOS-specific via powermetrics or ioreg)
    try:
        proc = subprocess.run(
            ["ioreg", "-r", "-d", "1", "-c", "AppleGPU"],
            capture_output=True, text=True, timeout=5,
        )
        import re
        m = re.search(r'"GPU Core Utilization\(%\)"\s*=\s*(\d+)', proc.stdout)
        if m:
            result["gpu_percent"] = float(m.group(1))
    except Exception:
        pass

    return result


def main():
    if len(sys.argv) < 2:
        emit_error("usage", "Usage: python -m python.sysmon snapshot")
        return

    if sys.argv[1] == "snapshot":
        snapshot = get_snapshot()
        emit_result(snapshot)
    else:
        emit_error("usage", f"Unknown command: {sys.argv[1]}")


if __name__ == "__main__":
    main()
