# 📒 记账日历 — 桌面版打包说明

## 开发调试

```bash
# 启动后端 + WebView 桌面壳
run_desktop_dev.bat
```

## 一键打包

```bash
build_onefile.bat
```

打包产物：`dist/记账日历.exe`

复制到任意 Windows 电脑即可运行，无需安装。

## 数据保存位置

数据库和备份存放在用户目录，不会被 exe 更新覆盖：

```
%APPDATA%\FinanceCalendar\
├── finance.db          # 数据库
└── backups\            # 自动备份
```

## 技术方案

- 后端：Python + FastAPI + SQLite → PyInstaller 打包为 exe
- 前端：原生 HTML 单文件，内嵌在 exe 中
- 桌面壳：Python WebView（pywebview），无需 Electron
- 启动流程：launcher.py → 启动 FastAPI → 打开 WebView 加载 localhost

## 注意事项

- 目标电脑需要 Microsoft Edge WebView2 Runtime（Win10/Win11 大多已预装）
- 如未安装，可从 [微软官网](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) 下载
- 数据库使用 WAL 模式，支持备份恢复
