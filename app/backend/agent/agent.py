from dataclasses import dataclass
from typing import Sequence, Optional
from httpx import AsyncClient
import logging

from pydantic_ai import Agent, Tool
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from groq import AsyncGroq
from openai import AsyncAzureOpenAI

from app.backend.config.config import Settings, settings


@dataclass
class AgentDependencies:
    settings: Settings
    session: AsyncClient


def create_groq_agent(
    groq_model: GroqModel,
    tools: Sequence[Tool[AgentDependencies]],
    system_prompt: str,
) -> Agent[AgentDependencies]:
    """
    Creates a PydanticAI Agent that uses Groq models.

    Args:
        groq_model: Groq model for PydanticAI.

    Returns:
        PydanticAI Agent that uses Groq models.
    """

    return Agent(
        model=groq_model,
        deps_type=AgentDependencies,
        system_prompt=system_prompt,
        tools=tools,
    )
    

def create_groq_model(groq_client: AsyncGroq) -> GroqModel:
    """
    Creates a GroqModel instance for PydanticAI.
    Args:
        groq_client: Groq client for PydanticAI.

    Returns:
        GroqModel instance for PydanticAI.
    """
    model = GroqModel(model_name=settings.GROQ_LLM_MODEL, provider=GroqProvider(groq_client=groq_client))
    return model

def create_openai_agent(openai_model: OpenAIModel,
                        tools: Sequence[Tool[AgentDependencies]],
                        system_prompt: str) -> Agent[AgentDependencies]:
    """
    Creates a PydanticAI Agent that uses OpenAI models.
    Args:
        openai_model: OpenAI model for PydanticAI.
        tools: List of tools for the agent.
        system_prompt: System prompt for the agent.
    Returns:
        PydanticAI Agent that uses OpenAI models.
    """
    return Agent(
        model=openai_model,
        deps_type=AgentDependencies,
        system_prompt=system_prompt,
        tools=tools,
    )
def create_openi_model(openai_client: AsyncAzureOpenAI) -> OpenAIModel:
    """
    Creates an OpenAIModel instance for PydanticAI.
    Args:
        openai_client: OpenAI client for PydanticAI.
    Returns:
        OpenAIModel instance for PydanticAI.
    """
    model = OpenAIModel('gpt-4o', provider=OpenAIProvider(openai_client=openai_client))
    return model


def create_openai_client_gpt() -> AsyncAzureOpenAI:
    """Creates and returns an AsyncAzureOpenAI client instance for GPT."""
    client = AsyncAzureOpenAI(
        azure_endpoint=settings.AZURE_GPT_ENDPOINT,
        api_key=settings.AZURE_GPT_API_KEY.get_secret_value(),
        api_version=settings.AZURE_GPT_API_VERSION,
    )
    return client