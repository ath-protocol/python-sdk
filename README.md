# Python SDK for ATH 可信协议

> 🐍 让你的Python AI项目快速获得可信交互能力

**[English README](README.en.md)**（英文版说明）

## 🎯 项目简介

这是 ATH 可信代理握手协议的官方 Python 开发工具包，完美适配 Python AI 开发生态，让你的大模型应用、数据分析脚本、自动化工具都能快速接入 ATH 可信体系。

本 SDK 与 [TypeScript SDK](https://github.com/ath-protocol/typescript-sdk) 的客户端 API 保持一致，并与 [Agent Trust Handshake 协议](https://github.com/ath-protocol/agent-trust-handshake-protocol) 的 JSON Schema（`schema/0.1`，本仓库 `schema/ath-protocol.schema.json`）对齐。实现细节（如令牌交换时的二次 `agent_attestation`、`revoke` 时的客户端认证等）随协议与 TS 参考实现同步更新。

**运行环境：需要 Python 3.10 及以上**（见 `pyproject.toml`）。

## ✨ 核心特性

- ✅ 纯 Python 实现，没有系统依赖，安装即用
- ✅ 同时支持同步和异步 API，满足不同性能需求
- ✅ 完整的类型注解，支持 mypy 静态检查
- ✅ 内置基于标准库的 JWT（ES256）代理身份证明，无需额外系统加密库
- ✅ 覆盖网关模式（`ATHGatewayClient`）与原生模式（`ATHNativeClient`）的完整协议流程
- ✅ 可在业务代码中按需封装工具类或 LangChain Tool（SDK 提供底层客户端）
- ✅ 与 LangChain、LlamaIndex 等框架组合使用时，只需在工具层调用本客户端即可

## 📦 安装方式

```bash
pip install ath-protocol-sdk
```

或使用 poetry 安装：

```bash
poetry add ath-protocol-sdk
```

> 若上述名称在 PyPI 上无法安装，请以 `pyproject.toml` 为准使用当前发布名 **`ath-sdk`**：`pip install ath-sdk` / `poetry add ath-sdk`。

本地开发可从源码安装：

```bash
pip install -e '.[dev]'
```

## 🚀 3 步快速上手（网关模式）

以下为与当前 `ath` 包一致的用法：发现网关 → 注册代理 → 用户授权后交换令牌 → 调用代理 API。

### 第一步：初始化客户端

```python
from ath import ATHGatewayClient

client = ATHGatewayClient(
    "https://your-ath-gateway.com",  # ATH 网关基地址（与 TS 的 `url` 一致）
    "https://your-agent.example.com/.well-known/agent.json",  # 代理 canonical agent_id（URI）
    open("agent-ec-private.pem").read(),  # PEM 格式的 EC P-256 私钥
    key_id="default",  # 可选，对应 JWT header 的 kid
)
```

### 第二步：注册并完成用户授权与令牌交换

```python
# 发现网关目录（可选，便于读取可用 provider）
client.discover()

# Phase A：向网关注册代理
reg = client.register(
    developer={"name": "示例公司", "id": "dev-001"},
    providers=[{"provider_id": "target-provider", "scopes": ["user:read"]}],
    purpose="说明本次接入用途",
)

# Phase B：发起授权，得到用户浏览器应打开的 authorization_url
auth = client.authorize("target-provider", ["user:read"])
# 用户在 IdP 完成授权后，从回调中取得 code，再与 ath_session_id 一起换令牌：
token = client.exchange_token(code="授权码", session_id=auth.ath_session_id)
print(f"访问令牌: {token.access_token}")
```

### 第三步：访问服务（经网关代理）

```python
# 使用 access_token 经网关访问上游 API（网关模式）
data = client.proxy("target-provider", "GET", "/v1/profile")
print(data)

# 用毕可撤销当前令牌
client.revoke()
```

**异步用法**：使用 `AsyncATHGatewayClient` / `AsyncATHNativeClient`，方法名相同，调用前加 `await`。**原生模式**：使用 `ATHNativeClient`，`discover()` 后通过 `api(method, path)` 访问服务发布的 `api_base`。

## 🌟 LangChain集成示例

只需几行代码，就能让你的LangChain Agent获得可信交互能力：

> 说明：若你直接使用本仓库的 `ath` 包，请在 Tool 内自行持有 `ATHGatewayClient` 并调用其 `register` / `authorize` / `exchange_token` / `proxy`；下面保留原有示例结构，便于与官方集成教程对照。

```python
from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import ChatOpenAI
from ath_sdk.langchain import ATHTool
# 包装一个需要ATH认证的服务
ath_tool = ATHTool(
    name="用户数据查询",
    description="查询用户的基本信息",
    client=client,
    service_id="user-service",
    endpoint="https://api.example.com/user/info"
)
# 初始化Agent
llm = ChatOpenAI(temperature=0)
agent = initialize_agent(
    [ath_tool],
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)
# Agent会自动完成握手、授权、访问的全部流程
response = agent.run("查询用户ID为123的基本信息")
```

## 🎯 适用场景

- 🤖 大模型应用开发
- 📊 数据分析服务接入
- 🧠 机器学习模型集成
- ⚙️ 自动化脚本开发
- 🔧 后端服务开发

## 📖 文档资源

- [完整 API 文档](https://athprotocol.dev/docs/sdk/python)
- [LangChain 集成教程](https://athprotocol.dev/docs/integrations/langchain)
- [示例项目](https://github.com/ath-protocol/python-sdk/tree/main/examples)（含 `examples/README.md`）

### 端到端测试（E2E）

`tests/test_e2e.py` 在**真实 HTTP** 下跑完整网关流程；**仅 OAuth2 IdP 为最小 mock**（`auto_approve=true`），网关与上游 API 由 `scripts/e2e_gateway_stack.mjs` 启动，底层为 `typescript-sdk` 里已构建的 `@ath-protocol/server`。

```bash
# 需已克隆 ath-protocol/typescript-sdk 到本仓库旁的 typescript-sdk/ 目录
make e2e
```

或手动：先 `pnpm -C typescript-sdk install && pnpm -C typescript-sdk run build`，再 `OAUTH_PORT=18100 GATEWAY_PORT=18101 UPSTREAM_PORT=18102 node scripts/e2e_gateway_stack.mjs`，然后 `ATH_GATEWAY_URL=http://127.0.0.1:18101 python3 -m pytest tests/test_e2e.py -v`。设置 `ATH_E2E_AUTO_STACK=1` 可在 pytest 会话开始时尝试自动构建并拉起栈（见 `tests/conftest.py`）。

## 🤝 与其他组件的关系

```
你的Python项目 → 本SDK → ATH网关 → 后端服务
```

本 SDK 封装协议规定的 HTTP 与 JWT 细节，你只需按业务流程调用 `register` / `authorize` / `exchange_token` 等接口即可。

## 📄 开源协议

本项目采用 **OpenATH License** 开源协议，具体条款请查看 [LICENSE](LICENSE) 文件。
