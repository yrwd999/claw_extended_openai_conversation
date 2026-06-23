"""Extended OpenAI Conversation agent entity."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    ChatLog,
    ConversationEntity,
    ConversationEntityFeature,
    ConversationInput,
    ConversationResult,
    async_get_chat_log,
)
from homeassistant.helpers.llm import llm
from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import ATTR_NAME, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    intent,
    template,
)
from homeassistant.helpers.chat_session import async_get_chat_session
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ExtendedOpenAIConfigEntry
from .const import (
    CONF_ATTACH_USERNAME,
    CONF_CHAT_MODEL,
    CONF_CONTEXT_THRESHOLD,
    CONF_CONTEXT_TRUNCATE_STRATEGY,
    CONF_FUNCTIONS,
    CONF_MAX_FUNCTION_CALLS_PER_CONVERSATION,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_USE_TOOLS,
    DEFAULT_ATTACH_USERNAME,
    DEFAULT_CHAT_MODEL,
    DEFAULT_CONF_FUNCTIONS,
    DEFAULT_CONTEXT_THRESHOLD,
    DEFAULT_CONTEXT_TRUNCATE_STRATEGY,
    DEFAULT_MAX_FUNCTION_CALLS_PER_CONVERSATION,
    DEFAULT_MAX_TOKENS,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_USE_TOOLS,
    DOMAIN,
    EVENT_CONVERSATION_FINISHED,
    MAX_TOOL_ITERATIONS,
)
from .exceptions import (
    FunctionLoadFailed,
    FunctionNotFound,
    InvalidFunction,
    ParseArgumentsFailed,
    TokenLengthExceededError,
)
from .helpers import get_function_executor

_LOGGER = logging.getLogger(__name__)


def _format_tool(tool: llm.Tool) -> dict:
    """Format an LLM tool for OpenAI API."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ExtendedOpenAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenAI Conversation entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue

        async_add_entities(
            [ExtendedOpenAIAgentEntity(hass, config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class ExtendedOpenAIAgentEntity(
    ConversationEntity, conversation.AbstractConversationAgent
):
    """OpenAI conversation agent."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = ConversationEntityFeature.CONTROL

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ExtendedOpenAIConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        self.subentry = subentry
        self.history: dict[str, list[dict]] = {}

        self.options = subentry.data
        self._attr_unique_id = subentry.subentry_id

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="OpenAI",
            model=self.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL),
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        self.client = entry.runtime_data

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a sentence."""
        with (
            async_get_chat_session(self.hass, user_input.conversation_id) as session,
            async_get_chat_log(self.hass, session, user_input) as chat_log,
        ):
            return await self._async_handle_message(user_input, chat_log)

    async def _async_handle_message(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
    ) -> ConversationResult:
        """Handle a conversation message using HA ChatLog framework (FR-2)."""
        intent_response = intent.IntentResponse(language=user_input.language)
        conversation_id = chat_log.conversation_id

        # FR-2.1: Call async_provide_llm_data FIRST to set up LLM context
        await chat_log.async_provide_llm_data(
            llm.APIInstance(
                platform=DOMAIN,
                context=user_input.context,
                user=user_input.context.user_id,
                language=user_input.language,
                assistant=conversation.DOMAIN,
                device_id=user_input.device_id,
            ),
            chat_log,
        )

        model = self.options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
        max_tokens = self.options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
        top_p = self.options.get(CONF_TOP_P, DEFAULT_TOP_P)
        temperature = self.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)

        # Build messages from chat_log content
        messages = [{"role": msg.role, "content": msg.content} for msg in chat_log.content]
        messages.append({"role": "user", "content": user_input.text})

        text = ""

        # FR-2.2: Call MiniMax API with tools from chat_log.llm_api
        if chat_log.llm_api and chat_log.llm_api.tools:
            # FR-2.3: Tool call loop (max MAX_TOOL_ITERATIONS iterations)
            for _ in range(MAX_TOOL_ITERATIONS):
                result = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=[_format_tool(tool) for tool in chat_log.llm_api.tools],
                    tool_choice="auto",
                    max_tokens=max_tokens,
                    top_p=top_p,
                    temperature=temperature,
                    user=conversation_id,
                )
                response = result.choices[0].message
                text = response.content or ""
                tool_calls = response.tool_calls

                if not tool_calls:
                    break

                # FR-2.4: Execute tools via chat_log.llm_api.async_call_tool
                for tool_call in tool_calls:
                    try:
                        tool_response = await chat_log.llm_api.async_call_tool(
                            tool_call.id,
                            {
                                "name": tool_call.function.name,
                                "arguments": json.loads(tool_call.function.arguments),
                            },
                        )
                    except (HomeAssistantError, vol.Invalid) as err:
                        tool_response = {"error": type(err).__name__, "message": str(err)}

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": json.dumps(tool_response),
                        }
                    )
        else:
            # No tools, single API call
            result = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                top_p=top_p,
                temperature=temperature,
                user=conversation_id,
            )
            response = result.choices[0].message
            text = response.content or ""

        # Fire event for conversation completion
        self.hass.bus.async_fire(
            EVENT_CONVERSATION_FINISHED,
            {
                "response": {"content": text},
                "user_input": user_input,
                "messages": messages,
                "agent_id": self.subentry.subentry_id,
            },
        )

        # Detect follow-up questions for continued conversation
        should_continue = text.rstrip().endswith("?") or any(
            phrase in text.lower()
            for phrase in [
                "which one", "would you like", "do you want", "would you prefer",
                "which do you", "what would you", "shall i", "should i",
                "choose from", "select from", "pick from",
            ]
        )

        intent_response.async_set_speech(text)
        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=conversation_id,
            continue_conversation=should_continue,
        )

