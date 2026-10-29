# VoiceFrame

**本地优先的视频配音工作台：打磨声音，也对齐每一刻。**

[English](README.md) · [详细构建计划](docs/PROJECT_PLAN.md) · [架构说明](docs/ARCHITECTURE.md) · [AWS 部署](deploy/aws/README.md)

把之前分散在终端中的步骤集中到网页：上传视频、准备字幕、选择音色、编辑读法、校准同步、确认试听，再导出最终视频。

## 🌍 一个世界，多种声音

**10 种语言 · 10 个场景 · 向世界问好。**

*One World, Many Voices* 展示短片的创意分镜：用一句问候和一种声音气质，连接每个地方。

| 语言 | 场景 | 字幕 / 口播问候 | 声音方向 |
| :--- | :--- | :---: | :--- |
| **英语** | 伦敦 · 泰晤士河畔 | Hello | 男声 · 温暖 |
| **普通话** | 桂林 · 山水之间 | 你好 | 女声 · 温柔 |
| **印地语** | 日出时分的泰姬陵 | नमस्ते | 男声 · 热情亲切 |
| **西班牙语** | 塞维利亚 · 阳光广场 | Hola | 女声 · 俏皮 |
| **法语** | 巴黎 · 塞纳河畔 | Bonjour | 男声 · 轻柔优雅 |
| **阿拉伯语** | 佩特拉 · 砂岩建筑 | <span dir="rtl">مرحبًا</span> | 女声 · 自信 |
| **孟加拉语** | 孟加拉国 · 河流与绿色乡野 | নমস্কার | 男声 · 沉思 |
| **葡萄牙语** | 里约 · 海岸线 | Olá | 女声 · 欢快 |
| **俄语** | 圣彼得堡 · 运河 | Привет | 男声 · 浑厚，有电影感 |
| **乌尔都语** | 拉合尔 · 灯火中的建筑 | <span dir="rtl">السلام علیکم</span> | 女声 · 温暖 |

> [!NOTE]
> 这是创意方案，不是已验证的语言支持列表，也不表示该视频由 VoiceFrame 生成。语言支持和音色控制取决于所选引擎与模型；请先逐种语言试听，再生成全片。

## 当前状态

0.1 版是**单用户、自托管应用**。API、字幕处理、缓存和真实 FFmpeg 合成已使用测试音频验证；Mac MLX 和 Windows/Linux PyTorch 的真实声音推理仍需在对应硬件上验证。跨平台 CI 已配置，不代表已经在 GitHub 运行。尚未创建 AWS 资源。

优先支持 **Apple Silicon Mac、Windows、Linux**。Intel Mac 后续再做。

## 功能

- 项目持久保存、显式保存和版本冲突检查。
- 上传视频并通过 FFprobe 检查格式、音视频轨和真实时长。
- 上传 SRT/VTT，提取内嵌文本字幕轨，可选画面字幕 OCR、原声转写。
- 字幕原文与实际读法分开；支持项目发音词典、逐句覆盖、多音字与数学公式读法。
- Qwen3-TTS 预设音色、参考声音克隆；参考音频需 3–30 秒及准确文字。
- 单独试听音色、生成带画面试听、正负时间偏移和画面锚点校准。
- 任务进度、取消、重试、逐句缓存；一次只运行一个语音任务。
- 预览确认后才生成全片；修改配置后需要重新确认。
- 导出 MP4、WAV、校准后 SRT；保留原始文件。
- 中英文界面；代码与 API 字段使用英文。
- 可选访问密钥登录、媒体访问保护、同源写入校验和路径范围限制。

## 快速启动

需要 **Python 3.11 或更新版本、FFmpeg（含 ffprobe）**，以及模型和视频所需的磁盘空间。普通启动不需要 Node.js、订阅或 API Key。首次安装依赖和下载模型需要联网。

### Apple Silicon Mac

如果使用 Homebrew：

```bash
brew install python@3.12 ffmpeg
cd voiceframe
bash start.sh --install-engine
```

启动器会创建独立 `.venv`，安装核心依赖和 MLX-Audio，并打开 `http://127.0.0.1:8765`。之后运行：

```bash
bash start.sh
```

使用原生 ARM64 Python，避免 Rosetta 环境。M3 / 18 GB 建议先生成短片试听，同时关闭其他大型模型进程。当前没有承诺实时性能或给出未经实测的内存数据。

### Windows

安装 Python 3.11+ 时勾选 **Add Python to PATH**；安装 FFmpeg 后新开终端，检查 `python --version`、`ffmpeg -version`、`ffprobe -version`。

在项目目录打开 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 --install-engine
```

也可以双击 `start.bat` 打开界面，再安装语音引擎：

```powershell
.\.venv\Scripts\python.exe scripts\install_engine.py --engine torch
```

NVIDIA 用户应根据驱动，从 [PyTorch 官方安装页面](https://pytorch.org/get-started/locally/)选择合适的 CUDA 构建，并安装到项目虚拟环境中。验证：

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
```

返回 `False` 表示 CPU 模式，生成可能很慢。此版没有实现 AMD、DirectML 或 ROCm 加速。安装成功不等于 GPU 已可用。

### Linux

在已具备 Python 3.11+ 的 Debian/Ubuntu 上：

```bash
sudo apt-get update
sudo apt-get install -y python3-venv ffmpeg libsndfile1
cd voiceframe
bash start.sh --install-engine
```

NVIDIA 用户同样需要合适的 CUDA 版 PyTorch，并检查 `torch.cuda.is_available()`。CPU 可以作为慢速备选。Apple Silicon 应用原生 MLX 路径；本项目的 Linux Docker 容器不能使用 Apple Metal GPU。

### 复用已有模型下载

在启动前，把 `HF_HOME` 指向旧缓存即可，例如之前的 QwenVoice：

```bash
export HF_HOME="$HOME/Documents/QwenVoice/.cache/huggingface"
bash start.sh --install-engine
```

默认仍使用独立 Python 环境。可通过 `VOICEFRAME_PYTHON=/实际路径/python` 指定已有解释器，但启动器会向其中安装核心依赖，可能影响该环境里的其他应用，因此优先推荐只复用模型缓存。

想继续使用之前满意的主讲音色：在声音页面上传旧项目中的 `reference.wav`，并从旧 `voice_config.json` 复制参考文字。本项目源码不包含你的私人视频或参考录音。

## 完整使用流程

1. **新建项目，上传原视频。** 更换视频会清空原有字幕列表。文件保存在你运行服务的机器上。
2. **导入或识别字幕。** 内嵌文本字幕轨、画面 OCR、原声转写是不同功能。识别结果需要校对，尤其是数学符号、字母和时间。
3. **设置音色。** 预设走 CustomVoice；参考克隆走 Base，不同时应用预设 speaker 与风格指令。首次使用会下载模型，切换模式可能下载第二个模型。
4. **调整读法。** 词典每行 `原文 => 读法`，例如 `2^n => 二的n次幂`。长词优先、不递归替换。单句“实际读法”优先于词典，字幕原文保持独立。拼写替换是模型提示，不能保证音素级控制。
5. **校准画面。** 选择一条字幕，将原视频暂停在它刚出现的画面，点击“用当前画面校准所选字幕”。正偏移让声音延后。再检查视频后面的位置；如果偏差逐渐增大，应逐句调整时间，不能只移动整条音轨。
6. **生成试听。** 可以指定起点和 3–90 秒时长，范围会扩展到完整包含相交的字幕句。当前是逐条字幕对齐，不是逐字强制对齐。
7. **确认并导出。** 只有当前版本的预览才能批准。全片复用同配置的逐句配音，替换全部原音轨，包括原背景音乐；独立配乐混音留待后续版本。

程序不会为了对齐而裁掉讲话。超时句会尝试最多三次合成，并在设定上限内调速；仍放不下时提供诊断报告。需要检查时间、读法或速度上限，不能为了赶时间随意缩短与烧录字幕对应的文字。

## 可选字幕识别组件

### 画面字幕 OCR

安装 Tesseract；识别中文还需要 `chi_sim` 语言数据。Mac 可使用 Homebrew 的 `tesseract`、`tesseract-lang`；Ubuntu 使用 `tesseract-ocr`、`tesseract-ocr-chi-sim`。Windows 安装 Tesseract 后将其可执行文件目录加入 PATH。

裁剪区域以画面高度比例表示，尽量只包含字幕。默认每 0.5 秒采样一次，时间边界是估计值。复杂数学公式需要人工修正。目前相邻帧按完全相同的文字合并，没有置信度驱动的模糊合并。

### 原声转写

```bash
# Mac / Linux
.venv/bin/python -m pip install 'faster-whisper>=1,<2'
```

```powershell
# Windows
.\.venv\Scripts\python.exe -m pip install "faster-whisper>=1,<2"
```

转写使用 CPU/int8 的 small 模型，首次下载。它识别原音轨中的讲话，不代表画面字幕文字。

## 常见问题

- **FFmpeg 缺失**：确认 ffmpeg 和 ffprobe 都在 PATH，或设置 `FFMPEG_PATH`、`FFPROBE_PATH` 为绝对路径。
- **首个任务较慢**：可能正在下载或加载模型。网页显示任务阶段，但暂不显示 Hugging Face 下载字节进度；可查看终端日志。
- **声音早于字幕**：先测量偏移。不存在适用于所有视频的 2.12 秒修正。
- **某句话放不下**：下载任务诊断报告，检查该句。不会生成截断或漏句的最终视频。
- **取消没有立即生效**：在当前句合成或媒体处理完成后生效。
- **服务重启**：运行中的任务标为已中断，重试会复用完成的句子。
- **保存冲突**：先刷新项目；后端不会静默覆盖新版本。
- **MLX 平台错误**：确认项目 Python 的 `platform.machine()` 返回 `arm64`。
- **端口被占用**：启动时加 `--port 8766`。
- **原视频浏览器无法播放**：建议转换为 H.264/AAC MP4，保持起始时间不变。最终输出已经采用浏览器兼容编码。

## 数据与访问

项目元数据位于 `data/voiceframe.sqlite3`，原始文件、缓存和结果位于 `data/<project-id>/`。可用 `VOICEFRAME_DATA` 修改路径。默认上传上限 1 GB，媒体最长 2 小时；`VOICEFRAME_MAX_UPLOAD_MB` 可调整文件上限。公开部署还应在代理层限制请求体大小，防止 multipart 临时文件先占满磁盘。

同一数据目录只允许一个进程、一个任务 worker，通过文件锁保证。不要启动多个 Uvicorn worker 或多副本共享 SQLite。本版是单用户共享工作空间，不具备多租户隔离。

本地只监听回环地址。远程 HTTPS 部署需要设置：

```text
VOICEFRAME_PUBLIC=1
VOICEFRAME_ACCESS_KEY=至少32位随机密钥
VOICEFRAME_ALLOWED_HOSTS=voice.example.com,127.0.0.1
```

原生启动需要真实环境变量，不会自动读取 `.env`；`.env.example` 仅供参考。AWS Compose 会读取 `deploy/aws/.env`。访问密钥不要提交 Git。公开会话 cookie 带 HttpOnly、Secure、SameSite=Strict，24 小时过期。密钥访问整个工作空间，不是独立用户账号。

备份时先停止服务并复制 data 目录，或者使用 SQLite 一致性备份并同步复制媒体。缓存可以省略后重算。历史合成结果与多次尝试音频会保留，自动清理策略待后续实现。

## Docker 与 AWS

Linux CPU：

```bash
docker compose up --build
```

已配置 NVIDIA Container Toolkit 的 GPU 主机：

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up --build
```

AWS 的 EC2、Caddy HTTPS、持久卷和 Terraform 见 [部署文档](deploy/aws/README.md)。当前提供部署模板，未在真实 AWS 账号部署。实例和磁盘会产生费用，需要你自己的账号、区域、配额及 AMI。

## 测试

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --check app/static/app.js
```

Node.js 只用于可选语法检查。测试音色只存在于测试代码，产品里不能选择。实际验证范围与硬件待测项见 [验证记录](docs/VERIFICATION.md)。

## 获取源码

```bash
git clone https://github.com/medxiaorudan/VoiceFrame.git voiceframe
cd voiceframe
```

然后按照上方对应平台的快速启动步骤操作。私有仓库需要 GitHub 身份验证。

## 许可证

源码采用 [Apache-2.0](LICENSE) 许可证。模型权重和依赖使用各自的许可证。
