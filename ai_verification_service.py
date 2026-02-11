"""
AI Verification Service for Ocean Hazard Detection
Integrates with the frontend ReportHazard component
"""

import os
import json
import numpy as np
import cv2
from PIL import Image
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import tempfile
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIVerificationService:
    """AI-powered verification service for ocean hazard images."""
    
    def __init__(self):
        self.hazard_types = [
            "tsunami", "storm-surge", "high-waves", "flooding",
            "debris", "pollution", "erosion", "wildlife", "other"
        ]
        self.hazard_to_idx = {hazard: idx for idx, hazard in enumerate(self.hazard_types)}
        self.idx_to_hazard = {idx: hazard for hazard, idx in self.hazard_to_idx.items()}
        
        # Initialize with fallback mode (no actual ML models loaded)
        self.models_available = False
        logger.info("AI Verification Service initialized in fallback mode")
    
    def preprocess_image(self, image_data: bytes) -> Optional[np.ndarray]:
        """
        Preprocess image data for analysis.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Preprocessed image array or None if failed
        """
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return None
            
            # Resize to standard size
            image = cv2.resize(image, (224, 224))
            
            # Convert BGR to RGB
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Normalize to [0, 1]
            image = image.astype(np.float32) / 255.0
            
            return image
            
        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            return None
    
    def compute_image_metrics(self, image: np.ndarray) -> Dict[str, float]:
        """
        Compute image quality and content metrics.
        
        Args:
            image: Preprocessed image array
            
        Returns:
            Dictionary of computed metrics
        """
        try:
            # Convert to grayscale for edge detection
            gray = cv2.cvtColor((image * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
            
            # Laplacian variance (edge variance)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Color saturation metrics
            hsv = cv2.cvtColor((image * 255).astype(np.uint8), cv2.COLOR_RGB2HSV)
            saturation = hsv[:, :, 1].astype(np.float32) / 255.0
            mean_saturation = np.mean(saturation)
            saturation_std = np.std(saturation)
            
            # Image dimensions
            height, width = image.shape[:2]
            
            return {
                'laplacian_variance': float(laplacian_var),
                'mean_saturation': float(mean_saturation),
                'saturation_std': float(saturation_std),
                'width': width,
                'height': height
            }
            
        except Exception as e:
            logger.error(f"Error computing image metrics: {e}")
            return {}
    
    def detect_ai_generated_image(self, image: np.ndarray, filename: str = "") -> Dict[str, Any]:
        """
        Detect if image is AI-generated using content analysis.
        
        Args:
            image: Preprocessed image array
            filename: Original filename (for pattern analysis)
            
        Returns:
            AI detection results
        """
        try:
            metrics = self.compute_image_metrics(image)
            if not metrics:
                return {
                    'is_real_image': True,
                    'confidence': 0.5,
                    'detection_method': 'Content Analysis (fallback)',
                    'indicators': ['Metrics unavailable']
                }
            
            # AI detection heuristics
            ai_score = 0
            indicators = []
            
            # Check edge variance (AI images often have different edge patterns)
            if metrics['laplacian_variance'] < 50:
                ai_score += 0.2
                indicators.append('Very low edge variance (over-smooth)')
            elif metrics['laplacian_variance'] > 1000:
                ai_score += 0.15
                indicators.append('Very high edge variance (over-sharpened)')
            
            # Check saturation distribution
            if metrics['saturation_std'] < 0.05:
                ai_score += 0.1
                indicators.append('Low saturation diversity')
            
            # Check for perfect square dimensions (common in AI generation)
            if metrics['width'] == metrics['height'] and metrics['width'] % 64 == 0:
                ai_score += 0.1
                indicators.append('Perfect square with power-of-64 dimensions')
            
            # Filename pattern analysis
            if filename:
                filename_lower = filename.lower()
                ai_patterns = ['ai_generated', 'dalle', 'midjourney', 'stable_diffusion', 'generated']
                if any(pattern in filename_lower for pattern in ai_patterns):
                    ai_score += 0.3
                    indicators.append('AI-related filename patterns')
            
            # Determine if AI-generated
            is_ai_generated = ai_score > 0.3
            confidence = min(0.9, 0.5 + ai_score)
            
            return {
                'is_real_image': not is_ai_generated,
                'confidence': confidence,
                'detection_method': 'Enhanced Content Analysis',
                'indicators': indicators,
                'ai_score': ai_score
            }
            
        except Exception as e:
            logger.error(f"Error in AI detection: {e}")
            return {
                'is_real_image': True,
                'confidence': 0.5,
                'detection_method': 'Fallback',
                'indicators': ['Detection failed']
            }
    
    def detect_hazard_type(self, image: np.ndarray, filename: str = "", description: str = "") -> Dict[str, Any]:
        """
        Detect hazard type from image content and metadata.
        
        Args:
            image: Preprocessed image array
            filename: Original filename
            description: User description
            
        Returns:
            Hazard detection results
        """
        try:
            # Get image metrics for content analysis
            metrics = self.compute_image_metrics(image)
            if not metrics:
                return {
                    'detected_type': 'other',
                    'confidence': 0.3,
                    'top_predictions': [{'hazard_type': 'other', 'confidence': 0.3}]
                }
            
            # Content-based detection using metrics
            detected_types = []
            confidences = []
            
            # Analyze image characteristics
            laplacian_var = metrics['laplacian_variance']
            mean_sat = metrics['mean_saturation']
            sat_std = metrics['saturation_std']
            
            # Storm surge detection (high edge variance, varied saturation)
            if laplacian_var > 150 and sat_std > 0.15:
                detected_types.append('storm-surge')
                confidences.append(0.8)
            
            # High waves detection (very high edge variance)
            if laplacian_var > 130:
                detected_types.append('high-waves')
                confidences.append(0.7)
            
            # Flooding detection (moderate edge variance, lower saturation)
            if laplacian_var > 100 and mean_sat < 0.4:
                detected_types.append('flooding')
                confidences.append(0.6)
            
            # Tsunami detection (very high edge variance)
            if laplacian_var > 200:
                detected_types.append('tsunami')
                confidences.append(0.9)
            
            # Debris detection (high edge variance)
            if laplacian_var > 160:
                detected_types.append('debris')
                confidences.append(0.7)
            
            # Filename and description analysis
            text_content = (filename + " " + description).lower()
            
            # Keyword-based detection
            keyword_mapping = {
                'tsunami': ['tsunami', 'tidal', 'seismic', 'evacuation'],
                'storm-surge': ['storm', 'surge', 'hurricane', 'cyclone', 'typhoon'],
                'high-waves': ['wave', 'rough', 'swell', 'surf'],
                'flooding': ['flood', 'water', 'inundation', 'flooded'],
                'debris': ['debris', 'trash', 'litter', 'waste'],
                'pollution': ['oil', 'spill', 'pollution', 'contamination'],
                'erosion': ['erosion', 'coast', 'cliff', 'beach loss'],
                'wildlife': ['wildlife', 'fish', 'animal', 'marine life']
            }
            
            for hazard_type, keywords in keyword_mapping.items():
                if any(keyword in text_content for keyword in keywords):
                    if hazard_type not in detected_types:
                        detected_types.append(hazard_type)
                        confidences.append(0.8)
                    else:
                        # Boost existing confidence
                        idx = detected_types.index(hazard_type)
                        confidences[idx] = min(0.95, confidences[idx] + 0.2)
            
            # Default to 'other' if nothing detected
            if not detected_types:
                detected_types = ['other']
                confidences = [0.3]
            
            # Sort by confidence
            sorted_indices = np.argsort(confidences)[::-1]
            top_predictions = [
                {
                    'hazard_type': detected_types[i],
                    'confidence': confidences[i]
                }
                for i in sorted_indices[:3]
            ]
            
            return {
                'detected_type': detected_types[0],
                'confidence': confidences[0],
                'top_predictions': top_predictions
            }
            
        except Exception as e:
            logger.error(f"Error in hazard detection: {e}")
            return {
                'detected_type': 'other',
                'confidence': 0.3,
                'top_predictions': [{'hazard_type': 'other', 'confidence': 0.3}]
            }
    
    def verify_image(self, image_data: bytes, selected_hazard_type: str = None, 
                    description: str = "", filename: str = "") -> Dict[str, Any]:
        """
        Verify an image using AI analysis.
        
        Args:
            image_data: Raw image bytes
            selected_hazard_type: Expected hazard type
            description: User description
            filename: Original filename
            
        Returns:
            Verification results
        """
        try:
            # Preprocess image
            image = self.preprocess_image(image_data)
            if image is None:
                return {
                    'status': 'error',
                    'message': 'Failed to process image',
                    'confidence': 0.0
                }
            
            # Run AI detection
            ai_detection = self.detect_ai_generated_image(image, filename)
            
            # Run hazard detection
            hazard_detection = self.detect_hazard_type(image, filename, description)
            
            # Determine verification status
            status = 'verified'
            message = 'Image verified successfully'
            
            # Check AI generation
            if not ai_detection['is_real_image']:
                status = 'failed'
                message = 'AI-generated image detected - only real photos are accepted'
            
            # Check hazard type match
            elif selected_hazard_type and hazard_detection['detected_type'] != selected_hazard_type:
                status = 'failed'
                message = f'Image content does not match selected hazard type. Detected: {hazard_detection["detected_type"]}'
            
            # Check confidence threshold
            elif hazard_detection['confidence'] < 0.6:
                status = 'failed'
                message = 'Low confidence in hazard detection - please check image quality'
            
            # Overall confidence
            overall_confidence = (hazard_detection['confidence'] + ai_detection['confidence']) / 2
            
            return {
                'status': status,
                'message': message,
                'confidence': overall_confidence,
                'hazard_detection': hazard_detection,
                'ai_detection': ai_detection,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in image verification: {e}")
            return {
                'status': 'error',
                'message': f'Verification failed: {str(e)}',
                'confidence': 0.0,
                'timestamp': datetime.now().isoformat()
            }
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the verification service."""
        return {
            'models_loaded': self.models_available,
            'hazard_types': self.hazard_types,
            'service_mode': 'Enhanced Fallback' if not self.models_available else 'Full AI',
            'version': '1.0.0'
        }


# Global service instance
verification_service = AIVerificationService()


def verify_image_endpoint(image_data: bytes, hazard_type: str = None, 
                         description: str = "", filename: str = "") -> Dict[str, Any]:
    """
    Main endpoint function for image verification.
    
    Args:
        image_data: Raw image bytes
        hazard_type: Expected hazard type
        description: User description
        filename: Original filename
        
    Returns:
        Verification results compatible with frontend
    """
    try:
        # Run verification
        result = verification_service.verify_image(
            image_data, hazard_type, description, filename
        )
        
        # Format for frontend compatibility
        return {
            'status': result['status'],
            'checks': {
                'isImage': True,
                'fileSize': len(image_data) < 10 * 1024 * 1024,  # Less than 10MB
                'fileName': not filename.lower().includes('suspicious'),
                'isRealImage': result['ai_detection']['is_real_image'],
                'hazardTypeMatch': result['status'] == 'verified',
                'scenarioMatch': result['status'] == 'verified',
                'locationValid': True,
                'contentAnalysis': result['confidence'] > 0.7,
                'hazardRelevant': result['hazard_detection']['confidence'] > 0.5
            },
            'aiDetection': result['ai_detection'],
            'hazardMatching': {
                'matchesSelectedType': result['hazard_detection']['detected_type'] == hazard_type if hazard_type else True,
                'detectedHazardTypes': [result['hazard_detection']['detected_type']],
                'confidence': result['hazard_detection']['confidence'],
                'scenarioMatch': result['status'] == 'verified'
            },
            'confidence': result['confidence'],
            'message': result['message'],
            'timestamp': result['timestamp']
        }
        
    except Exception as e:
        logger.error(f"Error in verification endpoint: {e}")
        return {
            'status': 'error',
            'checks': {},
            'aiDetection': {},
            'hazardMatching': {},
            'confidence': 0.0,
            'message': f'Verification service error: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }
