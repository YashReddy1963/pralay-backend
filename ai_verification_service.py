import requests
from datetime import datetime
from typing import Dict, Any

# 🔥 Hugging Face deployed API
MODEL_URL = "https://vsgmk-ocean-ai-model.hf.space/predict"
API_KEY = "ocean_ai_super_secret_key_2026"


def verify_image_endpoint(
    image_data: bytes,
    hazard_type: str = None,
    description: str = "",
    filename: str = "image.jpg"
) -> Dict[str, Any]:

    try:
        files = {
            "file": (filename, image_data, "image/jpeg")
        }

        headers = {
            "x-api-key": API_KEY
        }

        response = requests.post(
            MODEL_URL,
            files=files,
            headers=headers,
            timeout=60  # cold start safe
        )

        # 🔎 DEBUG (optional – remove later)
        # print(response.status_code)
        # print(response.text)

        if response.status_code != 200:
            return _error_response(f"Model error: {response.text}")

        model_result = response.json()

        authenticity = str(model_result.get("authenticity", "AI")).strip()
        auth_conf = float(model_result.get("auth_confidence", 0)) / 100
        hazard = str(model_result.get("hazard", "unknown")).strip()
        hazard_conf = float(model_result.get("hazard_confidence", 0)) / 100

        is_real = authenticity.lower() == "real"

        status = "verified"
        message = "Image verified successfully"

        if not is_real:
            status = "failed"
            message = "AI-generated image detected."

        elif hazard_type and hazard.lower() != hazard_type.lower():
            status = "failed"
            message = f"Detected hazard: {hazard}"

        overall_confidence = (auth_conf + hazard_conf) / 2

        return {
            "status": status,
            "checks": {
                "isRealImage": is_real,
                "hazardTypeMatch": hazard.lower() == hazard_type.lower() if hazard_type else True,
                "contentAnalysis": True,
                "hazardRelevant": hazard_conf > 0.5
            },
            "aiDetection": {
                "isRealImage": is_real,
                "confidence": auth_conf
            },
            "hazardMatching": {
                "matchesSelectedType": hazard.lower() == hazard_type.lower() if hazard_type else True,
                "detectedHazardTypes": [hazard],
                "confidence": hazard_conf
            },
            "confidence": overall_confidence,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return _error_response(str(e))


def _error_response(message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "checks": {
            "isRealImage": False,
            "hazardTypeMatch": False,
            "contentAnalysis": False,
            "hazardRelevant": False
        },
        "aiDetection": {
            "isRealImage": False,
            "confidence": 0
        },
        "hazardMatching": {
            "matchesSelectedType": False,
            "detectedHazardTypes": [],
            "confidence": 0
        },
        "confidence": 0.0,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }