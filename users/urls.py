from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/user/', views.dashboard_user, name='dashboard_user'),
    path('dashboard/authority/', views.dashboard_authority, name='dashboard_authority'),
    path('dashboard/admin/', views.dashboard_admin, name='dashboard_admin'),
    path('admin/create-authority/', views.create_authority, name='create_authority'),
    path('admin/manage-authorities/', views.manage_authorities, name='manage_authorities'),
    path('api/create-authority/', views.api_create_authority, name='api_create_authority'),
    
    # API endpoints for frontend
    path('api/auth/send-otp/', views.api_send_otp, name='api_send_otp'),
    path('api/auth/verify-otp/', views.api_verify_otp, name='api_verify_otp'),
    path('api/auth/register/', views.api_register, name='api_register'),
    path('api/auth/login/', views.api_login, name='api_login'),
    path('api/auth/logout/', views.api_logout, name='api_logout'),
    path('api/auth/refresh/', views.api_refresh_token, name='api_refresh_token'),
    path('api/auth/csrf-token/', views.api_get_csrf_token, name='api_get_csrf_token'),
    path('api/test-auth/', views.api_test_auth, name='api_test_auth'),
    path('api/officials/', views.api_get_officials, name='api_get_officials'),
    path('api/officials/<int:official_id>/details/', views.api_get_official_details, name='api_get_official_details'),
    path('api/officials/<int:official_id>/activity/', views.api_get_official_activity, name='api_get_official_activity'),
    path('api/officials/<int:official_id>/permissions/', views.api_update_official_permissions, name='api_update_official_permissions'),
    
    # Authority Management API endpoints
    path('api/authority/team-members/', views.api_get_authority_team_members, name='api_get_authority_team_members'),
    path('api/authority/sub-authorities/', views.api_get_authority_sub_authorities, name='api_get_authority_sub_authorities'),
    path('api/authority/team-members/<int:member_id>/remove/', views.api_remove_team_member, name='api_remove_team_member'),
    
    # Team Management API endpoints
    path('api/team-members/', views.api_get_team_members, name='api_get_team_members'),
    path('api/team-members/<int:member_id>/permissions/', views.api_update_team_member_permissions, name='api_update_team_member_permissions'),
    path('api/team-members/<int:member_id>/remove/', views.api_remove_team_member, name='api_remove_team_member'),
    
    # New Team and Sub-Authority Management API endpoints
    path('api/team-members-new/', views.api_get_team_members_new, name='api_get_team_members_new'),
    path('api/sub-authorities/', views.api_get_sub_authorities, name='api_get_sub_authorities'),
    path('api/add-team-member/', views.api_add_team_member, name='api_add_team_member'),
    path('api/create-sub-authority/', views.api_create_sub_authority, name='api_create_sub_authority'),
    path('api/create-team-member/', views.api_create_team_member, name='api_create_team_member'),
    path('api/remove-team-member-new/<int:team_member_id>/', views.api_remove_team_member_new, name='api_remove_team_member_new'),
    path('api/authority-info/', views.api_get_authority_info, name='api_get_authority_info'),
    
    # Sub-Authority Team Member Management API endpoints
    path('api/sub-authority/team-members/', views.api_get_sub_authority_team_members, name='api_get_sub_authority_team_members'),
    path('api/sub-authority/create-team-member/', views.api_create_sub_authority_team_member, name='api_create_sub_authority_team_member'),
    path('api/sub-authority/team-members/<int:member_id>/remove/', views.api_remove_sub_authority_team_member, name='api_remove_sub_authority_team_member'),
]
