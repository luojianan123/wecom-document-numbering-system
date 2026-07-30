# 文件编号系统

第一阶段 Web 应用，包含：

- 企业微信扫码登录。
- 管理员项目初始化和批量生成编码。
- 批量结果先预览，管理员确认后才写入正式编码库。
- 管理员可在项目内通过 AI 新增文件；AI 无法匹配时可手工补码，也可删除文件、编码或整个项目。
- 用户查询、取码和复制编码。
- 文件缺失时修正名称并生成编码。
- 板卡、软件、逻辑及操作系统类按 5 级规则判定。
- 逻辑测试名称按“仿真测试/确认测试”规范化。
- 评审结论报告的完整编码增加 `P-` 前缀。
- Python 固定规则生成 A～H 编号。

## 本地运行

### Windows（无需 Docker 和 Node.js）

在 PowerShell 中运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start-windows.ps1
```

也可以直接双击 `start-windows.cmd`。

脚本会创建独立的 `backend/.venv-win` 虚拟环境并安装后端依赖。后端会同时托管
`frontend/dist` 中已构建的页面，打开 `http://localhost:8088` 即可使用。

### Docker Compose

```bash
docker compose up --build
```

打开 `http://localhost:8088`。默认使用本地模拟身份，便于无企业微信密钥时开发：

- “用户界面”进入编码领取页。
- “管理员界面”进入项目初始化页。

可使用 `samples/文件名称清单.csv` 完成首次项目初始化。
清单中的“文件名称”不要包含项目号，项目号在管理员页面单独填写。

### 分别运行

后端：

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

## 企业微信扫码联调

复制 `.env.example` 为 `.env`，至少配置：

```dotenv
WECOM_AUTH_MODE=live
WECOM_CORP_ID=企业ID
WECOM_AGENT_ID=自建应用AgentID
WECOM_CORP_SECRET=自建应用Secret
WECOM_ADMIN_USER_IDS=管理员UserID
BACKEND_PUBLIC_URL=https://系统域名
FRONTEND_URL=https://系统域名
COOKIE_SECURE=true
SESSION_SECRET=足够长的随机值
```

企业微信后台的 Web 授权回调域必须与系统域名一致。`CorpSecret` 只配置在后端，不写入前端。

## AI 接入

默认 `AI_MODE=rules`，用于本地完成确定性的名称清理和规则联调。接入企业批准的 OpenAI-compatible 模型时配置：

```dotenv
AI_MODE=openai_compatible
AI_API_BASE_URL=https://模型服务地址/v1
AI_API_KEY=模型密钥
AI_MODEL=模型名称
```

模型只输出修正名称和候选字段，最终编码始终由 Python 固定规则生成。

## 验证

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/ruff check app tests migrations

cd ../frontend
npm run build
```
