from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending various types of emails"""

    @staticmethod
    def send_email(subject, plain_text, to_email):
        """
        Generic SendGrid email sender
        """
        try:
            url = "https://api.sendgrid.com/v3/mail/send"

            headers = {
                "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                "Content-Type": "application/json"
            }

            data = {
                "personalizations": [
                    {
                        "to": [{"email": to_email}],
                        "subject": subject
                    }
                ],
                "from": {"email": settings.DEFAULT_FROM_EMAIL},
                "content": [
                    {
                        "type": "text/plain",
                        "value": plain_text
                    }
                ]
            }

            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 202:
                return True
            else:
                print("SendGrid error:", response.text)
                return False

        except Exception as e:
            print("SendGrid exception:", str(e))
            return False
    
    @staticmethod
    def send_hazard_verification_email(report_data, citizen_email, citizen_name):
        """
        Send email notification when a hazard report is verified
        
        Args:
            report_data: Dictionary containing report details
            citizen_email: Email address of the citizen who reported
            citizen_name: Name of the citizen who reported
        """
        try:
            subject = f"Hazard Report Verified - Report ID: {report_data.get('report_id', 'N/A')}"
            
            # Create email content
            html_content = EmailService._create_verification_email_html(report_data, citizen_name)
            plain_text_content = EmailService._create_verification_email_text(report_data, citizen_name)
            

            #send mail using sendgrid
            mail = Mail(
                from_email=settings.DEFAULT_FROM_EMAIL,
                to_emails=citizen_email,
                subject=subject,
                html_content=html_content,
                plain_text_content=plain_text_content,
            )
            
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(mail)
            logger.info(f"Hazard verification email sent successfully to {citizen_email} for report {report_data.get('report_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send hazard verification email to {citizen_email}: {e}")
            return False
    
    @staticmethod
    def _create_verification_email_html(report_data, citizen_name):
        """Create HTML content for verification email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Hazard Report Verified</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background-color: #2E7D32;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 8px 8px 0 0;
                }}
                .content {{
                    background-color: #f9f9f9;
                    padding: 20px;
                    border-radius: 0 0 8px 8px;
                }}
                .report-details {{
                    background-color: white;
                    padding: 15px;
                    margin: 15px 0;
                    border-radius: 5px;
                    border-left: 4px solid #2E7D32;
                }}
                .status-badge {{
                    background-color: #4CAF50;
                    color: white;
                    padding: 5px 10px;
                    border-radius: 15px;
                    font-size: 12px;
                    font-weight: bold;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 20px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    color: #666;
                    font-size: 12px;
                }}
                .detail-row {{
                    margin: 8px 0;
                }}
                .detail-label {{
                    font-weight: bold;
                    color: #555;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎉 Your Hazard Report Has Been Verified!</h1>
            </div>
            
            <div class="content">
                <p>Dear {citizen_name},</p>
                
                <p>Great news! Your hazard report has been verified by the authorities and action has been taken. Thank you for helping to keep our coastal areas safe.</p>
                
                <div class="report-details">
                    <h3>Report Details</h3>
                    
                    <div class="detail-row">
                        <span class="detail-label">Report ID:</span> {report_data.get('report_id', 'N/A')}
                    </div>
                    
                    <div class="detail-row">
                        <span class="detail-label">Hazard Type:</span> {report_data.get('hazard_type_display', 'N/A')}
                    </div>
                    
                    <div class="detail-row">
                        <span class="detail-label">Location:</span> {report_data.get('location', {}).get('full_location', 'N/A')}
                    </div>
                    
                    <div class="detail-row">
                        <span class="detail-label">Description:</span> {report_data.get('description', 'N/A')}
                    </div>
                    
                    <div class="detail-row">
                        <span class="detail-label">Emergency Level:</span> {report_data.get('emergency_level', 'N/A').title()}
                    </div>
                    
                    <div class="detail-row">
                        <span class="detail-label">Reported Date:</span> {report_data.get('reported_at', 'N/A')}
                    </div>
                    
                    <div class="detail-row">
                        <span class="detail-label">Verified Date:</span> {report_data.get('reviewed_at', 'N/A')}
                    </div>
                    
                    <div class="detail-row">
                        <span class="detail-label">Status:</span> 
                        <span class="status-badge">VERIFIED</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="detail-label">Reviewed By:</span> {report_data.get('reviewed_by', {}).get('name', 'District Authority')}
                    </div>
                </div>
                
                <p>Your report is now part of our official hazard database and has been shared with relevant authorities for further action if needed.</p>
                
                <p>Thank you for your contribution to coastal safety!</p>
                
                <p>Best regards,<br>
                <strong>Pralay Coastal Safety Team</strong></p>
            </div>
            
            <div class="footer">
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>© 2024 Pralay Coastal Safety System</p>
            </div>
        </body>
        </html>
        """
    
    @staticmethod
    def _create_verification_email_text(report_data, citizen_name):
        """Create plain text content for verification email"""
        return f"""
Dear {citizen_name},

Your hazard report has been verified by the authorities!

REPORT DETAILS:
- Report ID: {report_data.get('report_id', 'N/A')}
- Hazard Type: {report_data.get('hazard_type_display', 'N/A')}
- Location: {report_data.get('location', {}).get('full_location', 'N/A')}
- Description: {report_data.get('description', 'N/A')}
- Emergency Level: {report_data.get('emergency_level', 'N/A').title()}
- Reported Date: {report_data.get('reported_at', 'N/A')}
- Verified Date: {report_data.get('reviewed_at', 'N/A')}
- Status: VERIFIED
- Reviewed By: {report_data.get('reviewed_by', {}).get('name', 'District Authority')}

Your report is now part of our official hazard database and has been shared with relevant authorities.

Thank you for helping to keep our coastal areas safe!

Best regards,
Pralay Coastal Safety Team

---
This is an automated message. Please do not reply to this email.
© 2026 Pralay Coastal Safety System
        """
