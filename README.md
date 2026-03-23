# auto_cpa_register

一个用于 ChatGPT 账号自动注册与补量的 Python 项目，支持：

- 邮箱服务：`tempmail_lol` / `duckmail` / `lamail` / `cfmail`
- 注册后 OAuth 获取 Codex Token
- Token 保存到本地并上传 CPA
- 调度器定时检测账号数量，不足时自动触发注册

---

## 目录结构

- `ncs_register.py`：主注册脚本（支持并发、OAuth、分批上传 CPA）
- `auto_scheduler.py`：自动调度器（定时检测 + 自动触发注册）
- `config.json`：项目运行配置
- `zhuce5_cfmail_accounts.json`：CF 自建邮箱配置（仅 `mail_provider=cfmail` 时使用）

---

## 环境要求

- Python 3.10+
- 依赖：`curl_cffi`

安装示例：

```bash
pip install curl_cffi
```

---

## 配置说明（config.json）

关键字段：

- `mail_provider`：`tempmail_lol` / `duckmail` / `lamail` / `cfmail`
- `proxy`：默认 `http://127.0.0.1:7890`
- `enable_oauth`：是否执行 OAuth 获取 Token
- `oauth_required`：OAuth 失败是否判定注册失败
- `upload_api_url` / `upload_api_token`：CPA 上传接口
- `upload_api_proxy`：CPA 上传单独代理。留空时优先沿用默认代理，失败后自动直连重试；可填 `direct` 强制直连
- `cpa_upload_every_n`：每成功 N 个账号触发一次 CPA 上传（默认 3）
- `lamail_api_base`：LaMail API 根地址，默认 `https://maliapi.215.im/v1`
- `lamail_api_key`：LaMail API Key，可留空；留空时走匿名临时邮箱能力
- `lamail_domain`：可选，指定 LaMail 创建邮箱时使用的域名

示例：

```json
{
  "mail_provider": "tempmail_lol",
  "lamail_api_base": "https://maliapi.215.im/v1",
  "lamail_api_key": "",
  "lamail_domain": "",
  "proxy": "http://127.0.0.1:7890",
  "enable_oauth": true,
  "oauth_required": true,
  "upload_api_url": "http://localhost:8317/v0/management/auth-files",
  "upload_api_token": "YOUR_TOKEN",
  "upload_api_proxy": "direct",
  "cpa_upload_every_n": 3
}
```

> 也支持环境变量覆盖，例如：`PROXY`、`MAIL_PROVIDER`、`LAMAIL_API_BASE`、`LAMAIL_API_KEY`、`LAMAIL_DOMAIN`、`UPLOAD_API_PROXY`、`CPA_UPLOAD_EVERY_N`。

### LaMail 接入说明

LaMail 对应文档：`https://maliapi.215.im/v1/llms.txt`

- 临时邮箱创建：`POST /accounts`
- 拉取邮件列表：`GET /messages?address=...`
- 拉取邮件详情：`GET /messages/{id}`
- 鉴权方式：使用创建邮箱返回的临时 `token` 作为 `Bearer Token`
- 若配置 `lamail_api_key`，创建邮箱时会额外带上 `X-API-Key`

如果要切到 LaMail，最小配置如下：

```json
{
  "mail_provider": "lamail",
  "lamail_api_base": "https://maliapi.215.im/v1",
  "lamail_api_key": "",
  "lamail_domain": ""
}
```

---

## 手动运行注册

```bash
python3 ncs_register.py
```

运行时交互项包括：

1. 代理确认
2. 是否执行预检（连通性检查）
3. 是否清理 CPA 无效号（若配置了 CPA）
4. 注册数量
5. 并发数
6. 每成功多少个账号触发 CPA 上传

---

## 自动调度运行

```bash
python3 auto_scheduler.py
```

调度器逻辑：

- 每隔 `CHECK_INTERVAL_SECONDS` 检测有效账号数
- 小于 `ACCOUNT_THRESHOLD` 时自动调用 `ncs_register.py`
- 自动传入：
  - 默认代理 `http://127.0.0.1:7890`
  - 预检默认 `n`（避免调度阻塞）
  - `cpa_upload_every_n`（默认 3，可在 `AUTO_PARAMS` 改）

---

## 分批上传 CPA 说明

在 `ncs_register.py` 中：

- 每成功 `N` 个账号（`cpa_upload_every_n`）触发一次 `_upload_all_tokens_to_cpa()`
- 任务结束后会再进行一次“收尾上传”，上传剩余不足 N 的 token

这样可以减少本地 token 堆积，并让上传更及时。

---

## 常见问题

### 1) `403` / `csrf 非 JSON`

通常是代理出口被风控拦截。建议：

- 更换高质量代理
- 降低并发到 1 先验证链路
- 使用脚本内预检功能排查

### 2) `OAuth 获取失败（oauth_required=true）`

请查看 OAuth 详细日志（已增强），重点关注：

- `authorize/continue` 状态码与返回 body
- `password/verify` 状态码与返回 body
- sentinel token 生成是否失败

---

## 安全提醒

- 不要在公开仓库提交真实 `upload_api_token`
- 建议使用环境变量注入敏感配置
