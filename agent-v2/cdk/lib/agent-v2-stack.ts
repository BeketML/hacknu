import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as servicediscovery from 'aws-cdk-lib/aws-servicediscovery';
import * as iam from 'aws-cdk-lib/aws-iam';

export class AgentV2Stack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ── VPC: public subnets only (no NAT gateway — avoids EIP quota issues)
    // Fargate tasks get public IPs so they can pull images from Docker Hub.
    const vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        { name: 'Public', subnetType: ec2.SubnetType.PUBLIC, cidrMask: 24 },
      ],
    });

    // ── ECS Cluster ───────────────────────────────────────────────────────────
    const cluster = new ecs.Cluster(this, 'Cluster', {
      vpc,
      clusterName: 'agent-v2',
      enableFargateCapacityProviders: true,
    });

    // ── Cloud Map namespace for service-to-service DNS ─────────────────────
    const namespace = new servicediscovery.PrivateDnsNamespace(this, 'Namespace', {
      name: 'agent.local',
      vpc,
      description: 'Private DNS for agent-v2 services',
    });

    // ── Secrets Manager (all .env values stored as one JSON secret) ──────────
    // Created beforehand with:
    //   aws secretsmanager create-secret --name agent-v2/env --secret-string '{...}'
    const envSecret = secretsmanager.Secret.fromSecretNameV2(
      this, 'EnvSecret', 'agent-v2/env',
    );

    // ── Shared task execution role ────────────────────────────────────────────
    const executionRole = new iam.Role(this, 'ExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy'),
      ],
    });
    envSecret.grantRead(executionRole);

    // ── CloudWatch log groups ─────────────────────────────────────────────────
    const backendLogs = new logs.LogGroup(this, 'BackendLogs', {
      logGroupName: '/ecs/agent-v2/backend',
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const webLogs = new logs.LogGroup(this, 'WebLogs', {
      logGroupName: '/ecs/agent-v2/web',
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ═══════════════════════════════════════════════════════════════════════
    //  BACKEND SERVICE
    // ═══════════════════════════════════════════════════════════════════════

    const backendTaskDef = new ecs.FargateTaskDefinition(this, 'BackendTaskDef', {
      cpu: 512,
      memoryLimitMiB: 1024,
      executionRole,
      taskRole: new iam.Role(this, 'BackendTaskRole', {
        assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
        inlinePolicies: {
          BedrockAccess: new iam.PolicyDocument({
            statements: [
              new iam.PolicyStatement({
                actions: ['bedrock:*'],
                resources: ['*'],
              }),
            ],
          }),
        },
      }),
    });

    backendTaskDef.addContainer('backend', {
      image: ecs.ContainerImage.fromRegistry('batyrbaev0520/agent-v2-backend:latest'),
      containerName: 'backend',
      portMappings: [{ containerPort: 8000 }],
      environment: {
        PYTHONUNBUFFERED: '1',
      },
      secrets: {
        GOOGLE_API_KEY:        ecs.Secret.fromSecretsManager(envSecret, 'GOOGLE_API_KEY'),
        PERPLEXITY_API_KEY:    ecs.Secret.fromSecretsManager(envSecret, 'PERPLEXITY_API_KEY'),
        AWS_ACCESS_KEY_ID:     ecs.Secret.fromSecretsManager(envSecret, 'AWS_ACCESS_KEY_ID'),
        AWS_SECRET_ACCESS_KEY: ecs.Secret.fromSecretsManager(envSecret, 'AWS_SECRET_ACCESS_KEY'),
        AWS_DEFAULT_REGION:    ecs.Secret.fromSecretsManager(envSecret, 'AWS_DEFAULT_REGION'),
      },
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'backend',
        logGroup: backendLogs,
      }),
      healthCheck: {
        command: [
          'CMD-SHELL',
          'python -c "import urllib.request; urllib.request.urlopen(\'http://localhost:8000/healthz\')"',
        ],
        interval: cdk.Duration.seconds(15),
        timeout: cdk.Duration.seconds(5),
        retries: 5,
        startPeriod: cdk.Duration.seconds(30),
      },
    });

    // Backend SG: only allow inbound from within the VPC
    const backendSg = new ec2.SecurityGroup(this, 'BackendSg', {
      vpc,
      description: 'agent-v2 backend',
      allowAllOutbound: true,
    });
    backendSg.addIngressRule(
      ec2.Peer.ipv4(vpc.vpcCidrBlock),
      ec2.Port.tcp(8000),
      'Allow VPC-internal traffic to backend',
    );

    const backendService = new ecs.FargateService(this, 'BackendService', {
      cluster,
      taskDefinition: backendTaskDef,
      serviceName: 'agent-v2-backend',
      desiredCount: 1,
      securityGroups: [backendSg],
      // Public subnet + public IP so the task can pull from Docker Hub (no NAT)
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      assignPublicIp: true,
      enableExecuteCommand: true,
      capacityProviderStrategies: [
        { capacityProvider: 'FARGATE', weight: 1 },
      ],
      cloudMapOptions: {
        name: 'backend',
        cloudMapNamespace: namespace,
        dnsRecordType: servicediscovery.DnsRecordType.A,
        dnsTtl: cdk.Duration.seconds(10),
      },
    });

    // ═══════════════════════════════════════════════════════════════════════
    //  WEB SERVICE  (nginx + React SPA)
    // ═══════════════════════════════════════════════════════════════════════

    const webTaskDef = new ecs.FargateTaskDefinition(this, 'WebTaskDef', {
      cpu: 256,
      memoryLimitMiB: 512,
      executionRole,
    });

    webTaskDef.addContainer('web', {
      image: ecs.ContainerImage.fromRegistry('batyrbaev0520/agent-v2-web:latest'),
      containerName: 'web',
      portMappings: [{ containerPort: 80 }],
      environment: {
        BACKEND_HOST: 'backend.agent.local',
      },
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'web',
        logGroup: webLogs,
      }),
    });

    // ── ALB ───────────────────────────────────────────────────────────────────
    const albSg = new ec2.SecurityGroup(this, 'AlbSg', {
      vpc,
      description: 'ALB for agent-v2',
      allowAllOutbound: true,
    });
    albSg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80), 'Public HTTP');

    const alb = new elbv2.ApplicationLoadBalancer(this, 'Alb', {
      vpc,
      internetFacing: true,
      securityGroup: albSg,
      loadBalancerName: 'agent-v2-alb',
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });

    const targetGroup = new elbv2.ApplicationTargetGroup(this, 'WebTg', {
      vpc,
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      healthCheck: {
        path: '/healthz',
        interval: cdk.Duration.seconds(30),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
      },
      deregistrationDelay: cdk.Duration.seconds(30),
    });

    alb.addListener('Http', {
      port: 80,
      defaultTargetGroups: [targetGroup],
    });

    const webSg = new ec2.SecurityGroup(this, 'WebSg', {
      vpc,
      description: 'agent-v2 web (nginx)',
      allowAllOutbound: true,
    });
    // Allow ALB → web container
    webSg.addIngressRule(albSg, ec2.Port.tcp(80), 'ALB to web container');

    const webService = new ecs.FargateService(this, 'WebService', {
      cluster,
      taskDefinition: webTaskDef,
      serviceName: 'agent-v2-web',
      desiredCount: 1,
      securityGroups: [webSg],
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      assignPublicIp: true,
      enableExecuteCommand: true,
      capacityProviderStrategies: [
        { capacityProvider: 'FARGATE', weight: 1 },
      ],
    });

    webService.attachToApplicationTargetGroup(targetGroup);

    // Allow web SG → backend SG
    backendSg.addIngressRule(webSg, ec2.Port.tcp(8000), 'web to backend');

    // Suppress the minHealthyPercent warning (single task per service is intentional)
    const backendCfn = backendService.node.defaultChild as cdk.CfnResource;
    backendCfn.addMetadata('aws:cdk:path', 'AgentV2Stack/BackendService/Service');
    const webCfn = webService.node.defaultChild as cdk.CfnResource;
    webCfn.addMetadata('aws:cdk:path', 'AgentV2Stack/WebService/Service');

    // ── Outputs ───────────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'AlbDns', {
      value: `http://${alb.loadBalancerDnsName}`,
      description: 'Open this URL in your browser',
    });
  }
}
