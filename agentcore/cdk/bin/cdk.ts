#!/usr/bin/env node
import { AgentCoreStack, type HarnessConfig } from '../lib/cdk-stack';
import { ConfigIO, HarnessSpecSchema, type AwsDeploymentTarget, type HarnessSpec } from '@aws/agentcore-cdk';
import { App, type Environment } from 'aws-cdk-lib';
import * as path from 'path';
import * as fs from 'fs';

function toEnvironment(target: AwsDeploymentTarget): Environment {
  return {
    account: target.account === '000000000000' ? (process.env.AWS_ACCOUNT_ID || process.env.CDK_DEFAULT_ACCOUNT || target.account) : target.account,
    region: target.region,
  };
}

function sanitize(name: string): string {
  return name.replace(/_/g, '-');
}

function toStackName(projectName: string, targetName: string): string {
  return `AgentCore-${sanitize(projectName)}-${sanitize(targetName)}`;
}

type DeployedCredentials = Record<string, { credentialProviderArn: string; clientSecretArn?: string }>;

export function resolveHarnessSpec(spec: HarnessSpec, credentials?: DeployedCredentials): HarnessSpec {
  const provider = process.env.RAMS_HARNESS_MODEL_PROVIDER;
  const credentialName = process.env.RAMS_HARNESS_API_KEY_CREDENTIAL_NAME;
  const apiKeyArn = process.env.RAMS_HARNESS_API_KEY_ARN || (credentialName ? credentials?.[credentialName]?.credentialProviderArn : undefined);
  const apiBase = process.env.RAMS_HARNESS_API_BASE || process.env.OPENAI_BASE_URL;
  const shouldOverride = !!(provider || apiKeyArn || credentialName || process.env.RAMS_HARNESS_API_BASE);
  if (!shouldOverride) {
    return spec;
  }

  const resolvedProvider = provider || (apiBase ? 'lite_llm' : spec.model.provider);
  const modelId = process.env.RAMS_HARNESS_MODEL_ID || process.env.OPENAI_MODEL || spec.model.modelId;
  if (resolvedProvider === 'lite_llm' && !apiBase) {
    throw new Error('RAMS_HARNESS_API_BASE or OPENAI_BASE_URL is required when RAMS_HARNESS_MODEL_PROVIDER=lite_llm');
  }
  if (resolvedProvider === 'lite_llm' && !apiKeyArn) {
    throw new Error(
      'RAMS_HARNESS_API_KEY_ARN or RAMS_HARNESS_API_KEY_CREDENTIAL_NAME is required when RAMS_HARNESS_MODEL_PROVIDER=lite_llm'
    );
  }

  const model: Record<string, unknown> = {
    provider: resolvedProvider,
    modelId,
  };
  if (apiKeyArn) {
    model.apiKeyArn = apiKeyArn;
  }
  if (resolvedProvider === 'lite_llm') {
    model.apiBase = apiBase;
  } else if (process.env.RAMS_HARNESS_API_FORMAT) {
    model.apiFormat = process.env.RAMS_HARNESS_API_FORMAT;
  }

  return HarnessSpecSchema.parse({ ...spec, model });
}

export function resolveHarnessConfigs(configs: HarnessConfig[], credentials?: DeployedCredentials): HarnessConfig[] {
  return configs.map(config => {
    if (!config.spec) {
      return config;
    }
    const spec = resolveHarnessSpec(config.spec, credentials);
    return {
      ...config,
      apiKeyArn: spec.model.apiKeyArn,
      apiFormat: spec.model.apiFormat,
      spec,
    };
  });
}

async function main() {
  // Config root is parent of cdk/ directory. The CLI sets process.cwd() to agentcore/cdk/.
  const configRoot = path.resolve(process.cwd(), '..');
  const configIO = new ConfigIO({ baseDir: configRoot });

  const spec = await configIO.readProjectSpec();
  const targets = await configIO.readAWSDeploymentTargets();

  // The vended CDK project compiles against the published @aws/agentcore-cdk
  // schema type, which may lag the CLI's own AgentCoreProjectSpec (e.g. payments,
  // harnesses, gateway fields). Cast once so those fields are reachable.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const specAny = spec as any;

  // Extract MCP configuration from project spec.
  // Gateway fields are stored in agentcore.json but may not yet be on the
  const mcpSpec = specAny.agentCoreGateways?.length
    ? {
        agentCoreGateways: specAny.agentCoreGateways,
        mcpRuntimeTools: specAny.mcpRuntimeTools,
        unassignedTargets: specAny.unassignedTargets,
      }
    : undefined;

  // Read deployed state for credential ARNs (populated by pre-deploy identity setup)
  let deployedState: Record<string, unknown> | undefined;
  try {
    deployedState = JSON.parse(fs.readFileSync(path.join(configRoot, '.cli', 'deployed-state.json'), 'utf8'));
  } catch {
    // Deployed state may not exist on first deploy
  }

  if (targets.length === 0) {
    throw new Error('No deployment targets configured. Please define targets in agentcore/aws-targets.json');
  }

  // Read harness configs: the full validated spec drives the CFN resource; the
  // role-scoped fields drive the IAM role + container build.
  const projectRoot = path.resolve(configRoot, '..');

  // Read non-S3 KB connector-config files and pass their parsed contents to the
  // L3 verbatim. The L3 does not read files; it expects the parsed
  // connectorParameters keyed by the data source's connectorConfigFile path.
  const connectorParametersByFile: Record<string, Record<string, unknown>> = {};
  for (const kb of specAny.knowledgeBases ?? []) {
    for (const ds of kb.dataSources ?? []) {
      if (ds.type !== 'S3' && ds.connectorConfigFile) {
        const abs = path.resolve(projectRoot, ds.connectorConfigFile);
        try {
          connectorParametersByFile[ds.connectorConfigFile] = JSON.parse(fs.readFileSync(abs, 'utf-8'));
        } catch (err) {
          throw new Error(
            `Could not read connector config '${ds.connectorConfigFile}' for knowledge base '${kb.name}' at ${abs}: ${err instanceof Error ? err.message : err}`
          );
        }
      }
    }
  }

  // Synthesize an AWS::BedrockAgentCore::Harness resource for each harness entry in the spec.
  const harnessConfigs: HarnessConfig[] = [];
  for (const entry of specAny.harnesses ?? []) {
    const harnessDir = path.resolve(projectRoot, entry.path);
    const harnessPath = path.resolve(harnessDir, 'harness.json');
    try {
      const harnessSpec = HarnessSpecSchema.parse(JSON.parse(fs.readFileSync(harnessPath, 'utf-8')));
      harnessConfigs.push({
        name: entry.name,
        executionRoleArn: harnessSpec.executionRoleArn,
        // Only an `existing` memory ref carries a name to wire IAM against; managed memory is
        // owned by the harness (no sibling) and disabled has none — both resolve to undefined.
        memoryName: harnessSpec.memory?.mode === 'existing' ? harnessSpec.memory.name : undefined,
        containerUri: harnessSpec.containerUri,
        hasDockerfile: !!harnessSpec.dockerfile,
        dockerfile: harnessSpec.dockerfile,
        codeLocation: harnessSpec.dockerfile ? harnessDir : undefined,
        tools: harnessSpec.tools,
        skills: harnessSpec.skills,
        apiKeyArn: harnessSpec.model?.apiKeyArn,
        efsAccessPoints: harnessSpec.efsAccessPoints,
        s3AccessPoints: harnessSpec.s3AccessPoints,
        apiFormat: harnessSpec.model?.apiFormat,
        // Full spec + dir drive the AWS::BedrockAgentCore::Harness CFN resource.
        spec: harnessSpec,
        harnessDir,
      });
    } catch (err) {
      throw new Error(
        `Could not read harness.json for "${entry.name}" at ${harnessPath}: ${err instanceof Error ? err.message : err}`
      );
    }
  }

  const app = new App();

  for (const target of targets) {
    const env = toEnvironment(target);
    const stackName = toStackName(spec.name, target.name);

    // Extract credentials from deployed state for this target
    const targetState = (deployedState as Record<string, unknown>)?.targets as
      | Record<string, Record<string, unknown>>
      | undefined;
    const targetResources = targetState?.[target.name]?.resources as Record<string, unknown> | undefined;
    const credentials = targetResources?.credentials as DeployedCredentials | undefined;

    // Payment credential provider ARNs live in the same credentials map as identity credentials
    const paymentCredentials = credentials;

    const paymentSpec = specAny.payments?.length
      ? specAny.payments.map(
          (p: {
            name: string;
            description?: string;
            authorizerType: 'AWS_IAM' | 'CUSTOM_JWT';
            authorizerConfiguration?: unknown;
            autoPayment?: boolean;
            paymentToolAllowlist?: string[];
            networkPreferences?: string[];
            connectors: { name: string; provider?: string; credentialName: string }[];
          }) => ({
            name: p.name,
            description: p.description,
            authorizerType: p.authorizerType,
            authorizerConfiguration: p.authorizerConfiguration,
            autoPayment: p.autoPayment,
            paymentToolAllowlist: p.paymentToolAllowlist,
            networkPreferences: p.networkPreferences,
            connectors: p.connectors.map(c => {
              const credentialProviderArn = paymentCredentials?.[c.credentialName]?.credentialProviderArn;
              if (!credentialProviderArn) {
                // Fail fast with an actionable message rather than passing an empty
                // ARN that fails opaquely server-side at CreatePaymentConnector.
                throw new Error(
                  `Payment connector "${c.name}" on manager "${p.name}" references credential ` +
                    `"${c.credentialName}", but no deployed credential provider was found for it. ` +
                    `Run \`agentcore deploy\` so the credential provider is created first.`
                );
              }
              return { name: c.name, provider: c.provider, credentialProviderArn };
            }),
          })
        )
      : undefined;

    new AgentCoreStack(app, stackName, {
      spec,
      mcpSpec,
      credentials,
      connectorParametersByFile,
      harnesses: harnessConfigs.length > 0 ? resolveHarnessConfigs(harnessConfigs, credentials) : undefined,
      paymentSpec,
      env,
      description: `AgentCore stack for ${spec.name} deployed to ${target.name} (${target.region})`,
      tags: {
        'agentcore:project-name': spec.name,
        'agentcore:target-name': target.name,
      },
    });
  }

  app.synth();
}

if (require.main === module) {
  main().catch((error: unknown) => {
    console.error('AgentCore CDK synthesis failed:', error instanceof Error ? error.message : error);
    process.exit(1);
  });
}
