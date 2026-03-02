# Bedrock Inference Profile CloudWatch Dashboard

Amazon Bedrock Application Inference Profile 전용 CloudWatch 모니터링 대시보드를 자동 생성하는 AWS CDK Construct입니다.

## Features

- **Inference Profile 자동 탐색** - Bedrock API를 호출하여 계정 내 모든 APPLICATION Inference Profile을 자동으로 검색합니다. 프로파일 추가/삭제 시 `cdk deploy`만 실행하면 대시보드가 갱신됩니다.
- **가격 정보 자동 조회** - AWS Price List API에서 모델별 on-demand 토큰 가격을 자동으로 가져옵니다. API에 미등록된 최신 모델은 수동 override로 보완할 수 있습니다.
- **2개 대시보드 자동 생성**
  - **Detail Dashboard** - 드롭다운으로 프로파일을 선택하여 상세 메트릭 확인
  - **Comparison Dashboard** - 모든 프로파일을 한눈에 비교

## Architecture

```
CDK Stack
  └─ BedrockInferenceProfileDashboard (Construct)
       ├─ Lambda Function (Python 3.12)
       │    ├─ Bedrock: ListInferenceProfiles → 프로파일 자동 탐색
       │    ├─ Bedrock: GetFoundationModel    → 기반 모델 정보 조회
       │    ├─ Pricing: GetProducts           → 토큰 가격 자동 조회
       │    └─ CloudWatch: PutDashboard       → 대시보드 생성/갱신
       ├─ Custom Resource Provider (cr.Provider)
       └─ CloudFormation Custom Resource
            └─ 배포 시 Lambda 실행 → 대시보드 자동 생성
```

## Metrics

| Metric | Description | Dashboard |
|--------|-------------|-----------|
| InputTokenCount / OutputTokenCount | 입출력 토큰 소비량 | Both |
| Estimated Token Cost (USD) | 토큰 가격 기반 비용 추정 | Both |
| Invocations | 호출 횟수 | Both |
| InvocationLatency (Avg/p50/p90/p99) | 지연 시간 분포 | Both |
| InvocationClientErrors / ServerErrors | 클라이언트/서버 오류 | Both |
| InvocationThrottles | 쓰로틀링 횟수 | Both |
| Cumulative Cost (USD) | 누적 비용 (RUNNING_SUM) | Comparison |

## Prerequisites

- Node.js >= 18
- AWS CDK v2
- AWS CLI configured with appropriate credentials
- Amazon Bedrock Application Inference Profile (1개 이상)

## Quick Start

```bash
# Install dependencies
npm install

# Configure your profiles in lib/bedrock-inference-profile-dashboard-stack.ts
# (pricing override only - profiles are auto-discovered)

# Deploy
npx cdk deploy --profile <your-aws-profile>
```

## Project Structure

```
.
├── bin/
│   └── app.ts                                    # CDK App entry point
├── lib/
│   ├── bedrock-inference-profile-dashboard.ts     # CDK Construct (Custom Resource)
│   ├── bedrock-inference-profile-dashboard-stack.ts # CDK Stack (pricing config)
│   └── lambda/
│       └── index.py                               # Dashboard builder Lambda
├── test-invocations.sh                            # Test script for Bedrock calls
├── cdk.json
├── package.json
└── tsconfig.json
```

## Configuration

### Pricing Override

AWS Price List API에서 가격을 자동 조회하지만, 미등록 모델은 수동으로 지정합니다.

```typescript
// lib/bedrock-inference-profile-dashboard-stack.ts
const pricing: PricingConfig = {
  '<profile-short-id>': {
    inputTokenPrice: 0.003,   // USD per 1K input tokens
    outputTokenPrice: 0.015,  // USD per 1K output tokens
  },
};
```

가격 해석 우선순위:
1. 수동 override (`pricing` config에 profile ID가 있으면)
2. AWS Price List API 자동 조회
3. 가격 없음 (비용 위젯 비활성)

### Construct Props

```typescript
new BedrockInferenceProfileDashboard(this, 'Dashboard', {
  dashboardName: 'MyDashboard',  // optional, default: 'BedrockInferenceProfile'
  period: Duration.minutes(5),    // optional, default: 5 minutes
  pricing: { ... },               // optional, manual pricing overrides
});
```

## Dashboard Details

### Detail Dashboard

CloudWatch Dashboard Variable (property type)을 사용하여 드롭다운에서 프로파일을 선택할 수 있습니다. 선택한 프로파일의 메트릭만 필터링되어 표시됩니다.

- Input / Output Token Count (time series)
- Estimated Token Cost - Input, Output, Total (stacked)
- Single Value Cards - Invocations, Avg/Min/Max Latency, Client Errors, Throttles
- Latency Distribution - Avg, p50, p90, p99
- Errors & Throttles (time series)

### Comparison Dashboard

모든 프로파일을 색상으로 구분하여 한 화면에서 비교합니다. Dashboard Variable이 없어 각 프로파일이 독립적으로 표시됩니다.

- Token Consumption - Input/Output by profile
- Performance - Invocation Count, Average Latency by profile
- Cost Estimation - Cost per Period, Cumulative Cost by profile
- Per-Profile Detail Sections - 각 프로파일별 상세 메트릭

## Cleanup

```bash
npx cdk destroy --profile <your-aws-profile>
```

Custom Resource의 Delete handler가 두 대시보드를 자동으로 삭제합니다.

## Limitations

- CloudWatch Dashboard Variable (`property` type)은 대시보드 내 모든 위젯에 전역으로 적용됩니다. 이 제약 때문에 Detail(드롭다운)과 Comparison(비교)을 별도 대시보드로 분리했습니다.
- AWS Price List API에 최신 모델(Claude Sonnet 4, Haiku 4.5 등)이 미등록된 경우가 있어 수동 pricing override가 필요할 수 있습니다.
