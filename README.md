# claw_extended_openai_conversation

HA custom integration: fork of extended_openai_conversation 2.0.2 with ChatLog framework for 71-tool injection via MiniMax LLM.

## 与原版 extended_openai_conversation 的关键差异

| 维度 | 原版 | 本 fork |
|------|------|---------|
| **LLM 工具注入** | 手动 function calling | **自动 via HA ChatLog 框架** |
| **工具数量** | 手动配置 | **71 工具自动注入** |
| **实现方式** | 自定义 function calling | `chat_log.async_provide_llm_data` + `llm.API` |
| **conversation.py 行数** | 578 | ~268 |

## 变更范围（v2.0 最小化改造）

- `manifest.json` - domain/name/version/codeowners
- `const.py` - DOMAIN + MAX_TOOL_ITERATIONS
- `conversation.py` - 重写 `_async_handle_message` + 删除 7 方法 + 1 类
- 其他文件 **100% 复制原版**，未修改

## 需求文档

完整需求规格见 [SPEC.md](./SPEC.md)

## 安装方式

### 方式一：HACS（推荐）

1. 在 HACS 中添加自定义仓库：
   - HACS → Integrations → ⋮ → Custom repositories
   - URL: `https://github.com/yrwd999/claw_extended_openai_conversation`
   - Category: Integration
2. 重启 Home Assistant
3. 在 HA UI 添加新集成：`设置` → `设备与服务` → `添加集成` → 搜索 `Claw Extended OpenAI Conversation`

### 方式二：手动安装

1. 备份原 `extended_openai_conversation` 目录（如有）
2. 克隆本仓库到 `/config/custom_components/claw_extended_openai_conversation/`
3. 重启 HA
4. 在 HA UI 添加新集成

## 部署后配置

1. 修改 `claw_assistant.options.primary_agent` 指向新集成

## 来源

- Forked from: [jekalmin/extended_openai_conversation](https://github.com/jekalmin/extended_openai_conversation) v2.0.2
- 集成类型: HACS private repository
