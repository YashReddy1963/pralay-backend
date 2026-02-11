"""
URL configuration for Pralay project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import verification_views, hazard_report_views, connection_views, take_action_views, analytics_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls')),
    # AI Verification API endpoints
    path('api/verify-image/', verification_views.verify_image_api, name='verify_image'),
    path('api/verify-video/', verification_views.verify_video_api, name='verify_video'),
    path('api/verify-images/', verification_views.batch_verify_images, name='batch_verify_images'),
    path('api/verification-info/', verification_views.verification_service_info, name='verification_info'),
    
    # Hazard Report API endpoints
    path('api/submit-hazard-report/', hazard_report_views.SubmitHazardReportView.as_view(), name='submit_hazard_report'),
    path('api/hazard-reports/', hazard_report_views.GetHazardReportsView.as_view(), name='get_hazard_reports'),
    path('api/map-hazard-reports/', hazard_report_views.GetMapHazardReportsView.as_view(), name='get_map_hazard_reports'),
    path('api/update-report-status/', hazard_report_views.UpdateHazardReportStatusView.as_view(), name='update_report_status'),
    path('api/bulk-update-reports/', hazard_report_views.BulkUpdateHazardReportsView.as_view(), name='bulk_update_reports'),
    path('api/bulk-delete-reports/', hazard_report_views.BulkDeleteHazardReportsView.as_view(), name='bulk_delete_reports'),
    path('api/hazard-reports/<str:report_id>/delete/', hazard_report_views.DeleteHazardReportView.as_view(), name='delete_hazard_report'),
    
            # Debug endpoints (for troubleshooting)
            path('api/test-user-reports/', hazard_report_views.TestUserReportsView.as_view(), name='test_user_reports'),
            path('api/debug-reports/', hazard_report_views.DebugReportsView.as_view(), name='debug_reports'),
            path('api/test-hazard-reports/', hazard_report_views.TestHazardReportsEndpointView.as_view(), name='test_hazard_reports'),
            path('api/test-email/', hazard_report_views.TestEmailNotificationView.as_view(), name='test_email'),
            
    # Take Action API endpoints
    path('api/take-action/', take_action_views.take_action_endpoint, name='take_action'),
    path('api/take-action/team-members/', take_action_views.get_team_members_endpoint, name='get_take_action_team_members'),
    path('api/take-action/twiml/', take_action_views.twiml_endpoint, name='twiml_endpoint'),
    path('api/test-auth/', take_action_views.test_auth_endpoint, name='test_auth'),
    
    # Analytics API endpoints
    path('api/analytics/', analytics_views.analytics_data_endpoint, name='analytics_data'),
    
    # Connection and service discovery endpoints
    path('api/connection-info/', connection_views.connection_info, name='connection_info'),
    path('api/health/', connection_views.health_check, name='health_check'),
        ]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
