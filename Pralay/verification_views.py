"""
Django views for AI image verification API endpoints
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import json
import logging
from datetime import datetime
from .ai_verification_service import verify_image_endpoint
# from .video_verification_service import verify_video_endpoint

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def verify_image_api(request):
    """
    API endpoint for image verification.
    
    Expected request format:
    - Content-Type: multipart/form-data
    - Fields:
      - image: Image file
      - hazard_type: Selected hazard type (optional)
      - description: User description (optional)
    """
    try:
        # Check if image file is present
        if 'image' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'No image file provided'
            }, status=400)
        
        image_file = request.FILES['image']
        
        # Validate file type
        if not image_file.content_type.startswith('image/'):
            return JsonResponse({
                'status': 'error',
                'message': 'File must be an image'
            }, status=400)
        
        # Validate file size (max 10MB)
        if image_file.size > 10 * 1024 * 1024:
            return JsonResponse({
                'status': 'error',
                'message': 'Image file too large (max 10MB)'
            }, status=400)
        
        # Get additional parameters
        hazard_type = request.POST.get('hazard_type', '')
        description = request.POST.get('description', '')
        
        # Read image data
        image_data = image_file.read()
        
        # Run verification
        result = verify_image_endpoint(
            image_data=image_data,
            hazard_type=hazard_type if hazard_type else None,
            description=description,
            filename=image_file.name
        )
        
        # Return result
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Error in verify_image_api: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error during verification',
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def verification_service_info(request):
    """
    API endpoint to get verification service information.
    """
    try:
        from .ai_verification_service import verification_service
        
        info = verification_service.get_service_info()
        return JsonResponse(info)
        
    except Exception as e:
        logger.error(f"Error in verification_service_info: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to get service info',
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def batch_verify_images(request):
    """
    API endpoint for batch image verification.
    
    Expected request format:
    - Content-Type: multipart/form-data
    - Fields:
      - images: Multiple image files
      - hazard_types: JSON array of hazard types (optional)
      - descriptions: JSON array of descriptions (optional)
    """
    try:
        # Check if images are present
        if 'images' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'No image files provided'
            }, status=400)
        
        image_files = request.FILES.getlist('images')
        
        # Validate number of images (max 5)
        if len(image_files) > 5:
            return JsonResponse({
                'status': 'error',
                'message': 'Too many images (max 5 allowed)'
            }, status=400)
        
        # Get additional parameters
        hazard_types_str = request.POST.get('hazard_types', '[]')
        descriptions_str = request.POST.get('descriptions', '[]')
        
        try:
            hazard_types = json.loads(hazard_types_str)
            descriptions = json.loads(descriptions_str)
        except json.JSONDecodeError:
            hazard_types = []
            descriptions = []
        
        # Process each image
        results = []
        for i, image_file in enumerate(image_files):
            # Validate file type
            if not image_file.content_type.startswith('image/'):
                results.append({
                    'filename': image_file.name,
                    'status': 'error',
                    'message': 'File must be an image'
                })
                continue
            
            # Validate file size
            if image_file.size > 10 * 1024 * 1024:
                results.append({
                    'filename': image_file.name,
                    'status': 'error',
                    'message': 'Image file too large (max 10MB)'
                })
                continue
            
            # Get parameters for this image
            hazard_type = hazard_types[i] if i < len(hazard_types) else None
            description = descriptions[i] if i < len(descriptions) else ''
            
            # Read image data
            image_data = image_file.read()
            
            # Run verification
            result = verify_image_endpoint(
                image_data=image_data,
                hazard_type=hazard_type,
                description=description,
                filename=image_file.name
            )
            
            # Add filename to result
            result['filename'] = image_file.name
            results.append(result)
        
        # Return batch results
        return JsonResponse({
            'status': 'success',
            'results': results,
            'total_images': len(image_files),
            'verified_count': sum(1 for r in results if r.get('status') == 'verified'),
            'failed_count': sum(1 for r in results if r.get('status') == 'failed'),
            'error_count': sum(1 for r in results if r.get('status') == 'error')
        })
        
    except Exception as e:
        logger.error(f"Error in batch_verify_images: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error during batch verification',
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def verify_video_api(request):
    """
    API endpoint for verifying ocean hazard videos.
    """
    try:
        # Get video file from request
        if 'video' not in request.FILES:
            return JsonResponse({
                'success': False,
                'message': 'No video file provided'
            }, status=400)
        
        video_file = request.FILES['video']
        filename = video_file.name
        
        # Validate file type (more lenient detection)
        is_video = (
            video_file.content_type.startswith('video/') or
            filename.lower().endswith(('.mp4', '.avi', '.mov', '.webm', '.mkv', '.flv', '.wmv')) or
            'video' in video_file.content_type.lower()
        )
        
        if not is_video:
            return JsonResponse({
                'success': False,
                'message': f'File must be a video. Received: {video_file.content_type} for {filename}'
            }, status=400)
        
        # Check file size (max 50MB)
        if video_file.size > 50 * 1024 * 1024:
            return JsonResponse({
                'success': False,
                'message': 'Video file too large (max 50MB)'
            }, status=400)
        
        # Get additional parameters
        hazard_type = request.POST.get('hazard_type', '')
        description = request.POST.get('description', '')
        
        logger.info(f"Verifying video: {filename}, hazard_type: {hazard_type}")
        
        # Read video data
        video_data = video_file.read()
        
        # Run video verification (using balanced mode for accuracy and speed)
        result = verify_video_endpoint(
            video_data=video_data,
            hazard_type=hazard_type,
            description=description,
            filename=filename,
            quick_mode=False  # Use balanced mode for better accuracy
        )
        
        logger.info(f"Video verification result: {result['status']}, confidence: {result['confidence']}")
        
        return JsonResponse({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error in video verification API: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=500)


