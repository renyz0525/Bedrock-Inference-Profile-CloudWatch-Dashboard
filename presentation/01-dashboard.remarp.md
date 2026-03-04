---
remarp: true
version: 1
title: "Bedrock Inference Profile 모니터링 대시보드"
author: "렌"
date: 2026-03-04
lang: ko

blocks:
  - name: dashboard
    title: "Bedrock Inference Profile 모니터링 대시보드"
    duration: 25

theme:
  primary: "#232F3E"
  accent: "#FF9900"

transition:
  default: slide
  duration: 400
---

---
remarp: true
block: dashboard
---

# Bedrock Inference Profile 모니터링 대시보드

팀별 AI 사용량 추적 및 비용 관리 자동화 솔루션

:::notes
{timing: 1min}
안녕하세요. 오늘은 Bedrock Inference Profile을 활용한 모니터링 대시보드 솔루션을 소개드리겠습니다.
이 솔루션은 여러 팀이 Bedrock을 공유할 때 팀별 사용량과 비용을 자동으로 추적하는 CDK 기반 솔루션입니다.
:::

---

## 목차

1. Inference Profile이란? {.click}
2. 왜 이 솔루션이 필요한가? {.click}
3. 전체 아키텍처 {.click}
4. 대시보드 구성 {.click}
5. 모니터링 지표 상세 {.click}
6. 코드 작성 가이드 {.click}
7. 배포 및 운영 {.click}

:::notes
{timing: 0.5min}
오늘 다룰 주요 내용입니다. Inference Profile의 개념부터 시작해서 코드 작성 방법과 배포까지 전체 흐름을 살펴보겠습니다.
:::

---

## Bedrock Inference Profile이란?

::: left
### Application Inference Profile

- Bedrock Foundation Model에 대한 **프록시 역할** {.click}
- 팀/프로젝트/환경별 **별도 프로파일** 생성 {.click}
- CloudWatch `ModelId` 차원으로 **개별 추적** {.click}
- 동일 모델, 서로 다른 메트릭 수집 {.click}
:::

::: right
### 핵심 개념

```
Team A ──→ Profile A ──┐
                       ├──→ Claude Sonnet 4.6
Team B ──→ Profile B ──┘

CloudWatch:
  ModelId = "Profile A ID" → Team A 메트릭
  ModelId = "Profile B ID" → Team B 메트릭
```
:::

:::notes
{timing: 2min}
Inference Profile은 Foundation Model 위에 만드는 가상의 엔드포인트입니다.
같은 모델을 여러 팀이 공유하더라도, 각 팀이 자신의 프로파일 ARN으로 호출하면 CloudWatch에서 팀별 메트릭이 분리됩니다.
{cue: question} "현재 여러 팀이 같은 Bedrock 모델을 공유하고 계신가요?"
:::

---
@type: compare

## Inference Profile 유형

### 단일 리전 (Single-Region)
- Foundation Model ARN 직접 지정
- **해당 리전에서만** 추론 가능
- `arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-6`
- 용도: 개발/테스트 환경

### 크로스 리전 (Cross-Region)
- System-defined Inference Profile ARN 지정
- **여러 리전에 자동 라우팅** (처리량/복원력 향상)
- `arn:aws:bedrock:us-east-1:ACCOUNT:inference-profile/us.anthropic.claude-sonnet-4-6`
- 용도: 프로덕션 환경

:::notes
{timing: 1.5min}
두 가지 유형이 있습니다.
단일 리전은 하나의 리전에서만 동작하므로 개발/테스트에 적합합니다.
크로스 리전은 여러 리전에 자동 라우팅되어 처리량과 가용성이 높아 프로덕션에 권장됩니다.
:::

---

## 왜 이 솔루션이 필요한가?

::: left
### 문제점

- 여러 팀이 같은 모델 사용 시 **누가 얼마나 사용하는지 파악 불가** {.click}
- 비용 분배가 어려움 {.click}
- 성능 이슈의 원인 팀 추적 불가 {.click}
- 수동 대시보드 구성은 번거롭고 오류 발생 {.click}
:::

::: right
### 해결

- Inference Profile로 **팀별 사용량 분리** {.click}
- **자동 비용 추정** (Price List API 연동) {.click}
- **실시간 성능 모니터링** (레이턴시, 에러) {.click}
- **배포 한 번**으로 전체 자동화 {.click}
:::

:::notes
{timing: 2min}
여러 팀이 Bedrock을 공유하면 누가 얼마나 토큰을 사용하는지, 비용을 어떻게 나눠야 하는지 파악이 어렵습니다.
이 솔루션은 CDK 배포 한 번으로 모든 프로파일을 자동 발견하고, 가격을 자동 조회하고, 대시보드를 자동 생성합니다.
:::

---
@type: canvas
@canvas-id: arch-flow

## 전체 아키텍처

:::canvas
box cdk "CDK Stack" at 30,30 size 130,50 color #FF9900 step 1
box cfn "CloudFormation" at 30,120 size 130,50 color #FF9900 step 1
box lambda "Lambda\n(Custom Resource)" at 30,210 size 130,60 color #FF9900 step 2

arrow cdk -> cfn "synthesize" step 1
arrow cfn -> lambda "trigger" step 2

box bedrock "Bedrock API\nListInferenceProfiles" at 250,30 size 180,50 color #6C5CE7 step 3
box pricing "Price List API\nGetProducts" at 250,120 size 180,50 color #6C5CE7 step 3
box cwapi "CloudWatch API\nPutDashboard" at 250,210 size 180,50 color #6C5CE7 step 3

arrow lambda -> bedrock "1. 프로파일 발견" step 3
arrow lambda -> pricing "2. 가격 조회" step 3
arrow lambda -> cwapi "3. 대시보드 생성" step 3

box detail "Detail Dashboard\n(드롭다운 선택)" at 520,80 size 170,60 color #2CA02C step 4
box comparison "Comparison Dashboard\n(전체 비교)" at 520,180 size 170,60 color #2CA02C step 4

arrow cwapi -> detail "" step 4
arrow cwapi -> comparison "" step 4

box teamA "Team A App" at 250,320 size 120,40 color #FF7F0E step 5
box teamB "Team B App" at 420,320 size 120,40 color #FF7F0E step 5
box bedrock2 "Bedrock" at 350,400 size 100,40 color #6C5CE7 step 5
box cw "CloudWatch\nMetrics" at 520,400 size 130,40 color #2CA02C step 5

arrow teamA -> bedrock2 "Profile ARN" step 5
arrow teamB -> bedrock2 "Profile ARN" step 5
arrow bedrock2 -> cw "metrics" step 5
:::

:::notes
{timing: 3min}
{cue: demo}
전체 아키텍처입니다. Play 버튼으로 단계별로 설명하겠습니다.
1단계: CDK가 CloudFormation 템플릿을 합성합니다.
2단계: Lambda Custom Resource가 트리거됩니다.
3단계: Lambda가 세 가지 API를 호출합니다 - 프로파일 자동 발견, 가격 자동 조회, 대시보드 생성.
4단계: Detail과 Comparison 두 개의 대시보드가 생성됩니다.
5단계: 각 팀 앱이 Profile ARN으로 Bedrock을 호출하면 CloudWatch에 팀별 메트릭이 수집됩니다.
:::

---
@type: timeline

## 배포 흐름

### 1. CDK Deploy
`npx cdk deploy` 실행

### 2. CloudFormation
인프라 프로비저닝

### 3. Lambda 실행
Custom Resource 트리거

### 4. 프로파일 발견
모든 APPLICATION 프로파일 자동 발견

### 5. 가격 조회
Price List API에서 토큰 가격 조회

### 6. 대시보드 생성
Detail + Comparison 대시보드 생성

### 7. 완료
Stack Output에 대시보드 URL 출력

:::notes
{timing: 1.5min}
배포는 매우 간단합니다. cdk deploy 한 줄로 모든 것이 자동화됩니다.
Lambda가 현재 계정의 모든 Application Inference Profile을 발견하고, 각 모델의 가격을 조회한 후, 두 개의 CloudWatch 대시보드를 생성합니다.
:::

---

## Detail Dashboard

::: left
### 주요 위젯

- **드롭다운 선택기** — 프로파일별 필터링 {.click}
- **토큰 사용량** — Input/Output 이중 Y축 {.click}
- **비용 추정** — Input/Output/Total (Stacked) {.click}
- **핵심 카드** — Invocations, Latency, Errors {.click}
- **레이턴시 분포** — Avg, p50, p90, p99 {.click}
- **에러 & 스로틀** — 시계열 그래프 {.click}
:::

::: right
### Dashboard Variable

```
┌─ Select Profile ──────────┐
│ ▼ deptA_penguin_dev       │
│   deptA_penguin_prod      │
│   deptB_general           │
│   my_team_prod            │
└───────────────────────────┘

→ 선택한 프로파일의
  메트릭만 표시
```
:::

:::notes
{timing: 2min}
Detail Dashboard는 CloudWatch의 Dashboard Variable 기능을 활용합니다.
상단 드롭다운에서 프로파일을 선택하면 해당 프로파일의 토큰 사용량, 비용, 레이턴시, 에러 등 모든 메트릭이 한 화면에 표시됩니다.
:::

---

## Comparison Dashboard

::: left
### 전체 프로파일 비교

- **컬러 코딩** — 10가지 색상 순환 {.click}
- **토큰 소비량** — 전체 프로파일 비교 {.click}
- **성능 비교** — Invocations, Latency {.click}
- **비용 추정** — Period별 + **누적 비용** {.click}
- **프로파일별 섹션** — 개별 상세 메트릭 {.click}
:::

::: right
### 누적 비용 (RUNNING_SUM)

```
Cumulative Cost (USD)
│      ╱── Total
│    ╱╱ ── Team A
│  ╱╱╱  ── Team B
│╱╱╱╱
└──────────── time

RUNNING_SUM(
  InputTokens/1000 * price
  + OutputTokens/1000 * price
)
```
:::

:::notes
{timing: 2min}
Comparison Dashboard는 모든 프로파일의 메트릭을 한 화면에 비교할 수 있습니다.
특히 누적 비용 그래프가 핵심입니다. CloudWatch의 RUNNING_SUM 함수를 사용해서 시간에 따른 비용 누적을 시각화합니다.
각 팀별 비용과 전체 Total 비용을 한눈에 파악할 수 있습니다.
:::

---
@type: tabs

## 모니터링 지표 - 토큰 & 호출

### 토큰 지표
| 지표 | 설명 | 통계 | 용도 |
|------|------|------|------|
| **InputTokenCount** | 입력 토큰 수 | Sum | 프롬프트 크기 추적 |
| **OutputTokenCount** | 출력 토큰 수 | Sum | 응답 크기 추적 |
| **Invocations** | API 호출 수 | SampleCount | 사용 빈도 파악 |

모든 지표는 `AWS/Bedrock` 네임스페이스의 `ModelId` 차원으로 수집됩니다.

### 비용 계산
**비용 계산식:**
```
Cost = (InputTokens / 1000 x InputPrice)
     + (OutputTokens / 1000 x OutputPrice)
```

**누적 비용:**
```
RUNNING_SUM(cost_per_period)
```

**가격 조회 우선순위:**
1. CDK Stack 수동 오버라이드 (최신 모델용)
2. AWS Price List API 자동 조회
3. 가격 없음 → 비용 위젯 미표시

:::notes
{timing: 2min}
핵심 모니터링 지표를 살펴보겠습니다.
토큰 지표는 InputTokenCount와 OutputTokenCount로, Sum 통계를 사용합니다.
비용은 토큰 수에 가격을 곱해서 계산하며, RUNNING_SUM으로 누적 비용을 추적합니다.
가격은 자동으로 Price List API에서 조회하지만, 최신 모델은 아직 등록되지 않았을 수 있어 수동 오버라이드를 지원합니다.
:::

---
@type: tabs

## 모니터링 지표 - 레이턴시 & 에러

### 레이턴시
| 통계 | 설명 | 활용 |
|------|------|------|
| **Average** | 평균 응답 시간 | 전반적 성능 파악 |
| **p50** | 50%ile (중앙값) | 일반적 사용자 경험 |
| **p90** | 90%ile | 대부분의 요청 시간 |
| **p99** | 99%ile | 꼬리 지연 시간 |
| **Min / Max** | 최소/최대 | 이상치 탐지 |

p90과 p99가 중요한 이유: **사용자 경험의 꼬리 지연** 파악

### 에러 & 스로틀
| 지표 | HTTP | 의미 | 대응 |
|------|------|------|------|
| **InvocationClientErrors** | 4xx | 잘못된 요청, 권한 문제 | 요청 형식/IAM 확인 |
| **InvocationServerErrors** | 5xx | AWS 내부 에러 | 재시도 로직 구현 |
| **InvocationThrottles** | 429 | 요율 제한 초과 | **용량 확보 필요** |

스로틀이 빈번하다면 → Provisioned Throughput 또는 Cross-Region 프로파일 고려

:::notes
{timing: 2min}
레이턴시는 여러 통계를 동시에 모니터링하는 것이 중요합니다.
Average만 보면 안 됩니다. p90, p99를 봐야 일부 사용자가 겪는 느린 응답을 파악할 수 있습니다.
에러 지표 중 특히 Throttle이 중요합니다. 쓰로틀이 발생하면 크로스 리전 프로파일이나 Provisioned Throughput을 고려해야 합니다.
:::

---

## 코드 가이드 - Profile 생성

```python {filename="create_profile.py" highlight="3-8"}
import boto3

client = boto3.client("bedrock", region_name="us-east-1")

# 단일 리전 프로파일 생성
response = client.create_inference_profile(
    inferenceProfileName="deptA_penguin_dev",
    description="DepartmentA Penguin Project Dev",
    modelSource={
        "copyFrom": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-6"
    },
)

print(f"ARN: {response['inferenceProfileArn']}")
# → arn:aws:bedrock:us-east-1:ACCOUNT:application-inference-profile/w2m9jvmdyfej
```

CLI 도구 제공:
```bash
# 단일 리전
python3 create_profile.py --name my_team_dev

# 크로스 리전 (프로덕션 권장)
python3 create_profile.py --name my_team_prod --cross-region
```

:::notes
{timing: 1.5min}
프로파일 생성은 간단합니다. create_inference_profile API 한 번 호출이면 됩니다.
모델 소스에 Foundation Model ARN을 지정하면 단일 리전, System Inference Profile ARN을 지정하면 크로스 리전 프로파일이 생성됩니다.
예제 코드의 CLI 도구도 함께 제공합니다.
:::

---

## 코드 가이드 - Profile 호출 (핵심!)

```python {filename="invoke_profile.py" highlight="5-6"}
import boto3, json

client = boto3.client("bedrock-runtime", region_name="us-east-1")

# Inference Profile ARN을 modelId로 사용
PROFILE_ARN = "arn:aws:bedrock:us-east-1:ACCOUNT:application-inference-profile/w2m9jvmdyfej"

response = client.invoke_model(
    modelId=PROFILE_ARN,
    contentType="application/json",
    accept="application/json",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "Hello!"}],
    }),
)

result = json.loads(response["body"].read())
print(result["content"][0]["text"])
```

> **modelId에 반드시 Inference Profile ARN을 사용!**
> Foundation Model ID를 직접 사용하면 팀별 구분이 불가합니다.
> 스트리밍도 동일: `invoke_model_with_response_stream()`

:::notes
{timing: 2min}
{cue: pause}
가장 중요한 부분입니다.
기존에 modelId에 "anthropic.claude-sonnet-4-6"처럼 모델 ID를 직접 넣었다면, 이것을 Inference Profile ARN으로 바꿔야 합니다.
이렇게 해야 CloudWatch에서 프로파일별 메트릭이 분리 수집됩니다.
스트리밍 호출도 동일하게 modelId만 변경하면 됩니다.
:::

---

## 코드 가이드 - CDK 배포

```typescript {filename="bedrock-inference-profile-dashboard-stack.ts" highlight="3-7"}
import { BedrockInferenceProfileDashboard, PricingConfig } from './bedrock-inference-profile-dashboard';

// 가격 오버라이드 (Price List API에 없는 최신 모델용)
const pricing: PricingConfig = {
  'w2m9jvmdyfej': { inputTokenPrice: 0.00025, outputTokenPrice: 0.00125 },  // Claude 3 Haiku
  '24ug7jehtrvr': { inputTokenPrice: 0.003,   outputTokenPrice: 0.015   },  // Claude Sonnet 4.6
};

new BedrockInferenceProfileDashboard(this, 'Dashboard', {
  dashboardName: 'BedrockInferenceProfileDashboard',
  period: Duration.minutes(5),
  pricing,
});
```

```bash
# 배포
npx cdk deploy

# Stack Output → 대시보드 URL 확인
# DetailDashboardUrl: https://us-east-1.console.aws.amazon.com/cloudwatch/...
# ComparisonDashboardUrl: https://us-east-1.console.aws.amazon.com/cloudwatch/...
```

:::notes
{timing: 1.5min}
CDK 배포 코드입니다. pricing 설정에는 Price List API에 아직 등록되지 않은 최신 모델의 가격을 수동으로 지정할 수 있습니다.
이미 등록된 모델은 Lambda가 자동으로 가격을 조회하므로 별도 설정이 필요 없습니다.
배포하면 Stack Output에 두 대시보드의 URL이 출력됩니다.
:::

---

## 가격 자동 조회 메커니즘

::: left
### 조회 우선순위

1. **수동 오버라이드** {.click}
   CDK Stack에 설정된 가격 (최신 모델용)

2. **AWS Price List API** {.click}
   `ServiceCode=AmazonBedrock`
   `Feature=On-demand Inference`
   모델명 + 리전으로 자동 조회

3. **미적용** {.click}
   가격 정보 없음 → 비용 위젯 미표시
:::

::: right
### 최적화

- **모델명 기반 캐싱** {.click}
  같은 모델 사용하는 프로파일은 1회만 조회

- **17개 리전 지원** {.click}
  US, EU, AP, SA, ME 전체

- **배포 시마다 갱신** {.click}
  `cdk deploy` 실행 시 최신 가격 반영

- **Foundation Model 이름 자동 해석** {.click}
  `GetFoundationModel` API로 모델 ID → 이름 변환
:::

:::notes
{timing: 1.5min}
가격 조회는 3단계 우선순위로 동작합니다.
먼저 CDK에 설정된 수동 오버라이드를 확인하고, 없으면 Price List API를 조회합니다.
같은 모델을 사용하는 여러 프로파일은 한 번만 조회해서 캐싱합니다.
최신 모델이 Price List API에 등록되지 않은 경우를 위해 수동 오버라이드를 지원합니다.
:::

---

## 주의사항 & 제약

- **Dashboard Variable 제약** {.click}
  필터링/비필터링 위젯 혼합 불가 → **Detail/Comparison 분리** 이유

- **Price List API 제약** {.click}
  최신 모델 미등록 가능 → **수동 오버라이드** 필요

- **메트릭 지연** {.click}
  CloudWatch 메트릭은 호출 후 **5-10분 후** 표시

- **프로파일 ARN 필수** {.click}
  기존 모델 ID로 호출하면 **프로파일별 추적 불가**

- **배포 시 갱신** {.click}
  프로파일 추가/삭제 시 `cdk deploy` **재실행 필요**

:::notes
{timing: 1.5min}
알아두실 주의사항입니다.
가장 중요한 것은 반드시 Inference Profile ARN으로 호출해야 한다는 점입니다.
그리고 새 프로파일을 만들거나 삭제하면 cdk deploy를 다시 실행해야 대시보드에 반영됩니다.
:::

---

## Key Takeaways

::: left
### 핵심 요약

- **Inference Profile** = 팀별 AI 사용량 분리의 핵심 {.click}
- **자동 발견** + 자동 가격 조회 + 자동 대시보드 {.click}
- **Detail** 대시보드: 프로파일별 심층 분석 {.click}
- **Comparison** 대시보드: 전체 비교 + 누적 비용 {.click}
- **CDK 배포 한 번**으로 모든 것이 자동화 {.click}
:::

::: right
### 다음 단계

1. 팀별 Inference Profile 생성 {.click}
2. 기존 코드의 `modelId`를 Profile ARN으로 변경 {.click}
3. `npx cdk deploy` → 대시보드 자동 생성 {.click}
4. 정기 배포로 새 프로파일 자동 반영 {.click}
:::

:::notes
{timing: 1.5min}
{cue: transition}
정리하면, Inference Profile로 팀별 사용량을 분리하고, 이 CDK 솔루션으로 대시보드를 자동화할 수 있습니다.
시작하시려면 먼저 팀별 프로파일을 생성하고, 기존 코드에서 modelId를 변경하고, cdk deploy를 실행하시면 됩니다.
질문 있으시면 말씀해주세요.
:::
