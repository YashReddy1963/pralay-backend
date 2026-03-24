from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils import timezone
from django.middleware.csrf import get_token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from functools import wraps
import json
import logging
from .email_service import EmailService
from .forms import CustomUserCreationForm, CustomAuthenticationForm, AuthorityCreationForm, TeamMemberForm, SubAuthorityForm, SubAuthorityCreationForm, TeamMemberCreationForm, SubAuthorityTeamMemberCreationForm
from .models import CustomUser, OTP, TeamMember, SubAuthority, SubAuthorityTeamMember, RefreshToken
from .authentication import token_required
from ai_verification_service import verify_image_endpoint
from Pralay.token_auth import token_authenticate_user

logger = logging.getLogger(__name__)

def cors_headers(view_func):
    """Decorator to ensure CORS headers are always added to responses"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            response = view_func(request, *args, **kwargs)
            # Ensure CORS headers are present
            if isinstance(response, JsonResponse):
                origin = request.META.get('HTTP_ORIGIN', '*')
                response['Access-Control-Allow-Origin'] = origin
                response['Access-Control-Allow-Credentials'] = 'true'
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken, X-Requested-With'
            return response
        except Exception as e:
            logger.error(f"Error in {view_func.__name__}: {str(e)}", exc_info=True)
            # Return error response with CORS headers
            origin = request.META.get('HTTP_ORIGIN', '*')
            response = JsonResponse({'error': f'Server error: {str(e)}'}, status=500)
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken, X-Requested-With'
            return response
    return _wrapped_view

def landing_page(request):
    """Landing page with Register and Login buttons"""
    return render(request, 'landing.html')


@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_get_monitoring(request):
    """Return AI monitoring setting for the authenticated authority user."""
    try:
        if request.user.role not in ['state_chairman', 'district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch']:
            return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)

        setting = getattr(request.user, 'authority_setting', None)
        ai_monitoring = bool(setting.ai_monitoring) if setting else False

        return JsonResponse({'success': True, 'ai_monitoring': ai_monitoring})
    except Exception as e:
        logger.exception(f"Error in api_get_monitoring: {e}")
        return JsonResponse({'success': False, 'message': 'Internal server error'}, status=500)


@csrf_exempt
@require_http_methods(["POST", "PATCH"])
@token_required
def api_set_monitoring(request):
    """Set AI monitoring on/off for the authenticated authority user. Expects JSON { ai_monitoring: true|false }"""
    try:
        if request.user.role not in ['state_chairman', 'district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch']:
            return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)

        try:
            body = json.loads(request.body or '{}')
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

        ai_monitoring = bool(body.get('ai_monitoring', False))

        from .models import AuthoritySetting

        setting, created = AuthoritySetting.objects.get_or_create(authority=request.user)
        setting.ai_monitoring = ai_monitoring
        setting.save()

        return JsonResponse({'success': True, 'ai_monitoring': setting.ai_monitoring, 'created': created})
    except Exception as e:
        logger.exception(f"Error in api_set_monitoring: {e}")
        return JsonResponse({'success': False, 'message': 'Internal server error'}, status=500)

def register_view(request):
    """User registration view - everyone becomes normal user"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.role = 'user'  # Everyone registers as normal user
            user.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'register.html', {'form': form})

def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'Login successful!')
            return redirect('dashboard')
    else:
        form = CustomAuthenticationForm()
        
    return render(request, 'login.html', {'form': form})

    

def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('landing')

@login_required
def dashboard(request):
    """Redirct to appropriate dashborad based on the user role"""
    user_role = request.user.role
    
    if user_role == 'user':
        return redirect('dashboard_user')
    elif user_role in ['state_chairman', 'district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch']:
        return redirect('dashboard_authority')
    elif user_role == 'admin':
        return redirect('dashboard_admin')
    else:
        messages.error(request, 'Invalid user role.')
        return redirect('landing')

@login_required
def dashboard_user(request):
    """User dashboard"""
    if request.user.role != 'user':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    return render(request, 'dashboard_user.html')

@login_required
def dashboard_authority(request):
    """Authority dashboard"""
    if request.user.role not in ['state_chairman', 'district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    return render(request, 'dashboard_authority.html')

@login_required
def dashboard_admin(request):
    """Admin dashboard"""
    if request.user.role != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    return render(request, 'dashboard_admin.html')

@login_required
def create_authority(request):
    """Create new authority user - only accessible by authorized users"""
    # Check if user can create authorities
    if request.user.role not in ['admin', 'state_chairman', 'district_chairman', 'nagar_panchayat_chairman']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AuthorityCreationForm(request.POST, creator=request.user)
        if form.is_valid():
            authority = form.save()
            messages.success(request, f'{authority.get_role_display()} created successfully!')
            return redirect('dashboard_admin')
    else:
        form = AuthorityCreationForm(creator=request.user)
    
    return render(request, 'create_authority.html', {'form': form})

@login_required
def manage_authorities(request):
    """Manage authorities - shows only users they can access"""
    # Check if user can manage authorities
    if request.user.role not in ['admin', 'state_chairman', 'district_chairman', 'nagar_panchayat_chairman']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get authorities based on user's access level
    if request.user.role == 'admin':
        authorities = CustomUser.objects.exclude(role='user').exclude(role='admin')
    elif request.user.role == 'state_chairman':
        authorities = CustomUser.objects.filter(
            state=request.user.state,
            role__in=['district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch']
        )
    elif request.user.role == 'district_chairman':
        authorities = CustomUser.objects.filter(
            district=request.user.district,
            role__in=['nagar_panchayat_chairman', 'village_sarpanch']
        )
    elif request.user.role == 'nagar_panchayat_chairman':
        authorities = CustomUser.objects.filter(
            nagar_panchayat=request.user.nagar_panchayat,
            role='village_sarpanch'
        )
    
    return render(request, 'manage_authorities.html', {'authorities': authorities})

@csrf_exempt
@require_http_methods(["POST"])
@token_required
def api_create_authority(request):
    """API endpoint for creating authority from frontend"""
    try:
        # Check if user can create authorities
        if request.user.role not in ['admin', 'state_chairman', 'district_chairman', 'nagar_panchayat_chairman']:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Handle file upload with FormData
        form = AuthorityCreationForm(request.POST, request.FILES, creator=request.user)
        if form.is_valid():
            authority = form.save()
            return JsonResponse({
                'success': True,
                'message': f'{authority.get_role_display()} created successfully!',
                'authority': {
                    'id': authority.id,
                    'name': authority.get_full_name(),
                    'email': authority.email,
                    'role': authority.get_role_display(),
                }
            })
        else:
            # Log the form errors for debugging
            print(f"Form validation errors: {form.errors}")
            print(f"Form data received: {request.POST}")
            return JsonResponse({
                'error': 'Invalid form data',
                'errors': form.errors.as_json()
            }, status=400)

    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)

# API Endpoints for Frontend
@cors_headers
@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_send_otp(request):
    """Send OTP to email for registration"""

    if request.method == 'OPTIONS':
        return JsonResponse({}, status=200)

    try:
        data = json.loads(request.body)
        email = data.get('email')

        if not email:
            return JsonResponse({'error': 'Email is required'}, status=400)

        if CustomUser.objects.filter(email=email).exists():
            return JsonResponse({'error': 'User with this email already exists'}, status=400)

        # ✅ Check SendGrid config instead of SMTP
        if not settings.SENDGRID_API_KEY or not settings.DEFAULT_FROM_EMAIL:
            logger.error("SendGrid configuration missing")
            return JsonResponse(
                {'error': 'Email service not configured properly'},
                status=500
            )

        # Generate OTP
        otp = OTP.generate_otp(email)

        subject = "Pralay Platform - OTP Verification"
        message = f"""
Welcome to Pralay Digital Disaster Management Platform!

Your OTP for registration is: {otp.otp_code}

This OTP will expire in 10 minutes.

If you did not request this, please ignore this email.

Best regards,
Pralay Team
"""

        # ✅ Use SendGrid service instead of send_mail
        email_sent = EmailService.send_email(
            subject=subject,
            plain_text=message,
            to_email=email
        )

        if not email_sent:
            return JsonResponse(
                {'error': 'Failed to send OTP email'},
                status=500
            )

        return JsonResponse({
            'success': True,
            'message': 'OTP sent successfully to your email'
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    except Exception as e:
        logger.error(f"Error in api_send_otp: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Server error'}, status=500)


@cors_headers
@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def api_verify_otp(request):
    """Verify OTP and complete registration"""
    # Handle CORS preflight requests
    if request.method == 'OPTIONS':
        response = JsonResponse({})
        origin = request.META.get('HTTP_ORIGIN', '*')
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Credentials'] = 'true'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken, X-Requested-With'
        response['Access-Control-Max-Age'] = '86400'
        return response
    
    try:
        data = json.loads(request.body)
        email = data.get('email')
        otp_code = data.get('otp')
        
        if not email or not otp_code:
            response = JsonResponse({'error': 'Email and OTP are required'}, status=400)
            origin = request.META.get('HTTP_ORIGIN', '*')
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'
            return response
        
        # Find and verify OTP
        try:
            otp = OTP.objects.get(email=email, otp_code=otp_code)
        except OTP.DoesNotExist:
            response = JsonResponse({'error': 'Invalid OTP'}, status=400)
            origin = request.META.get('HTTP_ORIGIN', '*')
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'
            return response
        
        if not otp.is_valid():
            response = JsonResponse({'error': 'OTP has expired or already used'}, status=400)
            origin = request.META.get('HTTP_ORIGIN', '*')
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'
            return response
        
        # Mark OTP as verified
        otp.verify()
        
        response = JsonResponse({
            'success': True,
            'message': 'OTP verified successfully'
        })
        origin = request.META.get('HTTP_ORIGIN', '*')
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Credentials'] = 'true'
        return response
        
    except json.JSONDecodeError:
        response = JsonResponse({'error': 'Invalid JSON data'}, status=400)
        origin = request.META.get('HTTP_ORIGIN', '*')
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Credentials'] = 'true'
        return response
    except Exception as e:
        logger.error(f"Error in api_verify_otp: {str(e)}", exc_info=True)
        response = JsonResponse({'error': f'Server error: {str(e)}'}, status=500)
        origin = request.META.get('HTTP_ORIGIN', '*')
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Allow-Credentials'] = 'true'
        return response

@csrf_exempt
@require_http_methods(["POST"])
def api_register(request):
    """Complete user registration after OTP verification"""
    try:
        data = json.loads(request.body)
        
        # Check if OTP is verified
        email = data.get('email')
        if not email:
            return JsonResponse({'error': 'Email is required'}, status=400)
        
        # Verify OTP is verified and not expired
        try:
            otp = OTP.objects.get(email=email, is_verified=True)
            # Check if OTP is expired (verified OTPs should not be expired)
            from django.utils import timezone
            if timezone.now() >= otp.expires_at:
                return JsonResponse({'error': 'OTP has expired. Please request a new one.'}, status=400)
        except OTP.DoesNotExist:
            return JsonResponse({'error': 'Please verify your email with OTP first'}, status=400)
        
        # Create user
        try:
            user = CustomUser.objects.create_user(
                username=data.get('email'),
                email=data.get('email'),
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                phone_number=data.get('phone_number'),
                password=data.get('password'),
                role='user',  # Everyone becomes normal user
                state=data.get('state', ''),
                district=data.get('district', ''),
                address=data.get('address', '')
            )
            
            # Clean up OTP
            otp.delete()
            
            # Return success - user must login separately to get token
            return JsonResponse({
                'success': True,
                'message': 'Registration successful! Please login to get your access token.',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': f'Registration failed: {str(e)}'}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def api_login(request):
    """API login - stateless token only. No session. Returns token for Authorization header."""
    try:
        data = json.loads(request.body)
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return JsonResponse({'error': 'Email and password are required'}, status=400)
        
        # CustomUser (authorities, admin, regular users) - full token auth
        try:
            user = CustomUser.objects.get(email=email)
            if user.check_password(password):
                user.last_login_time = timezone.now()
                user.save()
                refresh_token = RefreshToken.generate_token(user)
                # Same token used as Bearer for API and for refresh endpoint
                return JsonResponse({
                    'success': True,
                    'message': 'Login successful!',
                    'token': refresh_token.token,
                    'refresh_token': refresh_token.token,
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'role': user.role
                    }
                })
        except CustomUser.DoesNotExist:
            pass

        # SubAuthority login support (token-based)
        try:
            from django.contrib.auth.hashers import check_password
            sub_authority = SubAuthority.objects.get(email=email)
            if sub_authority.password_hash and check_password(password, sub_authority.password_hash):
            
                # Generate refresh token manually (like CustomUser)
                refresh_token = RefreshToken.generate_token(sub_authority)

                return JsonResponse({
                    'success': True,
                    'message': 'Login successful!',
                    'token': refresh_token.token,
                    'refresh_token': refresh_token.token,
                    'user': {
                        'id': sub_authority.id,
                        'email': sub_authority.email,
                        'first_name': sub_authority.first_name,
                        'last_name': sub_authority.last_name,
                        'role': sub_authority.role,  # Important
                        'state': sub_authority.state,
                        'district': sub_authority.district,
                    }
                })
        except SubAuthority.DoesNotExist:
            pass
        
        try:
            from django.contrib.auth.hashers import check_password
            sub_authority = SubAuthority.objects.get(email=email)
            if sub_authority.password_hash and check_password(password, sub_authority.password_hash):
                return JsonResponse({
                    'error': 'Sub-authority login is not supported via API. Use admin dashboard.'
                }, status=501)
        except SubAuthority.DoesNotExist:
            pass
        
        return JsonResponse({'error': 'Invalid credentials'}, status=401)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def api_logout(request):
    """API logout - revoke refresh token only. No session."""
    try:
        data = json.loads(request.body) if request.body else {}
        refresh_token_value = data.get('refresh_token')
        if refresh_token_value:
            try:
                refresh_token = RefreshToken.objects.get(token=refresh_token_value)
                refresh_token.revoke()
            except RefreshToken.DoesNotExist:
                pass
        return JsonResponse({'success': True, 'message': 'Logged out successfully'})
    except Exception as e:
        return JsonResponse({'success': True, 'message': 'Logged out successfully'})

@csrf_exempt
@require_http_methods(["POST"])
def api_refresh_token(request):
    """Refresh token: validate old token, issue new token (rotate). Stateless."""
    try:
        data = json.loads(request.body)
        refresh_token_value = data.get('refresh_token')
        if not refresh_token_value:
            return JsonResponse({'error': 'Refresh token is required'}, status=400)
        try:
            old_refresh = RefreshToken.objects.get(token=refresh_token_value)
        except RefreshToken.DoesNotExist:
            return JsonResponse({'error': 'Invalid refresh token'}, status=401)
        if not old_refresh.is_valid():
            return JsonResponse({'error': 'Refresh token has expired or been revoked'}, status=401)
        user = old_refresh.user
        old_refresh.revoke()
        new_refresh = RefreshToken.generate_token(user)
        user.last_login_time = timezone.now()
        user.save()
        return JsonResponse({
            'success': True,
            'message': 'Token refreshed successfully',
            'token': new_refresh.token,
            'refresh_token': new_refresh.token,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "POST"])
def api_auth_profile(request):
    """Get or update the profile of the currently authenticated user-like account."""
    try:
        profile_owner = None
        profile_owner_type = None

        if request.user.is_authenticated and isinstance(request.user, CustomUser):
            profile_owner = request.user
            profile_owner_type = 'custom_user'
        elif request.session.get('team_member_id'):
            team_member_id = request.session.get('team_member_id')
            profile_owner = TeamMember.objects.filter(id=team_member_id, is_active=True).first()
            profile_owner_type = 'team_member' if profile_owner else None
        elif request.session.get('sub_authority_id'):
            sub_authority_id = request.session.get('sub_authority_id')
            profile_owner = SubAuthority.objects.filter(id=sub_authority_id, is_active=True).first()
            profile_owner_type = 'sub_authority' if profile_owner else None
        else:
            token_user = token_authenticate_user(request)
            if token_user and isinstance(token_user, CustomUser):
                profile_owner = token_user
                profile_owner_type = 'custom_user'

        if not profile_owner:
            return JsonResponse({'error': 'Authentication required'}, status=401)

        def serialize_profile(current_user, current_type):
            if current_type == 'custom_user':
                return {
                    'id': current_user.id,
                    'email': current_user.email,
                    'username': current_user.username,
                    'first_name': current_user.first_name,
                    'middle_name': current_user.middle_name,
                    'last_name': current_user.last_name,
                    'phone_number': current_user.phone_number,
                    'profile_picture_url': request.build_absolute_uri(current_user.profile_picture.url) if current_user.profile_picture else None,
                    'role': current_user.role,
                    'role_display': current_user.get_role_display(),
                    'custom_role': current_user.custom_role,
                    'state': current_user.state,
                    'district': current_user.district,
                    'nagar_panchayat': current_user.nagar_panchayat,
                    'village': current_user.village,
                    'address': current_user.address,
                    'government_service_id': current_user.government_service_id,
                    'current_designation': current_user.current_designation,
                    'service_card_proof_url': request.build_absolute_uri(current_user.service_card_proof.url) if current_user.service_card_proof else None,
                    'can_view_reports': current_user.can_view_reports,
                    'can_approve_reports': current_user.can_approve_reports,
                    'can_manage_teams': current_user.can_manage_teams,
                    'created_by': current_user.created_by.get_full_name() if current_user.created_by else None,
                    'date_joined': current_user.date_joined.isoformat() if current_user.date_joined else None,
                    'last_login_time': current_user.last_login_time.isoformat() if current_user.last_login_time else None,
                }

            if current_type == 'team_member':
                return {
                    'id': current_user.id,
                    'email': current_user.email,
                    'username': current_user.email,
                    'first_name': current_user.first_name,
                    'middle_name': current_user.middle_name,
                    'last_name': current_user.last_name,
                    'phone_number': current_user.phone_number,
                    'profile_picture_url': request.build_absolute_uri(current_user.document_proof.url) if current_user.document_proof else None,
                    'role': 'team_member',
                    'role_display': current_user.get_role_display(),
                    'custom_role': '',
                    'state': current_user.state,
                    'district': current_user.district,
                    'nagar_panchayat': current_user.nagar_panchayat,
                    'village': current_user.village,
                    'address': current_user.address,
                    'government_service_id': current_user.government_service_id,
                    'current_designation': current_user.designation,
                    'service_card_proof_url': request.build_absolute_uri(current_user.document_proof.url) if current_user.document_proof else None,
                    'can_view_reports': current_user.can_view_reports,
                    'can_approve_reports': current_user.can_approve_reports,
                    'can_manage_teams': current_user.can_manage_teams,
                    'created_by': current_user.authority.get_full_name() if current_user.authority else None,
                    'date_joined': current_user.assigned_date.isoformat() if current_user.assigned_date else None,
                    'last_login_time': None,
                }

            return {
                'id': current_user.id,
                'email': current_user.email,
                'username': current_user.email,
                'first_name': current_user.first_name,
                'middle_name': current_user.middle_name,
                'last_name': current_user.last_name,
                'phone_number': current_user.phone_number,
                'profile_picture_url': request.build_absolute_uri(current_user.document_proof.url) if current_user.document_proof else None,
                'role': current_user.role,
                'role_display': current_user.get_role_display(),
                'custom_role': current_user.custom_role,
                'state': current_user.state,
                'district': current_user.district,
                'nagar_panchayat': current_user.nagar_panchayat,
                'village': current_user.village,
                'address': current_user.address,
                'government_service_id': current_user.government_service_id,
                'current_designation': current_user.custom_role,
                'service_card_proof_url': request.build_absolute_uri(current_user.document_proof.url) if current_user.document_proof else None,
                'can_view_reports': current_user.can_view_reports,
                'can_approve_reports': current_user.can_approve_reports,
                'can_manage_teams': current_user.can_manage_teams,
                'created_by': current_user.creator.get_full_name() if current_user.creator else None,
                'date_joined': current_user.created_date.isoformat() if current_user.created_date else None,
                'last_login_time': None,
            }

        if request.method == "GET":
            return JsonResponse({
                'success': True,
                'profile': serialize_profile(profile_owner, profile_owner_type)
            })

        content_type = request.content_type or ''
        is_multipart = content_type.startswith('multipart/form-data')

        if is_multipart:
            data = request.POST
        else:
            data = json.loads(request.body) if request.body else {}

        editable_fields = [
            'first_name',
            'middle_name',
            'last_name',
            'phone_number',
            'state',
            'district',
            'nagar_panchayat',
            'village',
            'address',
        ]

        updated_fields = []
        for field in editable_fields:
            if field in data:
                setattr(profile_owner, field, data.get(field) or '')
                updated_fields.append(field)

        if profile_owner_type == 'custom_user':
            if 'current_designation' in data:
                profile_owner.current_designation = data.get('current_designation') or ''
                updated_fields.append('current_designation')

            if 'custom_role' in data:
                profile_owner.custom_role = data.get('custom_role') or ''
                updated_fields.append('custom_role')

            uploaded_profile_picture = request.FILES.get('profile_picture')
            if uploaded_profile_picture:
                content_type_value = uploaded_profile_picture.content_type or ''
                if not content_type_value.startswith('image/'):
                    return JsonResponse({'error': 'Only image files are allowed for profile picture'}, status=400)

                max_size = 5 * 1024 * 1024
                if uploaded_profile_picture.size > max_size:
                    return JsonResponse({'error': 'Profile picture size must be less than 5MB'}, status=400)

                profile_owner.profile_picture = uploaded_profile_picture
                updated_fields.append('profile_picture')

            remove_profile_picture = str(data.get('remove_profile_picture', '')).lower() in ['1', 'true', 'yes']
            if remove_profile_picture and profile_owner.profile_picture:
                profile_owner.profile_picture.delete(save=False)
                profile_owner.profile_picture = None
                updated_fields.append('profile_picture')
        elif profile_owner_type == 'team_member':
            if 'current_designation' in data:
                profile_owner.designation = data.get('current_designation') or ''
                updated_fields.append('designation')

            uploaded_profile_picture = request.FILES.get('profile_picture')
            if uploaded_profile_picture:
                content_type_value = uploaded_profile_picture.content_type or ''
                if not content_type_value.startswith('image/'):
                    return JsonResponse({'error': 'Only image files are allowed for profile picture'}, status=400)

                max_size = 5 * 1024 * 1024
                if uploaded_profile_picture.size > max_size:
                    return JsonResponse({'error': 'Profile picture size must be less than 5MB'}, status=400)

                profile_owner.document_proof = uploaded_profile_picture
                updated_fields.append('document_proof')

            remove_profile_picture = str(data.get('remove_profile_picture', '')).lower() in ['1', 'true', 'yes']
            if remove_profile_picture and profile_owner.document_proof:
                profile_owner.document_proof.delete(save=False)
                profile_owner.document_proof = None
                updated_fields.append('document_proof')
        elif profile_owner_type == 'sub_authority':
            if 'current_designation' in data:
                profile_owner.custom_role = data.get('current_designation') or ''
                updated_fields.append('custom_role')
            if 'custom_role' in data:
                profile_owner.custom_role = data.get('custom_role') or ''
                updated_fields.append('custom_role')

            uploaded_profile_picture = request.FILES.get('profile_picture')
            if uploaded_profile_picture:
                content_type_value = uploaded_profile_picture.content_type or ''
                if not content_type_value.startswith('image/'):
                    return JsonResponse({'error': 'Only image files are allowed for profile picture'}, status=400)

                max_size = 5 * 1024 * 1024
                if uploaded_profile_picture.size > max_size:
                    return JsonResponse({'error': 'Profile picture size must be less than 5MB'}, status=400)

                profile_owner.document_proof = uploaded_profile_picture
                updated_fields.append('document_proof')

            remove_profile_picture = str(data.get('remove_profile_picture', '')).lower() in ['1', 'true', 'yes']
            if remove_profile_picture and profile_owner.document_proof:
                profile_owner.document_proof.delete(save=False)
                profile_owner.document_proof = None
                updated_fields.append('document_proof')

        if not updated_fields:
            return JsonResponse({'error': 'No valid fields provided to update'}, status=400)

        profile_owner.save(update_fields=list(set(updated_fields)))

        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully',
            'profile': serialize_profile(profile_owner, profile_owner_type)
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_get_official_details(request, official_id):
    """API endpoint to get detailed information about a specific official"""
    try:
        if request.user.role != 'admin':
            return JsonResponse({'error': 'Admin access required'}, status=403)
        
        # Get the official
        try:
            official = CustomUser.objects.get(id=official_id)
        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'Official not found'}, status=404)
        
        # Check if it's an authority (not regular user or admin)
        authority_roles = ['state_chairman', 'district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch', 'other']
        if official.role not in authority_roles:
            return JsonResponse({'error': 'Not an authority official'}, status=400)
        
        # Get sub-authorities created by this official
        sub_authorities = SubAuthority.objects.filter(creator=official, is_active=True).order_by('-created_date')
        sub_auth_data = []
        for sub_auth in sub_authorities:
            sub_auth_data.append({
                'id': sub_auth.id,
                'name': sub_auth.get_full_name(),
                'email': sub_auth.email,
                'role': sub_auth.get_role_display(),
                'state': sub_auth.state or '',
                'district': sub_auth.district or '',
                'created_date': sub_auth.created_date.isoformat(),
                'is_active': sub_auth.is_active
            })
        
        # Get team members under this official
        team_members = TeamMember.objects.filter(authority=official, is_active=True).order_by('-assigned_date')
        team_data = []
        for member in team_members:
            team_data.append({
                'id': member.id,
                'name': member.get_full_name(),
                'email': member.email,
                'designation': member.designation or '',
                'phone_number': member.phone_number or '',
                'assigned_date': member.assigned_date.isoformat(),
                'is_active': member.is_active
            })
        
        # Format official data
        official_data = {
            'id': official.id,
            'name': official.get_full_name(),
            'email': official.email,
            'role': official.get_role_display(),
            'role_value': official.role,
            'state': official.state or '',
            'district': official.district or '',
            'nagar_panchayat': official.nagar_panchayat or '',
            'village': official.village or '',
            'phone_number': official.phone_number or '',
            'government_service_id': official.government_service_id or '',
            'current_designation': official.current_designation or '',
            'last_login_time': official.last_login_time.isoformat() if official.last_login_time else None,
            'date_joined': official.date_joined.isoformat(),
            'can_view_reports': official.can_view_reports,
            'can_approve_reports': official.can_approve_reports,
            'can_manage_teams': official.can_manage_teams,
            'created_by': official.created_by.get_full_name() if official.created_by else 'System',
            'service_card_proof': request.build_absolute_uri(official.service_card_proof.url) if official.service_card_proof else None,
            'sub_authorities': sub_auth_data,
            'team_members': team_data,
            'sub_authorities_count': len(sub_auth_data),
            'team_members_count': len(team_data)
        }
        
        return JsonResponse({
            'success': True,
            'official': official_data
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@token_required
def api_update_official_permissions(request, official_id):
    """API endpoint to update permissions for a specific official"""
    try:
        if request.user.role != 'admin':
            return JsonResponse({'error': 'Admin access required'}, status=403)
        
        # Get the official
        try:
            official = CustomUser.objects.get(id=official_id)
        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'Official not found'}, status=404)
        
        # Parse request data
        data = json.loads(request.body)
        
        # Update permissions
        if 'can_view_reports' in data:
            official.can_view_reports = data['can_view_reports']
        if 'can_approve_reports' in data:
            official.can_approve_reports = data['can_approve_reports']
        if 'can_manage_teams' in data:
            official.can_manage_teams = data['can_manage_teams']
        
        official.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Permissions updated successfully',
            'permissions': {
                'can_view_reports': official.can_view_reports,
                'can_approve_reports': official.can_approve_reports,
                'can_manage_teams': official.can_manage_teams
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_get_authority_team_members(request):
    """API endpoint to get team members created by the authenticated authority"""
    try:
        # Check if user is an authority
        authority_roles = ['state_chairman', 'district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch', 'other']
        if request.user.role not in authority_roles:
            return JsonResponse({'error': 'Authority access required'}, status=403)
        
        # Get team members created by this authority
        team_members = TeamMember.objects.filter(authority=request.user).order_by('-assigned_date')
        
        team_members_data = []
        for member in team_members:
            # Build absolute URL for document_proof if present
            doc_url = None
            try:
                if member.document_proof:
                    doc_url = request.build_absolute_uri(member.document_proof.url)
            except Exception:
                doc_url = None

            team_members_data.append({
                'id': member.id,
                'first_name': member.first_name,
                'middle_name': member.middle_name,
                'last_name': member.last_name,
                'email': member.email,
                'phone_number': member.phone_number,
                'designation': member.designation,
                'state': member.state or '',
                'district': member.district or '',
                'nagar_panchayat': member.nagar_panchayat or '',
                'village': member.village or '',
                'address': member.address or '',
                'government_service_id': member.government_service_id or '',
                'document_proof': doc_url,
                'assigned_date': member.assigned_date.isoformat() if member.assigned_date else None,
                'can_view_reports': member.can_view_reports,
                'can_approve_reports': member.can_approve_reports,
                'can_manage_teams': member.can_manage_teams,
                'is_active': member.is_active
            })
        
        return JsonResponse({
            'success': True,
            'team_members': team_members_data,
            'total_count': len(team_members_data)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_get_authority_sub_authorities(request):
    """API endpoint to get sub-authorities created by the authenticated authority"""
    try:
        # Check if user is an authority
        authority_roles = ['state_chairman', 'district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch', 'other']
        if request.user.role not in authority_roles:
            return JsonResponse({'error': 'Authority access required'}, status=403)
        
        # Get sub-authorities created by this authority
        sub_authorities = SubAuthority.objects.filter(creator=request.user).order_by('-created_date')
        
        sub_authorities_data = []
        for sub_auth in sub_authorities:
            sub_authorities_data.append({
                'id': sub_auth.id,
                'first_name': sub_auth.first_name,
                'last_name': sub_auth.last_name,
                'email': sub_auth.email,
                'phone_number': sub_auth.phone_number,
                'role': sub_auth.role,
                'custom_role': sub_auth.custom_role,
                'state': sub_auth.state,
                'district': sub_auth.district,
                'nagar_panchayat': sub_auth.nagar_panchayat,
                'village': sub_auth.village,
                'created_date': sub_auth.created_date.isoformat(),
                'can_view_reports': sub_auth.can_view_reports,
                'can_approve_reports': sub_auth.can_approve_reports,
                'can_manage_teams': sub_auth.can_manage_teams,
                'is_active': sub_auth.is_active
            })
        
        return JsonResponse({
            'success': True,
            'sub_authorities': sub_authorities_data,
            'total_count': len(sub_authorities_data)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
@token_required
def api_remove_team_member(request, member_id):
    try:
        if request.user.role not in ['admin', 'state_chairman', 'district_chairman', 'nagar_panchayat_chairman']:
            return JsonResponse({'error': 'Access denied'}, status=403)

        try:
            team_member = TeamMember.objects.get(
                id=member_id,
                authority=request.user
            )
        except TeamMember.DoesNotExist:
            return JsonResponse({
                'error': 'Team member not found or you do not have permission'
            }, status=404)

        team_member.delete()

        return JsonResponse({
            'success': True,
            'message': 'Team member removed successfully'
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["PUT", "POST"])
@token_required
def api_update_team_member(request, member_id):
    """API endpoint to update a team member's editable fields
    Supports updating: designation, phone_number, address, government_service_id,
    can_view_reports, can_approve_reports, can_manage_teams, and optionally document_proof.
    Accepts JSON body or multipart/form-data (for file upload).
    """
    try:
        # Check if user is an authority
        authority_roles = ['state_chairman', 'district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch', 'other', 'admin']
        if request.user.role not in authority_roles:
            return JsonResponse({'error': 'Authority access required'}, status=403)

        # Retrieve the team member and ensure they belong to this authority
        try:
            team_member = TeamMember.objects.get(id=member_id, authority=request.user)
        except TeamMember.DoesNotExist:
            return JsonResponse({'error': 'Team member not found or you do not have permission to update this member'}, status=404)

        # Support multipart form (file upload) or JSON
        data = {}
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.POST
            files = request.FILES
        else:
            try:
                data = json.loads(request.body) if request.body else {}
            except Exception:
                data = {}
            files = {}

        # Update allowed fields
        if 'designation' in data:
            team_member.designation = data.get('designation')
        if 'phone_number' in data:
            team_member.phone_number = data.get('phone_number')
        if 'address' in data:
            team_member.address = data.get('address')
        if 'government_service_id' in data:
            team_member.government_service_id = data.get('government_service_id')

        # Permissions (ensure boolean conversion)
        if 'can_view_reports' in data:
            team_member.can_view_reports = str(data.get('can_view_reports')).lower() in ['true', '1', 'yes']
        if 'can_approve_reports' in data:
            team_member.can_approve_reports = str(data.get('can_approve_reports')).lower() in ['true', '1', 'yes']
        if 'can_manage_teams' in data:
            team_member.can_manage_teams = str(data.get('can_manage_teams')).lower() in ['true', '1', 'yes']

        # Handle document_proof upload
        if files and 'document_proof' in files:
            team_member.document_proof = files['document_proof']

        team_member.save()

        # Build response similar to GET
        doc_url = None
        try:
            if team_member.document_proof:
                doc_url = request.build_absolute_uri(team_member.document_proof.url)
        except Exception:
            doc_url = None

        resp = {
            'id': team_member.id,
            'first_name': team_member.first_name,
            'middle_name': team_member.middle_name,
            'last_name': team_member.last_name,
            'email': team_member.email,
            'phone_number': team_member.phone_number,
            'designation': team_member.designation,
            'state': team_member.state or '',
            'district': team_member.district or '',
            'nagar_panchayat': team_member.nagar_panchayat or '',
            'village': team_member.village or '',
            'address': team_member.address or '',
            'government_service_id': team_member.government_service_id or '',
            'document_proof': doc_url,
            'assigned_date': team_member.assigned_date.isoformat() if team_member.assigned_date else None,
            'can_view_reports': team_member.can_view_reports,
            'can_approve_reports': team_member.can_approve_reports,
            'can_manage_teams': team_member.can_manage_teams,
            'is_active': team_member.is_active
        }

        return JsonResponse({'success': True, 'team_member': resp})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["PUT", "POST"])
@token_required
def api_update_sub_authority_team_member(request, member_id):
    """API endpoint to update a sub-authority team member's editable fields
    Supports updating: designation, phone_number, address, government_service_id,
    can_view_reports, can_approve_reports, can_manage_teams, and optionally document_proof.
    Accepts JSON body or multipart/form-data (for file upload).
    """
    try:
        # Only district-level roles can update sub-authority team members
        allowed_roles = ['district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch']
        if request.user.role not in allowed_roles and request.user.role != 'admin':
            return JsonResponse({'error': 'Access denied'}, status=403)

        # Retrieve the member ensuring it belongs to the sub_authority (request.user)
        try:
            member = SubAuthorityTeamMember.objects.get(id=member_id, sub_authority=request.user)
        except SubAuthorityTeamMember.DoesNotExist:
            return JsonResponse({'error': 'Team member not found or you do not have permission to update this member'}, status=404)

        # Support multipart form (file upload) or JSON
        data = {}
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.POST
            files = request.FILES
        else:
            try:
                data = json.loads(request.body) if request.body else {}
            except Exception:
                data = {}
            files = {}

        # Update allowed fields
        if 'designation' in data:
            member.designation = data.get('designation')
        if 'phone_number' in data:
            member.phone_number = data.get('phone_number')
        if 'address' in data:
            member.address = data.get('address')
        if 'government_service_id' in data:
            member.government_service_id = data.get('government_service_id')

        # Permissions (ensure boolean conversion)
        if 'can_view_reports' in data:
            member.can_view_reports = str(data.get('can_view_reports')).lower() in ['true', '1', 'yes']
        if 'can_approve_reports' in data:
            member.can_approve_reports = str(data.get('can_approve_reports')).lower() in ['true', '1', 'yes']
        if 'can_manage_teams' in data:
            member.can_manage_teams = str(data.get('can_manage_teams')).lower() in ['true', '1', 'yes']

        # Handle document_proof upload
        if files and 'document_proof' in files:
            member.document_proof = files['document_proof']

        member.save()

        # Build response data
        doc_url = None
        try:
            if member.document_proof:
                doc_url = request.build_absolute_uri(member.document_proof.url)
        except Exception:
            doc_url = None

        resp = {
            'id': member.id,
            'first_name': member.first_name,
            'middle_name': member.middle_name,
            'last_name': member.last_name,
            'email': member.email,
            'phone_number': member.phone_number,
            'designation': member.designation,
            'state': member.state or '',
            'district': member.district or '',
            'nagar_panchayat': member.nagar_panchayat or '',
            'village': member.village or '',
            'address': member.address or '',
            'government_service_id': member.government_service_id or '',
            'document_proof': doc_url,
            'assigned_date': member.assigned_date.isoformat() if member.assigned_date else None,
            'can_view_reports': member.can_view_reports,
            'can_approve_reports': member.can_approve_reports,
            'can_manage_teams': member.can_manage_teams,
            'is_active': member.is_active
        }

        return JsonResponse({'success': True, 'sub_authority_team_member': resp})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_get_official_activity(request, official_id):
    """API endpoint to get activity data for a specific official"""
    try:
        if request.user.role != 'admin':
            return JsonResponse({'error': 'Admin access required'}, status=403)
        
        # Get the official
        try:
            official = CustomUser.objects.get(id=official_id)
        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'Official not found'}, status=404)
        
        # Check if it's an authority
        authority_roles = ['state_chairman', 'district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch', 'other']
        if official.role not in authority_roles:
            return JsonResponse({'error': 'Not an authority official'}, status=400)
        
        # Generate activity data for the last 12 months
        from datetime import datetime, timedelta
        import calendar
        
        activity_data = []
        current_date = datetime.now()
        
        for i in range(12):
            # Calculate the month
            month_date = current_date - timedelta(days=30 * i)
            month_name = calendar.month_name[month_date.month]
            year = month_date.year
            
            # Count sub-authorities created in this month
            sub_auth_count = SubAuthority.objects.filter(
                creator=official,
                created_date__year=year,
                created_date__month=month_date.month
            ).count()
            
            # Count team members created in this month
            team_count = TeamMember.objects.filter(
                authority=official,
                assigned_date__year=year,
                assigned_date__month=month_date.month
            ).count()
            
            activity_data.append({
                'month': f"{month_name} {year}",
                'sub_authorities': sub_auth_count,
                'team_members': team_count,
                'total': sub_auth_count + team_count
            })
        
        # Reverse to show chronological order (oldest first)
        activity_data.reverse()
        
        return JsonResponse({
            'success': True,
            'activity_data': activity_data,
            'official_name': official.get_full_name(),
            'total_sub_authorities': SubAuthority.objects.filter(creator=official).count(),
            'total_team_members': TeamMember.objects.filter(authority=official).count()
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_get_officials(request):
    """API endpoint to get all officials (authorities) with their activity status"""
    try:
        if request.user.role != 'admin':
            return JsonResponse({'error': 'Admin access required'}, status=403)
        
        # Get all users with authority roles (excluding regular users and admin)
        authority_roles = ['state_chairman', 'district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch', 'other']
        officials = CustomUser.objects.filter(role__in=authority_roles).order_by('-last_login_time', '-date_joined')
        
        # Format the officials data
        officials_data = []
        for official in officials:
            # Calculate last login status
            last_login_status = "Never"
            if official.last_login_time:
                now = timezone.now()
                time_diff = now - official.last_login_time
                
                if time_diff.days > 0:
                    last_login_status = f"{time_diff.days} day{'s' if time_diff.days > 1 else ''} ago"
                elif time_diff.seconds > 3600:  # More than 1 hour
                    hours = time_diff.seconds // 3600
                    last_login_status = f"{hours} hour{'s' if hours > 1 else ''} ago"
                elif time_diff.seconds > 60:  # More than 1 minute
                    minutes = time_diff.seconds // 60
                    last_login_status = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                else:
                    last_login_status = "Just now"
            
            # Determine status based on last login
            status = "Active" if official.last_login_time and (timezone.now() - official.last_login_time).days < 7 else "Inactive"
            
            officials_data.append({
                'id': official.id,
                'name': official.get_full_name(),
                'email': official.email,
                'role': official.get_role_display(),
                'role_value': official.role,
                'state': official.state or '',
                'district': official.district or '',
                'nagar_panchayat': official.nagar_panchayat or '',
                'village': official.village or '',
                'phone_number': official.phone_number or '',
                'government_service_id': official.government_service_id or '',
                'current_designation': official.current_designation or '',
                'status': status,
                'last_login': last_login_status,
                'last_login_time': official.last_login_time.isoformat() if official.last_login_time else None,
                'date_joined': official.date_joined.isoformat(),
                'can_view_reports': official.can_view_reports,
                'can_approve_reports': official.can_approve_reports,
                'can_manage_teams': official.can_manage_teams,
                'created_by': official.created_by.get_full_name() if official.created_by else 'System',
                'service_card_proof': request.build_absolute_uri(official.service_card_proof.url) if official.service_card_proof else None
            })
        
        return JsonResponse({
            'success': True,
            'officials': officials_data,
            'total_count': len(officials_data)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_test_auth(request):
    """Test endpoint to check token authentication"""
    return JsonResponse({
        'authenticated': True,
        'user': str(request.user),
        'user_id': request.user.id,
        'email': request.user.email,
    })

@csrf_exempt
@require_http_methods(["GET"])
def api_get_csrf_token(request):
    """API endpoint to get CSRF token (optional; APIs use Bearer token, no CSRF)."""
    try:
        csrf_token = get_token(request)
        return JsonResponse({
            'success': True,
            'csrf_token': csrf_token
        })
    except Exception as e:
        return JsonResponse({
            'error': f'Failed to get CSRF token: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_auth_me(request):
    """Return current user from Bearer token. Used by frontend getCurrentUser."""
    user = request.user
    return JsonResponse({
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'phone_number': user.phone_number or '',
        'role': user.role,
        'state': user.state or '',
        'district': user.district or '',
        'nagar_panchayat': user.nagar_panchayat or '',
        'village': user.village or '',
    })

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_get_team_members(request):
    """API endpoint to get team members for the current authority"""
    try:
        # Check if user can view team members
        if request.user.role not in ['admin', 'state_chairman', 'district_chairman']:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get team members based on user's role and location
        team_members = []
        
        if request.user.role == 'admin':
            # Admin can see all authorities
            team_members = CustomUser.objects.filter(
                role__in=['state_chairman', 'district_chairman', 'taluka_nagar_panchayat_chairman', 'village_talathi', 'other']
            ).exclude(id=request.user.id)
        elif request.user.role == 'state_chairman':
            # State chairman can see district chairmen in their state
            team_members = CustomUser.objects.filter(
                role='district_chairman',
                state=request.user.state
            ).exclude(id=request.user.id)
        elif request.user.role == 'district_chairman':
            # District chairman can see taluka/village officials in their district
            team_members = CustomUser.objects.filter(
                role__in=['taluka_nagar_panchayat_chairman', 'village_talathi', 'other'],
                state=request.user.state,
                district=request.user.district
            ).exclude(id=request.user.id)
        
        # Convert to list of dictionaries
        members_data = []
        for member in team_members:
            members_data.append({
                'id': member.id,
                'first_name': member.first_name,
                'last_name': member.last_name,
                'email': member.email,
                'phone_number': member.phone_number,
                'role': member.role,
                'custom_role': member.custom_role or '',
                'current_designation': member.current_designation or '',
                'state': member.state or '',
                'district': member.district or '',
                'taluka': member.taluka or '',
                'village': member.village or '',
                'nagar_panchayat': member.nagar_panchayat or '',
                'can_view_reports': member.can_view_reports,
                'can_approve_reports': member.can_approve_reports,
                'can_manage_teams': member.can_manage_teams,
                'created_at': member.date_joined.isoformat(),
            })
        
        return JsonResponse({
            'success': True,
            'team_members': members_data
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["PUT"])
@token_required
def api_update_team_member_permissions(request, member_id):
    """API endpoint to update team member permissions"""
    try:
        # Check if user can manage team members
        if request.user.role not in ['admin', 'state_chairman', 'district_chairman']:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get the team member
        try:
            member = CustomUser.objects.get(id=member_id)
        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'Team member not found'}, status=404)
        
        # Check if user can manage this specific member
        if not request.user.can_access_user(member):
            return JsonResponse({'error': 'Access denied to this team member'}, status=403)
        
        # Parse request data
        data = json.loads(request.body)
        
        # Update permissions
        if 'can_view_reports' in data:
            member.can_view_reports = data['can_view_reports']
        if 'can_approve_reports' in data:
            member.can_approve_reports = data['can_approve_reports']
        if 'can_manage_teams' in data:
            member.can_manage_teams = data['can_manage_teams']
        
        member.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Permissions updated successfully',
            'member': {
                'id': member.id,
                'can_view_reports': member.can_view_reports,
                'can_approve_reports': member.can_approve_reports,
                'can_manage_teams': member.can_manage_teams,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)


# New API endpoints for team and sub-authority management

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_get_team_members_new(request):
    """API endpoint to get team members for the current authority"""
    try:
        # Check if user can view team members
        if request.user.role not in ['admin', 'state_chairman', 'district_chairman', 'nagar_panchayat_chairman']:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get team members
        team_members = TeamMember.objects.filter(
            authority=request.user,
            is_active=True
        )
        
        # Convert to list of dictionaries
        members_data = []
        for team_member in team_members:
            members_data.append({
                'id': team_member.id,
                'first_name': team_member.first_name,
                'last_name': team_member.last_name,
                'email': team_member.email,
                'phone_number': team_member.phone_number,
                'role': team_member.get_role_display(),
                'designation': team_member.designation or '',
                'state': team_member.state or '',
                'district': team_member.district or '',
                'nagar_panchayat': team_member.nagar_panchayat or '',
                'village': team_member.village or '',
                'address': team_member.address or '',
                'government_service_id': team_member.government_service_id or '',
                'document_proof': request.build_absolute_uri(team_member.document_proof.url) if team_member.document_proof else '',
                'can_view_reports': team_member.can_view_reports,
                'can_approve_reports': team_member.can_approve_reports,
                'can_manage_teams': team_member.can_manage_teams,
                'assigned_date': team_member.assigned_date.isoformat(),
            })
        
        return JsonResponse({
            'success': True,
            'team_members': members_data
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_get_sub_authorities(request):
    try:
        if request.user.role not in ['admin', 'state_chairman']:
            return JsonResponse({'error': 'Access denied'}, status=403)

        sub_authorities = SubAuthority.objects.filter(
            creator=request.user,
            is_active=True
        ).order_by('-created_date')

        data = []
        for sa in sub_authorities:
            data.append({
                'id': sa.id,
                'first_name': sa.first_name,
                'middle_name': sa.middle_name,
                'last_name': sa.last_name,
                'email': sa.email,
                'phone_number': sa.phone_number,
                'role': sa.role,
                'custom_role': sa.custom_role,
                'state': sa.state,
                'district': sa.district,
                'nagar_panchayat': sa.nagar_panchayat,
                'village': sa.village,
                'address': sa.address,
                'government_service_id': sa.government_service_id,
                'can_view_reports': sa.can_view_reports,
                'can_approve_reports': sa.can_approve_reports,
                'can_manage_teams': sa.can_manage_teams,
                'created_date': sa.created_date.isoformat(),
                'is_active': sa.is_active,
            })

        return JsonResponse({
            'success': True,
            'sub_authorities': data
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@token_required
def api_add_team_member(request):
    """API endpoint to add a team member"""
    try:
        # Check if user can manage team members
        if request.user.role not in ['admin', 'state_chairman', 'district_chairman', 'nagar_panchayat_chairman']:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Parse request data
        data = json.loads(request.body)
        member_id = data.get('member_id')
        designation = data.get('designation', '')
        team_role = data.get('team_role', '')
        permissions = data.get('permissions', {})
        
        if not member_id:
            return JsonResponse({'error': 'Member ID is required'}, status=400)
        
        # Get the member
        try:
            member = CustomUser.objects.get(id=member_id, role='other')
        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'Member not found or invalid role'}, status=404)
        
        # Check if member is already in team
        if TeamMember.objects.filter(authority=request.user, member=member).exists():
            return JsonResponse({'error': 'Member is already in your team'}, status=400)
        
        # Create team member
        team_member = TeamMember.objects.create(
            authority=request.user,
            member=member,
            designation=designation,
            permissions={
                **permissions,
                'team_role': team_role
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Team member added successfully',
            'team_member': {
                'id': team_member.id,
                'member_id': member.id,
                'first_name': member.first_name,
                'last_name': member.last_name,
                'email': member.email,
                'designation': team_member.designation,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@token_required
def api_create_sub_authority(request):
    """API endpoint to create a sub-authority"""
    try:
        # Check if user can create sub-authorities (only state-level or admin)
        if request.user.role not in ['admin', 'state_chairman']:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Handle file upload with FormData
        form = SubAuthorityCreationForm(request.POST, request.FILES, creator=request.user)
        
        if not form.is_valid():
            return JsonResponse({'error': 'Invalid form data', 'errors': form.errors}, status=400)
        
        # Create the new sub-authority
        sub_authority = form.save()
        
        response_data = {
            'success': True,
            'message': f'{sub_authority.get_role_display()} created successfully!',
            'sub_authority': {
                'id': sub_authority.id,
                'name': sub_authority.get_full_name(),
                'email': sub_authority.email,
                'role': sub_authority.get_role_display(),
                'state': sub_authority.state or '',
                'district': sub_authority.district or '',
                'nagar_panchayat': sub_authority.nagar_panchayat or '',
                'village': sub_authority.village or '',
                'address': sub_authority.address or '',
                'phone_number': sub_authority.phone_number or '',
                'government_service_id': sub_authority.government_service_id or '',
                'custom_role': sub_authority.custom_role or '',
                'document_proof': request.build_absolute_uri(sub_authority.document_proof.url) if sub_authority.document_proof else '',
                'can_view_reports': sub_authority.can_view_reports,
                'can_approve_reports': sub_authority.can_approve_reports,
                'can_manage_teams': sub_authority.can_manage_teams,
                'created_date': sub_authority.created_date.isoformat(),
                'creator': sub_authority.creator.get_full_name(),
            }
        }
        
        return JsonResponse(response_data)
            
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
@token_required
def api_remove_team_member_new(request, team_member_id):
    """API endpoint to remove a team member"""
    try:
        # Check if user can manage team members
        if request.user.role not in ['admin', 'state_chairman', 'district_chairman', 'nagar_panchayat_chairman']:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get the team member
        try:
            team_member = TeamMember.objects.get(id=team_member_id, authority=request.user)
        except TeamMember.DoesNotExist:
            return JsonResponse({'error': 'Team member not found'}, status=404)
        
        # Remove the team member
        team_member.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Team member removed successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_get_authority_info(request):
    """API endpoint to get current authority information including location"""
    try:
        # Check if user is an authority
        if request.user.role not in ['admin', 'state_chairman', 'district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch']:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get authority information
        authority_data = {
            'id': request.user.id,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'role': request.user.role,
            'role_display': request.user.get_role_display(),
            'state': request.user.state or '',
            'district': request.user.district or '',
            'nagar_panchayat': request.user.nagar_panchayat or '',
            'village': request.user.village or '',
            'current_designation': request.user.current_designation or '',
            # capability flags indicate what this authority can do (backend-enforced)
            'can_create_sub_authority': True if request.user.role == 'state_chairman' else False,
            'can_create_team_member': True if request.user.role == 'state_chairman' else False,
            'can_create_sub_authority_team_member': True if request.user.role == 'district_chairman' else False,
            'can_view_reports': request.user.can_view_reports,
            'can_approve_reports': request.user.can_approve_reports,
            'can_manage_teams': request.user.can_manage_teams,
        }
        
        # Add location display based on role
        location_parts = []
        if request.user.state:
            location_parts.append(request.user.state)
        if request.user.district:
            location_parts.append(request.user.district)
        if request.user.nagar_panchayat:
            location_parts.append(request.user.nagar_panchayat)
        if request.user.village:
            location_parts.append(request.user.village)
        
        authority_data['location_display'] = ', '.join(location_parts)
        
        return JsonResponse({
            'success': True,
            'authority': authority_data
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@token_required
def api_create_team_member(request):
    """API endpoint to create a team member"""
    try:
        # Check if user can create team members (only state-level or admin)
        if request.user.role not in ['admin', 'state_chairman']:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Handle file upload with FormData
        form = TeamMemberCreationForm(request.POST, request.FILES, authority=request.user)
        
        if not form.is_valid():
            return JsonResponse({'error': 'Invalid form data', 'errors': form.errors}, status=400)
        
        # Create the new team member
        team_member = form.save()
        
        response_data = {
            'success': True,
            'message': f'Team member created successfully!',
            'team_member': {
                'id': team_member.id,
                'first_name': team_member.first_name,
                'middle_name': team_member.middle_name,
                'last_name': team_member.last_name,
                'email': team_member.email,
                'role': team_member.get_role_display(),
                'state': team_member.state or '',
                'district': team_member.district or '',
                'nagar_panchayat': team_member.nagar_panchayat or '',
                'village': team_member.village or '',
                'address': team_member.address or '',
                'phone_number': team_member.phone_number or '',
                'government_service_id': team_member.government_service_id or '',
                'designation': team_member.designation or '',
                'document_proof': request.build_absolute_uri(team_member.document_proof.url) if team_member.document_proof else None,
                'can_view_reports': team_member.can_view_reports,
                'can_approve_reports': team_member.can_approve_reports,
                'can_manage_teams': team_member.can_manage_teams,
                'assigned_date': team_member.assigned_date.isoformat(),
                'authority': team_member.authority.get_full_name(),
            }
        }
        
        return JsonResponse(response_data)
            
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@token_required
def api_create_sub_authority_team_member(request):
    """API endpoint to create a sub-authority team member"""
    try:
        # Check if user can create sub-authority team members (district chairman, etc.)
        if request.user.role not in ['district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch']:
            return JsonResponse({'error': 'Access denied. Only sub-authorities can create team members.'}, status=403)
        
        # Handle file upload with FormData
        form = SubAuthorityTeamMemberCreationForm(request.POST, request.FILES, sub_authority=request.user)
        
        if not form.is_valid():
            return JsonResponse({'error': 'Invalid form data', 'errors': form.errors}, status=400)
        
        # Create the new sub-authority team member
        team_member = form.save()
        
        response_data = {
            'success': True,
            'message': f'Sub-authority team member created successfully!',
            'team_member': {
                'id': team_member.id,
                'name': team_member.get_full_name(),
                'email': team_member.email,
                'role': team_member.get_role_display(),
                'state': team_member.state or '',
                'district': team_member.district or '',
                'nagar_panchayat': team_member.nagar_panchayat or '',
                'village': team_member.village or '',
                'address': team_member.address or '',
                'phone_number': team_member.phone_number or '',
                'government_service_id': team_member.government_service_id or '',
                'designation': team_member.designation or '',
                'document_proof': request.build_absolute_uri(team_member.document_proof.url) if team_member.document_proof else '',
                'can_view_reports': team_member.can_view_reports,
                'can_approve_reports': team_member.can_approve_reports,
                'can_manage_teams': team_member.can_manage_teams,
                'created_date': team_member.assigned_date.isoformat(),
                'sub_authority': team_member.sub_authority.get_full_name(),
            }
        }
        
        return JsonResponse(response_data)
            
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@token_required
def api_get_sub_authority_team_members(request):
    """API endpoint to get sub-authority team members"""
    try:
        # Check if user can view sub-authority team members
        if request.user.role not in ['district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch']:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get team members for this sub-authority
        team_members = SubAuthorityTeamMember.objects.filter(
            sub_authority=request.user,
            is_active=True
        ).order_by('-assigned_date')
        
        team_members_data = []
        for member in team_members:
            team_members_data.append({
                'id': member.id,
                'first_name': member.first_name,
                'middle_name': member.middle_name,
                'last_name': member.last_name,
                'email': member.email,
                'role': member.get_role_display(),
                'state': member.state or '',
                'district': member.district or '',
                'nagar_panchayat': member.nagar_panchayat or '',
                'village': member.village or '',
                'address': member.address or '',
                'phone_number': member.phone_number or '',
                'government_service_id': member.government_service_id or '',
                'designation': member.designation or '',
                'document_proof': request.build_absolute_uri(member.document_proof.url) if member.document_proof else '',
                'can_view_reports': member.can_view_reports,
                'can_approve_reports': member.can_approve_reports,
                'can_manage_teams': member.can_manage_teams,
                'created_date': member.assigned_date.isoformat(),
                'sub_authority': member.sub_authority.get_full_name(),
            })
        
        return JsonResponse({
            'success': True,
            'team_members': team_members_data
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
@token_required
def api_remove_sub_authority_team_member(request, member_id):
    """API endpoint to remove a sub-authority team member"""
    try:
        # Check if user can remove sub-authority team members
        if request.user.role not in ['district_chairman', 'nagar_panchayat_chairman', 'village_sarpanch']:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get the team member
        try:
            team_member = SubAuthorityTeamMember.objects.get(
                id=member_id,
                sub_authority=request.user,
                is_active=True
            )
        except SubAuthorityTeamMember.DoesNotExist:
            return JsonResponse({'error': 'Team member not found'}, status=404)
        
        # Deactivate the team member
        team_member.is_active = False
        team_member.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Team member removed successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)


# AI-Verification service
@csrf_exempt
@require_http_methods(["POST"])
@token_required
def api_verify_image(request):
    try:
        image = request.FILES.get("image")
        hazard_type = request.POST.get("hazard_type")
        description = request.POST.get("description", "")

        if not image:
            return JsonResponse({"error": "No image provided"}, status=400)

        result = verify_image_endpoint(
            image_data=image.read(),
            hazard_type=hazard_type,
            description=description,
            filename=image.name
        )

        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
