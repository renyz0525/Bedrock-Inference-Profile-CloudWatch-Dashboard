"""
Bedrock Inference Profile 호출 예시 코드

각 팀은 Bedrock API 호출 시 반드시 Inference Profile ARN을 model ID로 사용해야
CloudWatch 대시보드에서 프로파일별 메트릭이 정상적으로 수집됩니다.

사용법:
    # 기본 실행 (deptA_penguin_dev 프로파일 사용)
    python invoke_profile.py

    # 프로파일 지정
    python invoke_profile.py --profile deptA_penguin_prod

    # 스트리밍 모드
    python invoke_profile.py --profile deptB_general --stream
"""

import argparse
import boto3
import json

# ──────────────────────────────────────────────
# Inference Profile 설정
# 각 팀은 자신의 프로파일 ARN을 사용하세요.
# ──────────────────────────────────────────────
PROFILES = {
    "deptA_penguin_dev": {
        "arn": "arn:aws:bedrock:us-east-1:562082723483:application-inference-profile/w2m9jvmdyfej",
        "description": "DepartmentA Penguin Project Development",
    },
    "deptA_penguin_prod": {
        "arn": "arn:aws:bedrock:us-east-1:562082723483:application-inference-profile/7r61afh3dz6i",
        "description": "DepartmentA Penguin Project Production",
    },
    "deptB_general": {
        "arn": "arn:aws:bedrock:us-east-1:562082723483:application-inference-profile/nfi4dck22hn0",
        "description": "DepartmentB General Usage",
    },
    "my_team_prod": {
        "arn": "arn:aws:bedrock:us-east-1:562082723483:application-inference-profile/sx2q08488787",
        "description": "My Team Production (Sonnet 4.6, Cross-Region)",
    },
}


def invoke(profile_name: str, prompt: str, max_tokens: int = 256) -> str:
    """
    Inference Profile을 통해 Bedrock 모델을 호출합니다.

    Args:
        profile_name: PROFILES 딕셔너리의 키 (예: "deptA_penguin_dev")
        prompt: 사용자 프롬프트
        max_tokens: 최대 출력 토큰 수

    Returns:
        모델 응답 텍스트
    """
    profile = PROFILES[profile_name]
    client = boto3.client("bedrock-runtime", region_name="us-east-1")

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }

    response = client.invoke_model(
        modelId=profile["arn"],  # Inference Profile ARN 사용
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def invoke_stream(profile_name: str, prompt: str, max_tokens: int = 256):
    """
    Inference Profile을 통해 스트리밍 호출합니다.

    Args:
        profile_name: PROFILES 딕셔너리의 키
        prompt: 사용자 프롬프트
        max_tokens: 최대 출력 토큰 수

    Yields:
        스트리밍 텍스트 청크
    """
    profile = PROFILES[profile_name]
    client = boto3.client("bedrock-runtime", region_name="us-east-1")

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }

    response = client.invoke_model_with_response_stream(
        modelId=profile["arn"],  # Inference Profile ARN 사용
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    for event in response["body"]:
        chunk = json.loads(event["chunk"]["bytes"])
        if chunk["type"] == "content_block_delta":
            yield chunk["delta"].get("text", "")


def main():
    parser = argparse.ArgumentParser(description="Bedrock Inference Profile 호출 예시")
    parser.add_argument(
        "--profile",
        choices=list(PROFILES.keys()),
        default="deptA_penguin_dev",
        help="사용할 Inference Profile 이름",
    )
    parser.add_argument(
        "--prompt",
        default="Hello! Please introduce yourself in one sentence.",
        help="프롬프트 텍스트",
    )
    parser.add_argument("--stream", action="store_true", help="스트리밍 모드 사용")
    parser.add_argument("--max-tokens", type=int, default=256, help="최대 출력 토큰")
    args = parser.parse_args()

    profile = PROFILES[args.profile]
    print(f"Profile: {args.profile}")
    print(f"ARN:     {profile['arn']}")
    print(f"Desc:    {profile['description']}")
    print(f"Prompt:  {args.prompt}")
    print("-" * 60)

    if args.stream:
        print("Response (streaming):")
        for text in invoke_stream(args.profile, args.prompt, args.max_tokens):
            print(text, end="", flush=True)
        print()
    else:
        response = invoke(args.profile, args.prompt, args.max_tokens)
        print(f"Response:\n{response}")


if __name__ == "__main__":
    main()
