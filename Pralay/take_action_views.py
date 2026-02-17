import os
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from users.email_service import EmailService
from users.authentication import token_required
from django.template.loader import render_to_string
from django.utils import timezone
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
import uuid
import json

from users.models import SubAuthorityTeamMember, CustomUser, OceanHazardReport

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
@token_required
def take_action_endpoint(request):
    """
    API endpoint for Take Action feature
    Accepts report_id and audio_file, then sends voice calls and emails to team members
    """
    try:
        # Get the report ID
        report_id = request.POST.get('report_id')
        if not report_id:
            return JsonResponse({
                'success': False,
                'message': 'Report ID is required'
            }, status=400)
        
        # Get the hazard report
        try:
            hazard_report = OceanHazardReport.objects.get(report_id=report_id)
        except OceanHazardReport.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Hazard report not found'
            }, status=404)
        
        # Get the audio file
        audio_file = request.FILES.get('audio_file')
        if not audio_file:
            return JsonResponse({
                'success': False,
                'message': 'Audio file is required'
            }, status=400)
        
        # Validate audio file
        if not audio_file.content_type.startswith('audio/'):
            return JsonResponse({
                'success': False,
                'message': 'File must be an audio file'
            }, status=400)
        
        # Save the audio file
        file_extension = audio_file.name.split('.')[-1] if '.' in audio_file.name else 'wav'
        unique_filename = f"take_action_{report_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
        
        # Save to media directory
        file_path = default_storage.save(f"take_action_audio/{unique_filename}", ContentFile(audio_file.read()))
        audio_url = f"{settings.MEDIA_URL}{file_path}"
        
        # Get team members for the district chairman
        # Assuming the current user is the district chairman
        # Temporarily disabled for testing
        # if not request.user.is_authenticated:
        #     return JsonResponse({
        #         'success': False,
        #         'message': 'Authentication required'
        #     }, status=401)
        
        # Get team members under this district chairman (current user)
        team_members = SubAuthorityTeamMember.objects.filter(
            sub_authority=request.user,
            is_active=True
        )
        
        if not team_members.exists():
            return JsonResponse({
                'success': False,
                'message': 'No active team members found for this district chairman'
            }, status=404)
        
        # Initialize Twilio client
        try:
            twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        except Exception as e:
            logger.error(f"Failed to initialize Twilio client: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to initialize communication service'
            }, status=500)
        
        # Prepare results
        call_results = []
        email_results = []
        
        # Create a TwiML URL for playing the recorded audio
        # We'll create a simple TwiML response that plays the audio file
        base_url = request.build_absolute_uri('/').rstrip('/')
        audio_file_url = f"{base_url}{audio_url}"
        
        # Create TwiML XML for playing the audio
        twiml_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">This is an urgent message from the Pralay Hazard Management System.</Say>
    <Say voice="alice">A hazard has been reported in your district that requires immediate attention.</Say>
    <Say voice="alice">Report ID: {hazard_report.report_id}</Say>
    <Say voice="alice">Hazard Type: {hazard_report.get_hazard_type_display()}</Say>
    <Say voice="alice">Location: {hazard_report.city}, {hazard_report.district}</Say>
    <Say voice="alice">Please check your email for detailed information and take immediate action.</Say>
    <Say voice="alice">Thank you for your attention.</Say>
</Response>"""
        
        # For development, we'll use Twilio's built-in TwiML with dynamic content
        # Since localhost URLs don't work with Twilio, we'll use a simple approach
        # Create a TwiML that speaks the hazard details directly
        twiml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">This is an urgent message from the Pralay Hazard Management System.</Say>
    <Say voice="alice">A hazard has been reported in your district that requires immediate attention.</Say>
    <Say voice="alice">Report ID: {hazard_report.report_id}</Say>
    <Say voice="alice">Hazard Type: {hazard_report.get_hazard_type_display()}</Say>
    <Say voice="alice">Location: {hazard_report.city}, {hazard_report.district}</Say>
    <Say voice="alice">Please check your email for detailed information and take immediate action.</Say>
    <Say voice="alice">Thank you for your attention.</Say>
</Response>"""
        
        # For now, use a simple TwiML URL that works with Twilio
        # In production, you would host this TwiML on a publicly accessible server
        twiml_url = "http://demo.twilio.com/docs/voice.xml"
        
        # Process each team member
        for member in team_members:
            # Make Twilio call with inline TwiML
            try:
                call = twilio_client.calls.create(
                    to=member.phone_number,
                    from_=settings.TWILIO_PHONE_NUMBER,
                    twiml=twiml_content
                )
                call_results.append({
                    'member_id': member.id,
                    'member_name': member.get_full_name(),
                    'phone': member.phone_number,
                    'call_sid': call.sid,
                    'status': 'initiated'
                })
                logger.info(f"Call initiated for {member.get_full_name()} ({member.phone_number}): {call.sid}")
            except TwilioException as e:
                logger.error(f"Failed to call {member.get_full_name()} ({member.phone_number}): {e}")
                
                # If call fails due to trial account restrictions, try SMS instead
                try:
                    sms_message = f"""URGENT: Hazard Report Alert
Report ID: {hazard_report.report_id}
Type: {hazard_report.get_hazard_type_display()}
Location: {hazard_report.city}, {hazard_report.district}
Description: {hazard_report.description[:100]}...
Please check your email for full details and take immediate action."""
                    
                    sms = twilio_client.messages.create(
                        body=sms_message,
                        from_=settings.TWILIO_PHONE_NUMBER,
                        to=member.phone_number
                    )
                    
                    call_results.append({
                        'member_id': member.id,
                        'member_name': member.get_full_name(),
                        'phone': member.phone_number,
                        'sms_sid': sms.sid,
                        'status': 'sms_sent',
                        'fallback_reason': 'Call failed, SMS sent instead'
                    })
                    logger.info(f"SMS sent to {member.get_full_name()} ({member.phone_number}): {sms.sid}")
                    
                except TwilioException as sms_error:
                    logger.error(f"Failed to send SMS to {member.get_full_name()} ({member.phone_number}): {sms_error}")
                    call_results.append({
                        'member_id': member.id,
                        'member_name': member.get_full_name(),
                        'phone': member.phone_number,
                        'error': f"Call failed: {str(e)}, SMS failed: {str(sms_error)}",
                        'status': 'failed'
                    })
            
            # Send email
            try:
                email_subject = f"URGENT: Immediate Action Required for Hazard Report #{hazard_report.report_id}"
                
                email_body = f"""
URGENT ACTION REQUIRED

A hazard has been reported in your district that requires immediate attention.

REPORT DETAILS:
- Report ID: {hazard_report.report_id}
- Hazard Type: {hazard_report.get_hazard_type_display()}
- Location: {hazard_report.city}, {hazard_report.district}, {hazard_report.state}
- Description: {hazard_report.description}
- Reported By: {hazard_report.reported_by.get_full_name()}
- Reported At: {hazard_report.reported_at.strftime('%Y-%m-%d %H:%M:%S')}
- Status: {hazard_report.get_status_display()}

A voice message has been sent to your phone number: {member.phone_number}

Please take immediate action as required.

This is an automated message from the Pralay Hazard Management System.

---
District Chairman: District Chairman (ID: 1)
Action Taken At: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                
                EmailService.send_email(
                    subject=email_subject,
                    plain_text=email_body,
                    to_email=member.email
                )
                email_results.append({
                    'member_id': member.id,
                    'member_name': member.get_full_name(),
                    'email': member.email,
                    'status': 'sent'
                })
                logger.info(f"Email sent to {member.get_full_name()} ({member.email})")
                
            except Exception as e:
                logger.error(f"Failed to send email to {member.get_full_name()} ({member.email}): {e}")
                email_results.append({
                    'member_id': member.id,
                    'member_name': member.get_full_name(),
                    'email': member.email,
                    'error': str(e),
                    'status': 'failed'
                })
        
        # Count successful operations
        successful_calls = len([r for r in call_results if r.get('status') == 'initiated'])
        successful_sms = len([r for r in call_results if r.get('status') == 'sms_sent'])
        successful_emails = len([r for r in email_results if r.get('status') == 'sent'])
        total_communications = successful_calls + successful_sms
        
        return JsonResponse({
            'success': True,
            'message': f'Action taken successfully. Calls: {successful_calls}, SMS: {successful_sms}, Emails: {successful_emails} out of {len(team_members)} team members',
            'data': {
                'report_id': report_id,
                'report_title': f"Hazard Report #{hazard_report.report_id}",
                'audio_file_url': audio_file_url,
                'team_members_count': len(team_members),
                'call_results': call_results,
                'email_results': email_results,
                'successful_calls': successful_calls,
                'successful_sms': successful_sms,
                'successful_emails': successful_emails,
                'total_communications': total_communications,
                'action_taken_at': timezone.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error in take_action_endpoint: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Internal server error: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def get_team_members_endpoint(request):
    """API endpoint to get team members for the current authority. Requires Bearer token."""
    try:
        team_members = SubAuthorityTeamMember.objects.filter(
            sub_authority=request.user,
            is_active=True
        )
        
        members_data = []
        for member in team_members:
            members_data.append({
                'id': member.id,
                'name': member.get_full_name(),
                'phone_number': member.phone_number,
                'email': member.email,
                'designation': member.designation,
                'district': member.district,
                'village': member.village
            })
        
        return JsonResponse({
            'success': True,
            'team_members': members_data,
            'count': len(members_data)
        })
        
    except Exception as e:
        logger.error(f"Error in get_team_members_endpoint: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Internal server error: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def test_auth_endpoint(request):
    """Test endpoint for token authentication"""
    return JsonResponse({
        'success': True,
        'message': 'Test endpoint working',
        'user_authenticated': True,
        'user_id': request.user.id,
        'user_email': request.user.email
    })

@csrf_exempt
@require_http_methods(["GET"])
def twiml_endpoint(request):
    """
    TwiML endpoint for Twilio calls
    Returns TwiML XML that speaks the hazard report details
    """
    try:
        report_id = request.GET.get('report_id')
        if not report_id:
            return HttpResponse("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Error: No report ID provided.</Say>
</Response>""", content_type='text/xml')
        
        # Get the hazard report
        try:
            hazard_report = OceanHazardReport.objects.get(report_id=report_id)
        except OceanHazardReport.DoesNotExist:
            return HttpResponse("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Error: Hazard report not found.</Say>
</Response>""", content_type='text/xml')
        
        # Create TwiML response
        twiml_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">This is an urgent message from the Pralay Hazard Management System.</Say>
    <Say voice="alice">A hazard has been reported in your district that requires immediate attention.</Say>
    <Say voice="alice">Report ID: {hazard_report.report_id}</Say>
    <Say voice="alice">Hazard Type: {hazard_report.get_hazard_type_display()}</Say>
    <Say voice="alice">Location: {hazard_report.city}, {hazard_report.district}</Say>
    <Say voice="alice">Description: {hazard_report.description[:100]}...</Say>
    <Say voice="alice">Please check your email for detailed information and take immediate action.</Say>
    <Say voice="alice">Thank you for your attention.</Say>
</Response>"""
        
        return HttpResponse(twiml_xml, content_type='text/xml')
        
    except Exception as e:
        logger.error(f"Error in twiml_endpoint: {e}")
        return HttpResponse("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Error: Unable to process request.</Say>
</Response>""", content_type='text/xml')
