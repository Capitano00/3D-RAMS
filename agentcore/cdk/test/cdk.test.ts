import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { AgentCoreStack, RAMS_WORKFLOW_HARNESS_NAMES } from '../lib/cdk-stack';

test('AgentCoreStack synthesizes with empty spec', () => {
  const app = new cdk.App();
  const stack = new AgentCoreStack(app, 'TestStack', {
    spec: {
      name: 'testproject',
      version: 1,
      managedBy: 'CDK' as const,
      runtimes: [],
      memories: [],
      credentials: [],
      evaluators: [],
      onlineEvalConfigs: [],
      configBundles: [],
      policyEngines: [],
      payments: [],
      agentCoreGateways: [],
      mcpRuntimeTools: [],
      unassignedTargets: [],
      datasets: [],
      knowledgeBases: [],
    },
  });
  const template = Template.fromStack(stack);
  template.hasOutput('StackNameOutput', {
    Description: 'Name of the CloudFormation Stack',
  });
});

test('RAMS workflow harness list includes every supervisor subagent harness', () => {
  expect(RAMS_WORKFLOW_HARNESS_NAMES).toEqual([
    'rams_geospatial_harness',
    'rams_planning_harness',
    'rams_material_harness',
    'rams_hazard_harness',
    'rams_open_web_harness',
    'rams_annotation_harness',
    'rams_briefing_harness',
    'rams_review_harness',
  ]);
});
