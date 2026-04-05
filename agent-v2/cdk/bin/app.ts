#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { AgentV2Stack } from '../lib/agent-v2-stack';

const app = new cdk.App();

new AgentV2Stack(app, 'AgentV2Stack', {
  env: {
    account: '147885311931',
    region: 'eu-central-1',
  },
  description: 'ECS Fargate stack for agent-v2 (backend + web)',
});
