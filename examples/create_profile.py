"""
Bedrock Application Inference Profile 생성 예시 코드

Application Inference Profile을 생성하면 팀/프로젝트/환경별로
CloudWatch 메트릭을 분리 추적할 수 있습니다.

사용법:
    # 기본 실행 (단일 리전 프로파일 생성)
    python3 create_profile.py --name my_team_dev --description "My Team Development"

    # 크로스 리전 프로파일 생성
    python3 create_profile.py --name my_team_prod --description "My Team Production" --cross-region

    # 프로파일 삭제
    python3 create_profile.py --delete --profile-id <PROFILE_ID>

    # 프로파일 목록 조회
    python3 create_profile.py --list
"""

import argparse
import boto3

REGION = "us-east-1"

# ──────────────────────────────────────────────────────────────
# 모델 소스 설정
#
# 단일 리전: Foundation Model ARN 직접 지정
#   → 해당 리전에서만 추론 가능
#
# 크로스 리전: System-defined Inference Profile ARN 지정
#   → 여러 리전에 자동 라우팅되어 처리량/복원력 향상
# ──────────────────────────────────────────────────────────────
MODEL_SOURCE = {
    # 단일 리전 (us-east-1 only)
    "single_region": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-6",
    # 크로스 리전 (US regions)
    "cross_region": "arn:aws:bedrock:us-east-1:562082723483:inference-profile/us.anthropic.claude-sonnet-4-6",
}


def create_profile(name: str, description: str, cross_region: bool = False):
    """
    Application Inference Profile을 생성합니다.

    Args:
        name: 프로파일 이름 (영문, 숫자, 하이픈, 언더스코어만 허용)
        description: 프로파일 설명
        cross_region: True이면 크로스 리전 프로파일 생성

    Returns:
        생성된 프로파일 정보 (ARN, status 등)
    """
    client = boto3.client("bedrock", region_name=REGION)

    source_key = "cross_region" if cross_region else "single_region"
    model_arn = MODEL_SOURCE[source_key]

    response = client.create_inference_profile(
        inferenceProfileName=name,
        description=description,
        modelSource={"copyFrom": model_arn},
    )

    print(f"Profile created successfully!")
    print(f"  Name:   {name}")
    print(f"  ARN:    {response['inferenceProfileArn']}")
    print(f"  Status: {response['status']}")
    print(f"  Type:   {'Cross-Region' if cross_region else 'Single-Region'}")
    print(f"  Model:  Claude Sonnet 4.6")
    print()
    print("이 ARN을 modelId로 사용하여 Bedrock API를 호출하세요:")
    print(f'  modelId="{response["inferenceProfileArn"]}"')

    return response


def delete_profile(profile_id: str):
    """
    Inference Profile을 삭제합니다.

    Args:
        profile_id: 프로파일 ID (예: "w2m9jvmdyfej")
    """
    client = boto3.client("bedrock", region_name=REGION)

    client.delete_inference_profile(inferenceProfileIdentifier=profile_id)
    print(f"Profile '{profile_id}' deleted successfully.")


def list_profiles():
    """현재 계정의 모든 Application Inference Profile을 조회합니다."""
    client = boto3.client("bedrock", region_name=REGION)

    profiles = []
    next_token = None

    while True:
        params = {"typeEquals": "APPLICATION", "maxResults": 100}
        if next_token:
            params["nextToken"] = next_token
        resp = client.list_inference_profiles(**params)
        profiles.extend(resp.get("inferenceProfileSummaries", []))
        next_token = resp.get("nextToken")
        if not next_token:
            break

    if not profiles:
        print("No application inference profiles found.")
        return

    print(f"Found {len(profiles)} application inference profile(s):\n")
    print(f"{'Name':<30} {'ID':<20} {'Status':<10} {'Model'}")
    print("-" * 90)
    for p in profiles:
        name = p["inferenceProfileName"]
        pid = p["inferenceProfileId"]
        status = p.get("status", "N/A")
        models = p.get("models", [])
        model = models[0]["modelArn"].split("/")[-1] if models else "N/A"
        print(f"{name:<30} {pid:<20} {status:<10} {model}")


def main():
    parser = argparse.ArgumentParser(
        description="Bedrock Application Inference Profile 생성/삭제/조회"
    )
    parser.add_argument("--name", help="프로파일 이름")
    parser.add_argument("--description", default="", help="프로파일 설명")
    parser.add_argument(
        "--cross-region",
        action="store_true",
        help="크로스 리전 프로파일 생성 (여러 리전에 자동 라우팅)",
    )
    parser.add_argument("--delete", action="store_true", help="프로파일 삭제")
    parser.add_argument("--profile-id", help="삭제할 프로파일 ID")
    parser.add_argument("--list", action="store_true", help="프로파일 목록 조회")
    args = parser.parse_args()

    if args.list:
        list_profiles()
        return

    if args.delete:
        if not args.profile_id:
            parser.error("--delete requires --profile-id")
        delete_profile(args.profile_id)
        return

    if not args.name:
        parser.error("--name is required to create a profile")

    create_profile(args.name, args.description, args.cross_region)


if __name__ == "__main__":
    main()
