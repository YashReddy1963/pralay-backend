"""
Views for handling ocean hazard report submissions and management.
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import base64
import uuid

from users.models import OceanHazardReport, HazardImage, CustomUser
from users.email_service import EmailService
from users.authentication import TokenRequiredMixin

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class SubmitHazardReportView(TokenRequiredMixin, View):
    """API endpoint for submitting ocean hazard reports. Requires Bearer token."""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            hazard_type = data.get('hazard_type')
            description = data.get('description')
            location_data = data.get('location', {})
            images_data = data.get('images', [])
            verification_results = data.get('verification_results', [])
            
            if not all([hazard_type, description, location_data]):
                return JsonResponse({
                    'success': False,
                    'message': 'Missing required fields: hazard_type, description, location'
                }, status=400)
            
            user = request.user
            logger.info(f"SubmitHazardReportView: User {user.id} ({user.email}) submitting report")
            
            # Extract location information
            latitude = Decimal(str(location_data.get('latitude', 0)))
            longitude = Decimal(str(location_data.get('longitude', 0)))
            country = location_data.get('country', 'Unknown')
            state = location_data.get('state', 'Unknown')
            district = location_data.get('district', 'Unknown')
            city = location_data.get('city', 'Unknown')
            address = location_data.get('address', '')
            
            # Debug logging
            logger.info(f"Received hazard report data:")
            logger.info(f"  - Hazard type: {hazard_type}")
            logger.info(f"  - Description: {description[:100]}...")
            logger.info(f"  - Location: {city}, {district}, {state}, {country}")
            logger.info(f"  - Coordinates: {latitude}, {longitude}")
            logger.info(f"  - Images count: {len(images_data)}")
            logger.info(f"  - Verification results: {len(verification_results)}")
            
            # Create the hazard report
            hazard_report = OceanHazardReport.objects.create(
                reported_by=user,
                hazard_type=hazard_type,
                description=description,
                latitude=latitude,
                longitude=longitude,
                country=country,
                state=state,
                district=district,
                city=city,
                address=address,
                status='pending',
                is_verified=False,
                emergency_level='medium'
            )
            
            # Debug logging after creation
            logger.info(f"Created hazard report {hazard_report.report_id}:")
            logger.info(f"  - Saved location: {hazard_report.city}, {hazard_report.district}, {hazard_report.state}, {hazard_report.country}")
            logger.info(f"  - Saved coordinates: {hazard_report.latitude}, {hazard_report.longitude}")
            
            # Process images if provided
            saved_images = []
            for i, image_data in enumerate(images_data):
                try:
                    # Extract image data (assuming base64 encoded)
                    if 'data:' in image_data and 'base64,' in image_data:
                        # Handle data URL format
                        header, encoded_data = image_data.split(',', 1)
                        image_content = base64.b64decode(encoded_data)
                        
                        # Generate unique filename
                        file_extension = 'jpg'  # Default to jpg
                        if 'image/png' in header:
                            file_extension = 'png'
                        elif 'image/jpeg' in header:
                            file_extension = 'jpg'
                        elif 'image/webp' in header:
                            file_extension = 'webp'
                        
                        filename = f"hazard_{hazard_report.report_id}_{i+1}_{uuid.uuid4().hex[:8]}.{file_extension}"
                        
                        # Save image file
                        image_file = ContentFile(image_content, name=filename)
                        
                        # Get corresponding verification result
                        verification_result = verification_results[i] if i < len(verification_results) else {}
                        
                        # Create hazard image record with location data
                        hazard_image = HazardImage.objects.create(
                            hazard_report=hazard_report,
                            image_file=image_file,
                            image_type='evidence',
                            image_latitude=latitude,  # Add latitude from the main location
                            image_longitude=longitude,  # Add longitude from the main location
                            ai_verification_result=verification_result,
                            ai_confidence_score=verification_result.get('confidence', 0.0),
                            is_verified_by_ai=verification_result.get('status') == 'verified'
                        )
                        
                        # Debug logging for image creation
                        logger.info(f"Created hazard image {hazard_image.id}:")
                        logger.info(f"  - Image coordinates: {hazard_image.image_latitude}, {hazard_image.image_longitude}")
                        logger.info(f"  - AI verification: {hazard_image.is_verified_by_ai} (confidence: {hazard_image.ai_confidence_score})")
                        
                        saved_images.append({
                            'id': hazard_image.id,
                            'filename': filename,
                            'verified': hazard_image.is_verified_by_ai,
                            'confidence': hazard_image.ai_confidence_score
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing image {i}: {e}")
                    continue
            
            # Update report with AI verification summary
            if verification_results:
                # Calculate overall verification score
                verified_images = sum(1 for result in verification_results if result.get('status') == 'verified')
                total_images = len(verification_results)
                overall_confidence = sum(result.get('confidence', 0) for result in verification_results) / total_images if total_images > 0 else 0
                
                hazard_report.ai_verification_score = overall_confidence
                hazard_report.ai_verification_details = {
                    'verified_images': verified_images,
                    'total_images': total_images,
                    'overall_confidence': overall_confidence,
                    'individual_results': verification_results
                }
                
                # Auto-verify if all images are verified and confidence is high
                if verified_images == total_images and overall_confidence > 0.8:
                    hazard_report.is_verified = True
                    hazard_report.status = 'verified'
                
                hazard_report.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Hazard report submitted successfully',
                'report_id': hazard_report.report_id,
                'report_url': f'/admin/users/oceanhazardreport/{hazard_report.id}/',
                'images_saved': len(saved_images),
                'verification_status': hazard_report.get_verification_status_display(),
                'data': {
                    'report_id': hazard_report.report_id,
                    'hazard_type': hazard_report.get_hazard_type_display(),
                    'location': hazard_report.get_full_location(),
                    'reported_at': hazard_report.reported_at.isoformat(),
                    'status': hazard_report.status,
                    'is_verified': hazard_report.is_verified,
                    'ai_confidence': hazard_report.ai_verification_score
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error submitting hazard report: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error submitting report: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class GetHazardReportsView(TokenRequiredMixin, View):
    """API endpoint for retrieving hazard reports. Requires Bearer token."""
    
    def get(self, request):
        try:
            status = request.GET.get('status')
            hazard_type = request.GET.get('hazard_type')
            state = request.GET.get('state')
            district = request.GET.get('district')
            user_reports = request.GET.get('user_reports', '').lower() == 'true'
            limit = int(request.GET.get('limit', 50))
            
            reports_query = OceanHazardReport.objects.select_related('reported_by', 'reviewed_by').prefetch_related('hazard_images')
            
            if user_reports:
                reports_query = reports_query.filter(reported_by=request.user)
            
            if status:
                reports_query = reports_query.filter(status=status)
            if hazard_type:
                reports_query = reports_query.filter(hazard_type=hazard_type)
            if state:
                reports_query = reports_query.filter(state__icontains=state)
            if district:
                reports_query = reports_query.filter(district__icontains=district)
            
            reports = reports_query.order_by('-reported_at')[:limit]
            
            reports_data = []
            for report in reports:
                reports_data.append({
                    'id': report.id,
                    'report_id': report.report_id,
                    'hazard_type': report.hazard_type,
                    'hazard_type_display': report.get_hazard_type_display(),
                    'description': report.description,
                    'location': {
                        'latitude': float(report.latitude),
                        'longitude': float(report.longitude),
                        'country': report.country,
                        'state': report.state,
                        'district': report.district,
                        'city': report.city,
                        'address': report.address,
                        'full_location': report.get_full_location()
                    },
                    'status': report.status,
                    'status_display': report.get_verification_status_display(),
                    'is_verified': report.is_verified,
                    'emergency_level': report.emergency_level,
                    'reported_by': {
                        'name': report.reported_by.get_full_name(),
                        'email': report.reported_by.email
                    },
                    'reviewed_by': {
                        'name': report.reviewed_by.get_full_name(),
                        'email': report.reviewed_by.email
                    } if report.reviewed_by else None,
                    'reported_at': report.reported_at.isoformat(),
                    'reviewed_at': report.reviewed_at.isoformat() if report.reviewed_at else None,
                    'ai_verification_score': report.ai_verification_score,
                    'images_count': report.hazard_images.count(),
                    'images': [
                        {
                            'id': img.id,
                            'image_type': img.image_type,
                            'caption': img.caption,
                            'is_verified_by_ai': img.is_verified_by_ai,
                            'ai_confidence_score': img.ai_confidence_score,
                            'uploaded_at': img.uploaded_at.isoformat()
                        }
                        for img in report.hazard_images.all()
                    ]
                })
            
            return JsonResponse({
                'success': True,
                'count': len(reports_data),
                'reports': reports_data
            })
            
        except Exception as e:
            logger.error(f"Error retrieving hazard reports: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error retrieving reports: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class UpdateHazardReportStatusView(TokenRequiredMixin, View):
    """API endpoint for updating hazard report status (for officials). Requires Bearer token."""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            report_id = data.get('report_id')
            new_status = data.get('status')
            review_notes = data.get('review_notes', '')
            emergency_level = data.get('emergency_level', 'medium')
            
            if not all([report_id, new_status]):
                return JsonResponse({
                    'success': False,
                    'message': 'Missing required fields: report_id, status'
                }, status=400)
            
            try:
                report = OceanHazardReport.objects.get(report_id=report_id)
            except OceanHazardReport.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Report not found'
                }, status=404)
            
            # Update report status
            report.status = new_status
            report.review_notes = review_notes
            report.emergency_level = emergency_level
            report.reviewed_at = datetime.now()
            
            # Set verification status based on new status
            if new_status == 'verified':
                report.is_verified = True
            elif new_status == 'discarded':
                report.is_verified = False
            
            report.reviewed_by = request.user
            
            report.save()
            
            # Send email notification if report is verified
            if new_status == 'verified' and report.reported_by:
                try:
                    # Prepare report data for email
                    report_data = {
                        'report_id': report.report_id,
                        'hazard_type_display': report.get_hazard_type_display(),
                        'description': report.description,
                        'location': {
                            'full_location': report.get_full_location()
                        },
                        'emergency_level': report.emergency_level,
                        'reported_at': report.reported_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'reviewed_at': report.reviewed_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'reviewed_by': {
                            'name': report.reviewed_by.get_full_name() if report.reviewed_by else 'District Authority'
                        }
                    }
                    
                    # Send verification email to the citizen
                    citizen_name = report.reported_by.get_full_name()
                    citizen_email = report.reported_by.email
                    
                    email_sent = EmailService.send_hazard_verification_email(
                        report_data=report_data,
                        citizen_email=citizen_email,
                        citizen_name=citizen_name
                    )
                    
                    if email_sent:
                        logger.info(f"Verification email sent to {citizen_email} for report {report.report_id}")
                    else:
                        logger.warning(f"Failed to send verification email to {citizen_email} for report {report.report_id}")
                        
                except Exception as e:
                    logger.error(f"Error sending verification email for report {report.report_id}: {e}")
            
            return JsonResponse({
                'success': True,
                'message': f'Report status updated to {new_status}',
                'report_id': report.report_id,
                'new_status': report.status,
                'is_verified': report.is_verified,
                'reviewed_at': report.reviewed_at.isoformat()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error updating hazard report status: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error updating report: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class BulkUpdateHazardReportsView(TokenRequiredMixin, View):
    """API endpoint for bulk updating multiple hazard reports. Requires Bearer token."""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            report_ids = data.get('report_ids', [])
            new_status = data.get('status')
            review_notes = data.get('review_notes', '')
            
            if not report_ids or not new_status:
                return JsonResponse({
                    'success': False,
                    'message': 'Missing required fields: report_ids, status'
                }, status=400)
            
            # Update all reports with the given IDs
            updated_count = 0
            for report_id in report_ids:
                try:
                    report = OceanHazardReport.objects.get(report_id=report_id)
                    report.status = new_status
                    report.review_notes = review_notes
                    report.reviewed_at = datetime.now()
                    
                    # Set verification status based on new status
                    if new_status == 'verified':
                        report.is_verified = True
                    elif new_status == 'discarded':
                        report.is_verified = False
                    
                    report.reviewed_by = request.user
                    report.save()
                    updated_count += 1
                    
                    # Send email notification if report is verified
                    if new_status == 'verified' and report.reported_by:
                        try:
                            # Prepare report data for email
                            report_data = {
                                'report_id': report.report_id,
                                'hazard_type_display': report.get_hazard_type_display(),
                                'description': report.description,
                                'location': {
                                    'full_location': report.get_full_location()
                                },
                                'emergency_level': report.emergency_level,
                                'reported_at': report.reported_at.strftime('%Y-%m-%d %H:%M:%S'),
                                'reviewed_at': report.reviewed_at.strftime('%Y-%m-%d %H:%M:%S'),
                                'reviewed_by': {
                                    'name': report.reviewed_by.get_full_name() if report.reviewed_by else 'District Authority'
                                }
                            }
                            
                            # Send verification email to the citizen
                            citizen_name = report.reported_by.get_full_name()
                            citizen_email = report.reported_by.email
                            
                            email_sent = EmailService.send_hazard_verification_email(
                                report_data=report_data,
                                citizen_email=citizen_email,
                                citizen_name=citizen_name
                            )
                            
                            if email_sent:
                                logger.info(f"Bulk verification email sent to {citizen_email} for report {report.report_id}")
                            else:
                                logger.warning(f"Failed to send bulk verification email to {citizen_email} for report {report.report_id}")
                                
                        except Exception as e:
                            logger.error(f"Error sending bulk verification email for report {report.report_id}: {e}")
                    
                except OceanHazardReport.DoesNotExist:
                    logger.warning(f"Report {report_id} not found during bulk update")
                    continue
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully updated {updated_count} reports',
                'updated_count': updated_count,
                'total_requested': len(report_ids)
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in bulk update: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error updating reports: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class BulkDeleteHazardReportsView(TokenRequiredMixin, View):
    """API endpoint for bulk deleting multiple hazard reports. Requires Bearer token."""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            report_ids = data.get('report_ids', [])
            
            if not report_ids:
                return JsonResponse({
                    'success': False,
                    'message': 'Missing required field: report_ids'
                }, status=400)
            
            # Delete all reports with the given IDs
            deleted_count = 0
            for report_id in report_ids:
                try:
                    report = OceanHazardReport.objects.get(report_id=report_id)
                    report.delete()
                    deleted_count += 1
                except OceanHazardReport.DoesNotExist:
                    logger.warning(f"Report {report_id} not found during bulk delete")
                    continue
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully deleted {deleted_count} reports',
                'deleted_count': deleted_count,
                'total_requested': len(report_ids)
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in bulk delete: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error deleting reports: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class DeleteHazardReportView(TokenRequiredMixin, View):
    """API endpoint for deleting a single hazard report. Requires Bearer token."""
    
    def delete(self, request, report_id):
        try:
            try:
                report = OceanHazardReport.objects.get(report_id=report_id)
                report.delete()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Report {report_id} deleted successfully'
                })
            except OceanHazardReport.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Report not found'
                }, status=404)
                
        except Exception as e:
            logger.error(f"Error deleting report {report_id}: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error deleting report: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TestUserReportsView(TokenRequiredMixin, View):
    """Test endpoint to debug user reports. Requires Bearer token."""
    
    def get(self, request):
        try:
            total_reports = OceanHazardReport.objects.filter(reported_by=request.user).count()
            sample_report = OceanHazardReport.objects.filter(reported_by=request.user).first()
            return JsonResponse({
                'success': True,
                'message': 'Test successful',
                'user_id': request.user.id,
                'user_email': request.user.email,
                'total_reports': total_reports,
                'sample_report_id': sample_report.report_id if sample_report else None,
                'sample_report_hazard_type': sample_report.hazard_type if sample_report else None,
                'auth_header': request.META.get('HTTP_AUTHORIZATION', 'None'),
            })
            
        except Exception as e:
            logger.error(f"Error in TestUserReportsView: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}',
                'user_id': None,
                'user_email': None,
                'total_reports': 0
            })

@method_decorator(csrf_exempt, name='dispatch')
class DebugReportsView(TokenRequiredMixin, View):
    """Debug endpoint to check all reports and users. Requires Bearer token."""
    
    def get(self, request):
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            all_reports = OceanHazardReport.objects.select_related('reported_by').all()[:10]
            reports_data = [
                {
                    'report_id': r.report_id,
                    'hazard_type': r.hazard_type,
                    'reported_by_id': r.reported_by.id if r.reported_by else None,
                    'reported_by_email': r.reported_by.email if r.reported_by else None,
                    'reported_by_name': r.reported_by.get_full_name() if r.reported_by else None,
                    'reported_at': r.reported_at.isoformat(),
                }
                for r in all_reports
            ]
            all_users = User.objects.all()[:10]
            users_data = [
                {'user_id': u.id, 'user_email': u.email, 'user_name': u.get_full_name(), 'user_role': u.role}
                for u in all_users
            ]
            return JsonResponse({
                'success': True,
                'total_reports': OceanHazardReport.objects.count(),
                'total_users': User.objects.count(),
                'reports': reports_data,
                'users': users_data,
                'current_user_id': request.user.id,
                'current_user_email': request.user.email,
            })
            
        except Exception as e:
            logger.error(f"Error in DebugReportsView: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })

@method_decorator(csrf_exempt, name='dispatch')
class TestHazardReportsEndpointView(TokenRequiredMixin, View):
    """Test endpoint to verify the hazard reports endpoint. Requires Bearer token."""
    
    def get(self, request):
        try:
            user_reports = request.GET.get('user_reports', '').lower() == 'true'
            if user_reports:
                user_report_count = OceanHazardReport.objects.filter(reported_by=request.user).count()
                return JsonResponse({
                    'success': True,
                    'message': 'User reports endpoint is working',
                    'user_id': request.user.id,
                    'user_email': request.user.email,
                    'user_report_count': user_report_count,
                    'endpoint': '/api/hazard-reports/?user_reports=true'
                })
            total_reports = OceanHazardReport.objects.count()
            return JsonResponse({
                'success': True,
                'message': 'General hazard reports endpoint is working',
                'total_reports': total_reports,
                'endpoint': '/api/hazard-reports/'
            })
                
        except Exception as e:
            logger.error(f"Error in TestHazardReportsEndpointView: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })

@method_decorator(csrf_exempt, name='dispatch')
class TestEmailNotificationView(TokenRequiredMixin, View):
    """Test endpoint to verify email notification. Requires Bearer token."""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            test_email = data.get('email')
            
            if not test_email:
                return JsonResponse({
                    'success': False,
                    'message': 'Email address required for testing'
                }, status=400)
            
            # Create sample report data for testing
            test_report_data = {
                'report_id': 'TEST-12345',
                'hazard_type_display': 'Tsunami Warning',
                'description': 'This is a test hazard report for email notification verification.',
                'location': {
                    'full_location': 'Test Beach, Mumbai, Maharashtra'
                },
                'emergency_level': 'high',
                'reported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'reviewed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'reviewed_by': {
                    'name': 'Test District Chairman'
                }
            }
            
            # Send test email
            email_sent = EmailService.send_hazard_verification_email(
                report_data=test_report_data,
                citizen_email=test_email,
                citizen_name='Test User'
            )
            
            if email_sent:
                return JsonResponse({
                    'success': True,
                    'message': f'Test email sent successfully to {test_email}',
                    'report_data': test_report_data
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Failed to send test email to {test_email}'
                }, status=500)
                
        except Exception as e:
            logger.error(f"Error in test email endpoint: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error testing email: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class GetMapHazardReportsView(TokenRequiredMixin, View):
    """API endpoint for retrieving hazard reports for map. Requires Bearer token."""
    
    def get(self, request):
        try:
            status = request.GET.get('status')
            hazard_type = request.GET.get('hazard_type')
            limit = int(request.GET.get('limit', 100))
            reports_query = OceanHazardReport.objects.select_related('reported_by', 'reviewed_by').prefetch_related('hazard_images')
            
            if request.user.role == 'district_chairman':
                if request.user.district:
                    reports_query = reports_query.filter(district__icontains=request.user.district)
                    logger.info(f"Filtering reports for district chairman: {request.user.district}")
                else:
                    logger.warning(f"District chairman {request.user.email} has no district set")
            
            # Apply other filters
            if status:
                reports_query = reports_query.filter(status=status)
            if hazard_type:
                reports_query = reports_query.filter(hazard_type=hazard_type)
            
            # Get reports with location data
            reports = reports_query.filter(
                latitude__isnull=False,
                longitude__isnull=False
            ).order_by('-reported_at')[:limit]
            
            reports_data = []
            for report in reports:
                # Get hazard images count
                images_count = report.hazard_images.count()
                
                # Get image URLs
                images_data = []
                for img in report.hazard_images.all():
                    images_data.append({
                        'id': img.id,
                        'url': request.build_absolute_uri(img.image_file.url) if img.image_file else None,
                        'type': img.image_type,
                        'caption': img.caption,
                        'is_verified_by_ai': img.is_verified_by_ai,
                        'ai_confidence_score': img.ai_confidence_score,
                    })
                
                reports_data.append({
                            'id': report.id,
                            'report_id': report.report_id,
                            'hazard_type': report.hazard_type,
                            'hazard_type_display': report.get_hazard_type_display(),
                            'description': report.description,
                            'coordinates': [float(report.latitude), float(report.longitude)],
                            'location': {
                                'latitude': float(report.latitude),
                                'longitude': float(report.longitude),
                                'country': report.country,
                                'state': report.state,
                                'district': report.district,
                                'city': report.city,
                                'address': report.address,
                            },
                            'status': report.status,
                            'status_display': report.get_status_display(),
                            'is_verified': report.is_verified,
                            'reported_at': report.reported_at.isoformat(),
                            'reported_by': {
                                'id': report.reported_by.id,
                                'email': report.reported_by.email,
                                'first_name': report.reported_by.first_name,
                                'last_name': report.reported_by.last_name,
                            },
                            'images_count': images_count,
                            'has_images': images_count > 0,
                            'images': images_data,
                            'reviewed_by': {
                                'id': report.reviewed_by.id,
                                'email': report.reviewed_by.email,
                                'first_name': report.reviewed_by.first_name,
                                'last_name': report.reviewed_by.last_name,
                            } if report.reviewed_by else None,
                            'review_notes': report.review_notes,
                        })
            
            return JsonResponse({
                'success': True,
                'reports': reports_data,
                'total_count': len(reports_data),
                'user_role': request.user.role,
                'user_district': request.user.district or None,
                'filters_applied': {
                    'status': status,
                    'hazard_type': hazard_type,
                    'district_filtered': request.user.role == 'district_chairman'
                }
            })
            
        except Exception as e:
            logger.error(f"Error in GetMapHazardReportsView: {e}")
            return JsonResponse({
                'success': False,
                'message': f'Error fetching map reports: {str(e)}',
                'reports': []
            }, status=500)
