# Python SDK for ATH 可信协议
> 🐍 让你的Python AI项目快速获得可信交互能力
## 🎯 项目简介
这是ATH可信代理握手协议的官方Python开发工具包，完美适配Python AI开发生态，让你的大模型应用、数据分析脚本、自动化工具都能快速接入ATH可信体系。
本SDK完全对标TypeScript SDK的功能，API设计保持一致，同时兼容Python 3.8及以上版本，完美适配LangChain、AutoGPT、 LlamaIndex等主流AI框架。
## ✨ 核心特性
- ✅ 纯Python实现，没有系统依赖，安装即用
- ✅ 同时支持同步和异步API，满足不同性能需求
- ✅ 完整的类型注解，支持mypy静态检查
- ✅ 内置加密算法，不需要额外安装系统库
- ✅ 自动令牌管理，自动刷新过期令牌
- ✅ 提供装饰器，几行代码就能给现有接口加上ATH认证
- ✅ 完美适配LangChain、AutoGPT等主流AI框架
## 📦 安装方式
```bash
pip install ath-protocol-sdk
```
或者使用poetry安装：
```bash
poetry add ath-protocol-sdk
```
## 🚀 3步快速上手
### 第一步：初始化客户端
```python
from ath_sdk import ATHClient
client = ATHClient(
    gateway_url="https://your-ath-gateway.com",  # 你的ATH网关地址
    agent_id="your-agent-id",  # 你的AI代理ID
    private_key="your-agent-private-key"  # 你的AI代理私钥
)
```
### 第二步：发起握手请求
```python
# 申请访问某个服务的权限
handshake_result = client.handshake(
    service_id="target-service-id",  # 要访问的服务ID
    permissions=["user:read", "data:write"],  # 需要的权限列表
    expires_in=3600  # 权限有效期，单位秒
)
if handshake_result.approved:
    print(f"握手成功！获得访问令牌: {handshake_result.access_token}")
else:
    print(f"握手被拒绝: {handshake_result.reason}")
```
### 第三步：访问服务
```python
# 使用获得的令牌访问服务
response = client.request(
    "https://your-service-api.com/data",
    method="GET",
    headers={"Authorization": f"Bearer {handshake_result.access_token}"}
)
print(f"服务返回结果: {response.json()}")
```
## 🌟 LangChain集成示例
只需几行代码，就能让你的LangChain Agent获得可信交互能力：
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
- [完整API文档](https://athprotocol.dev/docs/sdk/python)
- [LangChain集成教程](https://athprotocol.dev/docs/integrations/langchain)
- [示例项目](https://github.com/ath-protocol/python-sdk/tree/main/examples)
## 🤝 与其他组件的关系
```
你的Python项目 → 本SDK → ATH网关 → 后端服务
```
本SDK封装了所有的协议实现细节，你不需要了解复杂的加密、认证流程，专注于业务逻辑即可。
## 📄 开源协议
本项目采用 **OpenATH License** 开源协议，具体条款请查看LICENSE文件。
