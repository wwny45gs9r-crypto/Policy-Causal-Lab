# Policy Causal Lab

Policy Causal Lab 是一个因果推断工作台，而不是通用实证论文生成器。系统围绕因果问题、反事实构造、处理分配机制、识别策略、数据可识别性、估计诊断和因果效应解释边界，帮助用户判断一个研究问题是否能够被可靠地解释为因果关系。

## 技术栈

- 前端：Next.js、React、TypeScript
- 后端：FastAPI、SQLAlchemy
- 数据库：PostgreSQL；未配置 `DATABASE_URL` 时默认使用 SQLite 便于本地体验
- LLM：DeepSeek OpenAI SDK 兼容接口，API Key 只从后端环境变量读取
- 系统知识库：老师课程资料作为后台 System Knowledge Base，普通用户不可直接查看或调用

## 普通用户工作流

1. 因果问题定义 Causal Question
2. 变量与因果结构 Variable & Causal Structure
3. 反事实构造 Counterfactual
4. 处理分配机制 Assignment Mechanism
5. 识别策略选择 Identification Strategy
6. 数据上传与可识别性检查 Data & Identifiability Check
7. 估计设定确认 Estimation Setup
8. 模型估计 Estimation Runner
9. 识别假设诊断 Assumption Diagnostics
10. 因果效应解释 Causal Effect Interpretation
11. 稳健性与敏感性分析 Robustness & Sensitivity
12. 因果推断报告 Causal Inference Report
13. 审计日志 Audit Log
14. 任务状态 Task Status

关键步骤都需要用户确认；用户反馈、修改、重新运行和系统风险提示都会写入 `AuditLog`。

## 管理员工作流

管理员后台访问：

```text
http://localhost:3000/admin
```

管理员功能包括：

- 系统知识库管理
- Gitee 课程资料同步
- Prompt 模板管理
- DeepSeek 模型配置

普通用户不能访问课程资料全文、系统 Prompt 或系统知识库检索入口。

## 系统知识库

默认课程资料源：

```text
https://gitee.com/zhiyuanryanchen/causal-inference-machine-learning
```

同步方式：

1. 前端开发环境设置 `NEXT_PUBLIC_ENABLE_DEV_ADMIN=true`
2. 打开 `/admin`
3. 在「系统知识库」中添加默认 Gitee 仓库并同步

系统会解析 `.md`、`.txt`、`.pdf`、`.docx`、`.pptx`，切分为 chunk，并作为 DeepSeek 的 hidden context。普通用户响应不会暴露课程全文；审计日志只保存引用元数据。

## DeepSeek 配置

在 `backend/.env` 中设置：

```dotenv
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DATABASE_URL=postgresql://policy_lab:policy_lab@localhost:5432/policy_lab
JWT_SECRET_KEY=replace_this_with_a_secure_random_string
FRONTEND_ORIGIN=http://localhost:3000
STORAGE_BACKEND=local
ENV=development
```

DeepSeek 调用集中封装在：

```text
backend/app/services/deepseek_client.py
```

API Key 不会进入前端代码或浏览器。

## 本地启动

安装依赖：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm install
```

分别启动：

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend
cp .env.example .env.local
npm run dev
```

访问：

- 普通用户工作台：`http://localhost:3000`
- 管理员后台：`http://localhost:3000/admin`
- FastAPI 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/api/health`
- 示例 API：`http://localhost:8000/api/hello`

一键启动：

```bash
./scripts/start-local.sh
```

## 数据库迁移

本地 MVP 启动时会执行 `Base.metadata.create_all`，新表可自动创建。生产环境建议使用 Alembic：

```bash
cd backend
source .venv/bin/activate
alembic revision --autogenerate -m "causal workflow"
alembic upgrade head
```

`DATABASE_URL` 统一从环境变量读取。本地未配置时使用 SQLite fallback；线上请使用 PostgreSQL。Render、Railway、Neon、Supabase 等平台提供的 `postgresql://...` 连接串可直接使用，后端会自动转换为 SQLAlchemy 使用的 `postgresql+psycopg://...` 驱动格式。

## 公网部署

本项目是前后端分离的 Web 应用，不适合用 GitHub Pages 部署完整系统。GitHub Pages 只能托管静态文件，不能运行 FastAPI、数据库、文件上传或 DeepSeek API 调用。

### 前端部署到 Vercel

1. 将项目推送到 GitHub。
2. 在 Vercel 选择 Import Git Repository。
3. Root Directory 选择 `frontend`。
4. Build Command 使用 `npm run build`。
5. Output 使用 Next.js 默认配置。
6. 配置环境变量：

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://policy-causal-lab-api.onrender.com
NEXT_PUBLIC_ENABLE_DEV_ADMIN=false
```

部署完成后，浏览器访问 Vercel 分配的地址，例如：

```text
https://your-project.vercel.app
```

前端所有 API 请求都会通过 `NEXT_PUBLIC_API_BASE_URL` 访问后端，例如 `https://policy-causal-lab-api.onrender.com/api/projects`。

### 后端部署到 Render

推荐先在 Render 创建 PostgreSQL，再创建 Web Service。

1. New PostgreSQL，记录 Internal Database URL 或 External Database URL。
2. New Web Service，连接 GitHub 仓库。
3. Root Directory 选择 `backend`。
4. Build Command：

```bash
pip install -r requirements.txt
```

5. Start Command：

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

6. 配置环境变量：

```dotenv
DATABASE_URL=<Render PostgreSQL connection string>
DEEPSEEK_API_KEY=<your DeepSeek API key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
JWT_SECRET_KEY=<secure random string>
FRONTEND_ORIGIN=https://your-project.vercel.app
STORAGE_ROOT=storage/projects
STORAGE_BACKEND=local
ENV=production
```

7. 如果使用 Alembic 初始化数据库，在 Render Shell 或一次性 Job 中运行：

```bash
alembic upgrade head
```

仓库根目录提供了 `render.yaml`，可作为 Render Blueprint 起点；`backend/Procfile` 也保留了同样的生产启动命令。

### Railway、Fly.io 和其他平台

后端只需要能运行 Python Web Service，并提供 `PORT`、`DATABASE_URL`、`FRONTEND_ORIGIN` 等环境变量即可。启动命令仍是：

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

数据库建议使用平台自带 PostgreSQL、Neon 或 Supabase。把连接串填入后端 `DATABASE_URL`，不要写入代码。

## Docker Compose

本地也可以用 Docker Compose 同时启动 PostgreSQL、后端和前端：

```bash
docker compose up --build
```

访问：

- 前端：`http://localhost:3000`
- 后端健康检查：`http://localhost:8000/api/health`
- 后端文档：`http://localhost:8000/docs`

## 环境变量清单

前端：

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_ENABLE_DEV_ADMIN=false
```

后端：

```dotenv
DATABASE_URL=postgresql://user:password@host:5432/policy_causal_lab
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
JWT_SECRET_KEY=replace_this_with_a_secure_random_string
FRONTEND_ORIGIN=http://localhost:3000
STORAGE_ROOT=storage/projects
STORAGE_BACKEND=local
ENV=development
```

`DEEPSEEK_API_KEY` 只在后端读取，不能放进 Vercel 前端环境变量。未配置时服务不会崩溃，AI 相关功能会返回明确 warning 或本地占位结果。

## 部署验收

后端是否正常：

```bash
curl https://policy-causal-lab-api.onrender.com/api/health
```

期望返回：

```json
{
  "status": "ok",
  "service": "policy-causal-lab-api"
}
```

前端请求后端失败时，按顺序检查：

- Vercel 的 `NEXT_PUBLIC_API_BASE_URL` 是否是后端公网地址，且不带结尾 `/`。
- Render 的 `FRONTEND_ORIGIN` 是否等于 Vercel 前端地址。
- 后端 `/api/health` 是否可从浏览器直接打开。
- 浏览器 DevTools Network 里失败请求的 URL 是否仍指向 `localhost`。
- Render 日志里是否有数据库连接、迁移或 DeepSeek API 错误。

免费部署平台可能限制：

- Render/Railway 免费实例可能冷启动，首次请求较慢。
- 本地磁盘可能不保证长期稳定保存上传文件。
- 后台长任务、批量估计、大文件解析可能受内存、CPU 和超时限制。
- DeepSeek API 调用耗时较长时，建议后续接入任务队列。

## 文件上传与存储

MVP 默认使用本地文件存储，路径由 `STORAGE_ROOT` 环境变量控制，不能写死到个人电脑目录。当前代码保留了 `StorageService` 抽象，后续可切换为 S3、MinIO 或 Supabase Storage。

生产环境建议尽快替换为对象存储，因为 Render、Railway、Fly.io 等平台的本地磁盘可能不是长期稳定存储。大文件解析、模型估计和报告生成也建议后续接入 Celery、RQ、Dramatiq 或平台任务队列。

## 当前支持的识别策略

已接入或保留：

- OLS
- DID
- Fixed Effects
- PSM
- Event Study

第一版流程中还支持作为识别策略对象管理：

- RCT
- Staggered DID
- PSM-DID
- RDD
- IV / 2SLS
- Synthetic Control
- Doubly Robust
- Descriptive only

## 当前 Placeholder

以下功能已有接口和前端位置，但不会假装真实完成：

- RDD 完整估计
- IV / 2SLS 完整估计
- Synthetic Control 完整估计
- Staggered DID 高级估计
- DID 平行趋势正式检验
- 安慰剂检验
- PSM 平衡性诊断和 Love Plot
- pgvector / Chroma 向量检索
- Celery 任务队列
- 对象存储

## 因果推断报告

报告入口在普通用户工作台第 12 步「因果推断报告」。报告结构为：

1. 因果问题定义
2. 因果结构与变量角色
3. 反事实构造
4. 处理分配机制
5. 识别策略
6. 数据可识别性检查
7. 估计设定与模型结果
8. 识别假设诊断
9. 稳健性与敏感性分析
10. 因果效应解释与边界
11. 可信度评级
12. 结论

系统不得编造政策事实、变量、数据来源、回归结果或检验结果。未完成项会写「尚未完成」或「当前数据不支持」。因果结论必须带识别假设条件。

## 系统限制

- 系统不能替代研究者判断。
- 如果数据不支持识别，系统会输出不可识别或高风险警告。
- 因果结论依赖识别假设、数据质量和诊断结果。
- 系统知识库只是方法论辅助，不代表政策事实来源。
- DeepSeek 负责解释、结构化建议和报告写作；真实数据检查和估计由 Python 后端执行。

## 测试

后端：

```bash
cd backend
source .venv/bin/activate
python -m pytest -q
```

前端：

```bash
cd frontend
npm run build
```
