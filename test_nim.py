import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("NVIDIA_API_KEY")

def test_nim_chat(model_name, base_url):
    print(f"Testing model: {model_name} with base_url: {base_url}")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.0,
        "max_tokens": 10
    }
    
    try:
        response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Success: {response.json()['choices'][0]['message']['content']}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")

# Test various combinations
print("--- TEST 1: meta/llama-3.1-70b-instruct with integrate base ---")
test_nim_chat("meta/llama-3.1-70b-instruct", "https://integrate.api.nvidia.com/v1")

print("\n--- TEST 2: meta/llama3-70b-instruct (Llama 3 non-3.1) ---")
test_nim_chat("meta/llama3-70b-instruct", "https://integrate.api.nvidia.com/v1")

print("\n--- TEST 3: meta/llama-3.1-70b-instruct with ai base ---")
test_nim_chat("meta/llama-3.1-70b-instruct", "https://ai.api.nvidia.com/v1")

print("\n--- TEST 6: meta/llama-4-scout-17b-16e-instruct with integrate base ---")
test_nim_chat("meta/llama-4-scout-17b-16e-instruct", "https://integrate.api.nvidia.com/v1")
