"""
一键桌面封装入口：
- 启动 FastAPI 后端
- 打开原 index.html GUI 的原生窗口
- 关闭窗口后自动退出
"""
from __future__ import annotations

import socket
import threading
import time
import sys
import os

import uvicorn
import webview

from main import app as fastapi_app


HOST = "127.0.0.1"
PORT = 8000


def find_free_port(start: int = 8000, end: int = 8099) -> int:
    """尽量使用 8000；如果被占用，就自动往后找。"""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError("没有找到可用端口 8000-8099")


def run_server(port: int) -> None:
    """在后台线程启动 uvicorn。"""
    uvicorn.run(
        fastapi_app,
        host=HOST,
        port=port,
        log_level="warning",
        access_log=False,
        reload=False,
        workers=1,
    )


def wait_port(port: int, timeout: float = 10.0) -> bool:
    """等待后端端口就绪。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main() -> None:
    port = find_free_port(PORT)
    url = f"http://{HOST}:{port}"

    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()

    if not wait_port(port):
        raise RuntimeError("后端启动超时")

    # 用系统 WebView 打开窗口，不改你的 index.html GUI。
    webview.create_window(
        title="记账日历",
        url=url,
        width=1280,
        height=860,
        min_size=(1000, 700),
        text_select=True,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    # PyInstaller Windows multiprocessing 保险项
    try:
        import multiprocessing
        multiprocessing.freeze_support()
    except Exception:
        pass
    main()
