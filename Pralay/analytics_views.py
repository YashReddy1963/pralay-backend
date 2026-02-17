from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from users.models import OceanHazardReport, CustomUser
from users.authentication import token_required
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET"])
@token_required
def analytics_data_endpoint(request):
    """
    API endpoint to get analytics data for the dashboard
    Returns data for charts and metrics
    """
    try:
        # Get date range from query parameters (default to last 30 days)
        days = int(request.GET.get('days', 30))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get all reports in the date range
        reports = OceanHazardReport.objects.filter(
            reported_at__gte=start_date,
            reported_at__lte=end_date
        )
        
        # Calculate key metrics
        total_reports = reports.count()
        verified_reports = reports.filter(status='verified').count()
        pending_reports = reports.filter(status='pending').count()
        critical_incidents = reports.filter(emergency_level='critical').count()
        
        # Calculate verification rate
        verification_rate = (verified_reports / total_reports * 100) if total_reports > 0 else 0
        
        # Calculate average response time (simplified - using reviewed_at - reported_at)
        reviewed_reports = reports.filter(reviewed_at__isnull=False)
        if reviewed_reports.exists():
            total_response_time = sum([
                (report.reviewed_at - report.reported_at).total_seconds() / 3600  # Convert to hours
                for report in reviewed_reports
            ])
            avg_response_time = total_response_time / reviewed_reports.count()
        else:
            avg_response_time = 0
        
        # Weekly trends data (last 7 days)
        weekly_data = []
        for i in range(7):
            date = end_date - timedelta(days=i)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_reports = reports.filter(
                reported_at__gte=day_start,
                reported_at__lt=day_end
            )
            
            weekly_data.append({
                'day': date.strftime('%a'),  # Mon, Tue, etc.
                'reports': day_reports.count(),
                'verified': day_reports.filter(status='verified').count(),
                'date': date.strftime('%Y-%m-%d')
            })
        
        # Reverse to get chronological order (oldest first)
        weekly_data.reverse()
        
        # Hazard type distribution
        hazard_types = reports.values('hazard_type').annotate(count=Count('hazard_type')).order_by('-count')
        hazard_distribution = []
        
        for hazard in hazard_types:
            hazard_type = hazard['hazard_type']
            count = hazard['count']
            percentage = (count / total_reports * 100) if total_reports > 0 else 0
            
            # Get display name
            display_name = dict(OceanHazardReport.HAZARD_TYPE_CHOICES).get(hazard_type, hazard_type)
            
            hazard_distribution.append({
                'type': display_name,
                'count': count,
                'percentage': round(percentage, 1)
            })
        
        # Citizen participation data (reports by day for bar chart)
        citizen_participation = weekly_data.copy()  # Same as weekly trends for now
        
        # Location hotspots (top 5 locations by report count)
        location_stats = reports.values('city', 'district', 'state').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        hotspots = []
        for location in location_stats:
            city = location['city'] or 'Unknown City'
            district = location['district'] or 'Unknown District'
            state = location['state'] or 'Unknown State'
            
            # Determine severity based on count
            count = location['count']
            if count >= 10:
                severity = 'High'
            elif count >= 5:
                severity = 'Medium'
            else:
                severity = 'Low'
            
            hotspots.append({
                'location': f"{city}, {district}",
                'reports': count,
                'severity': severity,
                'state': state
            })
        
        # Calculate trends (compare with previous period)
        prev_start_date = start_date - timedelta(days=days)
        prev_reports = OceanHazardReport.objects.filter(
            reported_at__gte=prev_start_date,
            reported_at__lt=start_date
        )
        
        prev_total = prev_reports.count()
        prev_verified = prev_reports.filter(status='verified').count()
        
        # Calculate percentage changes
        reports_change = ((total_reports - prev_total) / prev_total * 100) if prev_total > 0 else 0
        verified_change = ((verified_reports - prev_verified) / prev_verified * 100) if prev_verified > 0 else 0
        
        return JsonResponse({
            'success': True,
            'data': {
                'metrics': {
                    'totalReports': total_reports,
                    'verifiedReports': verified_reports,
                    'pendingReports': pending_reports,
                    'criticalIncidents': critical_incidents,
                    'verificationRate': round(verification_rate, 1),
                    'avgResponseTime': round(avg_response_time, 1),
                    'reportsChange': round(reports_change, 1),
                    'verifiedChange': round(verified_change, 1)
                },
                'weeklyTrends': weekly_data,
                'hazardDistribution': hazard_distribution,
                'citizenParticipation': citizen_participation,
                'hotspots': hotspots,
                'dateRange': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': days
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error in analytics_data_endpoint: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Internal server error: {str(e)}'
        }, status=500)
