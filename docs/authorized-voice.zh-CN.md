# 授权声音输出

MemWeave 可以把已经写好的回复交给外部 IndexTTS2 服务朗读。这个功能默认关闭，也不参与记忆提取、事实判断或回复措辞。

实际顺序是：MemWeave 先根据允许使用的证据生成固定 `reply_text`，经过运行时边界检查后，再把这段文字交给声音适配器。IndexTTS2 不能选择记忆、补充事实、改写回复，也不能绕过授权。

## 需要准备什么

- 单独安装的 IndexTTS2 源码、Python 环境和模型 checkpoints；
- 一个符合下文接口约定的 HTTP 适配器；
- `backend/.env` 中的声音配置；
- 当前人物档案下已授权的音频或视频参考；
- 使用视频参考时需要 FFmpeg。

源码仓库不包含 IndexTTS2、适配器 `server.py`、模型权重、声音参考或生成音频。Python、CUDA 和 checkpoints 的安装请以 [IndexTTS 上游仓库](https://github.com/index-tts/index-tts) 为准。能否运行仍取决于本机硬件和上游依赖，MemWeave 不替上游环境做兼容性保证。

## 配置后端

在 `backend/.env` 中加入：

```env
ENABLE_VOICE_GENERATION=true
VOICE_GENERATION_PROVIDER=indextts2
VOICE_GENERATION_BASE_URL=http://127.0.0.1:7861
VOICE_GENERATION_TIMEOUT_SECONDS=180
VOICE_REFERENCE_DIR=data/voice_references
VOICE_OUTPUT_DIR=data/voice_outputs
VOICE_VIDEO_FFMPEG_PATH=ffmpeg
VOICE_VIDEO_EXTRACT_TIMEOUT_SECONDS=120
```

`VOICE_GENERATION_BASE_URL` 只填适配器的基础地址，不要带 `/synthesize`、`/tts` 或 `/generate`，这些路径由 MemWeave 自动追加。

参考文件和输出目录如果使用相对路径，会从 `backend` 目录解析。修改 `backend/.env` 后要重启后端或桌面壳，正在运行的进程会缓存配置。

当前设置页只能查看声音服务和 FFmpeg 状态，不能直接编辑这些字段。真实配置仍以 `backend/.env` 为准。

## 启动适配器

可以自己管理适配器，也可以按 Electron 桌面壳约定的目录准备本地环境，让桌面壳尝试启动。

### 让桌面壳启动

目录必须符合：

```text
indextts2/
  server.py
  index-tts/
    .venv/
      Scripts/python.exe
    checkpoints/
      config.yaml
      ...模型文件
```

`server.py` 需要暴露 FastAPI 兼容的 `app`。桌面壳执行的命令是：

```text
python -m uvicorn server:app --host 127.0.0.1 --port 7861
```

完整路径分别是 `indextts2/server.py` 和 `indextts2/index-tts/checkpoints/config.yaml`。

命令在 `indextts2/` 下运行，但使用 `indextts2/index-tts/` 里的 Python 环境和 checkpoints。如果项目路径包含中文等非 ASCII 字符，桌面壳会先建立一个临时 ASCII junction，再从该路径启动。

桌面壳会先检查 `http://127.0.0.1:7861/health`。已有健康服务会直接复用；缺少 checkpoints 或 Python 时只显示可选警告，不会阻止 MemWeave 其他功能启动。

可以在启动桌面壳前设置这些进程变量：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `DESKTOP_INDEXTTS2_PORT` | `7861` | 桌面壳检查和启动的端口 |
| `INDEXTTS2_DEVICE` | `cuda` | 传给适配器的设备 |
| `INDEXTTS2_USE_FP16` | `false` | 传给模型的可选参数 |
| `INDEXTTS2_USE_CUDA_KERNEL` | `false` | 传给模型的可选参数 |
| `INDEXTTS2_USE_DEEPSPEED` | `false` | 传给模型的可选参数 |

如果修改 `DESKTOP_INDEXTTS2_PORT`，还要把 `VOICE_GENERATION_BASE_URL` 改成同一个端口。

### 自己启动适配器

只使用 Web 工作台时，不必遵守桌面目录。任何实现下文接口约定的本地或远程服务都可以作为适配器，然后把 `VOICE_GENERATION_BASE_URL` 指向它。

当前请求会传递本机参考音频路径，因此默认流程适合本地适配器。远程服务无法直接读取这个路径，除非你另外实现安全的文件上传或共享存储层。不要把本地声音服务直接暴露到公网。

## 适配器接口约定

MemWeave 按顺序尝试：

1. `POST /synthesize`
2. `POST /tts`
3. `POST /generate`

遇到 404 会继续尝试下一个端点；其他错误会合并到 `IndexTTS2 adapter call failed`。

请求示例：

```json
{
  "text": "已经确定的回复文字",
  "prompt_audio": "E:/path/to/reference.wav",
  "reference_audio": "E:/path/to/reference.wav",
  "audio_path": "E:/path/to/reference.wav",
  "emotion": null,
  "return_base64": true,
  "ai_generated": true
}
```

支持以下响应：

- 直接返回 `audio/*`；
- 返回 RIFF/WAV 字节；
- JSON 中提供 `audio_base64`、`audio` 或 `wav_base64`；
- JSON 中提供 `audio_url` 或 `url`。

`/health` 主要供桌面壳检查。健康接口通过只说明 HTTP 进程可访问，不代表模型一定能完成合成。最终应在 Voice Studio 里实际生成一次预览。

## 为视频参考准备 FFmpeg

直接上传音频不需要 FFmpeg。使用视频参考时，可以把 FFmpeg 加入 `PATH`、把 `VOICE_VIDEO_FFMPEG_PATH` 指向可执行文件，或运行：

```powershell
npm run voice:prepare-ffmpeg
```

脚本会把 `ffmpeg.exe` 放到 Git 已忽略的 `tools/ffmpeg/`。MemWeave 会保留原视频 raw source，再抽取一份 WAV 供 TTS 使用。如果抽取失败，原视频仍会保存，但声音生成会继续保持阻塞。

## 检查配置状态

重启后端后运行：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/voice/status
```

适配器配置正确时，至少应看到：

```text
enabled: true
configured: true
base_url: http://127.0.0.1:7861
```

设置页还会显示：

- IndexTTS2 是否开启、是否已配置接口；
- FFmpeg 是否可用；
- 系统自检中的声音服务状态。

系统自检只检查配置是否就绪，不会上传参考文件，也不会执行真实合成。

## 在 Voice Studio 中使用

1. 在 Chat 中选择活动人物档案。
2. 上传音频或视频参考，单个文件最大 100 MB。
3. 确认自己有权使用这段声音，并填写授权备注。
4. 如果上传视频，等待抽取音频；配置 FFmpeg 后也可以重试。
5. 确认片段属于目标人物，并允许 `voice_reference` 或 `voice_generation` 用途。
6. 选中这条参考声音，或设为当前人物默认参考。
7. 生成预览，或朗读一条已经生成的聊天回复。
8. 对本次生成再次确认同意。

如果请求带有 `chat_record_id`，`reply_text` 必须与对应记录的 `assistant_message` 完全一致，不能在送入 TTS 前另行改写。生成结果会记录为 AI generated，界面展示时也必须保留这一标记。

## 常见问题

| 提示或现象 | 检查方法 |
| --- | --- |
| `Voice generation is disabled.` | 把 `ENABLE_VOICE_GENERATION` 设为 `true`，然后重启后端。 |
| `IndexTTS2 endpoint is not configured.` | 填写不带端点后缀的 `VOICE_GENERATION_BASE_URL`，然后重启。 |
| `IndexTTS2 adapter call failed` | 查看每个端点后的错误，确认适配器至少实现一个支持的端点，并按支持格式返回音频。 |
| 7861 端口被占用，但适配器没有响应 | 停止无关进程，或同时修改桌面端口和后端 Base URL。 |
| 缺少 checkpoints 或 IndexTTS2 Python | 补全桌面目录，或自行启动一个兼容适配器。 |
| health 正常，但真实合成失败 | 查看适配器日志、上游模块导入、checkpoint 路径、设备/CUDA 兼容和第一次合成错误。 |
| 视频参考未就绪 | 运行 `npm run voice:prepare-ffmpeg`，配置其他 FFmpeg 路径，或直接上传音频。 |
| 片段归属或授权未确认 | 在 Voice Studio 或 Library 中确认目标人物、归属、片段授权和允许用途。 |
| `reply_text must match...` | 直接朗读选中的 assistant message，不要先修改文字。 |

## 不要提交运行文件

以下内容都应留在本地：

- `backend/.env`；
- `backend/data/voice_references/`；
- `backend/data/voice_outputs/`；
- `indextts2/`；
- `tools/ffmpeg/`；
- 模型 checkpoints、真实参考音视频、生成样本、日志、数据库和授权记录。

撤销或删除声音参考后，后续生成会被阻止，派生记录也会按当前清理流程移除。
