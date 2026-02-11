from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import random
import string

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('state_chairman', 'State Chairman'),
        ('district_chairman', 'District Chairman'),
        ('nagar_panchayat_chairman', 'Nagar Panchayat Chairman'),
        ('village_sarpanch', 'Village Sarpanch'),
        ('other', 'Other'),
        ('admin', 'Admin'),
    ]
    
    # Override username to make it unique
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    
    # Additional name fields
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    
    # Contact information
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    
    # Role and authority information
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='user')
    custom_role = models.CharField(max_length=100, blank=True, null=True)
    
    # Location information
    state = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    nagar_panchayat = models.CharField(max_length=100, blank=True, null=True)
    village = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Government service information
    government_service_id = models.CharField(max_length=100, blank=True, null=True)
    current_designation = models.CharField(max_length=200, blank=True, null=True, help_text="Current job designation/title")
    service_card_proof = models.FileField(upload_to='authority_documents/', blank=True, null=True)
    
    # Permissions
    can_view_reports = models.BooleanField(default=False)
    can_approve_reports = models.BooleanField(default=False)
    can_manage_teams = models.BooleanField(default=False)
    
    # For tracking who created this user (for access control)
    created_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users')
    
    # Activity tracking
    last_login_time = models.DateTimeField(null=True, blank=True, help_text="Last time the user logged in")
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    def get_full_name(self):
        """Return the full name of the user"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_role_display(self):
        """Return the display name for the role"""
        return dict(self.ROLE_CHOICES).get(self.role, self.role)
    
    def can_access_user(self, target_user):
        """Check if this user can access/modify target_user based on hierarchy"""
        if self.role == 'admin':
            return True  # Admin can access everyone
        elif self.role == 'state_chairman':
            return target_user.state == self.state
        elif self.role == 'district_chairman':
            return target_user.district == self.district and target_user.state == self.state
        elif self.role == 'nagar_panchayat_chairman':
            return (target_user.nagar_panchayat == self.nagar_panchayat and 
                   target_user.district == self.district and 
                   target_user.state == self.state)
        elif self.role == 'village_sarpanch':
            return (target_user.village == self.village and 
                   target_user.nagar_panchayat == self.nagar_panchayat and 
                   target_user.district == self.district and 
                   target_user.state == self.state)
        else:
            return False  # Regular users cannot access other users
    
    def __str__(self):
        return self.email

class OTP(models.Model):
    """Model for storing OTP codes for email verification"""
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    
    @classmethod
    def generate_otp(cls, email):
        """Generate a new OTP for the given email"""
        # Delete any existing OTPs for this email
        cls.objects.filter(email=email).delete()
        
        # Generate 6-digit OTP
        otp_code = ''.join(random.choices(string.digits, k=6))
        
        # Create new OTP with 10 minutes expiry
        otp = cls.objects.create(
            email=email,
            otp_code=otp_code,
            expires_at=timezone.now() + timezone.timedelta(minutes=10)
        )
        return otp
    
    def is_valid(self):
        """Check if the OTP is still valid"""
        return not self.is_verified and timezone.now() < self.expires_at
    
    def verify(self):
        """Mark the OTP as verified"""
        self.is_verified = True
        self.save()
    
    def __str__(self):
        return f"OTP for {self.email}: {self.otp_code}"

class TeamMember(models.Model):
    """Model to represent team members under an authority"""
    # Relationship fields
    authority = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='team_members')
    assigned_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Personal Information
    first_name = models.CharField(max_length=30, default='')
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=30, default='')
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=15, default='')
    
    # Role and Authority Information (Team members have fixed role)
    role = models.CharField(max_length=50, default='team_member')
    designation = models.CharField(max_length=200, blank=True, null=True)
    
    # Location Information
    state = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    nagar_panchayat = models.CharField(max_length=100, blank=True, null=True)
    village = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Government Service Information
    government_service_id = models.CharField(max_length=100, blank=True, null=True)
    document_proof = models.FileField(upload_to='team_member_documents/', blank=True, null=True)
    
    # Permissions
    can_view_reports = models.BooleanField(default=False)
    can_approve_reports = models.BooleanField(default=False)
    can_manage_teams = models.BooleanField(default=False)
    
    # Login credentials (stored separately for security)
    password_hash = models.CharField(max_length=255, default='')  # Store hashed password
    
    class Meta:
        pass  # unique_together will be added after migration
    
    def get_full_name(self):
        """Return the full name of the team member"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_role_display(self):
        """Return the display name for the role"""
        return "Team Member"
    
    def __str__(self):
        return f"{self.get_full_name()} - Team member of {self.authority.get_full_name()}"

class SubAuthorityTeamMember(models.Model):
    """Model to represent team members under a sub-authority (district chairman, etc.)"""
    # Relationship fields
    sub_authority = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sub_authority_team_members')
    assigned_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Personal Information
    first_name = models.CharField(max_length=30, default='')
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=30, default='')
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=15, default='')
    
    # Role and Authority Information (Team members have fixed role)
    role = models.CharField(max_length=50, default='team_member')
    designation = models.CharField(max_length=200, blank=True, null=True)
    
    # Location Information
    state = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    nagar_panchayat = models.CharField(max_length=100, blank=True, null=True)
    village = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Government Service Information
    government_service_id = models.CharField(max_length=100, blank=True, null=True)
    document_proof = models.FileField(upload_to='sub_authority_team_member_documents/', blank=True, null=True)
    
    # Permissions
    can_view_reports = models.BooleanField(default=False)
    can_approve_reports = models.BooleanField(default=False)
    can_manage_teams = models.BooleanField(default=False)
    
    # Login credentials (stored separately for security)
    password_hash = models.CharField(max_length=255, default='')  # Store hashed password
    
    class Meta:
        pass  # unique_together will be added after migration
    
    def get_full_name(self):
        """Return the full name of the sub-authority team member"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_role_display(self):
        """Return the display name for the role"""
        return "Sub-Authority Team Member"
    
    def __str__(self):
        return f"{self.get_full_name()} - Team member of {self.sub_authority.get_full_name()}"

class SubAuthority(models.Model):
    """Model to represent sub-authorities created by an authority"""
    ROLE_CHOICES = [
        ('state_chairman', 'State Chairman'),
        ('district_chairman', 'District Chairman'),
        ('nagar_panchayat_chairman', 'Nagar Panchayat Chairman'),
        ('village_sarpanch', 'Village Sarpanch'),
        ('other', 'Other'),
    ]
    
    # Relationship fields
    creator = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_sub_authorities')
    created_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Personal Information
    first_name = models.CharField(max_length=30, default='')
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=30, default='')
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=15, default='')
    
    # Role and Authority Information
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='other')
    custom_role = models.CharField(max_length=100, blank=True, null=True)
    
    # Location Information
    state = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    nagar_panchayat = models.CharField(max_length=100, blank=True, null=True)
    village = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Government Service Information
    government_service_id = models.CharField(max_length=100, blank=True, null=True)
    document_proof = models.FileField(upload_to='sub_authority_documents/', blank=True, null=True)
    
    # Permissions
    can_view_reports = models.BooleanField(default=False)
    can_approve_reports = models.BooleanField(default=False)
    can_manage_teams = models.BooleanField(default=False)
    
    # Login credentials (stored separately for security)
    password_hash = models.CharField(max_length=255, default='')  # Store hashed password
    
    class Meta:
        pass  # unique_together will be added after migration
    
    def get_full_name(self):
        """Return the full name of the sub-authority"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_role_display(self):
        """Return the display name for the role"""
        return dict(self.ROLE_CHOICES).get(self.role, self.role)
    
    def __str__(self):
        return f"{self.get_full_name()} - Sub-authority of {self.creator.get_full_name()}"

class RefreshToken(models.Model):
    """Model for storing refresh tokens"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='refresh_tokens')
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_revoked = models.BooleanField(default=False)
    
    @classmethod
    def generate_token(cls, user):
        """Generate a new refresh token for the user"""
        import secrets
        import hashlib
        
        # Delete any existing tokens for this user
        cls.objects.filter(user=user).delete()
        
        # Generate a secure random token
        token_string = f"{user.email}:{timezone.now().timestamp()}:{secrets.token_urlsafe(32)}"
        token = hashlib.sha256(token_string.encode()).hexdigest()
        
        # Create new refresh token with 30 days expiry
        refresh_token = cls.objects.create(
            user=user,
            token=token,
            expires_at=timezone.now() + timezone.timedelta(days=30)
        )
        return refresh_token
    
    def is_valid(self):
        """Check if the refresh token is still valid"""
        return not self.is_revoked and timezone.now() < self.expires_at
    
    def revoke(self):
        """Revoke the refresh token"""
        self.is_revoked = True
        self.save()
    
    def __str__(self):
        return f"Refresh token for {self.user.email}"

class OceanHazardReport(models.Model):
    """Model for storing ocean hazard reports submitted by citizens"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('verified', 'Verified'),
        ('discarded', 'Discarded'),
        ('under_investigation', 'Under Investigation'),
        ('resolved', 'Resolved'),
    ]
    
    HAZARD_TYPE_CHOICES = [
        ('tsunami', 'Tsunami Warning'),
        ('storm-surge', 'Storm Surge'),
        ('high-waves', 'High Waves'),
        ('flooding', 'Coastal Flooding'),
        ('debris', 'Marine Debris'),
        ('pollution', 'Water Pollution'),
        ('erosion', 'Coastal Erosion'),
        ('wildlife', 'Marine Wildlife Issue'),
        ('other', 'Other Hazard'),
    ]
    
    # Primary information
    id = models.AutoField(primary_key=True)
    report_id = models.CharField(max_length=20, unique=True, blank=True)
    
    # Citizen who reported (Foreign Key)
    reported_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='hazard_reports',
        help_text="The citizen who submitted this hazard report"
    )
    
    # Hazard details
    hazard_type = models.CharField(
        max_length=50, 
        choices=HAZARD_TYPE_CHOICES,
        help_text="Type of ocean hazard reported"
    )
    description = models.TextField(
        help_text="Detailed description of the hazard"
    )
    
    # Location information
    latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=8,
        help_text="GPS latitude coordinate"
    )
    longitude = models.DecimalField(
        max_digits=11, 
        decimal_places=8,
        help_text="GPS longitude coordinate"
    )
    country = models.CharField(max_length=100, help_text="Country where hazard occurred")
    state = models.CharField(max_length=100, help_text="State/Province where hazard occurred")
    district = models.CharField(max_length=100, help_text="District where hazard occurred")
    city = models.CharField(max_length=100, help_text="City/Town where hazard occurred")
    address = models.TextField(blank=True, null=True, help_text="Detailed address if available")
    
    # Status and verification
    status = models.CharField(
        max_length=30, 
        choices=STATUS_CHOICES, 
        default='pending',
        help_text="Current status of the hazard report"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether the hazard has been verified by authorities"
    )
    
    # Official action tracking
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_hazard_reports',
        help_text="Official who reviewed/acted on this report"
    )
    review_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Notes from the reviewing official"
    )
    
    # Timestamps
    reported_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the report was submitted"
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the report was reviewed by an official"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the report was last updated"
    )
    
    # AI Verification data
    ai_verification_score = models.FloatField(
        null=True,
        blank=True,
        help_text="AI verification confidence score"
    )
    ai_verification_details = models.JSONField(
        null=True,
        blank=True,
        help_text="Detailed AI verification results"
    )
    
    # Emergency level
    EMERGENCY_LEVEL_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    emergency_level = models.CharField(
        max_length=10,
        choices=EMERGENCY_LEVEL_CHOICES,
        default='medium',
        help_text="Assessed emergency level of the hazard"
    )
    
    # Additional metadata
    is_public = models.BooleanField(
        default=True,
        help_text="Whether this report is publicly visible"
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Tags for categorization and search"
    )
    
    class Meta:
        ordering = ['-reported_at']
        verbose_name = "Ocean Hazard Report"
        verbose_name_plural = "Ocean Hazard Reports"
        indexes = [
            models.Index(fields=['status', 'reported_at']),
            models.Index(fields=['hazard_type', 'status']),
            models.Index(fields=['state', 'district']),
            models.Index(fields=['reported_by', 'reported_at']),
        ]
    
    def save(self, *args, **kwargs):
        """Override save to generate report_id"""
        if not self.report_id:
            import random
            import string
            # Generate unique report ID: OH-YYYYMMDD-XXXXXX
            date_str = timezone.now().strftime('%Y%m%d')
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            self.report_id = f"OH-{date_str}-{random_str}"
        super().save(*args, **kwargs)
    
    def get_full_location(self):
        """Return formatted full location string"""
        location_parts = [self.city, self.district, self.state, self.country]
        return ', '.join(filter(None, location_parts))
    
    def get_gps_coordinates(self):
        """Return formatted GPS coordinates"""
        return f"{self.latitude}, {self.longitude}"
    
    def get_images(self):
        """Return all images associated with this report"""
        return self.hazard_images.all()
    
    def get_verification_status_display(self):
        """Return human-readable verification status"""
        if self.is_verified:
            return "Verified"
        elif self.status == 'discarded':
            return "Discarded"
        elif self.status == 'under_investigation':
            return "Under Investigation"
        elif self.status == 'resolved':
            return "Resolved"
        else:
            return "Pending Review"
    
    def __str__(self):
        return f"Report {self.report_id} - {self.get_hazard_type_display()} by {self.reported_by.get_full_name()}"

class HazardImage(models.Model):
    """Model for storing images associated with hazard reports"""
    
    IMAGE_TYPE_CHOICES = [
        ('primary', 'Primary Image'),
        ('evidence', 'Evidence Image'),
        ('damage', 'Damage Documentation'),
        ('location', 'Location Reference'),
        ('other', 'Other'),
    ]
    
    # Primary information
    id = models.AutoField(primary_key=True)
    
    # Foreign key to the hazard report
    hazard_report = models.ForeignKey(
        OceanHazardReport,
        on_delete=models.CASCADE,
        related_name='hazard_images',
        help_text="The hazard report this image belongs to"
    )
    
    # Image details
    image_file = models.ImageField(
        upload_to='hazard_images/%Y/%m/%d/',
        help_text="The actual image file"
    )
    image_type = models.CharField(
        max_length=20,
        choices=IMAGE_TYPE_CHOICES,
        default='evidence',
        help_text="Type/category of this image"
    )
    caption = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional caption for the image"
    )
    
    # Location data (if image has GPS coordinates)
    image_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="GPS latitude from image EXIF data"
    )
    image_longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="GPS longitude from image EXIF data"
    )
    
    # AI Verification data
    ai_verification_result = models.JSONField(
        null=True,
        blank=True,
        help_text="AI verification results for this specific image"
    )
    ai_confidence_score = models.FloatField(
        null=True,
        blank=True,
        help_text="AI confidence score for this image"
    )
    is_verified_by_ai = models.BooleanField(
        default=False,
        help_text="Whether this image passed AI verification"
    )
    
    # Metadata
    file_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes"
    )
    file_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of the image file for deduplication"
    )
    
    # Timestamps
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the image was uploaded"
    )
    
    class Meta:
        ordering = ['uploaded_at']
        verbose_name = "Hazard Image"
        verbose_name_plural = "Hazard Images"
        indexes = [
            models.Index(fields=['hazard_report', 'uploaded_at']),
            models.Index(fields=['is_verified_by_ai']),
            models.Index(fields=['file_hash']),
        ]
    
    def save(self, *args, **kwargs):
        """Override save to calculate file hash and size"""
        if self.image_file and not self.file_hash:
            import hashlib
            # Calculate file hash for deduplication
            self.image_file.seek(0)
            file_content = self.image_file.read()
            self.file_hash = hashlib.sha256(file_content).hexdigest()
            self.file_size = len(file_content)
            self.image_file.seek(0)  # Reset file pointer
        super().save(*args, **kwargs)
    
    def get_gps_coordinates(self):
        """Return formatted GPS coordinates if available"""
        if self.image_latitude and self.image_longitude:
            return f"{self.image_latitude}, {self.image_longitude}"
        return "No GPS data"
    
    def __str__(self):
        return f"Image for Report {self.hazard_report.report_id} - {self.get_image_type_display()}"