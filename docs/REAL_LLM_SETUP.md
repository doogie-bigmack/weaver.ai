# Real LLM Integration with SailPoint MCP

## Setup

1. Set your OpenAI API key as an environment variable:
   ```bash
   export OPENAI_API_KEY='sk-proj-...'  # Replace with your actual key
   ```

2. Run the demo:
   ```bash
   python3 demo_sailpoint_gpt.py
   ```

## What This Does

The integration combines:
- **SailPoint IIQ MCP Server**: Provides identity governance data (currently mock data)
- **OpenAI GPT-4**: Analyzes queries and generates intelligent responses
- **Weaver.AI Agents**: Orchestrates tool execution and LLM interactions

## Example Output

When you run the demo, you'll see:
1. GPT connection test
2. SailPoint data retrieval (1250 users, 85 roles)
3. GPT analysis of the data
4. Token usage statistics

## Full Test Suite

For more comprehensive testing:
```bash
python3 test_sailpoint_llm_fixed.py
```

This runs multiple queries showing how GPT can:
- Count users and roles
- Calculate ratios (active/inactive users)
- Compare role types (business vs IT)

## API Key Security

- Never commit API keys to git
- Use environment variables or .env files
- The demo will prompt for the key if not set

## Costs

- Each test run uses ~100-200 tokens
- With GPT-4o-mini: < $0.01 per run
- Monitor usage at: https://platform.openai.com/usage
