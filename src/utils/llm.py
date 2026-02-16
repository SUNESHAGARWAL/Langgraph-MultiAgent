"""
LLM Utilities
=============

Helper functions for LLM initialization and management.

Author: Claude Code
Date: 2024-12-15
"""

from langchain_openai import AzureChatOpenAI
from src.core.config import config


def get_llm(temperature: float = None, deployment: str = None) -> AzureChatOpenAI:
    """
    Get configured Azure OpenAI LLM instance.

    Args:
        temperature: Optional temperature override (0.0-1.0). Defaults to config value.
        deployment: Optional deployment name override. Defaults to GPT-4o from config.

    Returns:
        AzureChatOpenAI: Configured LLM instance

    Example:
        >>> llm = get_llm()  # Use defaults from config
        >>> llm = get_llm(temperature=0.7)  # Override temperature
        >>> llm = get_llm(deployment="gpt-4o-mini")  # Use different model
    """
    # Use provided values or fall back to config
    final_temperature = temperature if temperature is not None else config.azure_openai.temperature
    final_deployment = deployment if deployment is not None else config.azure_openai.gpt4o_deployment

    llm = AzureChatOpenAI(
        azure_endpoint=config.azure_openai.endpoint,
        api_key=config.azure_openai.api_key,
        api_version=config.azure_openai.api_version,
        azure_deployment=final_deployment,
        temperature=final_temperature,
        max_tokens=config.azure_openai.max_tokens,
    )

    return llm


def get_mini_llm(temperature: float = None) -> AzureChatOpenAI:
    """
    Get configured GPT-4o-mini LLM (faster, cheaper for simple tasks).

    Args:
        temperature: Optional temperature override (0.0-1.0). Defaults to config value.

    Returns:
        AzureChatOpenAI: Configured mini LLM instance

    Example:
        >>> mini_llm = get_mini_llm()  # Use for simple tasks
    """
    return get_llm(
        temperature=temperature,
        deployment=config.azure_openai.gpt4o_mini_deployment
    )
