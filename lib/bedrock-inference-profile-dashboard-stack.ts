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
      // Claude Sonnet 4 - not yet in Price List API
      'dr1ijc0v7yis': { inputTokenPrice: 0.003, outputTokenPrice: 0.015 },
      // Claude 3.5 Haiku - not yet in Price List API
      '0abjkxlnnd7w': { inputTokenPrice: 0.0008, outputTokenPrice: 0.004 },
      // Claude Haiku 4.5 - not yet in Price List API
      'ed6wepts4w10': { inputTokenPrice: 0.001, outputTokenPrice: 0.005 },
      // Nova Lite - available in Price List API (auto-resolved), but kept as reference
      // 'x58goas2lmv2': { inputTokenPrice: 0.00006, outputTokenPrice: 0.00024 },
    };

    new BedrockInferenceProfileDashboard(this, 'Dashboard', {
      dashboardName: 'BedrockInferenceProfileDashboard',
      period: Duration.minutes(5),
      pricing,
    });
  }
}
