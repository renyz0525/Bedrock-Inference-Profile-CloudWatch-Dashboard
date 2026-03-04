# Bedrock Inference Profile Monitoring Dashboard

> **[한국어 버전은 아래에 있습니다](#한국어)**

An AWS CDK solution that automatically creates CloudWatch monitoring dashboards for Amazon Bedrock **Application Inference Profiles**.

When multiple teams share the same Bedrock model, it's difficult to track **who is using how much**. This solution solves that problem by leveraging Inference Profiles for per-team metric separation and automated dashboard generation.

## Key Features

- **Auto-discovery** — Automatically discovers all APPLICATION Inference Profiles in the account (with pagination)
- **Auto-pricing** — Fetches per-model on-demand token prices from the AWS Price List API
- **Two dashboards auto-generated**
  - **Detail Dashboard** — Select a profile from a dropdown to view detailed metrics
  - **Comparison Dashboard** — Compare all profiles at a glance with cumulative cost tracking
- **One-command deployment** — Everything is automated with a single `npx cdk deploy`

## Architecture

```
CDK Stack
  └─ BedrockInferenceProfileDashboard (Construct)
       ├─ Lambda Function (Python 3.12)
       │    ├─ Bedrock: ListInferenceProfiles → Auto-discover profiles
       │    ├─ Bedrock: GetFoundationModel    → Retrieve base model info
       │    ├─ Pricing: GetProducts           → Auto-fetch token prices
       │    └─ CloudWatch: PutDashboard       → Create/update dashboards
       ├─ Custom Resource Provider (cr.Provider)
       └─ CloudFormation Custom Resource
            └─ Triggers Lambda on deploy → Auto-creates dashboards

Team Applications
  └─ Call Bedrock with Inference Profile ARN
       → CloudWatch metrics collected separately per profile
```

## Metrics

| Metric | Description | Dashboard |
|--------|-------------|-----------|
| InputTokenCount / OutputTokenCount | Input/output token consumption | Detail + Comparison |
| Estimated Token Cost (USD) | Cost estimation based on token prices | Detail + Comparison |
| Invocations | API call count | Detail + Comparison |
| InvocationLatency (Avg/p50/p90/p99) | Latency distribution | Detail + Comparison |
| InvocationClientErrors / ServerErrors | Client/server errors (4xx/5xx) | Detail + Comparison |
| InvocationThrottles | Throttle count (429) | Detail + Comparison |
| Cumulative Cost (USD) | Running total cost (`RUNNING_SUM`) | Comparison |

## Prerequisites

- **Node.js** >= 18
- **AWS CDK** v2
- **AWS CLI** configured with appropriate credentials
- **Amazon Bedrock Application Inference Profile** — At least one must exist

## Quick Start

### Step 1: Install Dependencies

```bash
npm install
```

### Step 2: Create Inference Profiles (if none exist)

Create an Inference Profile for each team/project/environment.

```bash
cd examples

# List existing profiles
python3 create_profile.py --list

# Create a single-region profile (for dev/test)
python3 create_profile.py --name my_team_dev --description "My Team Development"

# Create a cross-region profile (recommended for production — better throughput/resilience)
python3 create_profile.py --name my_team_prod --description "My Team Production" --cross-region
```

### Step 3: Configure Pricing Override (Optional)

Prices are auto-fetched from the AWS Price List API, but newer models may not yet be registered.
If needed, set manual prices in `lib/bedrock-inference-profile-dashboard-stack.ts`:

```typescript
const pricing: PricingConfig = {
  // Profile Short ID: price in USD per 1K tokens
  'w2m9jvmdyfej': { inputTokenPrice: 0.00025, outputTokenPrice: 0.00125 },  // Claude 3 Haiku
  'sx2q08488787': { inputTokenPrice: 0.003,   outputTokenPrice: 0.015   },  // Claude Sonnet 4.6
};
```

**Pricing resolution order:**
1. Manual override (if Profile ID exists in `pricing` config)
2. AWS Price List API auto-lookup
3. No price available → cost widgets hidden

### Step 4: Deploy the Dashboard

```bash
npx cdk deploy
```

On completion, dashboard URLs are printed in the Stack Outputs:

```
Outputs:
  DetailDashboardUrl     = https://us-east-1.console.aws.amazon.com/cloudwatch/...
  ComparisonDashboardUrl = https://us-east-1.console.aws.amazon.com/cloudwatch/...
  ProfileCount           = 4
```

## How to Use Inference Profiles (For Teams)

When calling the Bedrock API, you **must use the Inference Profile ARN as the `modelId`**.
Using the Foundation Model ID directly will not separate metrics by team.

```python
import boto3
import json

client = boto3.client("bedrock-runtime", region_name="us-east-1")

# ✅ Correct: Use Inference Profile ARN
response = client.invoke_model(
    modelId="arn:aws:bedrock:us-east-1:ACCOUNT:application-inference-profile/w2m9jvmdyfej",
    contentType="application/json",
    accept="application/json",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "Hello!"}],
    }),
)

# ❌ Wrong: Using Foundation Model ID directly → no per-team separation
# modelId="anthropic.claude-sonnet-4-6"
```

Streaming mode also uses the Inference Profile ARN:

```python
response = client.invoke_model_with_response_stream(
    modelId="arn:aws:bedrock:us-east-1:ACCOUNT:application-inference-profile/w2m9jvmdyfej",
    ...
)
```

See `examples/invoke_profile.py` for more detailed examples.

## Project Structure

```
.
├── bin/
│   └── app.ts                                      # CDK App entry point
├── lib/
│   ├── bedrock-inference-profile-dashboard.ts       # CDK Construct (Custom Resource)
│   ├── bedrock-inference-profile-dashboard-stack.ts  # CDK Stack (pricing config)
│   └── lambda/
│       └── index.py                                 # Dashboard builder Lambda
├── examples/
│   ├── create_profile.py                            # Inference Profile create/delete/list CLI
│   └── invoke_profile.py                            # Inference Profile invocation examples
├── presentation/
│   ├── 01-dashboard.html                            # Solution overview presentation
│   ├── index.html                                   # Presentation table of contents
│   └── common/                                      # Presentation framework files
├── cdk.json
├── package.json
└── tsconfig.json
```

## CDK Construct Configuration

```typescript
import { BedrockInferenceProfileDashboard, PricingConfig } from './bedrock-inference-profile-dashboard';

new BedrockInferenceProfileDashboard(this, 'Dashboard', {
  // Dashboard name prefix (default: 'BedrockInferenceProfile')
  // → Creates 'BedrockInferenceProfile-Detail' / 'BedrockInferenceProfile-Comparison'
  dashboardName: 'MyDashboard',

  // Metric aggregation period (default: 5 minutes)
  period: Duration.minutes(5),

  // Manual pricing override (optional)
  pricing: {
    '<profile-short-id>': {
      inputTokenPrice: 0.003,   // USD per 1K input tokens
      outputTokenPrice: 0.015,  // USD per 1K output tokens
    },
  },
});
```

## Dashboard Details

### Detail Dashboard

Uses CloudWatch Dashboard Variables to let you **select a profile from a dropdown**. Only the selected profile's metrics are shown.

![Detail Dashboard](image/Cloudwatch-Dashboard-Detailed.png)

- **Token Usage** — Input/Output Token Count (dual Y-axis time series)
- **Cost Estimation** — Input Cost + Output Cost + Total (Stacked Area)
- **Key Metric Cards** — Invocations, Avg/Min/Max Latency, Client Errors, Throttles
- **Latency Distribution** — Average, p50, p90, p99 (time series)
- **Errors & Throttles** — Client Errors, Server Errors, Throttles (time series)

### Comparison Dashboard

Compares all profiles on a single screen with **10 color-coded series**.

![Comparison Dashboard](image/Cloudwatch-Dashboard-All.png)

- **Token Consumption** — Input/Output Token comparison across all profiles
- **Performance** — Invocation Count, Average Latency comparison
- **Cost Estimation** — Per-period cost + **Cumulative Cost** (using `RUNNING_SUM`)
- **Per-Profile Detail Sections** — Full metrics for each profile (tokens, cost, latency, errors)

## Example Tools

### Profile Create/Delete/List (`examples/create_profile.py`)

```bash
# List profiles
python3 examples/create_profile.py --list

# Create single-region profile
python3 examples/create_profile.py --name deptA_penguin_dev --description "DeptA Penguin Dev"

# Create cross-region profile
python3 examples/create_profile.py --name my_team_prod --description "My Team Production" --cross-region

# Delete a profile
python3 examples/create_profile.py --delete --profile-id <PROFILE_ID>
```

### Profile Invocation Test (`examples/invoke_profile.py`)

```bash
# Default (deptA_penguin_dev profile)
python3 examples/invoke_profile.py

# Specify a profile
python3 examples/invoke_profile.py --profile deptA_penguin_prod

# Streaming mode
python3 examples/invoke_profile.py --profile deptB_general --stream

# Custom prompt
python3 examples/invoke_profile.py --profile my_team_prod --prompt "Tell me about AWS"
```

## Updating After Profile Changes

After creating or deleting Inference Profiles, simply **redeploy the dashboard**:

```bash
npx cdk deploy
```

The Lambda automatically re-discovers all APPLICATION profiles and updates the dashboards.

## Cleanup

```bash
npx cdk destroy
```

The Custom Resource Delete handler automatically removes both dashboards.
Inference Profiles must be deleted separately:

```bash
python3 examples/create_profile.py --delete --profile-id <PROFILE_ID>
```

## Limitations

| Item | Description |
|------|-------------|
| **Dashboard Variable** | CloudWatch Dashboard Variables apply globally to all widgets. This is why Detail (dropdown) and Comparison (side-by-side) are split into separate dashboards. |
| **Price List API** | Newer models (Claude Sonnet 4, Haiku 4.5, etc.) may not yet be registered in the API. Use the `pricing` config for manual overrides. |
| **Metric Delay** | CloudWatch metrics appear approximately 5–10 minutes after a Bedrock API call. |
| **Profile ARN Required** | Using the Foundation Model ID directly prevents per-profile metric tracking. Always use the Inference Profile ARN as `modelId`. |
| **Redeploy on Change** | Run `cdk deploy` again after adding or removing profiles to update the dashboards. |
| **Region Scope** | Only profiles in the CDK Stack's deployed region are discovered. |

## Presentation

A solution overview presentation is included in the `presentation/` directory.
Open `presentation/01-dashboard.html` in a browser to view the interactive slides.

- `←` `→` or `Space` — Navigate slides
- `P` — Presenter view (with speaker notes)
- `F` — Fullscreen
- `PDF Export` button (top-right) — Export to PDF

---

<a id="한국어"></a>

# 한국어

# Bedrock Inference Profile 모니터링 대시보드

Amazon Bedrock **Application Inference Profile** 전용 CloudWatch 모니터링 대시보드를 자동으로 생성하는 AWS CDK 솔루션입니다.

여러 팀이 같은 Bedrock 모델을 공유할 때, **누가 얼마나 사용하는지 파악하기 어려운 문제**를 Inference Profile과 자동 대시보드로 해결합니다.

## 핵심 기능

- **프로파일 자동 발견** — 계정 내 모든 APPLICATION Inference Profile을 자동으로 검색합니다 (페이지네이션 지원)
- **가격 자동 조회** — AWS Price List API에서 모델별 on-demand 토큰 가격을 자동으로 가져옵니다
- **2개 대시보드 자동 생성**
  - **Detail Dashboard** — 드롭다운으로 프로파일을 선택하여 상세 메트릭 확인
  - **Comparison Dashboard** — 모든 프로파일을 한눈에 비교, 누적 비용 추적
- **배포 한 번으로 완료** — `npx cdk deploy` 한 줄로 모든 것이 자동화됩니다

## 아키텍처

```
CDK Stack
  └─ BedrockInferenceProfileDashboard (Construct)
       ├─ Lambda Function (Python 3.12)
       │    ├─ Bedrock: ListInferenceProfiles → 프로파일 자동 발견
       │    ├─ Bedrock: GetFoundationModel    → 기반 모델 정보 조회
       │    ├─ Pricing: GetProducts           → 토큰 가격 자동 조회
       │    └─ CloudWatch: PutDashboard       → 대시보드 생성/갱신
       ├─ Custom Resource Provider (cr.Provider)
       └─ CloudFormation Custom Resource
            └─ 배포 시 Lambda 실행 → 대시보드 자동 생성

각 팀 애플리케이션
  └─ Inference Profile ARN으로 Bedrock 호출
       → CloudWatch 메트릭이 프로파일별로 분리 수집
```

## 모니터링 지표

| 지표 | 설명 | 대시보드 |
|------|------|----------|
| InputTokenCount / OutputTokenCount | 입출력 토큰 소비량 | Detail + Comparison |
| Estimated Token Cost (USD) | 토큰 가격 기반 비용 추정 | Detail + Comparison |
| Invocations | API 호출 횟수 | Detail + Comparison |
| InvocationLatency (Avg/p50/p90/p99) | 지연 시간 분포 | Detail + Comparison |
| InvocationClientErrors / ServerErrors | 클라이언트/서버 오류 (4xx/5xx) | Detail + Comparison |
| InvocationThrottles | 쓰로틀링 횟수 (429) | Detail + Comparison |
| Cumulative Cost (USD) | 누적 비용 (`RUNNING_SUM` 함수) | Comparison |

## 사전 요구사항

- **Node.js** >= 18
- **AWS CDK** v2
- **AWS CLI** — 적절한 자격 증명이 구성되어 있어야 합니다
- **Amazon Bedrock Application Inference Profile** — 1개 이상 생성되어 있어야 합니다

## 빠른 시작

### 1단계: 의존성 설치

```bash
npm install
```

### 2단계: Inference Profile 생성 (아직 없는 경우)

각 팀/프로젝트/환경별로 Inference Profile을 생성합니다.

```bash
cd examples

# 프로파일 목록 조회
python3 create_profile.py --list

# 단일 리전 프로파일 생성 (개발/테스트용)
python3 create_profile.py --name my_team_dev --description "My Team Development"

# 크로스 리전 프로파일 생성 (프로덕션 권장 — 처리량/복원력 향상)
python3 create_profile.py --name my_team_prod --description "My Team Production" --cross-region
```

### 3단계: 가격 오버라이드 설정 (선택)

AWS Price List API에서 가격을 자동 조회하지만, 최신 모델은 아직 API에 미등록일 수 있습니다.
필요한 경우 `lib/bedrock-inference-profile-dashboard-stack.ts`에서 수동 가격을 지정합니다.

```typescript
const pricing: PricingConfig = {
  // Profile Short ID: 가격 (USD per 1K tokens)
  'w2m9jvmdyfej': { inputTokenPrice: 0.00025, outputTokenPrice: 0.00125 },  // Claude 3 Haiku
  'sx2q08488787': { inputTokenPrice: 0.003,   outputTokenPrice: 0.015   },  // Claude Sonnet 4.6
};
```

**가격 조회 우선순위:**
1. 수동 오버라이드 (위의 `pricing` 설정에 Profile ID가 있으면)
2. AWS Price List API 자동 조회
3. 가격 없음 → 비용 위젯 미표시

### 4단계: 대시보드 배포

```bash
npx cdk deploy
```

배포가 완료되면 Stack Output에 대시보드 URL이 표시됩니다:

```
Outputs:
  DetailDashboardUrl     = https://us-east-1.console.aws.amazon.com/cloudwatch/...
  ComparisonDashboardUrl = https://us-east-1.console.aws.amazon.com/cloudwatch/...
  ProfileCount           = 4
```

## Inference Profile 사용법 (팀 담당자용)

Bedrock API 호출 시 **반드시 Inference Profile ARN을 `modelId`로 사용**해야 합니다.
Foundation Model ID를 직접 사용하면 팀별 메트릭이 분리되지 않습니다.

```python
import boto3
import json

client = boto3.client("bedrock-runtime", region_name="us-east-1")

# ✅ 올바른 방법: Inference Profile ARN 사용
response = client.invoke_model(
    modelId="arn:aws:bedrock:us-east-1:ACCOUNT:application-inference-profile/w2m9jvmdyfej",
    contentType="application/json",
    accept="application/json",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "Hello!"}],
    }),
)

# ❌ 잘못된 방법: Foundation Model ID 직접 사용 → 팀별 구분 불가
# modelId="anthropic.claude-sonnet-4-6"
```

스트리밍 모드도 동일하게 Inference Profile ARN을 사용합니다:

```python
response = client.invoke_model_with_response_stream(
    modelId="arn:aws:bedrock:us-east-1:ACCOUNT:application-inference-profile/w2m9jvmdyfej",
    ...
)
```

더 자세한 예제는 `examples/invoke_profile.py`를 참고하세요.

## 프로젝트 구조

```
.
├── bin/
│   └── app.ts                                      # CDK App 진입점
├── lib/
│   ├── bedrock-inference-profile-dashboard.ts       # CDK Construct (Custom Resource 정의)
│   ├── bedrock-inference-profile-dashboard-stack.ts  # CDK Stack (가격 오버라이드 설정)
│   └── lambda/
│       └── index.py                                 # 대시보드 빌더 Lambda 함수
├── examples/
│   ├── create_profile.py                            # Inference Profile 생성/삭제/조회 CLI
│   └── invoke_profile.py                            # Inference Profile 호출 예시 코드
├── presentation/
│   ├── 01-dashboard.html                            # 솔루션 소개 프레젠테이션
│   ├── index.html                                   # 프레젠테이션 목차
│   └── common/                                      # 프레젠테이션 프레임워크 파일
├── cdk.json
├── package.json
└── tsconfig.json
```

## CDK Construct 설정

```typescript
import { BedrockInferenceProfileDashboard, PricingConfig } from './bedrock-inference-profile-dashboard';

new BedrockInferenceProfileDashboard(this, 'Dashboard', {
  // 대시보드 이름 접두사 (기본값: 'BedrockInferenceProfile')
  // → 'BedrockInferenceProfile-Detail' / 'BedrockInferenceProfile-Comparison' 생성
  dashboardName: 'MyDashboard',

  // 메트릭 집계 주기 (기본값: 5분)
  period: Duration.minutes(5),

  // 수동 가격 오버라이드 (선택)
  pricing: {
    '<profile-short-id>': {
      inputTokenPrice: 0.003,   // USD per 1K input tokens
      outputTokenPrice: 0.015,  // USD per 1K output tokens
    },
  },
});
```

## 대시보드 상세

### Detail Dashboard

CloudWatch Dashboard Variable을 사용하여 **드롭다운에서 프로파일을 선택**할 수 있습니다. 선택한 프로파일의 메트릭만 필터링되어 표시됩니다.

![Detail Dashboard](image/Cloudwatch-Dashboard-Detailed.png)

- **토큰 사용량** — Input/Output Token Count (이중 Y축 시계열)
- **비용 추정** — Input Cost + Output Cost + Total (Stacked Area)
- **핵심 지표 카드** — Invocations, Avg/Min/Max Latency, Client Errors, Throttles
- **레이턴시 분포** — Average, p50, p90, p99 (시계열)
- **에러 & 스로틀** — Client Errors, Server Errors, Throttles (시계열)

### Comparison Dashboard

모든 프로파일을 **10가지 색상으로 구분**하여 한 화면에서 비교합니다.

![Comparison Dashboard](image/Cloudwatch-Dashboard-All.png)

- **토큰 소비량** — 전체 프로파일의 Input/Output Token 비교
- **성능 비교** — Invocation Count, Average Latency 비교
- **비용 추정** — Period별 비용 + **누적 비용** (`RUNNING_SUM` 함수 활용)
- **프로파일별 상세 섹션** — 각 프로파일의 전체 메트릭 (토큰, 비용, 레이턴시, 에러)

## 예제 도구

### Profile 생성/삭제/조회 (`examples/create_profile.py`)

```bash
# 프로파일 목록 조회
python3 examples/create_profile.py --list

# 단일 리전 프로파일 생성
python3 examples/create_profile.py --name deptA_penguin_dev --description "DeptA Penguin Dev"

# 크로스 리전 프로파일 생성
python3 examples/create_profile.py --name my_team_prod --description "My Team Production" --cross-region

# 프로파일 삭제
python3 examples/create_profile.py --delete --profile-id <PROFILE_ID>
```

### Profile 호출 테스트 (`examples/invoke_profile.py`)

```bash
# 기본 실행 (deptA_penguin_dev 프로파일)
python3 examples/invoke_profile.py

# 프로파일 지정
python3 examples/invoke_profile.py --profile deptA_penguin_prod

# 스트리밍 모드
python3 examples/invoke_profile.py --profile deptB_general --stream

# 커스텀 프롬프트
python3 examples/invoke_profile.py --profile my_team_prod --prompt "AWS에 대해 알려줘"
```

## 프로파일 추가/변경 시

새로운 Inference Profile을 생성하거나 기존 프로파일을 삭제한 후에는 **대시보드를 재배포**하면 됩니다:

```bash
npx cdk deploy
```

Lambda가 자동으로 모든 APPLICATION 프로파일을 다시 검색하고 대시보드를 갱신합니다.

## 리소스 정리

```bash
npx cdk destroy
```

Custom Resource의 Delete handler가 두 대시보드를 자동으로 삭제합니다.
Inference Profile은 별도로 삭제해야 합니다:

```bash
python3 examples/create_profile.py --delete --profile-id <PROFILE_ID>
```

## 주의사항 및 제약

| 항목 | 설명 |
|------|------|
| **Dashboard Variable 제약** | CloudWatch Dashboard Variable은 대시보드 내 모든 위젯에 전역 적용됩니다. 이 때문에 Detail(드롭다운)과 Comparison(비교)을 별도 대시보드로 분리했습니다. |
| **Price List API 제약** | 최신 모델(Claude Sonnet 4, Haiku 4.5 등)이 아직 API에 미등록일 수 있습니다. 이 경우 `pricing` 설정으로 수동 오버라이드가 필요합니다. |
| **메트릭 지연** | CloudWatch 메트릭은 Bedrock API 호출 후 약 5~10분 후에 표시됩니다. |
| **Profile ARN 필수** | 기존 Foundation Model ID로 호출하면 프로파일별 메트릭 추적이 불가합니다. 반드시 Inference Profile ARN을 `modelId`로 사용해야 합니다. |
| **배포 시 갱신** | 프로파일 추가/삭제 후 `cdk deploy`를 재실행해야 대시보드에 반영됩니다. |
| **리전** | 대시보드는 CDK Stack이 배포된 리전의 프로파일만 검색합니다. |

## 발표 자료

솔루션 소개 프레젠테이션이 `presentation/` 디렉토리에 포함되어 있습니다.
브라우저에서 `presentation/01-dashboard.html`을 열면 인터랙티브 슬라이드를 볼 수 있습니다.

- 키보드 `←` `→` 또는 `Space`로 슬라이드 탐색
- `P` 키로 발표자 뷰 (스피커 노트 포함)
- `F` 키로 전체화면
- 우측 상단 `PDF Export` 버튼으로 PDF 출력
