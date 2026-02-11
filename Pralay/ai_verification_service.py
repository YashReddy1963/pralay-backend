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
            
            # Water content analysis
            water_metrics = self.analyze_water_content(image)
            
            return {
                'laplacian_variance': float(laplacian_var),
                'mean_saturation': float(mean_saturation),
                'saturation_std': float(saturation_std),
                'width': width,
                'height': height,
                **water_metrics
            }
            
        except Exception as e:
            logger.error(f"Error computing image metrics: {e}")
            return {}
    
    def analyze_water_content(self, image: np.ndarray) -> Dict[str, float]:
        """
        Analyze if the image contains water/ocean content.
        
        Args:
            image: RGB image array (0-1 normalized)
            
        Returns:
            Dictionary with water content metrics
        """
        try:
            # Convert to uint8 for OpenCV operations
            image_uint8 = (image * 255).astype(np.uint8)
            
            # Convert to HSV for better color analysis
            hsv = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2HSV)
            
            # Define comprehensive water color ranges
            # Blue water: H=100-130, S=50-255, V=30-255
            # White foam: H=0-180, S=0-30, V=150-255 (low saturation, high brightness)
            # Grey storm water: H=0-180, S=0-50, V=50-150 (low saturation, medium brightness)
            # Brown muddy water: H=10-30, S=50-200, V=30-150
            # Cyan/teal water: H=80-100, S=50-255, V=30-255
            
            # Create masks for different water conditions
            blue_mask1 = cv2.inRange(hsv, (100, 50, 30), (130, 255, 255))  # Standard blue water
            blue_mask2 = cv2.inRange(hsv, (100, 100, 20), (130, 255, 200))  # Deep blue water
            blue_mask3 = cv2.inRange(hsv, (100, 50, 100), (130, 150, 255))  # Light blue water
            cyan_mask = cv2.inRange(hsv, (80, 50, 30), (100, 255, 255))     # Cyan/teal water
            
            # White foam from breaking waves
            white_foam_mask = cv2.inRange(hsv, (0, 0, 150), (180, 30, 255))
            
            # Grey storm water
            grey_water_mask = cv2.inRange(hsv, (0, 0, 50), (180, 50, 150))
            
            # Brown muddy water (flooding, debris)
            brown_water_mask = cv2.inRange(hsv, (10, 50, 30), (30, 200, 150))
            
            # Combine all water masks
            water_mask = cv2.bitwise_or(blue_mask1, cv2.bitwise_or(blue_mask2, cv2.bitwise_or(blue_mask3, 
                cv2.bitwise_or(cyan_mask, cv2.bitwise_or(white_foam_mask, cv2.bitwise_or(grey_water_mask, brown_water_mask))))))
            
            # Calculate water percentage
            total_pixels = image.shape[0] * image.shape[1]
            water_pixels = np.sum(water_mask > 0)
            water_percentage = water_pixels / total_pixels
            
            # Analyze edge patterns typical of water surfaces
            gray = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2GRAY)
            
            # Detect horizontal edges (typical of water surfaces)
            sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            
            # Calculate edge direction distribution
            edge_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
            edge_direction = np.arctan2(sobel_y, sobel_x)
            
            # Count different edge patterns typical of water
            horizontal_edges = np.sum((edge_direction > -0.3) & (edge_direction < 0.3))  # Horizontal waves
            vertical_edges = np.sum((edge_direction > 1.4) | (edge_direction < -1.4))    # Vertical splashes
            diagonal_edges = np.sum((edge_direction > 0.3) & (edge_direction < 1.4)) + \
                           np.sum((edge_direction > -1.4) & (edge_direction < -0.3))  # Diagonal turbulence
            total_edges = np.sum(edge_magnitude > 30)  # Threshold for significant edges
            
            # Calculate water-like edge patterns (waves, splashes, turbulence)
            water_edges = horizontal_edges + vertical_edges * 0.8 + diagonal_edges * 0.6
            water_edge_ratio = water_edges / total_edges if total_edges > 0 else 0
            
            # Also keep the original horizontal edge ratio for backward compatibility
            horizontal_edge_ratio = horizontal_edges / total_edges if total_edges > 0 else 0
            
            # Analyze texture uniformity (water surfaces have characteristic textures)
            texture_variance = np.var(gray)
            
            # Calculate enhanced water confidence score
            water_confidence = (
                water_percentage * 0.4 +  # Water color presence (blue, white, grey, brown)
                min(water_edge_ratio * 1.5, 1.0) * 0.35 +  # Water-like edge patterns (waves, splashes, turbulence)
                min(texture_variance / 1000, 1.0) * 0.25  # Texture characteristics
            )
            
            # Additional validation: Check for coherent water regions
            # Random noise should not have large coherent regions of water colors
            if water_percentage > 0.1:
                # Check if water regions are coherent (not just scattered pixels)
                contours, _ = cv2.findContours(water_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    largest_contour_area = max([cv2.contourArea(c) for c in contours])
                    coherent_water_ratio = largest_contour_area / total_pixels
                    # If largest water region is too small, likely noise
                    if coherent_water_ratio < 0.05:  # Less than 5% coherent region
                        water_confidence *= 0.3  # Significantly reduce confidence
            
            return {
                'water_percentage': float(water_percentage),
                'water_confidence': float(water_confidence),
                'water_edge_ratio': float(water_edge_ratio),
                'horizontal_edge_ratio': float(horizontal_edge_ratio),
                'texture_variance': float(texture_variance),
                'has_significant_water': water_percentage > 0.4 and water_confidence > 0.75
            }
            
        except Exception as e:
            logger.error(f"Error analyzing water content: {e}")
            return {
                'water_percentage': 0.0,
                'water_confidence': 0.0,
                'water_edge_ratio': 0.0,
                'horizontal_edge_ratio': 0.0,
                'texture_variance': 0.0,
                'has_significant_water': False
            }
    
    def has_water_content(self, image: np.ndarray) -> bool:
        """
        Quick check if image has significant water content.
        
        Args:
            image: Preprocessed image array
            
        Returns:
            True if significant water content detected, False otherwise
        """
        try:
            # Get water metrics
            water_metrics = self.analyze_water_content(image)
            
            # Check if water content is significant
            return water_metrics.get('has_significant_water', False)
            
        except Exception as e:
            logger.error(f"Error checking water content: {e}")
            return False
    
    def has_coherent_water_regions(self, image_uint8: np.ndarray, water_mask: np.ndarray) -> bool:
        """
        Check if water regions are coherent (not just scattered noise).
        
        Args:
            image_uint8: Image in uint8 format
            water_mask: Binary mask of water pixels
            
        Returns:
            True if water regions are coherent, False otherwise
        """
        try:
            total_pixels = image_uint8.shape[0] * image_uint8.shape[1]
            water_pixels = np.sum(water_mask > 0)
            
            # If very little water, not significant
            if water_pixels < total_pixels * 0.1:
                return False
            
            # Find contours of water regions
            contours, _ = cv2.findContours(water_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return False
            
            # Check if we have coherent water regions
            largest_contour_area = max([cv2.contourArea(c) for c in contours])
            coherent_water_ratio = largest_contour_area / total_pixels
            
            # Require at least 5% of image to be a coherent water region
            return coherent_water_ratio >= 0.05
            
        except Exception as e:
            logger.error(f"Error checking coherent water regions: {e}")
            return False
    
    def has_hazard_indicators(self, image: np.ndarray) -> bool:
        """
        Check if image contains actual hazard indicators (damage, destruction, emergency situations).
        
        Args:
            image: Preprocessed image array
            
        Returns:
            True if hazard indicators are detected, False otherwise
        """
        try:
            # Convert to uint8 for OpenCV operations
            image_uint8 = (image * 255).astype(np.uint8)
            
            # Get image metrics for analysis
            metrics = self.compute_image_metrics(image)
            if not metrics:
                return False
            
            # Check for hazard indicators
            hazard_score = 0
            indicators_found = []
            
            # 1. High edge variance indicates destruction/damage
            if metrics['laplacian_variance'] > 200:
                hazard_score += 0.3
                indicators_found.append('high_chaos_damage')
            
            # 2. Very high edge variance indicates severe destruction
            if metrics['laplacian_variance'] > 500:
                hazard_score += 0.2
                indicators_found.append('severe_destruction')
            
            # 3. Check for debris-like patterns (high texture variance with mixed colors)
            if metrics['texture_variance'] > 2000:
                hazard_score += 0.2
                indicators_found.append('debris_patterns')
            
            # 4. Analyze color patterns for emergency/danger indicators
            emergency_indicators = self.detect_emergency_color_patterns(image_uint8)
            hazard_score += emergency_indicators['score']
            if emergency_indicators['score'] > 0.1:
                indicators_found.extend(emergency_indicators['indicators'])
            
            # 5. Check for structural damage patterns
            structural_damage = self.detect_structural_damage(image_uint8)
            hazard_score += structural_damage['score']
            if structural_damage['score'] > 0.1:
                indicators_found.extend(structural_damage['indicators'])
            
            # 6. Check for emergency equipment/vehicles
            emergency_equipment = self.detect_emergency_equipment(image_uint8)
            hazard_score += emergency_equipment['score']
            if emergency_equipment['score'] > 0.1:
                indicators_found.extend(emergency_equipment['indicators'])
            
            # Require significant hazard indicators (more strict for camera photos)
            has_hazards = hazard_score > 0.6 and len(indicators_found) >= 3
            
            logger.info(f"Hazard detection - Score: {hazard_score:.2f}, Indicators: {indicators_found}, Result: {has_hazards}")
            
            return has_hazards
            
        except Exception as e:
            logger.error(f"Error detecting hazard indicators: {e}")
            return False
    
    def detect_emergency_color_patterns(self, image_uint8: np.ndarray) -> Dict[str, Any]:
        """Detect emergency/danger color patterns like orange, red, yellow."""
        try:
            hsv = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2HSV)
            
            indicators = []
            score = 0
            
            # Orange emergency equipment (life jackets, buoys, cones)
            orange_mask = cv2.inRange(hsv, (10, 100, 100), (25, 255, 255))
            orange_pixels = np.sum(orange_mask > 0)
            if orange_pixels > 1000:  # Significant orange presence
                score += 0.15
                indicators.append('orange_emergency_equipment')
            
            # Red danger signs, emergency vehicles
            red_mask = cv2.inRange(hsv, (0, 100, 100), (10, 255, 255))
            red_pixels = np.sum(red_mask > 0)
            if red_pixels > 1000:
                score += 0.15
                indicators.append('red_danger_signs')
            
            # Yellow warning signs, caution tape
            yellow_mask = cv2.inRange(hsv, (20, 100, 100), (30, 255, 255))
            yellow_pixels = np.sum(yellow_mask > 0)
            if yellow_pixels > 1000:
                score += 0.1
                indicators.append('yellow_warning_signs')
            
            return {'score': score, 'indicators': indicators}
            
        except Exception as e:
            logger.error(f"Error detecting emergency colors: {e}")
            return {'score': 0, 'indicators': []}
    
    def detect_structural_damage(self, image_uint8: np.ndarray) -> Dict[str, Any]:
        """Detect structural damage patterns like broken edges, debris."""
        try:
            gray = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2GRAY)
            
            indicators = []
            score = 0
            
            # Detect sharp, irregular edges (damaged structures)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            if edge_density > 0.1:  # High edge density indicates damage
                score += 0.2
                indicators.append('high_edge_density_damage')
            
            # Detect irregular shapes (debris, broken structures)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                # Check for irregular, non-geometric shapes
                irregular_shapes = 0
                for contour in contours:
                    if cv2.contourArea(contour) > 100:  # Significant contours
                        # Calculate shape irregularity
                        perimeter = cv2.arcLength(contour, True)
                        area = cv2.contourArea(contour)
                        if area > 0:
                            circularity = 4 * np.pi * area / (perimeter * perimeter)
                            if circularity < 0.3:  # Very irregular shape
                                irregular_shapes += 1
                
                if irregular_shapes > 5:  # Multiple irregular shapes
                    score += 0.15
                    indicators.append('irregular_debris_shapes')
            
            return {'score': score, 'indicators': indicators}
            
        except Exception as e:
            logger.error(f"Error detecting structural damage: {e}")
            return {'score': 0, 'indicators': []}
    
    def detect_emergency_equipment(self, image_uint8: np.ndarray) -> Dict[str, Any]:
        """Detect emergency equipment like vehicles, barriers, rescue gear."""
        try:
            hsv = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2HSV)
            gray = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2GRAY)
            
            indicators = []
            score = 0
            
            # Detect large rectangular shapes (vehicles, equipment)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                vehicle_like_objects = 0
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > 5000:  # Large objects
                        # Check if roughly rectangular (vehicle-like)
                        x, y, w, h = cv2.boundingRect(contour)
                        aspect_ratio = w / h if h > 0 else 0
                        if 1.5 < aspect_ratio < 4.0:  # Vehicle-like proportions
                            vehicle_like_objects += 1
                
                if vehicle_like_objects > 0:
                    score += 0.1
                    indicators.append('vehicle_like_objects')
            
            # Detect bright/reflective surfaces (emergency equipment)
            bright_mask = cv2.inRange(hsv, (0, 0, 200), (180, 30, 255))
            bright_pixels = np.sum(bright_mask > 0)
            if bright_pixels > 2000:
                score += 0.1
                indicators.append('reflective_equipment')
            
            return {'score': score, 'indicators': indicators}
            
        except Exception as e:
            logger.error(f"Error detecting emergency equipment: {e}")
            return {'score': 0, 'indicators': []}
    
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
            if metrics['laplacian_variance'] < 30:
                ai_score += 0.2
                indicators.append('Very low edge variance (over-smooth)')
            elif metrics['laplacian_variance'] > 2000:
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
            
            # More balanced hazard detection with overlapping thresholds
            
            # Storm surge detection (high edge variance, varied saturation)
            if laplacian_var > 120 and sat_std > 0.12:
                detected_types.append('storm-surge')
                confidences.append(0.7)
            
            # High waves detection (moderate to high edge variance)
            if laplacian_var > 100:
                detected_types.append('high-waves')
                confidences.append(0.6)
            
            # Flooding detection (moderate edge variance, lower saturation)
            if laplacian_var > 80 and mean_sat < 0.5:
                detected_types.append('flooding')
                confidences.append(0.5)
            
            # Tsunami detection (very high edge variance)
            if laplacian_var > 180:
                detected_types.append('tsunami')
                confidences.append(0.8)
            
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
            
            # Check water content (most important check)
            elif not self.has_water_content(image):
                status = 'failed'
                message = 'No significant water content detected - please upload images with water/ocean scenes'
            
            # Check for actual hazard indicators (damage, destruction, emergency situations)
            elif not self.has_hazard_indicators(image):
                status = 'failed'
                message = 'No hazard indicators detected - please upload images showing actual flood damage, destruction, or emergency situations'
            
            # Check hazard type match (with related hazard types)
            elif selected_hazard_type and not self.is_hazard_type_compatible(selected_hazard_type, hazard_detection['detected_type']):
                status = 'failed'
                message = f'Image content does not match selected hazard type. Detected: {hazard_detection["detected_type"]}'
            
            # Check confidence threshold (more lenient)
            elif hazard_detection['confidence'] < 0.4:
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
    
    def is_hazard_type_compatible(self, selected_type: str, detected_type: str) -> bool:
        """
        Check if two hazard types are compatible (related or same).
        
        Args:
            selected_type: User-selected hazard type
            detected_type: AI-detected hazard type
            
        Returns:
            True if types are compatible, False otherwise
        """
        # Exact match
        if selected_type == detected_type:
            return True
        
        # Define compatible hazard type groups
        compatible_groups = {
            # Water-related hazards
            'water_hazards': ['flooding', 'storm-surge', 'high-waves', 'tsunami'],
            
            # Weather-related hazards  
            'weather_hazards': ['storm-surge', 'tsunami', 'high-waves'],
            
            # Environmental hazards
            'environmental_hazards': ['pollution', 'debris', 'erosion'],
            
            # Marine hazards
            'marine_hazards': ['wildlife', 'pollution', 'debris']
        }
        
        # Check if both types are in the same compatible group
        for group_name, types in compatible_groups.items():
            if selected_type in types and detected_type in types:
                return True
        
        # Special cases for very similar hazard types
        similar_pairs = [
            ('flooding', 'storm-surge'),
            ('storm-surge', 'high-waves'),
            ('high-waves', 'tsunami'),
            ('pollution', 'debris'),
            ('erosion', 'debris')
        ]
        
        for pair in similar_pairs:
            if (selected_type == pair[0] and detected_type == pair[1]) or \
               (selected_type == pair[1] and detected_type == pair[0]):
                return True
        
        # If no compatibility found, be more lenient for ocean-related content
        ocean_related = ['flooding', 'storm-surge', 'high-waves', 'tsunami', 'pollution', 'debris', 'erosion']
        if selected_type in ocean_related and detected_type in ocean_related:
            # For ocean-related hazards, be more lenient if confidence is high
            return True
        
        return False
    

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
                'fileName': 'suspicious' not in filename.lower(),
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
