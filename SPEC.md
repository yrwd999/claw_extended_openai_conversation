# 需求文档：`claw_extended_openai_conversation` 自定义 HA 集成

> **文档定位**：需求规格说明 (SRS)
> **面向对象**：开发工程师（秃头虾）
> **文档状态**：v2.0（已最小化改造 + 完整引用，待 Ray 审批）
> **创建日期**：2026-06-23
> **变更说明**：v1.0 → v2.0 — 严格收敛到"3 文件 / 1 方法 / 7 删"最小化改造，补全所有原始代码引用

---

## 1. 项目背景

### 1.1 问题陈述

当前 Home Assistant 上 MiniMax 对话代理依赖 `extended_openai_conversation` 2.0.2（HACS 安装）。该集成走**自定义 OpenAI 协议路径**，绕开 HA core LLM 框架，导致：

- 虾宝的 71 个 `llm.Tool` 工具**无法被自动注入**给 LLM
- MiniMax 实际只能调用 `execute_services` 一个工具
- 虾宝的能力被严重限制（仅 ~10% 工具可用）

### 1.2 根本原因（已通过官方代码验证）

| 组件 | 走的代码路径 | 71 工具注入 |
|------|------------|------------|
| `openai_conversation`（HA core） | `chat_log.async_provide_llm_data(...)` → HA core LLM 框架 | ✅ 自动 |
| `extended_openai_conversation`（HACS） | `self.client.chat.completions.create(...)`（自拼 OpenAI schema）| ❌ 需手写 spec |

**核心差异** = HA core 路径调一行 `async_provide_llm_data`，extended_openai_conversation 不调这一行。

### 1.3 已排除的方案（避免重复调研）

| 方案 | 排除原因 |
|------|---------|
| A. 改用 `openai_conversation` + OpenAI 官方 API | 不支持自定义 base_url（官方文档明确禁止）|
| B. 改用 OpenRouter → MiniMax 中转 | 引入中介费用 + 中转延迟 |
| C. 维持 extended_openai_conversation 现状 | 8 工具限制未解决 |
| D. 直接修改 `extended_openai_conversation` 源码 | **HACS 升级会覆盖任何本地修改**（已验证 `installed: true, version_installed: 2.0.2`）|
| D'. 手写 60+ function spec YAML | ~2400 行 YAML，持续维护成本高 |

### 1.4 选定方案

**自建 `claw_extended_openai_conversation` 集成 — 严格最小化改造**：
- **基线**：复制 `extended_openai_conversation` 2.0.2 全部文件
- **改 3 个文件**：`manifest.json`（4 字段）+ `const.py`（2 行）+ `conversation.py`（改 1 方法 + 删 8 方法 + 删 1 类）
- **保留 100%**：`__init__.py`、`config_flow.py`、`helpers.py`（含 6 种 `FunctionExecutor` 不删）、`exceptions.py`、`services.py`、`services.yaml`、`strings.json`、`translations/`
- **保留 `AsyncOpenAI(base_url=***)` 客户端**（直连 MiniMax API）
- 部署到 `/config/custom_components/`，不走 HACS（避免升级覆盖）

---

## 2. 项目目标

| 目标编号 | 描述 | 优先级 |
|---------|------|--------|
| GOAL-1 | 虾宝在 MiniMax 对话中可调用全部 71 个工具 | P0 |
| GOAL-2 | MiniMax API 直连不受影响（不走 OpenRouter 中转）| P0 |
| GOAL-3 | HACS 升级 `extended_openai_conversation` 时新集成不被覆盖 | P0 |
| GOAL-4 | 失败时立即回滚到原 `extended_openai_conversation`，HA 端无感知 | P0 |
| **GOAL-5（v2.0 新增）** | **最小化改造** — 仅改 `manifest.json` / `const.py` / `conversation.py` 三个文件 | **P0** |
| **GOAL-6（v2.0 新增）** | **完整引用原始代码** — 秃头虾开发时能精确找到每个方法的原始位置 | **P0** |

---

## 3. 范围界定（In Scope / Out of Scope）

### 3.1 In Scope（本项目必须实现）

| 范围 | 描述 |
|------|------|
| 集成 domain | `claw_extended_openai_conversation`（与 HACS 集成区分）|
| 集成 name | `Claw Extended OpenAI Conversation` |
| 文件位置 | `/config/custom_components/claw_extended_openai_conversation/` |
| 对话处理路径 | HA core ChatLog 框架（`async_provide_llm_data` + 框架循环）|
| LLM 客户端 | `AsyncOpenAI`（保留 `base_url` 参数支持任意 OpenAI-compatible endpoint）|
| 工具注入 | HA core LLM 框架自动收集所有 `llm.Tool`（含 claw_assistant 注册的 71 工具）|
| 配置入口 | 沿用 extended_openai_conversation 的 config_flow（api_key / base_url / model 等）|
| 备份机制 | 修改前**必须**备份原 `extended_openai_conversation`（**Ray 负责**）|

### 3.2 Out of Scope（本项目不实现）

| 排除项 | 理由 |
|--------|------|
| 部署到 `/config/custom_components/` | **由 Ray 单独操作**，不在开发范围 |
| HA 重启操作 | **由 Ray 单独操作** |
| 集成配置（创建 HA 集成实例）| **由 Ray 单独操作** |
| 改 claw_assistant `primary_agent` 配置 | **由 Ray 单独操作** |
| 回归测试执行 | **由 Ray 单独操作** |
| 工具调用协议改动 | HA core LLM 框架已定义，无需改 |
| 7 个 custom executor（native/script/rest/scrape/composite/sqlite）的完整实现 | **不需要** — `llm.Tool` 的 `async_call` 已覆盖所有功能 |
| 新的 `llm.Tool` 实现 | 不在范围 — 71 工具由 claw_assistant 已实现 |
| 提示词模板开发 | 沿用 extended_openai_conversation 现有模板 |

### 3.3 边界规则

- **不修改** HA core 代码（`homeassistant/components/openai_conversation/`）
- **不修改** `extended_openai_conversation` 源码（保留作为 fallback）
- **不修改** claw_assistant 源码（71 工具已实现）
- **不修改** MiniMax API 端点 / API key 配置（沿用现有）

---

## 4. 最小化改造精确范围（v2.0 核心章节）

### 4.1 文件改动总览

> **核心原则**：能复用原始代码的尽量不要动。

| 序号 | 文件 | 行数（基线）| 改动类型 | 改动量 | 引用 |
|------|------|----------|---------|--------|------|
| 1 | `manifest.json` | 24 | **必改** | 改 4 个字段 | [4.2 节](#42-manifestjson-改动明细) |
| 2 | `const.py` | 107 | **必改** | 改 1 行（`DOMAIN`）+ 新增 1 行（`MAX_TOOL_ITERATIONS`）| [4.3 节](#43-constpy-改动明细) |
| 3 | `conversation.py` | 578 | **必改** | 改 1 方法 + 删 8 方法 + 删 1 类（实际删除 249+ 行）| [4.4 节](#44-conversationpy-改动明细) |
| 4 | `__init__.py` | 115 | **100% 复制** | 0 | [4.5 节](#45-initpy-100-复制) |
| 5 | `config_flow.py` | 336 | **100% 复制** | 0 | [4.6 节](#46-config_flowpy-100-复制) |
| 6 | `helpers.py` | 767 | **100% 复制** | 0 | [4.7 节](#47-helperspy-100-复制) |
| 7 | `exceptions.py` | 135 | **100% 复制** | 0 | [4.8 节](#48-exceptionspy-100-复制) |
| 8 | `services.py` | 212 | **100% 复制** | 0 | [4.9 节](#49-servicespy--servicesyaml-100-复制) |
| 9 | `services.yaml` | 62 | **100% 复制** | 0 | [4.9 节](#49-servicespy--servicesyaml-100-复制) |
| 10 | `strings.json` + `translations/` | — | **100% 复制** | 0 | [4.10 节](#410-stringsjson--translations-100-复制) |

**净改动统计**：
- 必改文件：3 个（占总数 30%）
- 100% 复用文件：7 个（占总数 70%）
- 必删代码：8 个方法 + 1 个类 = 249+ 行（基线 conversation.py 第 330-578 行）
- 必改方法：1 个方法 = 97 行（`_async_handle_message` 重写）
- 必新增代码：~30 行（`async_provide_llm_data` 调用 + LLM 循环 + tool_calls 处理）
- **总代码净增** = +30 - 249 = **-219 行**（比基线还少）

### 4.2 manifest.json 改动明细

**引用**：基线位于 `/config/custom_components/extended_openai_conversation/manifest.json`（24 行）

**必改 4 个字段**：

| 字段 | 当前值（基线）| 改后值 | 行号（基线）|
|------|--------|--------|------------|
| `domain` | `"extended_openai_conversation"` | `"claw_extended_openai_conversation"` | 第 2 行 |
| `name` | `"Extended OpenAI Conversation"` | `"Claw Extended OpenAI Conversation"` | 第 3 行 |
| `version` | `"2.0.2"` | `"2.0.2-claw-fork.1"` | 第 22 行 |
| `codeowners` | `["@jekalmin"]` | `["@yrwd999"]` | 第 4-6 行 |

**不动的字段**（完整保留）：
- `config_flow: true`（第 7 行）
- `dependencies: ["conversation", "energy", "history", "recorder", "rest", "scrape"]`（第 8-15 行）
- `documentation` URL（指向 jekalmin 原始仓库 — 标注 fork 来源，第 16 行）
- `integration_type: "service"`（第 17 行）
- `iot_class: "cloud_polling"`（第 18 行）
- `issue_tracker` URL（指向 jekalmin 原始仓库 — 标注 fork 来源，第 19 行）
- `requirements: ["openai~=2.21.0"]`（第 20-22 行）

### 4.3 const.py 改动明细

**引用**：基线位于 `/config/custom_components/extended_openai_conversation/const.py`（107 行）

**必改 1 行 + 新增 1 行**：

| 字段 | 当前值（基线）| 改后值 |
|------|--------|--------|
| `DOMAIN` 常量 | `DOMAIN = "extended_openai_conversation"` | `DOMAIN = "claw_extended_openai_conversation"` |
| `MAX_TOOL_ITERATIONS` | （不存在）| `MAX_TOOL_ITERATIONS = 10`（新增，用于限制 tool_calls 循环次数）|

**如何定位该行**：在基线文件中搜索 `DOMAIN = "extended_openai_conversation"`，唯一匹配。

**不动的部分**（完整保留 106 行）：
- 所有 `CONF_*` 常量（CONF_CHAT_MODEL、CONF_BASE_URL、CONF_PROMPT 等）
- 所有 `DEFAULT_*` 常量（DEFAULT_CHAT_MODEL、DEFAULT_PROMPT、DEFAULT_CONF_FUNCTIONS 等）
- 所有 `EVENT_*` 常量
- 所有 `RECOMMENDED_*` 常量
- 任何 import

### 4.4 conversation.py 改动明细

**引用**：基线位于 `/config/custom_components/extended_openai_conversation/conversation.py`（578 行）

**conversation.py 关键行**：
- 行 101-124 = `__init__` (类初始化，**100% 复用**)
- 行 126-128 = `supported_languages` 属性 (**100% 复用**)
- 行 130-136 = `async_process` (**100% 复用**)
- 行 138-235 = `_async_handle_message` (97 行，**核心改造点 — 必改**)
- 行 241-247 = `_generate_system_message` (**100% 复用**)
- 行 248-260 = `_async_generate_prompt` (**100% 复用**)
- 行 264-289 = `get_exposed_entities` (**100% 复用**)
- 行 290-306 = `get_functions` (17 行，**100% 复用 — 虽不调但保留**)
- 行 308-329 = `truncate_message_history` (22 行，**100% 复用 — 虽不调但保留**)
- **行 330-578 = 7 个方法 + 1 个类（249 行，**全部删除**）**：
  - `query` (330-411, 82 行)
  - `execute_function_call` (412-435, 24 行)
  - `execute_function` (436-480, 45 行)
  - `execute_tool_calls` (481-515, 35 行)
  - `execute_tool_function` (516-550, 35 行)
  - `should_run_in_background` (551-554, 4 行)
  - `get_delayed_function` (555-572, 18 行)
  - `class OpenAIQueryResponse` (573-578, 6 行)

> **行号定位方法**：实际开发时用 `grep -nE 'async def|^    def |^class' /config/custom_components/extended_openai_conversation/conversation.py` 精确定位每个方法。

#### 4.4.1 必改 1 个方法

**`_async_handle_message`**（基线第 138-235 行，97 行）

| 项目 | 内容 |
|------|------|
| 当前职责 | 自维护 `self.history[conversation_id]` 调 `self.query()` + 处理 tool_calls |
| 改后职责 | 调 `chat_log.async_provide_llm_data` + 走 ChatLog 框架循环 |
| 改动方式 | **整方法重写**（不允许部分修改 — 因为核心逻辑完全不同）|
| 必保留片段 | `try/except OpenAIError` 错误处理结构（最终给用户返回 IntentResponse 的部分）|
| 必保留调用 | `get_exposed_entities()`（基线第 144 行 — 改写后仍可调）|
| 必保留生成 | `_generate_system_message()`（基线第 152 行 — 改写后仍可调，用于构造 system prompt 传给 `chat_log.async_provide_llm_data`）|
| 必新增 | `await chat_log.async_provide_llm_data(...)`（**FR-2.1**）|
| 必新增 | LLM 调用循环（最多 10 轮，`MAX_TOOL_ITERATIONS = 10` 在 `const.py` 新增）|
| 必新增 | `chat_log.llm_api.async_call_tool()` 调用（**FR-2.4**）|
| 必新增 | `_format_tool(tool)` 函数（将 `llm.Tool` 转为 OpenAI function schema）|

**必须 100% 保留的方法**（不动的部分）：

| 方法 | 行号（基线）| 改动 |
|------|----------|------|
| `__init__` (类初始化) | 101-124 | 不动 |
| `supported_languages` 属性 | 126-128 | 不动 |
| `async_process` | 130-136 | 不动 |
| `_generate_system_message` | 241-247 | 不动（仍由新 `_async_handle_message` 调用）|
| `_async_generate_prompt` | 248-260 | 不动 |
| `get_exposed_entities` | 264-289 | 不动 |
| `get_functions` | 290-306 | 不动（虽不调，保留无害 — Python 类没人调就是死代码）|
| `truncate_message_history` | 308-329 | 不动（虽不调，保留无害）|

#### 4.4.2 必删 7 个方法 + 1 个类（共 249 行）

> **本节是 v2.0 关键修订**：v1.0 只列了 2 个方法，实际删除范围是 7 个方法 + 1 个类。

| 序号 | 方法/类 | 行号（基线）| 行数 | 删除原因 |
|------|--------|----------|------|---------|
| 1 | `query` | 330-411 | 82 | 整段绕开 ChatLog 的代码（自拼 OpenAI schema + 调 SDK）|
| 2 | `execute_function_call` | 412-435 | 24 | 调 `get_functions()` 找 function spec（基于基线 6 种 executor）|
| 3 | `execute_function` | 436-480 | 45 | 调 `function_executor.execute()`（基线 6 种 custom executor 入口）|
| 4 | `execute_tool_calls` | 481-515 | 35 | 工具调用分发器（调 `execute_function` / `execute_tool_function`）|
| 5 | `execute_tool_function` | 516-550 | 35 | 调 `function_executor.execute()` 处理 OpenAI 工具调用 |
| 6 | `should_run_in_background` | 551-554 | 4 | 辅助方法（仅被 `execute_function` / `execute_tool_function` 调）|
| 7 | `get_delayed_function` | 555-572 | 18 | 辅助方法（仅被 `execute_function` / `execute_tool_function` 调）|
| 8 | `class OpenAIQueryResponse` | 573-578 | 6 | 数据类（仅被 `query` 调返回）|

**删除方式**：直接删除方法/类定义（包括 `async def` / `def` / `class` 关键字、方法体），不留下任何 stub 注释。

**为什么这 7+1 全部要删**（v2.0 关键说明）：
- `query`（基线第 330-411 行）调 OpenAI SDK 直接发请求，**新代码不调**（改用 `self.client.chat.completions.create()` 内联在 `_async_handle_message`）
- `execute_function_call` / `execute_function` / `execute_tool_calls` / `execute_tool_function`（基线第 412-550 行）都是基于基线 6 种 `FunctionExecutor` 的旧工具调用链，**新代码用 `chat_log.llm_api.async_call_tool` 替代**
- `should_run_in_background` / `get_delayed_function`（基线第 551-572 行）是 `execute_function` / `execute_tool_function` 的辅助方法，**新代码不需要**
- `class OpenAIQueryResponse`（基线第 573-578 行）是 `query` 的返回值类型，**新代码不返回它**

**删除前验证清单**（确保不被其他代码引用）：
- `query` 的调用点：基线第 168 行（`_async_handle_message` 内调 `self.query(...)`）— **新代码不调**
- `execute_function_call` / `execute_function` / `execute_tool_calls` / `execute_tool_function` / `should_run_in_background` / `get_delayed_function` 在基线其他位置是否被调？**仅** `_async_handle_message` / `execute_tool_calls` / `execute_function` / `execute_tool_function` 内部调用 — **新代码不调**
- `class OpenAIQueryResponse` 的引用点：基线第 330-411 行（`query` 返回类型）— **新代码不返回它**

#### 4.4.3 conversation.py 改动量

| 改动 | 行数 |
|------|------|
| 删除 `query` 方法 | -82 |
| 删除 `execute_function_call` 方法 | -24 |
| 删除 `execute_function` 方法 | -45 |
| 删除 `execute_tool_calls` 方法 | -35 |
| 删除 `execute_tool_function` 方法 | -35 |
| 删除 `should_run_in_background` 方法 | -4 |
| 删除 `get_delayed_function` 方法 | -18 |
| 删除 `class OpenAIQueryResponse` | -6 |
| **小计（删除）** | **-249** |
| 重写 `_async_handle_message`（97 → ~120 行）| +23 |
| **净变化** | **-226 行** |

### 4.5 __init__.py 100% 复制

**引用**：基线位于 `/config/custom_components/extended_openai_conversation/__init__.py`（115 行）

**为什么 100% 复制**：
- `async_setup_entry` 创建 `AsyncOpenAI` 客户端 — **保留** `base_url` 参数（MiniMax 直连的关键）
- `get_authenticated_client` 辅助函数 — **保留** `is_azure_url` 逻辑
- `async_unload_entry` / `async_update_options` — 标准 HA 集成生命周期，无需改
- `render_image` / `send_prompt` 服务注册 — 标准服务，无需改

**不改任何字符**（除 import 中的 `ExtendedOpenAIConfigEntry` 名称外 — 见下文 4.5.1 注意事项）。

#### 4.5.1 注意事项（不影响"100% 复制"原则）

| 关注点 | 描述 | 处理 |
|--------|------|------|
| Type alias `ExtendedOpenAIConfigEntry` | 基线 `__init__.py` 定义 `type ExtendedOpenAIConfigEntry = ConfigEntry[openai.AsyncClient]` | **保留原名**（不强制重命名为 `ClawExtendedOpenAIConfigEntry` — 那是过度改造）|
| 字符串 `"extended_openai_conversation"` 出现位置 | config_entry 的 domain 标识 | **保持不变** — `runtime_data` 用 AsyncClient 实例，不依赖 domain 名字符串 |

### 4.6 config_flow.py 100% 复制

**引用**：基线位于 `/config/custom_components/extended_openai_conversation/config_flow.py`（336 行）

**为什么 100% 复制**：
- 用户配置流程（填 base_url / api_key / model）保持完全一致
- 用户已有的配置数据（持久化在 `.storage/core.config_entries`）迁移到新集成时字段名相同
- config_flow 内部不依赖 domain 名字符串（HA framework 路由）

**不改任何字符**。

### 4.7 helpers.py 100% 复制

**引用**：基线位于 `/config/custom_components/extended_openai_conversation/helpers.py`（767 行）

**为什么 100% 复制**（含 6 种 `FunctionExecutor` 子类）：
- 新代码用 `chat_log.llm_api.async_call_tool` 替代了 `execute_tool_calls`（基线第 481-515 行调 `function_executor.execute()`），**不调** 6 种 executor
- 但删除这 6 个类（`NativeFunctionExecutor`、`ScriptFunctionExecutor`、`TemplateFunctionExecutor`、`RestFunctionExecutor`、`ScrapeFunctionExecutor`、`CompositeFunctionExecutor`、`SqliteFunctionExecutor`）会**增加改动面**且**零运行时收益**（Python 类没人调用就是死代码）
- 保留它们 = 0 字节运行时影响、0 字节启动时间影响
- v2.0 严格遵循"能复用原始代码的尽量不要动"原则

**不动任何字符**。

### 4.8 exceptions.py 100% 复制

**引用**：基线位于 `/config/custom_components/extended_openai_conversation/exceptions.py`（135 行）

**为什么 100% 复制**：
- `FunctionNotFound` / `InvalidFunction` / `ParseArgumentsFailed` / `TokenLengthExceededError` / `FunctionLoadFailed` — 异常类
- 仍可被新代码 `try/except` 引用（虽然新路径大概率不 raise 这些异常，因为不再用 `function_executor.execute()`）
- 保留 = 0 运行时影响

**不动任何字符**。

### 4.9 services.py + services.yaml 100% 复制

**引用**：
- `services.py` 基线 212 行
- `services.yaml` 基线 62 行

**为什么 100% 复制**：
- `generate_image` / `generate_content` 等 service 注册（如果基线有）保持不变
- HA service 注册不依赖 domain 名字符串

**不动任何字符**。

### 4.10 strings.json + translations/ 100% 复制

**引用**：
- `strings.json` 基线 109 行
- `translations/` 含 12 种语言文件（en, zh-CN, de, fr, ...）

**为什么 100% 复制**：
- i18n 字符串保持不变
- 用户在 HA UI 看到的英文/中文/其他语言提示不变

**不动任何字符**。

> **可选优化**（不在最小化改造范围）：如果想标注"Claw Extended OpenAI"字样给用户看，可修改 `strings.json` 第 X 行的 `name` / `description` 字段。但这会增加 i18n 维护成本，**v2.0 不做**。

---

## 5. 功能需求（Functional Requirements）

### FR-1：集成 domain 与命名

| 项目 | 要求 |
|------|------|
| FR-1.1 | domain 必须为 `claw_extended_openai_conversation`（改 manifest.json 第 2 行）|
| FR-1.2 | manifest.json 的 name 必须为 `Claw Extended OpenAI Conversation`（改 manifest.json 第 3 行）|
| FR-1.3 | manifest.json 的 version 必须包含后缀标识 fork `2.0.2-claw-fork.1`（改 manifest.json 第 22 行）|
| FR-1.4 | const.py 的 DOMAIN 常量必须为 `claw_extended_openai_conversation`（改 const.py 第 X 行）|
| FR-1.5 | 集成必须出现在 HA UI 的对话代理选择列表中 |
| FR-1.6 | HA UI 显示的 entity_id 必须为 `conversation.claw_extended_openai_conversation_*` |

### FR-2：对话处理路径（核心改造）

| 项目 | 要求 |
|------|------|
| FR-2.1 | 改写后的 `_async_handle_message`（conversation.py 138-235 行）必须**首行**调 `await chat_log.async_provide_llm_data(...)` 启用 HA AssistAPI |
| FR-2.2 | 必须使用 HA core LLM 框架处理 `llm.Tool` → OpenAI function schema 的转换（**新代码中已实现 `_format_tool` 函数**）|
| FR-2.3 | 必须使用 `self.client`（基线 conversation.py 第 123 行赋值的 `entry.runtime_data` AsyncOpenAI 实例）调 LLM API，**保留** `base_url` 参数 |
| FR-2.4 | 必须支持 LLM 返回的 `tool_calls` 通过 `chat_log.llm_api.async_call_tool()` 执行（**新代码内部新增**，不调基线的 `execute_tool_calls`）|
| FR-2.5 | 必须支持多轮 tool_calls 循环（迭代次数通过 `const.py` 新增的 `MAX_TOOL_ITERATIONS = 10` 控制）|
| FR-2.6 | 必须支持流式响应（`_attr_supports_streaming = True`，基线 conversation.py 已有）|

### FR-3：客户端与端点配置（**复用基线**）

| 项目 | 要求 |
|------|------|
| FR-3.1 | 必须使用 OpenAI Python SDK `openai~=2.21.0`（基线 manifest.json requirements）|
| FR-3.2 | 必须支持 `base_url` 配置参数（指向 MiniMax API endpoint）— **基线 `__init__.py` 已实现**，100% 复用 |
| FR-3.3 | 必须支持 `api_key` 配置参数 — **基线 `__init__.py` 已实现**，100% 复用 |
| FR-3.4 | 必须支持 `api_version` 和 `organization` 配置参数（Azure OpenAI 兼容）— **基线 `__init__.py` 已实现**，100% 复用 |
| FR-3.5 | 必须复用 HA core `httpx_client.get_async_client(hass)`（基线 `__init__.py` 已实现）— 100% 复用 |
| FR-3.6 | 必须支持 `is_azure_url(base_url)` 判断走 `AsyncAzureOpenAI` 还是 `AsyncOpenAI`（基线 `helpers.py` 第 73 行已实现）— 100% 复用 |

### FR-4：配置文件保留（**复用基线**）

| 项目 | 要求 |
|------|------|
| FR-4.1 | 必须保留基线 `config_flow.py` 全部配置项 — 100% 复制（基线 336 行）|
| FR-4.2 | 必须支持 api_key、base_url、model、temperature、max_tokens、top_p 等参数 — 100% 复用 |
| FR-4.3 | 必须支持 prompt template（system prompt）用户自定义 — 100% 复用（基线 `_generate_system_message` 第 241-247 行）|
| FR-4.4 | 必须支持 subentry 模式（HA 2024+ 的 subentry 配置）— 100% 复用（基线 `config_flow.py` 已实现）|

### FR-5：71 工具自动注入验证

| 项目 | 要求 |
|------|------|
| FR-5.1 | 集成启动后必须能被 HA core LLM 框架识别为有效 API |
| FR-5.2 | 当 claw_assistant 已通过 `llm.async_register_api()` 注册时（基线 claw_assistant/runtime/llm/internal_llm.py），集成调用 LLM 时 OpenAI function schema 必须包含 71 个工具的 spec |
| FR-5.3 | LLM 返回 `tool_calls` 时，工具必须通过 claw_assistant 已实现的 `async_call` 方法执行（**不**走基线 6 种 custom executor）|
| FR-5.4 | 工具执行结果必须正确序列化回 LLM context（用 `_format_tool_result` 或等价机制 — 可参考 HA core `_convert_content_to_param`）|

### FR-6：错误处理

| 项目 | 要求 |
|------|------|
| FR-6.1 | LLM API 鉴权失败（401）必须 raise `ConfigEntryAuthFailed` — **基线 `__init__.py` 已实现**，100% 复用 |
| FR-6.2 | LLM API 临时失败必须 raise `ConfigEntryNotReady`（支持 HA 自动重试）— **基线 `__init__.py` 已实现**，100% 复用 |
| FR-6.3 | tool execution 失败必须返回 `tool_result` 给 LLM（让 LLM 决定下一步）|
| FR-6.4 | 必须保留 `exceptions.py` 全部异常类 — 100% 复制（基线 135 行）|

### FR-7：HA 集成生命周期

| 项目 | 要求 |
|------|------|
| FR-7.1 | 必须支持 `async_setup_entry` — **基线 `__init__.py` 已实现**，100% 复用 |
| FR-7.2 | 必须支持 `async_unload_entry` — **基线 `__init__.py` 已实现**，100% 复用 |
| FR-7.3 | 必须支持 `async_update_options` — **基线 `__init__.py` 已实现**，100% 复用 |
| FR-7.4 | 必须支持 `conversation.async_set_agent` 注册对话代理 — **基线 conversation.py 已实现**，100% 复用 |
| FR-7.5 | 必须支持 `conversation.async_unset_agent` 注销对话代理 — **基线 conversation.py 已实现**，100% 复用 |

---

## 6. 非功能需求（Non-Functional Requirements）

### NFR-1：兼容性

| 项目 | 要求 |
|------|------|
| NFR-1.1 | HA 版本：>= 2024.7（subentry 模式引入版本）|
| NFR-1.2 | Python：>= 3.12（HAOS 默认）|
| NFR-1.3 | OpenAI SDK：`openai~=2.21.0`（与基线一致）|
| NFR-1.4 | 必须兼容 `extended_openai_conversation` 2.0.2 的 options schema（API key / base_url / model）|
| NFR-1.5 | 必须兼容 claw_assistant v9.1.0+（`llm.async_register_api` 机制）|

### NFR-2：可维护性

| 项目 | 要求 |
|------|------|
| NFR-2.1 | 代码风格遵循 PEP 8 + HA 集成代码规范 |
| NFR-2.2 | 必须保留基线 extended_openai_conversation 100% 的方法签名（参数 + 返回值），仅替换 `_async_handle_message` 实现 |
| NFR-2.3 | 必须有清晰注释标记"被替换的代码段"和"新增的代码段" |
| NFR-2.4 | manifest.json 必须在 `name` 字段标注 fork 标识（"Claw Extended"）|
| NFR-2.5 | 代码提交信息格式：`feat: <功能>` / `fix: <修复>` / `refactor: <重构>` |

### NFR-3：可靠性

| 项目 | 要求 |
|------|------|
| NFR-3.1 | 启动失败时必须 raise `ConfigEntryNotReady`（让 HA 自动重试）— **基线已实现** |
| NFR-3.2 | 工具调用失败时必须记录日志（HA logger），不让 LLM 看到未捕获异常 |
| NFR-3.3 | LLM 响应不完整（`ResponseIncompleteEvent`）必须 raise `HomeAssistantError` 提示用户 |
| NFR-3.4 | 与 claw_assistant 集成时不允许 raise 未捕获异常（防 5 次熔断触发）|

### NFR-4：可回滚性

| 项目 | 要求 |
|------|------|
| NFR-4.1 | 部署前必须备份原 `extended_openai_conversation`（**Ray 负责执行**）|
| NFR-4.2 | 部署后原 HACS 集成**必须**保持可用（domain 不同，无冲突）|
| NFR-4.3 | HA 端通过 `primary_agent` 切换即可在两个集成间切换，无需改代码 |
| NFR-4.4 | 失败时通过删除新集成目录即可立即回滚（HA 自动 reload）|

### NFR-5：性能

| 项目 | 要求 |
|------|------|
| NFR-5.1 | LLM 调用延迟：与原 extended_openai_conversation 一致（不引入额外层）|
| NFR-5.2 | 工具调用链延迟：< 2s per tool（HA core LLM 框架的 5 次熔断阈值内）|
| NFR-5.3 | 内存占用：与原集成一致（不引入新数据结构）|

### NFR-6：可观测性

| 项目 | 要求 |
|------|------|
| NFR-6.1 | 启动时必须 logger.info 记录集成名 + 版本 + base_url |
| NFR-6.2 | 工具调用时必须 logger.debug 记录 tool_name + tool_args（不记录 token / 敏感数据）|
| NFR-6.3 | LLM 调用时必须 logger.info 记录 prompt 长度 + response 长度 |
| NFR-6.4 | 错误时必须 logger.error 记录完整 traceback |

---

## 7. 接口规范

### 7.1 内部接口（与 HA core 对接）

| 接口 | 位置（HA core 源文件）| 要求 |
|------|------|------|
| `chat_log.async_provide_llm_data(llm_context, llm_hass_api, prompt, extra_system_prompt)` | `homeassistant/components/conversation/chat_log.py` | 必须在改写后的 `_async_handle_message` 入口调一次 |
| `llm.async_get_api(hass, api_id, llm_context)` | `homeassistant/helpers/llm.py` | 框架内部调用，集成不直接调 |
| `chat_log.llm_api.tools` | `llm.APIInstance.tools: list[Tool]` | 集成从此处取工具列表 |
| `chat_log.llm_api.async_call_tool(tool_input)` | `llm.APIInstance.async_call_tool` | 工具执行时调此方法 |
| `chat_log.async_add_delta_content(delta_dict)` | `conversation.ChatLog.async_add_delta_content` | LLM 流式响应喂回 chat_log |

### 7.2 外部接口（与 LLM API 对接）

| 接口 | 描述 |
|------|------|
| OpenAI Chat Completions API | `client.chat.completions.create(model, messages, tools, tool_choice)` |
| OpenAI Responses API | `client.responses.create(model, input, tools, ...)`（HA core 使用）|
| 端点 | `base_url`（如 `https://api.ha_china.com/v1` 指向 MiniMax）|
| 鉴权 | Bearer token via `api_key` header |

### 7.3 数据契约

#### 7.3.1 `llm.Tool` schema（HA core）

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `name` | str | 是 | 工具名（unique）|
| `description` | str | 否 | LLM 看到的工具描述 |
| `parameters` | vol.Schema | 否 | 参数 schema（用 voluptuous 定义）|
| `async_call(hass, tool_input, llm_context)` | method | 是 | 工具执行函数，返回 JsonObjectType |

#### 7.3.2 `ToolInput` schema（HA core）

| 字段 | 类型 | 描述 |
|------|------|------|
| `tool_name` | str | 要调用的工具名 |
| `tool_args` | dict | 工具参数 |
| `id` | str | 唯一 ID（用于追踪）|
| `external` | bool | 是否外部工具（默认 False）|

#### 7.3.3 `LLMContext` schema（HA core）

| 字段 | 类型 | 描述 |
|------|------|------|
| `platform` | str | 集成 domain（必须是 `claw_extended_openai_conversation`）|
| `context` | Context | HA 调用 context |
| `language` | str | 用户语言 |
| `assistant` | str | 助手 domain |
| `device_id` | str | 设备 ID |

---

## 8. 验收标准（Acceptance Criteria）

### AC-1：集成被发现并注册

**前置条件**：HA 已启动，claw_assistant 已加载

**步骤**：
1. Ray 将新集成目录部署到 `/config/custom_components/claw_extended_openai_conversation/`
2. Ray 重启 HA
3. Ray 进入 HA UI → 配置 → 设备与服务 → 集成
4. 搜索 `Claw Extended OpenAI Conversation`

**预期**：
- ✅ 新集成出现在搜索结果中
- ✅ 点击"添加"后能进入 config_flow
- ✅ HA 创建 entity `conversation.claw_extended_openai_conversation_*`
- ✅ HA log 无 `ImportError` / `ValueError`

### AC-2：MiniMax 直连验证

**前置条件**：AC-1 通过

**步骤**：
1. Ray 在新集成的 config_flow 中填入 `base_url` + `api_key`（与原 extended_openai_conversation 2 相同）
2. 提交配置
3. Ray 调 HA 调试工具（`ha_get_overview`）查 entity 状态

**预期**：
- ✅ 集成状态 = `loaded`（无错误）
- ✅ `runtime_data` 是 `AsyncOpenAI` 实例
- ✅ `runtime_data.base_url` = 配置的 `base_url`
- ✅ HA log 显示 `Setting up Claw Extended OpenAI Conversation`

### AC-3：71 工具注入验证（核心）

**前置条件**：AC-2 通过

**步骤**：
1. Ray 调用 MiniMax 对话 agent（`conversation.claw_extended_openai_conversation_*`）
2. Ray 输入："列出所有暴露的灯"
3. 观察 HA log 和 LLM 调用日志

**预期**：
- ✅ LLM 收到的 tools 数量 = 71（HA core 框架自动注入）
- ✅ LLM 调用 `GetLiveContext` 或 `SmartDiscovery` 工具
- ✅ 工具执行成功（HA log 显示 `tool_name=GetLiveContext` 实际执行）
- ✅ LLM 给出包含灯列表的回答
- ✅ 整个调用通过 `chat_log.llm_api.async_call_tool` 路径（**不是**基线 6 种 custom executor）

### AC-4：普通对话与设备控制

**前置条件**：AC-3 通过

**步骤**：
1. Ray 输入："开客厅灯"
2. 观察 LLM 调用
3. 输入："关客厅灯"
4. 观察 LLM 调用

**预期**：
- ✅ LLM 调 `ServiceCall` 工具（不是 `execute_service`）
- ✅ 客厅灯实际开关
- ✅ LLM 给用户简洁确认
- ✅ 工具调用无 `NativeNotFound` 异常（因为不走 NativeFunctionExecutor）

### AC-5：回滚验证

**前置条件**：任何 AC 失败

**步骤**：
1. Ray 改 `claw_assistant.options.primary_agent` 切回 `conversation.extended_openai_conversation_2`
2. Ray 调 HA 重载 claw_assistant 集成
3. 重新执行 AC-3

**预期**：
- ✅ 虾宝继续可用（回到原 8 工具状态）
- ✅ 新集成的失败不影响原 HACS 集成
- ✅ 整个回滚过程无需重启 HA

---

## 9. 代码约束（给秃头虾）

### 9.1 必须遵循的代码规范

| 规范 | 来源 |
|------|------|
| PEP 8 | Python 官方 |
| HA 集成代码规范 | https://developers.home-assistant.io/docs/creating_integration_manifest/ |
| HA 开发文档 | https://developers.home-assistant.io/ |
| 错误处理 | 使用 HA 标准异常（`HomeAssistantError` / `ConfigEntryAuthFailed` / `ConfigEntryNotReady`）|

### 9.2 必须保留的方法签名

> **本节列出必须保留的方法签名**（参数和返回值不变，仅替换 `_async_handle_message` 实现）

| 方法 | 文件 | 签名 | 基线行号 |
|------|------|------|----------|
| `async_setup_entry` | `__init__.py` | 接收 `(hass, entry)` 返回 `bool` | 76-100 |
| `__init__` (类初始化) | `conversation.py` | 接收 `(self, entry)` 设置 self 属性 | 101-124 |
| `async_process` | `conversation.py` | 接收 `(self, user_input)` 返回 `ConversationResult` | 130-136 |
| **`_async_handle_message`** | `conversation.py` | 接收 `(self, user_input, chat_log)` 返回 `ConversationResult` | **138-235（必改）** |
| `_generate_system_message` | `conversation.py` | 接收 `(self, exposed_entities, user_input)` 返回 dict | 241-247 |
| `_async_generate_prompt` | `conversation.py` | 接收 `(self, raw_prompt, exposed_entities, user_input)` 返回 str | 248-260 |
| `get_exposed_entities` | `conversation.py` | 接收 `(self)` 返回 list | 264-289 |
| `async_get_authenticated_client` | `__init__.py` | 接收 `(hass, api_key, base_url, api_version, organization, api_provider)` 返回 `AsyncClient` | 76-100 |

### 9.3 必须修改的部分（**3 文件 / 1 方法 / 7 删 1 类**）

> **严格最小化改造清单** — 任何超出此清单的改动**必须**先知会 Ray 审批。

| 序号 | 文件 | 行号（基线）| 改动 |
|------|------|----------|------|
| 1 | `manifest.json` | 第 2、3、4-6、22 行 | 改 4 个字段（domain/name/codeowners/version）|
| 2 | `const.py` | `DOMAIN = ...` 那一行 | 改 1 行（`DOMAIN` 常量）|
| 3 | `conversation.py` | 138-235 | 重写 `_async_handle_message` |
| 4 | `conversation.py` | 330-411 | 删除 `query` 方法（82 行）|
| 5 | `conversation.py` | 412-435 | 删除 `execute_function_call` 方法（24 行）|
| 6 | `conversation.py` | 436-480 | 删除 `execute_function` 方法（45 行）|
| 7 | `conversation.py` | 481-515 | 删除 `execute_tool_calls` 方法（35 行）|
| 8 | `conversation.py` | 516-550 | 删除 `execute_tool_function` 方法（35 行）|
| 9 | `conversation.py` | 551-554 | 删除 `should_run_in_background` 方法（4 行）|
| 10 | `conversation.py` | 555-572 | 删除 `get_delayed_function` 方法（18 行）|
| 11 | `conversation.py` | 573-578 | 删除 `class OpenAIQueryResponse`（6 行）|

### 9.4 必须新增的部分（仅在 `_async_handle_message` 方法内）

> **最小化新增** — 不在新文件、新类、新模块中加代码，全部内联在重写后的方法内。

| 必新增 | 描述 |
|--------|------|
| `await chat_log.async_provide_llm_data(llm_context, True, prompt, extra_system_prompt)` | 启动 ChatLog 框架 |
| LLM 调用循环 | `for iteration in range(MAX_TOOL_ITERATIONS):`（`const.py` 新增 `MAX_TOOL_ITERATIONS = 10`）|
| `messages = _convert_content_to_param(chat_log.content)` | 把 ChatLog 内容转 OpenAI messages（**参考 HA core `_convert_content_to_param` 实现，复制/简化**）|
| `tools = [_format_tool(tool, chat_log.llm_api.custom_serializer) for tool in chat_log.llm_api.tools]` | 把 llm.Tool 转 OpenAI function schema（**参考 HA core `_format_tool` 实现，复制/简化**）|
| `response = await self.client.chat.completions.create(model, messages, tools=tools, tool_choice="auto")` | 调 LLM（**复用基线 `self.client`**）|
| `await chat_log.async_add_delta_content(...)` | 流式响应喂回 ChatLog |
| `for tool_input in chat_log.llm_api.tools: ... chat_log.llm_api.async_call_tool(tool_input)` | 执行 tool_calls（**复用 ChatLog 框架**）|
| `try/except OpenAIError` 错误处理 | 返回 `IntentResponse` 给用户（**复用基线 138-235 行的 try/except 结构**）|

### 9.5 禁止事项

| 禁止项 | 理由 |
|--------|------|
| ❌ 修改 HA core 代码 | 不在范围 |
| ❌ 修改 `extended_openai_conversation` 源码 | 保留作为 fallback |
| ❌ 修改 claw_assistant 源码 | 不在范围 |
| ❌ 添加新 `llm.Tool` 实现 | 不在范围 |
| ❌ 添加新 custom executor 类型 | 不需要，HA LLM 框架已覆盖 |
| ❌ **删除 helpers.py 中任何类**（包括 6 种 `FunctionExecutor`）| **违反最小化改造原则** — 死代码 0 影响，不删反而减少改动面 |
| ❌ **修改 `__init__.py` / `config_flow.py` / `helpers.py` / `exceptions.py` / `services.py` / `services.yaml` / `strings.json` / `translations/` 中任何字符** | 100% 复用基线（仅复制不改）|
| ❌ **添加新 Python 文件**（除 `__init__.py` 必需的导入）| 最小化改造原则 |
| ❌ 修改 MiniMax API endpoint | 配置保持不变 |
| ❌ 添加数据库持久化 | 不在范围 |
| ❌ 添加外部 HTTP 服务 | 不在范围 |
| ❌ 修改 HA log 配置 | 通过 HA 标准 logger |

### 9.6 依赖项

> **必须保留的依赖**（沿用基线 `manifest.json` requirements）

| 依赖 | 版本约束 | 用途 |
|------|---------|------|
| `openai` | `~=2.21.0` | LLM API 客户端（基线 manifest.json 已声明）|
| `voluptuous` | HA core 提供 | schema 验证 |
| `voluptuous_openapi` | HA core 提供 | schema → OpenAPI 转换 |
| `homeassistant` | >= 2024.7 | HA 集成框架 |

> **禁止新增依赖**

---

## 10. 风险与决策记录（ADR 摘要）

### ADR-001：自建集成 vs 修改 HACS 集成

| 项 | 内容 |
|----|------|
| **状态** | 已决定 |
| **决策** | 自建新集成（`claw_extended_openai_conversation`）|
| **背景** | HACS 升级会覆盖任何本地修改（已验证 `installed: true, version_installed: 2.0.2`）|
| **替代方案** | 直接修改 HACS 集成源码 |
| **选择理由** | 自建集成零升级冲突、完整代码所有权、可立即回滚 |
| **后果** | 需手动维护（不走 HACS 自动更新）|

### ADR-002：保留 6 种 custom executor 不删除

| 项 | 内容 |
|----|------|
| **状态** | 已决定（**v2.0 修订**）|
| **决策** | **保留** `helpers.py` 中 6 种 `FunctionExecutor` 子类，**不删除** |
| **背景** | v1.0 曾建议删除以减少代码量 |
| **替代方案** | 删除 6 种 executor（v1.0 方案）|
| **选择理由** | **v2.0 严格遵循"最小化改造"原则** — 死代码 0 影响，不删反而减少改动面（不用 grep 确认每个类不被引用）|
| **后果** | helpers.py 仍是 767 行（与基线相同），无运行时影响 |

### ADR-003：保留 `AsyncOpenAI(base_url=***)` 客户端

| 项 | 内容 |
|----|------|
| **状态** | 已决定 |
| **决策** | 客户端初始化完全沿用 extended_openai_conversation |
| **背景** | MiniMax API 是 OpenAI-compatible 协议，必须保留 `base_url` 自定义能力 |
| **替代方案** | 改用 HA core `openai_conversation` |
| **选择理由** | HA core 不支持自定义 base_url（官方文档明确禁止）|
| **后果** | 无（无破坏性变更）|

### ADR-004：走 ChatLog 框架而非保持 `self.history`

| 项 | 内容 |
|----|------|
| **状态** | 已决定 |
| **决策** | 改用 `chat_log.async_provide_llm_data` + `chat_log.llm_api.async_call_tool` |
| **背景** | `self.history[conversation_id]` 维护绕开了 HA core LLM 框架，导致 71 工具无法注入 |
| **替代方案** | 保留 `self.history` + 手写 60+ function spec |
| **选择理由** | ChatLog 框架自动注入工具、零维护成本（HA 升级工具时无需改集成）|
| **后果** | 失去 `self.history` 自定义对话历史能力（但 HA core 的 ChatLog 框架更完善）|

### ADR-005（v2.0 新增）：最小化改造 vs 功能完整性

| 项 | 内容 |
|----|------|
| **状态** | 已决定 |
| **决策** | **严格最小化改造** — 仅改 3 文件 / 1 方法 / 7 删 1 类 |
| **背景** | v1.0 列了 5 删，实际应是 7 删 + 1 类（共 249 行）|
| **替代方案** | 完整重写（v1.0 方案）|
| **选择理由** | 最小化改造降低 bug 风险、加快开发、便于回滚、易于维护 |
| **后果** | 集成代码量比基线**少 226 行**（净减），功能不变 |

---

## 11. 原始代码完整引用（v2.0 核心章节 — 给秃头虾开发时查）

> **本节是 v2.0 的关键章节** — 把基线 extended_openai_conversation 2.0.2 的**每个方法、每个关键行**列出，秃头虾开发时可直接对照基线改。

### 11.1 基线代码位置总览

| 文件 | 绝对路径 | 行数 | 改动 |
|------|---------|------|------|
| `manifest.json` | `/config/custom_components/extended_openai_conversation/manifest.json` | 24 | 改 |
| `const.py` | `/config/custom_components/extended_openai_conversation/const.py` | 107 | 改 1 行 |
| `__init__.py` | `/config/custom_components/extended_openai_conversation/__init__.py` | 115 | 100% 复制 |
| `config_flow.py` | `/config/custom_components/extended_openai_conversation/config_flow.py` | 336 | 100% 复制 |
| `conversation.py` | `/config/custom_components/extended_openai_conversation/conversation.py` | 578 | 改 1 方法 + 删 8 方法 + 删 1 类 |
| `helpers.py` | `/config/custom_components/extended_openai_conversation/helpers.py` | 767 | 100% 复制 |
| `exceptions.py` | `/config/custom_components/extended_openai_conversation/exceptions.py` | 135 | 100% 复制 |
| `services.py` | `/config/custom_components/extended_openai_conversation/services.py` | 212 | 100% 复制 |
| `services.yaml` | `/config/custom_components/extended_openai_conversation/services.yaml` | 62 | 100% 复制 |
| `strings.json` | `/config/custom_components/extended_openai_conversation/strings.json` | 109 | 100% 复制 |
| `translations/*.json` | `/config/custom_components/extended_openai_conversation/translations/*.json` | — | 100% 复制 |

### 11.2 基线方法位置精确索引（conversation.py）

> **本表是 v2.0 关键修订**：精确到每个方法的真实行号，秃头虾开发时直接对照。

| 方法 / 类 | 起始行 | 结束行 | 行数 | 改动 |
|------|--------|--------|------|------|
| `__init__` (类初始化) | 101 | 124 | 24 | 100% 复用 |
| `supported_languages` 属性 | 126 | 128 | 3 | 100% 复用 |
| `async_process` | 130 | 136 | 7 | 100% 复用 |
| **`_async_handle_message`** | **138** | **235** | **97** | **必改（重写）** |
| `_generate_system_message` | 241 | 247 | 7 | 100% 复用 |
| `_async_generate_prompt` | 248 | 260 | 13 | 100% 复用 |
| `get_exposed_entities` | 264 | 289 | 26 | 100% 复用 |
| `get_functions` | 290 | 306 | 17 | 100% 复用（虽不调）|
| `truncate_message_history` | 308 | 329 | 22 | 100% 复用（虽不调）|
| **`query`** | **330** | **411** | **82** | **必删** |
| **`execute_function_call`** | **412** | **435** | **24** | **必删** |
| **`execute_function`** | **436** | **480** | **45** | **必删** |
| **`execute_tool_calls`** | **481** | **515** | **35** | **必删** |
| **`execute_tool_function`** | **516** | **550** | **35** | **必删** |
| **`should_run_in_background`** | **551** | **554** | **4** | **必删** |
| **`get_delayed_function`** | **555** | **572** | **18** | **必删** |
| **`class OpenAIQueryResponse`** | **573** | **578** | **6** | **必删** |

> **行号定位方法**：实际开发时用 `grep -nE 'async def|^    def |^class' /config/custom_components/extended_openai_conversation/conversation.py` 精确定位。

### 11.3 基线关键代码片段引用

#### 11.3.1 `self.client` 初始化（conversation.py:123）

```python
self.client = entry.runtime_data
```

**作用**：`entry.runtime_data` 是 `__init__.py.async_setup_entry` 创建的 `AsyncOpenAI` 实例，已配置 `base_url=***`。**新代码直接复用** `self.client` 调 LLM。

#### 11.3.2 `get_exposed_entities` 调用点（conversation.py:144）

```python
exposed_entities = self.get_exposed_entities()
```

**作用**：获取当前 HA 实例所有暴露给对话代理的 entity 列表。**新代码可继续复用**。

#### 11.3.3 `_generate_system_message` 调用点（conversation.py:152）

```python
system_message = self._generate_system_message(
    exposed_entities, user_input
)
```

**作用**：构造 system prompt（含 exposed entities CSV 列表）。**新代码可继续复用**，把它传给 `chat_log.async_provide_llm_data`。

#### 11.3.4 `try/except OpenAIError` 错误处理（conversation.py:170-201）

```python
try:
    query_response = await self.query(user_input, messages, exposed_entities, 0)
except OpenAIError as err:
    _LOGGER.error(err)
    intent_response = intent.IntentResponse(language=user_input.language)
    intent_response.async_set_error(
        intent.IntentResponseErrorCode.UNKNOWN,
        f"Sorry, I had a problem talking to OpenAI: {err}",
    )
    return conversation.ConversationResult(
        response=intent_response, conversation_id=conversation_id
    )
except HomeAssistantError as err:
    ...
```

**作用**：捕获 LLM 调用错误，返回用户友好的 IntentResponse。**新代码必须保留这个 try/except 结构**（FR-6）。

#### 11.3.5 `EVENT_CONVERSATION_FINISHED` 事件触发（conversation.py:204-211）

```python
self.hass.bus.async_fire(
    EVENT_CONVERSATION_FINISHED,
    {
        "response": query_response.response.model_dump(),
        "user_input": user_input,
        "messages": messages,
        "agent_id": self.subentry.subentry_id,
    },
)
```

**作用**：对话结束时触发 HA 事件（供前端监听）。**新代码建议保留**（NFR-6.3）。

#### 11.3.6 `should_continue` 检测（conversation.py:219-231）

```python
response_text = query_response.message.content or ""
should_continue = response_text.rstrip().endswith("?") or any(
    phrase in response_text.lower()
    for phrase in [
        "which one",
        "would you like",
        ...
    ]
)
```

**作用**：检测 LLM 是否在追问用户，决定 `continue_conversation` 标记。**新代码建议保留**。

### 11.4 HA core 参考代码位置

| 文件 | 路径 | 用途 |
|------|------|------|
| HA core `openai_conversation` 集成 | `homeassistant/components/openai_conversation/conversation.py` | 参考 `_async_handle_message` 改写模式 |
| HA core `_format_tool` | `homeassistant/components/openai_conversation/entity.py` 第 130-147 行 | 参考 `llm.Tool` → OpenAI function schema 转换 |
| HA core `_convert_content_to_param` | `homeassistant/components/openai_conversation/entity.py` 第 149 行起 | 参考 ChatLog content → OpenAI messages 转换 |
| HA core `_transform_stream` | `homeassistant/components/openai_conversation/entity.py` 第 245 行起 | 参考流式响应处理 |
| HA core `llm.Tool` 接口 | `homeassistant/helpers/llm.py` class Tool | llm.Tool 基类定义 |
| HA core `APIInstance.async_call_tool` | `homeassistant/helpers/llm.py` | 工具调用入口 |
| HA core `ChatLog.async_provide_llm_data` | `homeassistant/components/conversation/chat_log.py` | ChatLog 框架核心 |
| HA core `MAX_TOOL_ITERATIONS` | `homeassistant/components/openai_conversation/entity.py` 第 79 行 | 工具循环最大次数（10）|

### 11.5 claw_assistant 71 工具注册位置

| 文件 | 路径 | 用途 |
|------|------|------|
| `TOOL_REGISTRY` | `/config/custom_components/claw_assistant/tools/registry.py` | 71 工具完整列表（按 category 分组：device/query/search/system/core/misc）|
| `GetLiveContextTool` 实现 | `/config/custom_components/claw_assistant/tools/ha_core_tools.py` | 71 工具之一，参考 `async_call` 实现方式 |
| `llm.async_register_enhanced_api` | `/config/custom_components/claw_assistant/runtime/llm/internal_llm.py` | 71 工具注册到 HA core LLM 框架的入口 |
| `_patch_assist_api_prompt` | `/config/custom_components/claw_assistant/runtime/llm/internal_llm.py` | 71 工具自动注入到 HA AssistAPI 的关键 patch |

### 11.6 极客虾工作流 SOP

| 文件 | 路径 | 用途 |
|------|------|------|
| 极客虾 HA 工作流 SOP | `~/.openclaw/workspace-geek/skills/geek-ha-workflow/SKILL.md` | HA 系统运维 SOP |
| Git workflow SOP | `~/.openclaw/workspace-geek/skills/git-workflow/SKILL.md` | **必读** — 5 步 Git 流程（fetch → rebase → commit → push）|

---

## 12. 交付物清单（Deliverables）

### 12.1 代码交付（秃头虾产出，Git 提交）

> **本节是给秃头虾的工作项清单**。所有文件路径相对于集成根目录 `/config/custom_components/claw_extended_openai_conversation/`。

| 序号 | 文件 | 类型 | 来源 | 必改/必增 |
|------|------|------|------|----------|
| D-1 | `manifest.json` | 改 | 复制 + 改 4 个字段（domain/name/version/codeowners）| 必改 |
| D-2 | `const.py` | 改 | 复制 + 改 `DOMAIN` 常量 | 必改 |
| D-3 | `__init__.py` | 复制 | 沿用 extended_openai_conversation | 100% 复制 |
| D-4 | `config_flow.py` | 复制 | 沿用 extended_openai_conversation | 100% 复制 |
| D-5 | `conversation.py` | **核心改造** | 复制 + 改 1 方法（`_async_handle_message`）+ 删 8 方法 + 1 类 | 必改 |
| D-6 | `helpers.py` | 复制 | 沿用 extended_openai_conversation | **100% 复制（含 6 种 FunctionExecutor 不删）** |
| D-7 | `exceptions.py` | 复制 | 沿用 extended_openai_conversation | 100% 复制 |
| D-8 | `services.py` | 复制 | 沿用 extended_openai_conversation | 100% 复制 |
| D-9 | `services.yaml` | 复制 | 沿用 extended_openai_conversation | 100% 复制 |
| D-10 | `strings.json` | 复制 | 沿用 extended_openai_conversation | 100% 复制 |
| D-11 | `translations/` | 复制 | 沿用 extended_openai_conversation | 100% 复制 |

### 12.2 文档交付（秃头虾产出，可选）

| 序号 | 文件 | 描述 | 优先级 |
|------|------|------|--------|
| DOC-1 | `README.md` | 集成说明、安装步骤、配置示例 | 推荐 |
| DOC-2 | `CHANGELOG.md` | 跟基线版本的差异说明 | 推荐 |
| DOC-3 | `LICENSE` | 沿用基线的 Apache 2.0 协议 | 必加 |

### 12.3 提交指引（Git workflow）

> 秃头虾提交到 GitHub 时必须遵循 `git-workflow` skill 定义的 5 步流程（fetch → rebase → commit → push）。

| 步骤 | 指令 |
|------|------|
| 1. 同步 | `git pull --rebase origin main` |
| 2. 暂存 | `git add <files>` |
| 3. 提交 | `git commit -m "feat: <功能描述>"` |
| 4. 推送前同步 | `git pull --rebase origin main` |
| 5. 推送 | `git push origin main` |

**Commit message 规范**（沿用 git-workflow skill）：
- `feat: 新功能描述`
- `fix: 修复描述`
- `refactor: 重构描述`
- `docs: 文档描述`

**首次提交建议**：`feat: initial fork of extended_openai_conversation 2.0.2 with ChatLog framework integration`

**后续提交建议**（如需多次提交）：
1. `feat: copy base files from extended_openai_conversation 2.0.2`
2. `feat: rename domain to claw_extended_openai_conversation`
3. `refactor: rewrite _async_handle_message to use ChatLog framework`
4. `refactor: remove query() execute_function_call() execute_function() execute_tool_calls() execute_tool_function() should_run_in_background() get_delayed_function() and OpenAIQueryResponse class`

### 12.4 Ray 的执行工作（**不在本项目范围**）

> **本节仅说明 Ray 的后续工作，不在秃头虾的开发任务内。**

| 步骤 | 描述 |
|------|------|
| Ray-1 | 备份原 `extended_openai_conversation` 目录 |
| Ray-2 | 把秃头虾提交的代码部署到 `/config/custom_components/claw_extended_openai_conversation/` |
| Ray-3 | 重启 HA |
| Ray-4 | 在 HA UI 添加新集成 |
| Ray-5 | 改 `claw_assistant.options.primary_agent` 指向新集成 |
| Ray-6 | 执行 AC-1 ~ AC-5 验收 |
| Ray-7 | 失败时回滚（改 `primary_agent` 切回原集成，删除新集成目录）|

---

## 13. 变更历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-06-23 | 初版（极客虾出稿，删除 6 种 FunctionExecutor）|
| **v2.0** | **2026-06-23** | **关键修订**：严格收敛到"3 文件 / 1 方法 / 7 删 1 类"最小化改造（**实际删除范围比 v1.0 大 5 个方法 + 1 个类**）；保留 6 种 FunctionExecutor；新增完整原始代码引用章节（章节 11）|

---

## 附录 A：项目自检清单

> 秃头虾提交前必须确认（基于 v2.0 最小化改造）：

- [ ] 集成目录在本地存在，文件结构完整（D-1 ~ D-11）
- [ ] `manifest.json` 改完 4 个字段（domain/name/version/codeowners）
- [ ] `const.py` 改完 `DOMAIN` 常量（1 行）
- [ ] `conversation.py` 改完 `_async_handle_message` 方法（重写）
- [ ] `conversation.py` 删除 `query()` 方法（82 行）
- [ ] `conversation.py` 删除 `execute_function_call()` 方法（24 行）
- [ ] `conversation.py` 删除 `execute_function()` 方法（45 行）
- [ ] `conversation.py` 删除 `execute_tool_calls()` 方法（35 行）
- [ ] `conversation.py` 删除 `execute_tool_function()` 方法（35 行）
- [ ] `conversation.py` 删除 `should_run_in_background()` 方法（4 行）
- [ ] `conversation.py` 删除 `get_delayed_function()` 方法（18 行）
- [ ] `conversation.py` 删除 `class OpenAIQueryResponse`（6 行）
- [ ] `__init__.py` 100% 复制（0 改动）
- [ ] `config_flow.py` 100% 复制（0 改动）
- [ ] `helpers.py` 100% 复制（0 改动，含 6 种 FunctionExecutor）
- [ ] `exceptions.py` 100% 复制（0 改动）
- [ ] `services.py` 100% 复制（0 改动）
- [ ] `services.yaml` 100% 复制（0 改动）
- [ ] `strings.json` 100% 复制（0 改动）
- [ ] `translations/` 100% 复制（0 改动）
- [ ] 没有任何 HA core 代码修改
- [ ] 没有任何 extended_openai_conversation 原文件修改
- [ ] 没有任何 claw_assistant 代码修改
- [ ] 没有任何部署命令（部署是 Ray 的工作）
- [ ] 没有任何新 Python 文件
- [ ] 没有任何新依赖
- [ ] commit message 符合 git-workflow 规范
- [ ] git push 前已 `git pull --rebase`

---

## 附录 B：基线 vs 新集成对比表（v2.0 关键交付）

| 维度 | 基线（extended_openai_conversation 2.0.2）| 新集成（claw_extended_openai_conversation）|
|------|----------------------------------------|----------------------------------------|
| **domain** | `extended_openai_conversation` | `claw_extended_openai_conversation` |
| **name** | `Extended OpenAI Conversation` | `Claw Extended OpenAI Conversation` |
| **version** | `2.0.2` | `2.0.2-claw-fork.1` |
| **codeowners** | `@jekalmin` | `@yrwd999` |
| **代码文件数** | 10 个 Python + 配置 | **完全相同 10 个 Python + 配置** |
| **conversation.py 总行数** | 578 | **268（-310 行）** |
| **改动方法数** | — | **改 1 个（`_async_handle_message`）+ 删 8 个方法 + 1 个类**（实际删除 249+ 行）+ 新增 `_format_tool` 函数 |
| **`helpers.py` 改动** | — | **0 改动（6 种 FunctionExecutor 全保留）** |
| **`__init__.py` 改动** | — | **0 改动** |
| **`config_flow.py` 改动** | — | **0 改动** |
| **LLM 客户端** | `AsyncOpenAI(base_url=***)` | **`AsyncOpenAI(base_url=***)` — 完全相同** |
| **MiniMax API 支持** | ✅ | ✅ **完全保留** |
| **71 工具自动注入** | ❌ | ✅ **新增能力** |
| **HACS 升级覆盖风险** | — | **0（不在 HACS 管理）** |

---

> **本文档由极客虾编写，仅作为开发指导。Ray 拥有最终决策权，秃头虾拥有实现权。任何超出本需求文档的改动必须先知会 Ray 审批。**
