"""Check available cloud CV/API credentials."""
import os

print("=== Cloud CV/API Credential Check ===")
print()

# Azure Computer Vision
azure_key = os.environ.get("AZURE_VISION_KEY", "")
azure_endpoint = os.environ.get("AZURE_VISION_ENDPOINT", "")
print(f"Azure Computer Vision:")
print(f"  Key set: {bool(azure_key)}")
print(f"  Endpoint set: {bool(azure_endpoint)}")
if azure_key:
    print(f"  Key length: {len(azure_key)} chars")
if azure_endpoint:
    print(f"  Endpoint: {azure_endpoint}")
print()

# Google Cloud Vision
google_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
print(f"Google Cloud Vision:")
print(f"  Credentials file env: {google_creds}")
if google_creds and os.path.exists(google_creds):
    print(f"  File exists: YES")
    import json
    try:
        with open(google_creds) as f:
            data = json.load(f)
            print(f"  Type: {data.get('type', 'unknown')}")
    except:
        print(f"  Could not parse JSON")
print()

# AWS Rekognition
aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
print(f"AWS Rekognition:")
print(f"  Key set: {bool(aws_key)}")
print(f"  Secret set: {bool(aws_secret)}")
print()

# Ollama/Llama.cpp (local LLM with vision)
ollama_url = os.environ.get("OLLAMA_URL", "")
print(f"Ollama (local LLM with vision):")
print(f"  URL: {ollama_url}")
print()

print("=== End Check ===")