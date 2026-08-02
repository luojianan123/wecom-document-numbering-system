# 文件编号系统

第一阶段 Web 应用，包含：

- 企业微信扫码登录。
- 管理员项目初始化和批量生成编码。
- 批量结果先预览，管理员确认后才写入正式编码库。
- 管理员可在项目内通过 AI 新增文件；AI 无法匹配时可手工补码，也可删除文件、编码或整个项目。
- 用户查询、取码和复制编码。
- 用户输入名称会拒绝纯数字、重复字符、网址、表情、特殊符号和明显无关内容。
- 同项目内执行标准化查重和相似名称检测；正常名称直接生成编号，明显异常、相似名称及特殊编号项目提交管理员审核。
- 管理员修改并确认正确名称后，系统才生成编号并返回给申请用户。
- 管理员可将项目标记为“特殊编号项目”。管理员自行新增文件仍按正常规则编号；普通用户申请新编号时转管理员人工编号，并支持该项目自己的编号格式。
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

脚本会创建独立的 `backend/.venv-win` 虚拟环境、安装后端依赖并自动执行数据库迁移。后端会同时托管
`frontend/dist` 中已构建的页面，打开 `http://localhost:8088` 即可使用。

### Docker Compose

```bash
docker compose up --build
```

打开 `http://localhost:8088`。Docker 环境默认使用持久化 SQLite 数据卷，无需单独部署数据库。
默认使用本地模拟身份，便于无企业微信密钥时开发：

- “用户界面”进入编码领取页。
- “管理员界面”进入项目初始化页。

可使用 `samples/文件名称清单.csv` 完成首次项目初始化。
清单中的“文件名称”不要包含项目号，项目号在管理员页面单独填写。

### 生产环境 HTTPS

公网仅开放自定义端口时，生产环境使用 `acme.sh` 的阿里云 DNS-01
自动申请和续期证书，由 Nginx 在 `WEB_PORT` 上提供 HTTPS：

```bash
install -d -m 700 /opt/filecode-system/secrets
# 将 AccessKey ID 和 Secret 分别写入 aliyun_dns_key、aliyun_dns_secret
chmod 600 /opt/filecode-system/secrets/aliyun_dns_*
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

生产 `.env` 至少需要：

```dotenv
APP_ENV=production
CERT_DOMAIN=pivot.ucas.com.cn
WEB_PORT=24088
FRONTEND_URL=https://pivot.ucas.com.cn:24088
BACKEND_PUBLIC_URL=https://pivot.ucas.com.cn:24088
CORS_ORIGINS=https://pivot.ucas.com.cn:24088
COOKIE_SECURE=true
WECOM_AUTH_MODE=live
```

阿里云 AccessKey 仅通过 Docker secrets 提供给证书容器，不会进入 Web
或后端容器。ACME 账户、证书和私钥保存在独立数据卷中，容器重建后仍会保留；
Nginx 检测到续期后的证书文件变化会自动安全重载。

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
WECOM_ADMIN_USER_IDS=jingping.li,luojianan
BACKEND_PUBLIC_URL=https://系统域名
FRONTEND_URL=https://系统域名
COOKIE_SECURE=true
SESSION_SECRET=足够长的随机值
```

企业微信后台的 Web 授权回调域必须与系统域名一致。`CorpSecret` 只配置在后端，不写入前端。多个管理员 UserID 使用英文逗号分隔；管理员会收到新编号申请提醒，审核通过后申请人会收到结果提醒。

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
