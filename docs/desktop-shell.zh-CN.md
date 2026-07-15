# Electron 桌面开发壳

MemWeave 提供一个用于本地开发的 Electron 壳，它不是已经打包好的 Windows 安装程序。

## 启动

```powershell
npm run setup
npm run client:check
npm run client:start
```

启动器优先使用 `backend/.venv/Scripts/python.exe`，不存在时使用 PATH 中的 Python；Node 也从 PATH 解析。Electron 会启动或复用本地前后端，并把运行日志写入 `logs/`。

前端就绪判断会实际请求页面引用的 Next.js 静态资源，因此只有 HTML、CSS/JS 资源损坏的状态不会被误报为 ready。

## 可选声音适配器

如果用户自行在 `indextts2/index-tts` 准备了外部 IndexTTS2 源码、虚拟环境和 checkpoints，桌面壳可以尝试启动它。缺少权重或运行环境只会产生可选警告，不阻止 MemWeave 其他功能启动。

本仓库不包含 IndexTTS2 源码、模型权重、参考音频或生成音频。

## 分发边界

当前没有 installer builder、代码签名、自动更新、内置 Python/Node 或内置模型运行时。这些属于后续独立的桌面分发工作。
