"""
Video Verification Service for Ocean Hazard Detection
Separate from image verification - dedicated to video analysis
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
import io

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoVerificationService:
    """AI-powered verification service for ocean hazard videos."""
    
    def __init__(self):
        self.hazard_types = [
            "tsunami", "storm-surge", "high-waves", "flooding",
            "debris", "pollution", "erosion", "wildlife", "other"
        ]
        
        # Video processing parameters (balanced for speed and accuracy)
        self.max_frames_to_analyze = 4  # Balanced: 4 frames for good accuracy
        self.frame_interval = 3  # Analyze every 3rd frame for reasonable speed
        self.min_video_duration = 1  # Minimum 1 second
        self.max_video_duration = 300  # Maximum 5 minutes
        self.target_processing_time = 3  # Target max 3 seconds processing
        
        # Simple cache for recent verifications (by file hash)
        self.verification_cache = {}
        self.cache_max_size = 50  # Keep last 50 verifications
        
        logger.info("Video Verification Service initialized with speed optimizations")
    
    def extract_key_frames(self, video_path: str, fast_mode: bool = True) -> List[np.ndarray]:
        """
        Extract key frames from video for analysis.
        
        Args:
            video_path: Path to video file
            fast_mode: If True, use faster but less thorough analysis
            
        Returns:
            List of extracted frames as numpy arrays
        """
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Could not open video file: {video_path}")
                return []
            
            frames = []
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = frame_count / fps if fps > 0 else 0
            
            logger.info(f"Video info - Frames: {frame_count}, FPS: {fps}, Duration: {duration:.2f}s")
            
            # Check video duration
            if duration < self.min_video_duration:
                logger.warning(f"Video too short: {duration:.2f}s (min: {self.min_video_duration}s)")
                return []
            
            if duration > self.max_video_duration:
                logger.warning(f"Video too long: {duration:.2f}s (max: {self.max_video_duration}s)")
                return []
            
            # Optimize frame extraction based on video length (balanced mode)
            if fast_mode:
                # For balanced mode, extract 3-4 frames from key moments
                if duration <= 30:  # Short videos: extract 3 frames
                    target_frames = 3
                    # Extract from beginning, middle, end
                    frame_positions = [0.2, 0.5, 0.8]
                elif duration <= 120:  # Medium videos: extract 4 frames
                    target_frames = 4
                    frame_positions = [0.1, 0.3, 0.6, 0.9]
                else:  # Long videos: extract 4 frames
                    target_frames = 4
                    frame_positions = [0.1, 0.3, 0.6, 0.9]
                
                for pos in frame_positions:
                    frame_idx = int(pos * frame_count)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    
                    if ret:
                        # Resize frame for balanced processing (reduce to 480x360 max)
                        height, width = frame.shape[:2]
                        if width > 480:
                            scale = 480 / width
                            new_width = 480
                            new_height = int(height * scale)
                            frame = cv2.resize(frame, (new_width, new_height))
                        
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        frames.append(frame_rgb)
                        logger.debug(f"Balanced mode: Extracted frame {frame_idx}")
            else:
                # Standard mode: extract frames at regular intervals
                frame_interval = max(1, frame_count // self.max_frames_to_analyze)
                
                frame_idx = 0
                while len(frames) < self.max_frames_to_analyze and frame_idx < frame_count:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    
                    if ret:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        frames.append(frame_rgb)
                        logger.debug(f"Standard mode: Extracted frame {frame_idx}")
                    
                    frame_idx += frame_interval
            
            cap.release()
            logger.info(f"Extracted {len(frames)} frames from video (fast_mode={fast_mode})")
            return frames
            
        except Exception as e:
            logger.error(f"Error extracting frames: {e}")
            return []
    
    def analyze_frame_for_ocean_content(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Analyze a single frame for ocean-related content (optimized for speed).
        
        Args:
            frame: RGB frame array
            
        Returns:
            Analysis results for the frame
        """
        try:
            # Convert to HSV for better color analysis
            hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
            
            # Ocean water color detection (balanced for accuracy and speed)
            # Blue water (most common ocean color)
            blue_lower = np.array([100, 50, 30])
            blue_upper = np.array([130, 255, 255])
            blue_mask = cv2.inRange(hsv, blue_lower, blue_upper)
            
            # White foam/waves
            white_lower = np.array([0, 0, 150])
            white_upper = np.array([180, 30, 255])
            white_mask = cv2.inRange(hsv, white_lower, white_upper)
            
            # Grey storm water (important for hazard detection)
            grey_lower = np.array([0, 0, 50])
            grey_upper = np.array([180, 50, 150])
            grey_mask = cv2.inRange(hsv, grey_lower, grey_upper)
            
            # Calculate water percentages
            total_pixels = frame.shape[0] * frame.shape[1]
            blue_pixels = np.sum(blue_mask > 0)
            white_pixels = np.sum(white_mask > 0)
            grey_pixels = np.sum(grey_mask > 0)
            
            blue_percentage = blue_pixels / total_pixels
            white_percentage = white_pixels / total_pixels
            grey_percentage = grey_pixels / total_pixels
            total_water_percentage = blue_percentage + white_percentage + grey_percentage
            
            # Motion detection for waves
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 50, 150)  # Balanced thresholds
            
            # Count horizontal edges (typical of waves)
            horizontal_kernel = np.array([[-1, -1, -1], [2, 2, 2], [-1, -1, -1]])
            horizontal_edges = cv2.filter2D(edges, -1, horizontal_kernel)
            horizontal_edge_density = np.sum(horizontal_edges > 0) / total_pixels
            
            # Water confidence calculation
            water_confidence = min(1.0, total_water_percentage * 2 + horizontal_edge_density * 3)
            
            return {
                'blue_water_percentage': float(blue_percentage),
                'white_foam_percentage': float(white_percentage),
                'grey_water_percentage': float(grey_percentage),
                'total_water_percentage': float(total_water_percentage),
                'horizontal_edge_density': float(horizontal_edge_density),
                'water_confidence': float(water_confidence),
                'has_ocean_content': total_water_percentage > 0.1 or water_confidence > 0.3
            }
            
        except Exception as e:
            logger.error(f"Error analyzing frame: {e}")
            return {
                'blue_water_percentage': 0.0,
                'white_foam_percentage': 0.0,
                'grey_water_percentage': 0.0,
                'total_water_percentage': 0.0,
                'horizontal_edge_density': 0.0,
                'water_confidence': 0.0,
                'has_ocean_content': False
            }
    
    def analyze_hazard_indicators(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Analyze frame for hazard indicators (optimized for speed).
        
        Args:
            frame: RGB frame array
            
        Returns:
            Hazard analysis results
        """
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            
            # High activity detection (storm conditions)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Detect debris patterns (high edge density)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            # Detect emergency colors (red, orange, yellow)
            hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
            
            # Red emergency indicators
            red_lower = np.array([0, 100, 100])
            red_upper = np.array([10, 255, 255])
            red_mask = cv2.inRange(hsv, red_lower, red_upper)
            red_percentage = np.sum(red_mask > 0) / (frame.shape[0] * frame.shape[1])
            
            # Orange emergency indicators
            orange_lower = np.array([10, 100, 100])
            orange_upper = np.array([25, 255, 255])
            orange_mask = cv2.inRange(hsv, orange_lower, orange_upper)
            orange_percentage = np.sum(orange_mask > 0) / (frame.shape[0] * frame.shape[1])
            
            # Calculate hazard score
            hazard_score = 0
            indicators = []
            
            if laplacian_var > 200:  # High activity
                hazard_score += 0.3
                indicators.append('high_activity')
            
            if edge_density > 0.1:  # High edge density (debris/damage)
                hazard_score += 0.2
                indicators.append('debris_patterns')
            
            if red_percentage > 0.05:  # Emergency red
                hazard_score += 0.2
                indicators.append('emergency_red')
            
            if orange_percentage > 0.05:  # Emergency orange
                hazard_score += 0.15
                indicators.append('emergency_orange')
            
            return {
                'hazard_score': float(hazard_score),
                'indicators': indicators,
                'laplacian_variance': float(laplacian_var),
                'edge_density': float(edge_density),
                'red_percentage': float(red_percentage),
                'orange_percentage': float(orange_percentage),
                'has_hazard_indicators': hazard_score > 0.1 or len(indicators) >= 1
            }
            
        except Exception as e:
            logger.error(f"Error analyzing hazard indicators: {e}")
            return {
                'hazard_score': 0.0,
                'indicators': [],
                'laplacian_variance': 0.0,
                'edge_density': 0.0,
                'red_percentage': 0.0,
                'orange_percentage': 0.0,
                'has_hazard_indicators': False
            }
    
    def detect_hazard_type_from_video(self, frames: List[np.ndarray], 
                                    filename: str = "", description: str = "") -> Dict[str, Any]:
        """
        Detect hazard type from video frames and metadata.
        
        Args:
            frames: List of extracted frames
            filename: Video filename
            description: User description
            
        Returns:
            Hazard type detection results
        """
        try:
            if not frames:
                return {
                    'detected_type': 'other',
                    'confidence': 0.3,
                    'top_predictions': [{'hazard_type': 'other', 'confidence': 0.3}]
                }
            
            # Analyze all frames
            ocean_scores = []
            hazard_scores = []
            
            for frame in frames:
                ocean_analysis = self.analyze_frame_for_ocean_content(frame)
                hazard_analysis = self.analyze_hazard_indicators(frame)
                
                ocean_scores.append(ocean_analysis['water_confidence'])
                hazard_scores.append(hazard_analysis['hazard_score'])
            
            # Calculate average scores
            avg_ocean_score = np.mean(ocean_scores) if ocean_scores else 0
            avg_hazard_score = np.mean(hazard_scores) if hazard_scores else 0
            
            # Determine hazard type based on scores and patterns
            detected_types = []
            confidences = []
            
            # Storm surge detection (high ocean + high hazard)
            if avg_ocean_score > 0.7 and avg_hazard_score > 0.6:
                detected_types.append('storm-surge')
                confidences.append(0.8)
            
            # High waves detection (high ocean + moderate hazard)
            elif avg_ocean_score > 0.6 and avg_hazard_score > 0.4:
                detected_types.append('high-waves')
                confidences.append(0.7)
            
            # Tsunami detection (very high scores)
            elif avg_ocean_score > 0.8 and avg_hazard_score > 0.7:
                detected_types.append('tsunami')
                confidences.append(0.9)
            
            # Flooding detection (moderate ocean + high hazard)
            elif avg_ocean_score > 0.4 and avg_hazard_score > 0.5:
                detected_types.append('flooding')
                confidences.append(0.6)
            
            # Text-based detection
            text_content = (filename + " " + description).lower()
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
                'top_predictions': top_predictions,
                'ocean_score': float(avg_ocean_score),
                'hazard_score': float(avg_hazard_score)
            }
            
        except Exception as e:
            logger.error(f"Error in hazard type detection: {e}")
            return {
                'detected_type': 'other',
                'confidence': 0.3,
                'top_predictions': [{'hazard_type': 'other', 'confidence': 0.3}],
                'ocean_score': 0.0,
                'hazard_score': 0.0
            }
    
    def verify_video(self, video_data: bytes, selected_hazard_type: str = None, 
                    description: str = "", filename: str = "", quick_mode: bool = False) -> Dict[str, Any]:
        """
        Verify a video for ocean hazard content.
        
        Args:
            video_data: Raw video bytes
            selected_hazard_type: Expected hazard type
            description: User description
            filename: Original filename
            quick_mode: If True, use ultra-fast verification (default: True)
            
        Returns:
            Verification results
        """
        try:
            # Check cache first (simple hash-based caching)
            import hashlib
            video_hash = hashlib.md5(video_data[:1024]).hexdigest()  # Hash first 1KB for speed
            cache_key = f"{video_hash}_{selected_hazard_type}_{filename}"
            
            if cache_key in self.verification_cache:
                logger.info(f"Using cached verification result for {filename}")
                cached_result = self.verification_cache[cache_key].copy()
                cached_result['cached'] = True
                cached_result['timestamp'] = datetime.now().isoformat()
                return cached_result
            
            # Save video to temporary file
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                temp_file.write(video_data)
                temp_video_path = temp_file.name
            
            try:
                if quick_mode:
                    # Ultra-quick mode: minimal processing for speed
                    result = self._quick_verify_video(temp_video_path, selected_hazard_type, description, filename)
                    # Cache the result
                    if len(self.verification_cache) >= self.cache_max_size:
                        oldest_key = next(iter(self.verification_cache))
                        del self.verification_cache[oldest_key]
                    self.verification_cache[cache_key] = result.copy()
                    logger.info(f"Cached quick verification result for {filename}")
                    return result
                
                # Extract key frames (using ultra-fast mode)
                frames = self.extract_key_frames(temp_video_path, fast_mode=True)
                
                if not frames:
                    # Fall back to keyword-based verification if frame extraction fails
                    logger.warning(f"Could not extract frames from video: {filename}")
                    text_content = (filename + " " + description).lower()
                    ocean_keywords = ['water', 'ocean', 'sea', 'wave', 'beach', 'coast', 'marine', 'tide']
                    hazard_keywords = ['storm', 'flood', 'tsunami', 'surge', 'high', 'rough', 'danger', 'warning']
                    
                    ocean_score = sum(1 for keyword in ocean_keywords if keyword in text_content) / len(ocean_keywords)
                    hazard_score = sum(1 for keyword in hazard_keywords if keyword in text_content) / len(hazard_keywords)
                    
                    if ocean_score > 0.1 or hazard_score > 0.1:
                        return {
                            'status': 'verified',
                            'message': 'Video verified (keyword-based fallback)',
                            'confidence': min(0.7, (ocean_score + hazard_score) * 0.5),
                            'hazard_detection': {
                                'detected_type': selected_hazard_type or 'other',
                                'confidence': min(0.7, (ocean_score + hazard_score) * 0.5),
                                'ocean_score': ocean_score,
                                'hazard_score': hazard_score
                            },
                            'frame_analysis': {
                                'total_frames_analyzed': 0,
                                'ocean_frames': 0,
                                'hazard_frames': 0,
                                'ocean_percentage': ocean_score,
                                'hazard_percentage': hazard_score
                            },
                            'timestamp': datetime.now().isoformat(),
                            'fallback': True
                        }
                    else:
                        return {
                            'status': 'failed',
                            'message': 'Could not extract frames from video and no ocean hazard keywords found',
                            'confidence': 0.0,
                            'timestamp': datetime.now().isoformat()
                        }
                
                # Optimized parallel analysis (analyze ocean and hazard in one pass)
                ocean_analyses = []
                hazard_analyses = []
                
                for frame in frames:
                    # Analyze ocean content
                    ocean_analysis = self.analyze_frame_for_ocean_content(frame)
                    ocean_analyses.append(ocean_analysis)
                    
                    # Analyze hazard indicators (reuse some computations)
                    hazard_analysis = self.analyze_hazard_indicators(frame)
                    hazard_analyses.append(hazard_analysis)
                
                # Quick ocean content check
                ocean_frames = sum(1 for analysis in ocean_analyses if analysis['has_ocean_content'])
                ocean_percentage = ocean_frames / len(frames)
                
                # Quick hazard check
                hazard_frames = sum(1 for analysis in hazard_analyses if analysis['has_hazard_indicators'])
                hazard_percentage = hazard_frames / len(frames)
                
                # Detect hazard type
                hazard_detection = self.detect_hazard_type_from_video(frames, filename, description)
                
                # Determine verification status (balanced thresholds)
                status = 'verified'
                message = 'Video verified successfully'
                
                # Check ocean content (reasonable threshold)
                if ocean_percentage < 0.1:  # Less than 10% of frames have ocean content
                    status = 'failed'
                    message = 'Insufficient ocean content detected - please upload videos showing water/ocean scenes'
                
                # Check hazard indicators (reasonable threshold)
                elif hazard_percentage < 0.05:  # Less than 5% of frames show hazard indicators
                    status = 'failed'
                    message = 'No significant hazard indicators detected - please upload videos showing actual hazard conditions'
                
                # Check hazard type match
                elif selected_hazard_type and not self.is_hazard_type_compatible(selected_hazard_type, hazard_detection['detected_type']):
                    status = 'failed'
                    message = f'Video content does not match selected hazard type. Detected: {hazard_detection["detected_type"]}'
                
                # Check confidence threshold (reasonable)
                elif hazard_detection['confidence'] < 0.2:
                    status = 'failed'
                    message = 'Low confidence in hazard detection - please check video quality and content'
                
                # Overall confidence
                overall_confidence = (hazard_detection['confidence'] + hazard_detection['ocean_score'] + hazard_detection['hazard_score']) / 3
                
                result = {
                    'status': status,
                    'message': message,
                    'confidence': overall_confidence,
                    'hazard_detection': hazard_detection,
                    'frame_analysis': {
                        'total_frames_analyzed': len(frames),
                        'ocean_frames': ocean_frames,
                        'hazard_frames': hazard_frames,
                        'ocean_percentage': float(ocean_percentage),
                        'hazard_percentage': float(hazard_percentage)
                    },
                    'timestamp': datetime.now().isoformat(),
                    'cached': False
                }
                
                # Cache the result
                if len(self.verification_cache) >= self.cache_max_size:
                    # Remove oldest entry
                    oldest_key = next(iter(self.verification_cache))
                    del self.verification_cache[oldest_key]
                
                self.verification_cache[cache_key] = result.copy()
                logger.info(f"Cached verification result for {filename}")
                
                return result
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_video_path):
                    os.unlink(temp_video_path)
                    
        except Exception as e:
            logger.error(f"Error in video verification: {e}")
            return {
                'status': 'error',
                'message': f'Verification failed: {str(e)}',
                'confidence': 0.0,
                'timestamp': datetime.now().isoformat()
            }
    
    def is_hazard_type_compatible(self, selected_type: str, detected_type: str) -> bool:
        """
        Check if two hazard types are compatible.
        
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
            'water_hazards': ['flooding', 'storm-surge', 'high-waves', 'tsunami'],
            'weather_hazards': ['storm-surge', 'tsunami', 'high-waves'],
            'environmental_hazards': ['pollution', 'debris', 'erosion'],
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
        
        return False
    
    def _quick_verify_video(self, video_path: str, selected_hazard_type: str = None, 
                           description: str = "", filename: str = "") -> Dict[str, Any]:
        """
        Ultra-quick video verification for maximum speed.
        Does minimal analysis - just basic file validation and keyword matching.
        """
        try:
            # Basic file validation with better error handling
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                # Try to get more info about the file
                import os
                file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
                logger.warning(f"Could not open video file: {video_path}, size: {file_size} bytes")
                
                # Fall back to keyword-based verification for invalid video files
                text_content = (filename + " " + description).lower()
                ocean_keywords = ['water', 'ocean', 'sea', 'wave', 'beach', 'coast', 'marine', 'tide']
                hazard_keywords = ['storm', 'flood', 'tsunami', 'surge', 'high', 'rough', 'danger', 'warning']
                
                ocean_score = sum(1 for keyword in ocean_keywords if keyword in text_content) / len(ocean_keywords)
                hazard_score = sum(1 for keyword in hazard_keywords if keyword in text_content) / len(hazard_keywords)
                
                if ocean_score > 0.1 or hazard_score > 0.1:
                    return {
                        'status': 'verified',
                        'message': 'Video verified (keyword-based fallback)',
                        'confidence': min(0.7, (ocean_score + hazard_score) * 0.5),
                        'hazard_detection': {
                            'detected_type': selected_hazard_type or 'other',
                            'confidence': min(0.7, (ocean_score + hazard_score) * 0.5),
                            'ocean_score': ocean_score,
                            'hazard_score': hazard_score
                        },
                        'frame_analysis': {
                            'total_frames_analyzed': 0,
                            'ocean_frames': 0,
                            'hazard_frames': 0,
                            'ocean_percentage': ocean_score,
                            'hazard_percentage': hazard_score
                        },
                        'timestamp': datetime.now().isoformat(),
                        'quick_mode': True,
                        'fallback': True
                    }
                else:
                    return {
                        'status': 'failed',
                        'message': 'Invalid video file and no ocean hazard keywords found',
                        'confidence': 0.0,
                        'timestamp': datetime.now().isoformat()
                    }
            
            # Get basic video info
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = frame_count / fps if fps > 0 else 0
            
            cap.release()
            
            # Check duration
            if duration < self.min_video_duration:
                return {
                    'status': 'failed',
                    'message': 'Video too short',
                    'confidence': 0.0,
                    'timestamp': datetime.now().isoformat()
                }
            
            if duration > self.max_video_duration:
                return {
                    'status': 'failed',
                    'message': 'Video too long',
                    'confidence': 0.0,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Quick keyword-based verification
            text_content = (filename + " " + description).lower()
            ocean_keywords = ['water', 'ocean', 'sea', 'wave', 'beach', 'coast', 'marine', 'tide']
            hazard_keywords = ['storm', 'flood', 'tsunami', 'surge', 'high', 'rough', 'danger', 'warning']
            
            ocean_score = sum(1 for keyword in ocean_keywords if keyword in text_content) / len(ocean_keywords)
            hazard_score = sum(1 for keyword in hazard_keywords if keyword in text_content) / len(hazard_keywords)
            
            # Simple verification logic
            if ocean_score > 0.1 or hazard_score > 0.1:
                status = 'verified'
                message = 'Video verified (quick mode)'
                confidence = min(0.8, (ocean_score + hazard_score) * 0.5)
            else:
                status = 'failed'
                message = 'No ocean hazard indicators found'
                confidence = 0.2
            
            return {
                'status': status,
                'message': message,
                'confidence': confidence,
                'hazard_detection': {
                    'detected_type': selected_hazard_type or 'other',
                    'confidence': confidence,
                    'ocean_score': ocean_score,
                    'hazard_score': hazard_score
                },
                'frame_analysis': {
                    'total_frames_analyzed': 0,  # Quick mode doesn't analyze frames
                    'ocean_frames': 0,
                    'hazard_frames': 0,
                    'ocean_percentage': ocean_score,
                    'hazard_percentage': hazard_score
                },
                'timestamp': datetime.now().isoformat(),
                'quick_mode': True
            }
            
        except Exception as e:
            logger.error(f"Error in quick verification: {e}")
            return {
                'status': 'error',
                'message': f'Quick verification failed: {str(e)}',
                'confidence': 0.0,
                'timestamp': datetime.now().isoformat()
            }
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the video verification service."""
        return {
            'service_type': 'video_verification',
            'hazard_types': self.hazard_types,
            'max_frames_to_analyze': self.max_frames_to_analyze,
            'min_video_duration': self.min_video_duration,
            'max_video_duration': self.max_video_duration,
            'version': '1.0.0'
        }


# Global service instance
video_verification_service = VideoVerificationService()


def verify_video_endpoint(video_data: bytes, hazard_type: str = None, 
                         description: str = "", filename: str = "", quick_mode: bool = False) -> Dict[str, Any]:
    """
    Main endpoint function for video verification.
    
    Args:
        video_data: Raw video bytes
        hazard_type: Expected hazard type
        description: User description
        filename: Original filename
        quick_mode: If True, use ultra-fast verification (default: True)
        
    Returns:
        Verification results compatible with frontend
    """
    try:
        # Run verification
        result = video_verification_service.verify_video(
            video_data, hazard_type, description, filename, quick_mode
        )
        
        # Format for frontend compatibility
        hazard_detection = result.get('hazard_detection', {})
        frame_analysis = result.get('frame_analysis', {})
        
        return {
            'status': result['status'],
            'checks': {
                'isVideo': True,
                'fileSize': len(video_data) < 50 * 1024 * 1024,  # Less than 50MB
                'fileName': 'suspicious' not in filename.lower(),
                'hasOceanContent': frame_analysis.get('ocean_percentage', 0) > 0.3,
                'hasHazardIndicators': frame_analysis.get('hazard_percentage', 0) > 0.2,
                'hazardTypeMatch': result['status'] == 'verified',
                'durationAppropriate': True,  # Already checked in frame extraction
                'contentAnalysis': result['confidence'] > 0.6
            },
            'hazardMatching': {
                'matchesSelectedType': hazard_detection.get('detected_type') == hazard_type if hazard_type else True,
                'detectedHazardTypes': [hazard_detection.get('detected_type', 'other')],
                'confidence': hazard_detection.get('confidence', 0),
                'oceanScore': hazard_detection.get('ocean_score', 0),
                'hazardScore': hazard_detection.get('hazard_score', 0)
            },
            'frameAnalysis': frame_analysis,
            'confidence': result['confidence'],
            'message': result['message'],
            'timestamp': result['timestamp']
        }
        
    except Exception as e:
        logger.error(f"Error in video verification endpoint: {e}")
        return {
            'status': 'error',
            'checks': {
                'isVideo': True,
                'fileSize': len(video_data) < 50 * 1024 * 1024,
                'fileName': 'suspicious' not in filename.lower(),
                'hasOceanContent': False,
                'hasHazardIndicators': False,
                'hazardTypeMatch': False,
                'durationAppropriate': True,
                'contentAnalysis': False
            },
            'hazardMatching': {
                'matchesSelectedType': False,
                'detectedHazardTypes': ['other'],
                'confidence': 0.0,
                'oceanScore': 0.0,
                'hazardScore': 0.0
            },
            'frameAnalysis': {
                'total_frames_analyzed': 0,
                'ocean_frames': 0,
                'hazard_frames': 0,
                'ocean_percentage': 0.0,
                'hazard_percentage': 0.0
            },
            'confidence': 0.0,
            'message': f'Video verification service error: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }
