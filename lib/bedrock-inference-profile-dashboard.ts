/**
 * CDK Construct: Bedrock Inference Profile CloudWatch Monitoring Dashboard
 *
 * Uses a Lambda Custom Resource to:
 * 1. Auto-discover APPLICATION inference profiles from Bedrock
 * 2. Build and deploy two CloudWatch dashboards (Detail + Comparison)
 *
 * Detail Dashboard: dropdown to select a profile, shows detailed metrics
 * Comparison Dashboard: all profiles side by side, no variable filter
 */

import { Construct } from 'constructs';
import { Aws, CfnOutput, CustomResource, Duration } from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as path from 'path';

export interface PricingConfig {
  [profileId: string]: {
    inputTokenPrice: number;
    outputTokenPrice: number;
  };
}

export interface BedrockInferenceProfileDashboardProps {
  readonly dashboardName?: string;
  readonly period?: Duration;
  readonly pricing?: PricingConfig;
}

export class BedrockInferenceProfileDashboard extends Construct {
  public readonly detailDashboardName: string;
  public readonly comparisonDashboardName: string;

  constructor(scope: Construct, id: string, props?: BedrockInferenceProfileDashboardProps) {
    super(scope, id);

    const baseName = props?.dashboardName ?? 'BedrockInferenceProfile';
    this.detailDashboardName = `${baseName}-Detail`;
    this.comparisonDashboardName = `${baseName}-Comparison`;
    const period = props?.period?.toSeconds() ?? 300;

    // Lambda function for Custom Resource
    const fn = new lambda.Function(this, 'DashboardBuilder', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, 'lambda')),
      timeout: Duration.minutes(5),
      memorySize: 256,
    });

    // IAM permissions
    fn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:ListInferenceProfiles', 'bedrock:GetFoundationModel'],
      resources: ['*'],
    }));
    fn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['cloudwatch:PutDashboard', 'cloudwatch:DeleteDashboards'],
      resources: ['*'],
    }));
    fn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['pricing:GetProducts'],
      resources: ['*'],
    }));

    // Custom Resource Provider
    const provider = new cr.Provider(this, 'Provider', {
      onEventHandler: fn,
    });

    // Custom Resource
    const resource = new CustomResource(this, 'DashboardResource', {
      serviceToken: provider.serviceToken,
      properties: {
        DetailDashboardName: this.detailDashboardName,
        ComparisonDashboardName: this.comparisonDashboardName,
        Period: String(period),
        Pricing: JSON.stringify(props?.pricing ?? {}),
        // Change this value to force re-evaluation on each deploy
        Timestamp: new Date().toISOString(),
      },
    });

    new CfnOutput(this, 'DetailDashboardUrl', {
      value: `https://${Aws.REGION}.console.aws.amazon.com/cloudwatch/home?region=${Aws.REGION}#dashboards/name=${this.detailDashboardName}`,
      description: 'Detail Dashboard (with dropdown)',
    });
    new CfnOutput(this, 'ComparisonDashboardUrl', {
      value: `https://${Aws.REGION}.console.aws.amazon.com/cloudwatch/home?region=${Aws.REGION}#dashboards/name=${this.comparisonDashboardName}`,
      description: 'Comparison Dashboard (all profiles)',
    });
    new CfnOutput(this, 'ProfileCount', {
      value: resource.getAttString('ProfileCount'),
      description: 'Number of discovered inference profiles',
    });
  }
}
