# Legacy Bedrock Provider Note

This file is retained so old links do not send operators looking for a missing document. Bedrock is no longer the standard 3D-RAMS live model-provider path.

Current live model testing should use the team's OpenAI-compatible hosted gateway:

```bash
ENABLE_LIVE_MODEL=true
RAMS_LLM_PROVIDER=openai
ENTRY_AGENT_PROVIDER=openai
ENTRY_INTAKE_PROVIDER=openai
OPENAI_BASE_URL=https://<gateway-host>/v1
OPENAI_API_KEY=<local-or-hosted-secret>
OPENAI_MODEL=gpt-5.4-mini
python3 scripts/openai-gateway-smoke.py
```

Keep gateway URLs and API keys in hosted secrets or local untracked `.env` files only. Do not commit secrets, signed URLs, runtime ARNs, account IDs, private session ids, or real client/site data.

`bedrock-agentcore` package, ARN, IAM action, and service names may still appear in AgentCore runtime plumbing. Those names do not make Bedrock the model provider.

Use `RAMS_LLM_PROVIDER=bedrock` and `ENABLE_BEDROCK=true` only for deliberate legacy-provider experiments outside the standard demo/smoke path. Do not make Bedrock mandatory for teammate testing, CI, or Demo1.
