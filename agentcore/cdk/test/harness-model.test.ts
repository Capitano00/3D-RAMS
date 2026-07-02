import type { HarnessSpec } from '@aws/agentcore-cdk';
import { resolveHarnessSpec } from '../bin/cdk';

const BASE_SPEC: HarnessSpec = {
  name: 'rams_test_harness',
  model: {
    provider: 'bedrock',
    modelId: 'amazon.nova-micro-v1:0',
    apiFormat: 'converse_stream',
  },
  systemPrompt: 'Return a bounded test payload.',
  tools: [],
  skills: [],
  allowedTools: [],
  memory: { mode: 'disabled' },
  maxIterations: 1,
  maxTokens: 1000,
  timeoutSeconds: 60,
  truncation: { strategy: 'summarization' },
  environmentVariables: {},
};

afterEach(() => {
  delete process.env.RAMS_HARNESS_MODEL_PROVIDER;
  delete process.env.RAMS_HARNESS_MODEL_ID;
  delete process.env.RAMS_HARNESS_API_BASE;
  delete process.env.RAMS_HARNESS_API_KEY_ARN;
  delete process.env.RAMS_HARNESS_API_KEY_CREDENTIAL_NAME;
  delete process.env.OPENAI_BASE_URL;
  delete process.env.OPENAI_MODEL;
});

test('resolves harness model override through LiteLLM and a named AgentCore credential', () => {
  process.env.RAMS_HARNESS_MODEL_PROVIDER = 'lite_llm';
  process.env.RAMS_HARNESS_MODEL_ID = 'gpt-5.4-mini';
  process.env.RAMS_HARNESS_API_BASE = 'https://example.test/v1';
  process.env.RAMS_HARNESS_API_KEY_CREDENTIAL_NAME = 'openai-gateway';

  const spec = resolveHarnessSpec(BASE_SPEC, {
    'openai-gateway': {
      credentialProviderArn: 'arn:aws:bedrock-agentcore:eu-west-2:123456789012:apikeycredentialprovider/openai-gateway',
    },
  });

  expect(spec.model).toEqual({
    provider: 'lite_llm',
    modelId: 'gpt-5.4-mini',
    apiKeyArn: 'arn:aws:bedrock-agentcore:eu-west-2:123456789012:apikeycredentialprovider/openai-gateway',
    apiBase: 'https://example.test/v1',
  });
});
