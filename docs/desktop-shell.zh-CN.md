# Electron 桌面开发壳

Electron 开发壳用来在桌面窗口中打开本地 MemWeave 服务。它不是已打包的 Windows 应用。

## 启动

```powershell
npm run setup
npm run client:check
npm run client:start
```

启动器优先使用 `backend/.venv/Scripts/python.exe`，没有该文件时再使用 PATH 中的 Python。Node 也从 PATH 解析。Electron 会启动或复用本地前后端，并把日志写入 `logs/`。

就绪检查会请求页面引用的 Next.js 静态资源。如果服务器只能返回 HTML，但 CSS 或 JavaScript 已损坏，它不会被标记为 ready。

## 可选声音适配器

如果用户已在 `indextts2/index-tts` 自行准备外部 IndexTTS2 源码、虚拟环境和 checkpoints，桌面壳可以尝试启动它。缺少权重或运行环境只会产生可选警告，不会阻止 MemWeave 其他功能。

本仓库不包含 IndexTTS2 源码、模型权重、参考音频或生成音频。

自动启动还需要兼容的 `indextts2/server.py` 适配器和对应的后端环境配置。完整目录、接口约定和检查方法见 [授权声音输出](authorized-voice.zh-CN.md)。

## 它没有打包的内容

当前没有 installer builder、代码签名、自动更新、内置 Python/Node 或内置模型运行时。这些属于后续独立的桌面分发工作。
