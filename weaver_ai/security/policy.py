from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException
from pydantic import BaseModel


class GuardrailDecision(BaseModel):
    text: str


def load_policies(path: Path) -> dict[str, Any]:
    """Load security policies from YAML file with validation."""
    # Validate path to prevent directory traversal
    try:
        resolved_path = path.resolve()
        # Ensure the path is within expected directory
        if not str(resolved_path).startswith(str(Path.cwd())):
            raise ValueError("Policy file path outside of application directory")
    except (RuntimeError, ValueError) as e:
        raise ValueError(f"Invalid policy file path: {e}")
    
    with path.open() as f:
        return yaml.safe_load(f) or {}


def normalize_text(text: str) -> str:
    """Normalize text to prevent obfuscation-based bypasses."""
    # Unicode normalization to handle different representations
    text = unicodedata.normalize('NFKD', text)
    
    # Remove zero-width characters and control characters
    text = ''.join(char for char in text if not unicodedata.category(char).startswith('C'))
    
    # Convert to lowercase for case-insensitive matching
    text = text.lower()
    
    # Remove multiple spaces
    text = ' '.join(text.split())
    
    return text


def input_guard(text: str, policies: dict[str, Any]) -> None:
    """Check input text against deny patterns with normalization."""
    if not text:
        return
    
    # Normalize the input text
    normalized_text = normalize_text(text)
    
    # Also check the original text to catch exact matches
    texts_to_check = [text, normalized_text]
    
    for pattern in policies.get("deny_patterns", []):
        # Normalize the pattern as well
        normalized_pattern = normalize_text(pattern)
        
        for check_text in texts_to_check:
            # Try exact match first
            if pattern in check_text or normalized_pattern in check_text:
                raise HTTPException(status_code=400, detail="Input blocked by security policy")
            
            # Try regex match for more complex patterns
            try:
                if re.search(re.escape(normalized_pattern), check_text, re.IGNORECASE):
                    raise HTTPException(status_code=400, detail="Input blocked by security policy")
            except re.error:
                # If regex is invalid, fall back to string matching
                continue


def output_guard(
    text: str, policies: dict[str, Any], *, redact: bool = True
) -> GuardrailDecision:
    """Apply output filtering and redaction policies."""
    if not text:
        return GuardrailDecision(text=text)
    
    if redact:
        # Apply PII redaction patterns
        for regex_pattern in policies.get("pii_regexes", []):
            try:
                # Compile regex with case-insensitive flag
                pattern = re.compile(regex_pattern, re.IGNORECASE)
                text = pattern.sub("[redacted]", text)
            except re.error:
                # Skip invalid regex patterns
                continue
        
        # Additional built-in PII patterns (use [redacted] to match test expectations)
        # SSN pattern (xxx-xx-xxxx)
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[redacted]', text)
        
        # Credit card pattern (xxxx-xxxx-xxxx-xxxx)
        text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[redacted]', text)
        
        # Email pattern
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[redacted]', text)
        
        # Phone number pattern
        text = re.sub(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', '[redacted]', text)
    
    return GuardrailDecision(text=text)
