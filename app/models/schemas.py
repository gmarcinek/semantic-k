"""Pydantic models and schemas for the application."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Chat request model."""
    prompt: str = Field(..., description="User's message/prompt")
    session_id: Optional[str] = Field(None, description="Session identifier for conversation continuity")


class WikipediaResearchRequest(BaseModel):
    """Request to research a specific Wikipedia article."""
    session_id: str = Field(..., description="Session identifier")
    pageid: int = Field(..., description="Wikipedia page ID to research")
    title: Optional[str] = Field(None, description="Optional article title for logging/UI")


class ChatMessage(BaseModel):
    """Chat message model for history."""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    metadata: Optional[Dict] = Field(None, description="Additional metadata")
    model: Optional[str] = Field(None, description="Model used for generation")


class AdvisoryResult(BaseModel):
    """Result from an advisory tool."""
    tool_name: str = Field(..., description="Name of the advisory tool")
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    reasoning: str = Field(..., description="Explanation of the result")
    metadata: Dict = Field(default_factory=dict, description="Additional metadata")


class ClassificationMetadata(BaseModel):
    """Metadata about prompt classification."""
    topic: str = Field(..., description="Identified topic/category")
    topic_relevance: float = Field(..., ge=0.0, le=1.0, description="Topic relevance score")
    is_dangerous: float = Field(..., ge=0.0, le=1.0, description="Security risk score")
    is_continuation: float = Field(..., ge=0.0, le=1.0, description="Conversation continuation score")
    topic_change: float = Field(..., ge=0.0, le=1.0, description="Topic change detection score")
    summary: str = Field(..., description="Human-readable summary")
    intent: str = Field(default="INFO", description="User intent: INFO or DEEP_DIVE")
    intent_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence of intent classification")
    needs_wikipedia: bool = Field(default=False, description="Set true if reliable answer needs Wikipedia sources")
    advisory_results: List[AdvisoryResult] = Field(default_factory=list, description="Results from advisory tools")


class SessionResetRequest(BaseModel):
    """Session reset request."""
    session_id: Optional[str] = Field(None, description="Session ID to reset")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    config_loaded: bool
    default_model: str
    available_models: List[str]


class ConfigResponse(BaseModel):
    """Configuration response (sanitized)."""
    default_model: str
    models: Dict
    routing_rules: List[Dict]


class WikipediaSource(BaseModel):
    """Wikipedia article source/citation."""
    title: str = Field(..., description="Wikipedia article title")
    url: str = Field(..., description="Wikipedia article URL")
    pageid: int = Field(..., description="Wikipedia page ID")
    extract: str = Field(..., description="Article extract/snippet")
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relevance score from reranker")
    image_url: Optional[str] = Field(None, description="Optional lead image/thumbnail URL")


class WikipediaMetadata(BaseModel):
    """Metadata about Wikipedia search and sources used."""
    query: str = Field(..., description="Original search query")
    sources: List[WikipediaSource] = Field(default_factory=list, description="Wikipedia sources used")
    total_results: int = Field(..., description="Total number of search results")
    reranked: bool = Field(False, description="Whether results were reranked")
    reranking_model: Optional[str] = Field(None, description="Model used for reranking")


class ChatMessageWithSources(ChatMessage):
    """Chat message with Wikipedia sources."""
    wikipedia_metadata: Optional[WikipediaMetadata] = Field(None, description="Wikipedia source information")
