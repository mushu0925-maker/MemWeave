# Windows 安装指南

MemWeave v0.2.0 可以构建为 unsigned Windows x64 NSIS 安装包。

## 分发边界

安装包会携带：

- Electron 及其 Node 运行时。
- Next.js standalone 前端和追踪出的生产依赖。
- 由 PyInstaller 打包的 FastAPI 后端运行时。
- 可选的本地声音配置助手。

安装包不包含 API Key、个人记忆数据、声音参考、生成音频、IndexTTS2 源码或模型权重。应用的本地服务只绑定 `127.0.0.1`。

安装包没有代码签名，Windows 可能显示“未知发布者”警告。运行前请把 Setup.exe 的 SHA-256 与 GitHub Release 说明中的值对比。

## 安装与数据

运行 `MemWeave-0.2.0-Setup.exe` 并选择安装目录。首次启动时，MemWeave 会启动已打包的前端和后端，并把可写状态创建在：

```text
%LOCALAPPDATA%\MemWeave
```

该目录包含本地配置、JSON/SQLite 数据、日志、上传文件、声音参考、生成音频和 Electron 浏览器状态。程序安装目录中的资源保持只读。

## 备份与导入

换电脑或卸载前：

1. 打开“设置”。
2. 选择“导出完整备份”。
3. 把 ZIP 保存到受保护的位置。

仪表盘也可以只导出当前人物。单人备份会包含该人物的证据、A-M 人格条目、Skill、聊天记录、已授权声音参考和生成音频，前提是这些文件由应用管理。

备份 ZIP 没有加密。它不包含 API Key、服务商凭据、模型权重、程序依赖和全局 AI 配置。导入会先显示人物冲突预览，再要求选择“合并”或“作为新人物导入”，不会静默覆盖已有人物。

## 卸载

卸载时会明确警告本地记忆和设置将被删除。继续卸载会默认删除 `%LOCALAPPDATA%\MemWeave`，包括日志、附件和生成音频。需要保留数据时请先导出备份。

## 可选声音配置

安装版“设置”页可以打开本地声音配置助手。助手要求用户已有包含 `config.yaml` 的 IndexTTS2 模型目录。它可以获取 upstream 源码、创建 Python 环境、安装依赖并可选安装 FFmpeg，但绝不下载或复制模型权重。

声音输出仍需要已确认的来源归属、明确授权和已生成的固定 `reply_text`。启用前请阅读 [授权声音输出](authorized-voice.zh-CN.md)。

## 从源码构建

环境要求：Windows 10/11、PowerShell 5.1+、Node.js 20+ 和 Python 3.11+。

```powershell
npm ci --ignore-scripts
npm --prefix frontend ci
npm run package:setup
npm run package:win
```

`package:setup` 会从配置的镜像下载 Electron，根据 Electron 包内的 `checksums.json` 校验，并安装隔离的 Python 打包依赖。`package:win` 会构建前端/后端、生成 NSIS 安装包，并运行产物完整性检查。

产物输出到：

```text
release/installers/MemWeave-0.2.0-Setup.exe
release/installers/MemWeave-0.2.0-Setup.exe.blockmap
```

发布前请运行 `npm test`、前端 typecheck/lint/build 以及 `npm run package:verify`。
