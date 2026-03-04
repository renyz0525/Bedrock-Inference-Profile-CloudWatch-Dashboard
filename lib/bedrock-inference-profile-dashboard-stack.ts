import { Stack, StackProps, Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  BedrockInferenceProfileDashboard,
  PricingConfig,
} from './bedrock-inference-profile-dashboard';

export class BedrockInferenceProfileDashboardStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Manual pricing override: only needed for models not yet in the AWS Price List API.
    // The Lambda auto-resolves pricing via Price List API first; these are fallback overrides.
    // Prices are per 1K tokens (USD).
    const pricing: PricingConfig = {
      // deptA_penguin_dev - Claude 3 Haiku ($0.25/MTok input, $1.25/MTok output)
      'w2m9jvmdyfej': { inputTokenPrice: 0.00025, outputTokenPrice: 0.00125 },
      // deptA_penguin_prod - Claude 3 Haiku
      '7r61afh3dz6i': { inputTokenPrice: 0.00025, outputTokenPrice: 0.00125 },
      // deptB_general - Claude 3 Haiku
      'nfi4dck22hn0': { inputTokenPrice: 0.00025, outputTokenPrice: 0.00125 },
      // my_team_prod - Claude Sonnet 4.6 ($3/MTok input, $15/MTok output)
      'sx2q08488787': { inputTokenPrice: 0.003, outputTokenPrice: 0.015 },
    };

    new BedrockInferenceProfileDashboard(this, 'Dashboard', {
      dashboardName: 'BedrockInferenceProfileDashboard',
      period: Duration.minutes(5),
      pricing,
    });
  }
}
