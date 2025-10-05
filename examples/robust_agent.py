#!/usr/bin/env python3
"""
Robust Agent Example with Model Selection and Advanced Features
Demonstrates production-ready patterns for Weaver AI agents
"""

import asyncio
import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from weaver_ai import Workflow
from weaver_ai.agents import BaseAgent, agent
from weaver_ai.cache import RedisCache
from weaver_ai.events import Event
from weaver_ai.models import ModelConfig, ModelRouter
from weaver_ai.telemetry import track_metrics

# ============================================================================
# Data Models
# ============================================================================


class ModelProvider(str, Enum):
    """Supported model providers"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    LOCAL = "local"
    MOCK = "mock"


class TaskComplexity(str, Enum):
    """Task complexity levels for model selection"""

    SIMPLE = "simple"  # Use fast, cheap models
    MODERATE = "moderate"  # Use balanced models
    COMPLEX = "complex"  # Use powerful models
    CRITICAL = "critical"  # Use best available with fallbacks


class Document(BaseModel):
    """Input document for processing"""

    id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    complexity: TaskComplexity = TaskComplexity.MODERATE
    language: str = "en"
    max_tokens: int = 2000
    temperature: float = 0.7
    require_citations: bool = False


class ProcessedChunk(BaseModel):
    """Processed document chunk"""

    document_id: str
    chunk_index: int
    content: str
    embeddings: list[float] = Field(default_factory=list)
    tokens_used: int
    model_used: str
    processing_time_ms: float


class Summary(BaseModel):
    """Document summary with metadata"""

    document_id: str
    summary: str
    key_points: list[str]
    entities: list[str]
    sentiment: float  # -1 to 1
    confidence: float
    model_used: str
    citations: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class QualityReport(BaseModel):
    """Quality assessment report"""

    document_id: str
    quality_score: float  # 0 to 1
    issues_found: list[str]
    suggestions: list[str]
    approved: bool
    reviewer_model: str


# ============================================================================
# Model Selection and Configuration
# ============================================================================


class ModelSelector:
    """Intelligent model selection based on task requirements"""

    # Model configurations by complexity
    MODEL_CONFIGS = {
        TaskComplexity.SIMPLE: [
            ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-3.5-turbo",
                max_tokens=1000,
                temperature=0.3,
                timeout=10,
                retry_count=2,
            ),
            ModelConfig(  # Fallback
                provider=ModelProvider.MOCK, model_name="mock-fast", max_tokens=1000
            ),
        ],
        TaskComplexity.MODERATE: [
            ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-4",
                max_tokens=2000,
                temperature=0.5,
                timeout=30,
                retry_count=3,
            ),
            ModelConfig(  # Fallback
                provider=ModelProvider.ANTHROPIC,
                model_name="claude-3-haiku",
                max_tokens=2000,
                temperature=0.5,
            ),
        ],
        TaskComplexity.COMPLEX: [
            ModelConfig(
                provider=ModelProvider.ANTHROPIC,
                model_name="claude-3-opus",
                max_tokens=4000,
                temperature=0.7,
                timeout=60,
                retry_count=3,
            ),
            ModelConfig(  # Fallback
                provider=ModelProvider.OPENAI, model_name="gpt-4-turbo", max_tokens=4000
            ),
        ],
        TaskComplexity.CRITICAL: [
            ModelConfig(
                provider=ModelProvider.ANTHROPIC,
                model_name="claude-3-opus",
                max_tokens=8000,
                temperature=0.3,
                timeout=120,
                retry_count=5,
                use_caching=True,
            ),
            ModelConfig(  # Fallback 1
                provider=ModelProvider.OPENAI, model_name="gpt-4-turbo", max_tokens=8000
            ),
            ModelConfig(  # Fallback 2
                provider=ModelProvider.GOOGLE, model_name="gemini-pro", max_tokens=8000
            ),
        ],
    }

    @classmethod
    def get_configs(cls, complexity: TaskComplexity) -> list[ModelConfig]:
        """Get model configurations for given complexity"""
        return cls.MODEL_CONFIGS.get(
            complexity, cls.MODEL_CONFIGS[TaskComplexity.MODERATE]
        )


# ============================================================================
# Production Agents with Advanced Features
# ============================================================================


@agent(
    agent_type="document_processor",
    capabilities=["text_processing", "chunking", "embedding"],
    memory_strategy="analyst",
    cache_enabled=True,
)
class DocumentProcessor(BaseAgent):
    """Processes documents with intelligent model selection"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = RedisCache(prefix="doc_processor")
        self.model_selector = ModelSelector()

    async def process(self, event: Event) -> list[ProcessedChunk]:
        document: Document = event.data

        # Check cache first
        cache_key = f"{document.id}:{document.complexity}"
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            self.logger.info(f"Cache hit for document {document.id}")
            return cached_result

        # Select model based on complexity
        model_configs = self.model_selector.get_configs(document.complexity)

        # Process with fallback support
        chunks = []
        for i, chunk_text in enumerate(self._chunk_document(document.content)):
            chunk = await self._process_chunk_with_fallback(
                document, i, chunk_text, model_configs
            )
            chunks.append(chunk)

        # Cache the result
        await self.cache.set(cache_key, chunks, ttl=3600)

        # Track metrics
        await track_metrics(
            {
                "document_chunks": len(chunks),
                "total_tokens": sum(c.tokens_used for c in chunks),
                "cache_miss": 1,
            }
        )

        return chunks

    def _chunk_document(self, content: str, chunk_size: int = 1000) -> list[str]:
        """Smart document chunking with overlap"""
        words = content.split()
        chunks = []
        overlap = 100  # Word overlap between chunks

        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i : i + chunk_size])
            chunks.append(chunk)

        return chunks

    async def _process_chunk_with_fallback(
        self,
        document: Document,
        chunk_index: int,
        chunk_text: str,
        model_configs: list[ModelConfig],
    ) -> ProcessedChunk:
        """Process chunk with model fallback"""

        start_time = asyncio.get_event_loop().time()
        last_error = None

        for config in model_configs:
            try:
                # Initialize model router with specific config
                router = ModelRouter(config)

                # Build prompt
                prompt = self._build_prompt(chunk_text, document.metadata)

                # Process with model
                response = await router.generate(
                    prompt,
                    max_tokens=config.max_tokens,
                    temperature=document.temperature,
                )

                # Generate embeddings if available
                embeddings = []
                if hasattr(router, "embed"):
                    embeddings = await router.embed(chunk_text)

                processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

                return ProcessedChunk(
                    document_id=document.id,
                    chunk_index=chunk_index,
                    content=response.text,
                    embeddings=embeddings,
                    tokens_used=response.tokens_used,
                    model_used=config.model_name,
                    processing_time_ms=processing_time,
                )

            except Exception as e:
                self.logger.warning(f"Model {config.model_name} failed: {e}")
                last_error = e
                continue

        # All models failed
        raise Exception(f"All models failed. Last error: {last_error}")

    def _build_prompt(self, chunk: str, metadata: dict) -> str:
        """Build processing prompt with metadata context"""
        context = json.dumps(metadata, indent=2) if metadata else "No metadata"
        return f"""Process this document chunk:

Context: {context}

Chunk:
{chunk}

Extract key information and provide structured output."""


@agent(
    agent_type="summarizer",
    capabilities=["summarization", "entity_extraction", "sentiment_analysis"],
    memory_strategy="coordinator",
)
class IntelligentSummarizer(BaseAgent):
    """Creates summaries with configurable model selection"""

    async def process(self, event: Event) -> Summary:
        chunks: list[ProcessedChunk] = event.data

        if not chunks:
            raise ValueError("No chunks to summarize")

        document_id = chunks[0].document_id

        # Determine complexity based on chunk count
        complexity = self._determine_complexity(len(chunks))

        # Get appropriate model
        model_configs = ModelSelector.get_configs(complexity)
        model_config = model_configs[0]  # Primary model

        # Initialize router with specific model
        router = ModelRouter(model_config)

        # Combine chunks intelligently
        combined_text = self._combine_chunks(chunks)

        # Generate summary with specific requirements
        summary_prompt = f"""Summarize this document:

{combined_text}

Requirements:
1. Provide a concise summary (max 500 words)
2. Extract 5-10 key points
3. Identify main entities (people, organizations, locations)
4. Determine overall sentiment (-1 to 1)
5. Assess confidence level (0 to 1)
"""

        response = await router.generate(
            summary_prompt,
            max_tokens=model_config.max_tokens,
            temperature=0.5,
            response_format="json",  # Request structured output
        )

        # Parse structured response
        try:
            result = json.loads(response.text)
        except json.JSONDecodeError:
            # Fallback to text parsing
            result = self._parse_text_response(response.text)

        # Extract citations if requested
        citations = self._extract_citations(combined_text)

        return Summary(
            document_id=document_id,
            summary=result.get("summary", response.text[:500]),
            key_points=result.get("key_points", []),
            entities=result.get("entities", []),
            sentiment=result.get("sentiment", 0.0),
            confidence=result.get("confidence", 0.8),
            model_used=model_config.model_name,
            citations=citations,
            metrics={
                "chunks_processed": len(chunks),
                "total_tokens": sum(c.tokens_used for c in chunks),
                "model_provider": model_config.provider,
            },
        )

    def _determine_complexity(self, chunk_count: int) -> TaskComplexity:
        """Determine task complexity based on chunk count"""
        if chunk_count <= 5:
            return TaskComplexity.SIMPLE
        elif chunk_count <= 20:
            return TaskComplexity.MODERATE
        elif chunk_count <= 50:
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.CRITICAL

    def _combine_chunks(self, chunks: list[ProcessedChunk]) -> str:
        """Intelligently combine chunks removing redundancy"""
        # Simple combination for demo - production would use semantic deduplication
        return "\n\n".join(chunk.content for chunk in chunks[:50])  # Limit for demo

    def _extract_citations(self, text: str) -> list[str]:
        """Extract citations from text"""
        # Simplified - production would use regex or NLP
        citations = []
        lines = text.split("\n")
        for line in lines:
            if "http" in line or "doi:" in line:
                citations.append(line.strip())
        return citations[:10]  # Limit citations

    def _parse_text_response(self, text: str) -> dict:
        """Fallback text parsing when JSON fails"""
        return {
            "summary": text[:500],
            "key_points": text.split("\n")[:5],
            "entities": [],
            "sentiment": 0.0,
            "confidence": 0.7,
        }


@agent(
    agent_type="quality_validator",
    capabilities=["validation", "fact_checking"],
    memory_strategy="validator",
)
class QualityValidator(BaseAgent):
    """Validates output quality with specialized models"""

    async def process(self, event: Event) -> QualityReport:
        summary: Summary = event.data

        # Use a different model for validation (cross-validation)
        validator_config = ModelConfig(
            provider=ModelProvider.ANTHROPIC,
            model_name="claude-3-haiku",  # Fast validation model
            max_tokens=1000,
            temperature=0.2,  # Low temperature for consistency
        )

        router = ModelRouter(validator_config)

        # Validation prompt
        validation_prompt = f"""Evaluate this summary for quality:

Summary: {summary.summary}
Key Points: {summary.key_points}
Confidence: {summary.confidence}

Check for:
1. Accuracy and factual correctness
2. Completeness of key points
3. Clarity and coherence
4. Potential biases or issues

Provide a quality score (0-1) and specific feedback."""

        # Generate validation (response would be used in production)
        _ = await router.generate(validation_prompt)

        # Parse validation results
        quality_score = summary.confidence * 0.9  # Simplified
        issues = []
        suggestions = []

        if summary.confidence < 0.7:
            issues.append("Low confidence summary")
            suggestions.append("Consider using more powerful model")

        if len(summary.key_points) < 3:
            issues.append("Insufficient key points extracted")
            suggestions.append("Reprocess with deeper analysis")

        approved = quality_score >= 0.7 and len(issues) == 0

        return QualityReport(
            document_id=summary.document_id,
            quality_score=quality_score,
            issues_found=issues,
            suggestions=suggestions,
            approved=approved,
            reviewer_model=validator_config.model_name,
        )


# ============================================================================
# Advanced Workflow with Model Management
# ============================================================================


async def run_production_workflow():
    """Production-ready workflow with model selection and monitoring"""

    print("=== Production Document Processing Workflow ===\n")

    # Configure workflow with specific models per agent
    workflow = (
        Workflow("document_pipeline", redis_url="redis://localhost:6379")
        # Document processor with GPT-4 for moderate complexity
        .add_agent(
            DocumentProcessor,
            model="gpt-4",
            api_key="sk-your-key",  # BYOK support
            temperature=0.5,
            max_tokens=2000,
            error_handling="retry",
            max_retries=3,
            retry_delay=2.0,
        )
        # Summarizer with Claude for high quality
        .add_agent(
            IntelligentSummarizer,
            model="claude-3-opus",
            api_key="anthropic-key",
            temperature=0.3,
            error_handling="retry",
            max_retries=2,
        )
        # Validator with fast model
        .add_agent(
            QualityValidator,
            model="claude-3-haiku",
            error_handling="skip",  # Optional validation
        )
        # Workflow configuration
        .with_observability(True)
        .with_intervention(True)
        .with_timeout(300)  # 5 minute timeout
        # Add conditional routing for failed validation
        .add_route(
            when=lambda result: isinstance(result, QualityReport)
            and not result.approved,
            from_agent="quality_validator",
            to_agent="summarizer",  # Retry summarization
            priority=10,
        )
    )

    # Test documents with different complexities
    test_documents = [
        Document(
            id="doc_001",
            content=(
                "Short simple document about Python programming. "
                "Python is a high-level programming language."
            ),
            complexity=TaskComplexity.SIMPLE,
            temperature=0.3,
        ),
        Document(
            id="doc_002",
            content="Complex technical document " * 100,  # Long document
            complexity=TaskComplexity.COMPLEX,
            temperature=0.7,
            require_citations=True,
        ),
        Document(
            id="doc_003",
            content="Critical financial report requiring high accuracy " * 50,
            complexity=TaskComplexity.CRITICAL,
            temperature=0.2,
            max_tokens=8000,
        ),
    ]

    # Process documents
    for doc in test_documents:
        print(f"\n📄 Processing {doc.id} (Complexity: {doc.complexity.value})")
        print("-" * 50)

        try:
            # Run workflow
            result = await workflow.run(doc)

            if result.state == "completed":
                report: QualityReport = result.result
                print(f"✅ Quality Score: {report.quality_score:.2f}")
                print(f"📊 Approved: {report.approved}")
                print(f"🤖 Reviewer Model: {report.reviewer_model}")

                # Show metrics
                print("\nMetrics:")
                for agent_id, metrics in result.metrics.items():
                    print(f"  {agent_id}: {metrics}")

            else:
                print(f"❌ Workflow failed: {result.error}")

        except Exception as e:
            print(f"❌ Error processing document: {e}")

        print("-" * 50)

    print("\n=== Workflow Complete ===")


# ============================================================================
# Model Pool Management Example
# ============================================================================


async def run_model_pool_example():
    """Demonstrate connection pooling for high throughput"""

    print("\n=== Model Connection Pool Example ===\n")

    from weaver_ai.models import ConnectionPool

    # Create connection pool with multiple model instances
    pool_config = {
        "pool_size": 5,
        "max_overflow": 10,
        "timeout": 30,
        "recycle": 3600,  # Recycle connections after 1 hour
        "pre_ping": True,  # Test connections before use
    }

    # Initialize pool with different models
    model_pool = ConnectionPool(
        models=[
            ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-3.5-turbo"),
            ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4"),
            ModelConfig(provider=ModelProvider.ANTHROPIC, model_name="claude-3-haiku"),
        ],
        **pool_config,
    )

    # Simulate high-throughput processing
    async def process_with_pool(text: str, request_id: int):
        # Get available model from pool
        async with model_pool.get_model() as model:
            response = await model.generate(f"Request {request_id}: {text}")
            return response

    # Process multiple requests concurrently
    tasks = []
    for i in range(20):
        task = process_with_pool("Process this text", i)
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    print(f"Processed {len(results)} requests using model pool")

    # Show pool statistics
    stats = model_pool.get_stats()
    print("\nPool Statistics:")
    print(f"  Active connections: {stats['active']}")
    print(f"  Idle connections: {stats['idle']}")
    print(f"  Total created: {stats['created']}")
    print(f"  Pool efficiency: {stats['efficiency']:.1%}")


if __name__ == "__main__":
    # Run the production workflow
    asyncio.run(run_production_workflow())

    # Uncomment to run pool example
    # asyncio.run(run_model_pool_example())
