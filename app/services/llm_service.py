"""LLM service for managing API communication with language models."""
import json
import logging
import os
from typing import Dict, List, Optional

from openai import AsyncOpenAI
from app.utils.colored_logger import get_plugin_logger

logger = logging.getLogger(__name__)
plugin_logger = get_plugin_logger(__name__, 'llm')


class LLMService:
    """Service for managing LLM API calls."""

    def __init__(self):
        """Initialize LLM service."""
        self._clients: Dict[str, AsyncOpenAI] = {}

    def _get_client(self, api_key_env: str) -> AsyncOpenAI:
        """Get or create OpenAI client for a specific API key.

        Args:
            api_key_env: Environment variable name for API key

        Returns:
            AsyncOpenAI client

        Raises:
            ValueError: If API key not found in environment
        """
        if api_key_env not in self._clients:
            api_key = os.getenv(api_key_env)
            if not api_key:
                raise ValueError(f"{api_key_env} not set in environment variables")

            self._clients[api_key_env] = AsyncOpenAI(api_key=api_key)
            logger.info(f"Created OpenAI client using {api_key_env}")

        return self._clients[api_key_env]

    async def generate_completion(
        self,
        messages: List[Dict],
        model_config: Dict,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None
    ) -> str:
        """Generate completion from LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model_config: Model configuration from config.yml
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            response_format: Optional response format (e.g., {"type": "json_object"})

        Returns:
            Generated text content

        Raises:
            Exception: If API call fails
        """
        try:
            client = self._get_client(model_config['api_key_env'])

            # Build API parameters
            api_params = {
                "model": model_config['model_id'],
                "messages": messages,
            }

            # Add optional parameters
            if max_tokens:
                api_params['max_completion_tokens'] = max_tokens
            elif 'max_completion_tokens' in model_config:
                api_params['max_completion_tokens'] = model_config['max_completion_tokens']

            # Temperature handling (GPT-5 doesn't support it)
            if temperature is not None:
                if model_config.get('model_id') != 'gpt-5':
                    api_params['temperature'] = temperature
            elif 'temperature' in model_config and model_config.get('model_id') != 'gpt-5':
                api_params['temperature'] = model_config['temperature']

            # Response format (for structured outputs)
            if response_format:
                api_params['response_format'] = response_format

            logger.debug(f"Calling LLM with model {model_config['model_id']}")

            response = await client.chat.completions.create(**api_params)
            content = response.choices[0].message.content

            logger.debug(f"Received response from LLM: {len(content)} chars")

            # Log LLM response
            preview = content[:150] + "..." if len(content) > 150 else content
            plugin_logger.info(f"🤖 LLM Response ({model_config['model_id']}): {len(content)} chars")
            plugin_logger.info(f"   {preview}")

            return content

        except Exception as e:
            logger.error(f"LLM API error: {e}", exc_info=True)
            raise

    async def generate_structured_completion(
        self,
        messages: List[Dict],
        model_config: Dict,
        temperature: Optional[float] = 0.3
    ) -> Dict:
        """Generate structured JSON completion from LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model_config: Model configuration from config.yml
            temperature: Temperature for generation (lower for structured output)

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If response is not valid JSON
            Exception: If API call fails
        """
        response_format = {"type": "json_object"}

        # Ensure the system message asks for JSON
        json_instruction = "\n\nYou must respond with valid JSON only."
        if messages and messages[0].get('role') == 'system':
            messages[0]['content'] += json_instruction
        else:
            messages.insert(0, {
                'role': 'system',
                'content': f"You are a helpful assistant.{json_instruction}"
            })

        content = await self.generate_completion(
            messages=messages,
            model_config=model_config,
            temperature=temperature,
            response_format=response_format
        )

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {content}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")

    async def generate_chat_response(
        self,
        prompt: str,
        chat_history: List[Dict],
        system_prompt: str,
        model_config: Dict
    ) -> str:
        """Generate chat response with conversation context.

        Args:
            prompt: Current user prompt
            chat_history: Previous conversation messages
            system_prompt: System prompt for context
            model_config: Model configuration

        Returns:
            Generated response text
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add chat history
        messages.extend(chat_history)

        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        return await self.generate_completion(messages, model_config)
