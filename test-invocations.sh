#!/bin/bash
# Test invocations for Bedrock Inference Profile Dashboard
# Calls each application inference profile multiple times with varying prompts

PROFILE="bedrock-dashboard"
REGION="us-east-1"

SONNET4_ARN="arn:aws:bedrock:us-east-1:936249129428:application-inference-profile/dr1ijc0v7yis"
HAIKU35_ARN="arn:aws:bedrock:us-east-1:936249129428:application-inference-profile/0abjkxlnnd7w"
HAIKU45_ARN="arn:aws:bedrock:us-east-1:936249129428:application-inference-profile/ed6wepts4w10"

call_converse() {
  local model_arn="$1"
  local prompt="$2"
  local label="$3"
  local max_tokens="${4:-200}"

  echo "  [$label] Calling with: \"${prompt:0:50}...\""

  local result
  result=$(aws bedrock-runtime converse \
    --profile "$PROFILE" \
    --region "$REGION" \
    --model-id "$model_arn" \
    --messages "[{\"role\":\"user\",\"content\":[{\"text\":\"$prompt\"}]}]" \
    --inference-config "{\"maxTokens\":$max_tokens}" \
    --query 'usage' \
    --output json 2>&1)

  if [ $? -eq 0 ]; then
    echo "    OK - $result"
  else
    echo "    ERROR - $result"
  fi
}

echo "============================================"
echo " Bedrock Inference Profile Test Invocations"
echo "============================================"
echo ""

# ── Sonnet 4 (Platform) - 5 calls ──
echo "[1/3] Sonnet 4 (Platform) - 5 invocations"
call_converse "$SONNET4_ARN" "Explain what Amazon Bedrock inference profiles are in 2 sentences." "Sonnet4" 150
call_converse "$SONNET4_ARN" "Write a Python function to calculate fibonacci numbers with memoization." "Sonnet4" 300
call_converse "$SONNET4_ARN" "What are the benefits of using CloudWatch dashboards for monitoring?" "Sonnet4" 200
call_converse "$SONNET4_ARN" "Summarize the key features of AWS CDK in bullet points." "Sonnet4" 250
call_converse "$SONNET4_ARN" "Explain the difference between on-demand and provisioned throughput in Bedrock." "Sonnet4" 200
echo ""

# ── Haiku 3.5 (Cost-Opt) - 8 calls (more calls, cheaper model) ──
echo "[2/3] Haiku 3.5 (Cost-Opt) - 8 invocations"
call_converse "$HAIKU35_ARN" "What is 2+2? Answer in one word." "Haiku35" 10
call_converse "$HAIKU35_ARN" "Name 3 AWS regions." "Haiku35" 50
call_converse "$HAIKU35_ARN" "What is serverless computing?" "Haiku35" 100
call_converse "$HAIKU35_ARN" "List 5 programming languages." "Haiku35" 50
call_converse "$HAIKU35_ARN" "What is an API gateway?" "Haiku35" 100
call_converse "$HAIKU35_ARN" "Define cloud native in one sentence." "Haiku35" 50
call_converse "$HAIKU35_ARN" "What is Infrastructure as Code?" "Haiku35" 100
call_converse "$HAIKU35_ARN" "Name 3 benefits of microservices architecture." "Haiku35" 100
echo ""

# ── Haiku 4.5 (Chatbot) - 6 calls ──
echo "[3/3] Haiku 4.5 (Chatbot) - 6 invocations"
call_converse "$HAIKU45_ARN" "Hello! How are you today? Please respond cheerfully." "Haiku45" 100
call_converse "$HAIKU45_ARN" "What is the weather like in Seoul in March? Give a general answer." "Haiku45" 150
call_converse "$HAIKU45_ARN" "Recommend a good book about machine learning for beginners." "Haiku45" 200
call_converse "$HAIKU45_ARN" "Explain what a large language model is to a 10 year old." "Haiku45" 200
call_converse "$HAIKU45_ARN" "Write a short poem about cloud computing." "Haiku45" 150
call_converse "$HAIKU45_ARN" "What are 3 tips for writing good API documentation?" "Haiku45" 200
echo ""

echo "============================================"
echo " All invocations complete!"
echo " CloudWatch metrics may take 5-10 minutes"
echo " to appear on the dashboard."
echo "============================================"
