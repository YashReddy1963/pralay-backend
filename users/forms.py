from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.hashers import make_password
from .models import CustomUser, TeamMember, SubAuthority, SubAuthorityTeamMember

class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, label='First Name')
    last_name = forms.CharField(max_length=30, required=True, label='Last Name')
    email = forms.EmailField(required=True, label='Email')
    phone_number = forms.CharField(max_length=15, required=True, label='Phone Number')
    
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'password1', 'password2')
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and (len(phone_number) < 10 or len(phone_number) > 15 or not phone_number.isdigit()):
            raise forms.ValidationError('Phone number must be between 10-15 digits.')
        return phone_number

class AuthorityCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, label='First Name')
    middle_name = forms.CharField(max_length=100, required=False, label='Middle Name')
    last_name = forms.CharField(max_length=30, required=True, label='Last Name')
    email = forms.EmailField(required=True, label='Email Address')
    phone_number = forms.CharField(max_length=15, required=True, label='Phone Number')
    role = forms.ChoiceField(choices=[
        ('state_chairman', 'State Chairman'),
        ('district_chairman', 'District Chairman'),
        ('nagar_panchayat_chairman', 'Nagar Panchayat Chairman'),
        ('village_sarpanch', 'Village Sarpanch'),
        ('other', 'Other'),
    ], required=True, label='Role')
    
    # Location fields
    state = forms.CharField(max_length=100, required=False, label='State')
    district = forms.CharField(max_length=100, required=False, label='District')
    village = forms.CharField(max_length=100, required=False, label='Village')
    nagar_panchayat = forms.CharField(max_length=100, required=False, label='Nagar Panchayat')
    address = forms.CharField(max_length=300, required=False, label='Address')
    
    # Authority specific fields
    government_service_id = forms.CharField(max_length=100, required=False, label='Government Service ID')
    current_designation = forms.CharField(max_length=200, required=False, label='Current Designation')
    custom_role = forms.CharField(max_length=100, required=False, label='Custom Role')
    service_card_proof = forms.FileField(required=False, label='Service Card / ID Proof')
    
    # Permissions
    can_view_reports = forms.BooleanField(required=False, label='Can View Reports')
    can_approve_reports = forms.BooleanField(required=False, label='Can Approve Reports')
    can_manage_teams = forms.BooleanField(required=False, label='Can Manage Teams')
    
    class Meta:
        model = CustomUser
        fields = ('first_name', 'middle_name', 'last_name', 'email', 'phone_number', 'role', 
                 'state', 'district', 'village', 'nagar_panchayat', 'address',
                 'government_service_id', 'current_designation', 'custom_role', 'can_view_reports', 'can_approve_reports', 'can_manage_teams',
                 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator', None)
        super().__init__(*args, **kwargs)
        
        # Set role choices based on creator's role
        if self.creator:
            if self.creator.role == 'admin':
                self.fields['role'].choices = [
                    ('state_chairman', 'State Chairman'),
                    ('district_chairman', 'District Chairman'),
                    ('nagar_panchayat_chairman', 'Nagar Panchayat Chairman'),
                    ('village_sarpanch', 'Village Sarpanch'),
                    ('other', 'Other'),
                ]
            elif self.creator.role == 'state_chairman':
                self.fields['role'].choices = [
                    ('district_chairman', 'District Chairman'),
                    ('other', 'Other'),
                ]
                self.fields['state'].initial = self.creator.state
                self.fields['state'].widget.attrs['readonly'] = True
            elif self.creator.role == 'district_chairman':
                self.fields['role'].choices = [
                    ('nagar_panchayat_chairman', 'Nagar Panchayat Chairman'),
                    ('other', 'Other'),
                ]
                self.fields['state'].initial = self.creator.state
                self.fields['district'].initial = self.creator.district
                self.fields['state'].widget.attrs['readonly'] = True
                self.fields['district'].widget.attrs['readonly'] = True
            elif self.creator.role == 'nagar_panchayat_chairman':
                self.fields['role'].choices = [
                    ('village_sarpanch', 'Village Sarpanch'),
                    ('other', 'Other'),
                ]
                self.fields['state'].initial = self.creator.state
                self.fields['district'].initial = self.creator.district
                self.fields['nagar_panchayat'].initial = self.creator.nagar_panchayat
                self.fields['state'].widget.attrs['readonly'] = True
                self.fields['district'].widget.attrs['readonly'] = True
                self.fields['nagar_panchayat'].widget.attrs['readonly'] = True
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and (len(phone_number) < 10 or len(phone_number) > 15 or not phone_number.isdigit()):
            raise forms.ValidationError('Phone number must be between 10-15 digits.')
        return phone_number
    
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        custom_role = cleaned_data.get('custom_role')
        
        # If role is 'other', custom_role is required
        if role == 'other' and not custom_role:
            raise forms.ValidationError("Custom role is required when selecting 'Other' role.")
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Set username to email if not provided
        if not user.username:
            user.username = self.cleaned_data['email']
        
        user.role = self.cleaned_data['role']
        user.state = self.cleaned_data.get('state')
        user.district = self.cleaned_data.get('district')
        user.village = self.cleaned_data.get('village')
        user.nagar_panchayat = self.cleaned_data.get('nagar_panchayat')
        user.address = self.cleaned_data.get('address')
        user.government_service_id = self.cleaned_data.get('government_service_id')
        user.custom_role = self.cleaned_data.get('custom_role')
        user.can_view_reports = self.cleaned_data.get('can_view_reports', False)
        user.can_approve_reports = self.cleaned_data.get('can_approve_reports', False)
        user.can_manage_teams = self.cleaned_data.get('can_manage_teams', False)
        user.created_by = self.creator
        
        if commit:
            user.save()
        return user

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'autofocus': True}))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Email'

class TeamMemberForm(forms.ModelForm):
    """Form for managing existing team members"""
    class Meta:
        model = TeamMember
        fields = ['designation', 'can_view_reports', 'can_approve_reports', 'can_manage_teams', 'is_active']
    
    def __init__(self, *args, **kwargs):
        self.authority = kwargs.pop('authority', None)
        super().__init__(*args, **kwargs)

class SubAuthorityForm(forms.ModelForm):
    """Form for managing existing sub-authorities"""
    class Meta:
        model = SubAuthority
        fields = ['is_active']
    
    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator', None)
        super().__init__(*args, **kwargs)


class SubAuthorityCreationForm(forms.ModelForm):
    """Form for creating sub-authorities with all required fields"""
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput,
        min_length=8,
        help_text='Password must be at least 8 characters long.'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput,
        help_text='Enter the same password as before, for verification.'
    )
    
    class Meta:
        model = SubAuthority
        fields = [
            'first_name', 'middle_name', 'last_name', 'email', 'phone_number',
            'role', 'custom_role', 'state', 'district', 'nagar_panchayat', 
            'village', 'address', 'government_service_id', 'document_proof',
            'can_view_reports', 'can_approve_reports', 'can_manage_teams',
            'password1', 'password2'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.creator = kwargs.pop('creator', None)
        super().__init__(*args, **kwargs)
        
        # Set role choices based on creator's role
        if self.creator:
            if self.creator.role == 'admin':
                self.fields['role'].choices = [
                    ('state_chairman', 'State Chairman'),
                    ('district_chairman', 'District Chairman'),
                    ('nagar_panchayat_chairman', 'Nagar Panchayat Chairman'),
                    ('village_sarpanch', 'Village Sarpanch'),
                    ('other', 'Other'),
                ]
            elif self.creator.role == 'state_chairman':
                self.fields['role'].choices = [
                    ('district_chairman', 'District Chairman'),
                    ('other', 'Other'),
                ]
                self.fields['state'].initial = self.creator.state
                self.fields['state'].widget.attrs['readonly'] = True
            elif self.creator.role == 'district_chairman':
                self.fields['role'].choices = [
                    ('nagar_panchayat_chairman', 'Nagar Panchayat Chairman'),
                    ('other', 'Other'),
                ]
                self.fields['state'].initial = self.creator.state
                self.fields['district'].initial = self.creator.district
                self.fields['state'].widget.attrs['readonly'] = True
                self.fields['district'].widget.attrs['readonly'] = True
            elif self.creator.role == 'nagar_panchayat_chairman':
                self.fields['role'].choices = [
                    ('village_sarpanch', 'Village Sarpanch'),
                    ('other', 'Other'),
                ]
                self.fields['state'].initial = self.creator.state
                self.fields['district'].initial = self.creator.district
                self.fields['nagar_panchayat'].initial = self.creator.nagar_panchayat
                self.fields['state'].widget.attrs['readonly'] = True
                self.fields['district'].widget.attrs['readonly'] = True
                self.fields['nagar_panchayat'].widget.attrs['readonly'] = True
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and (len(phone_number) < 10 or len(phone_number) > 15 or not phone_number.isdigit()):
            raise forms.ValidationError('Phone number must be between 10-15 digits.')
        return phone_number
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        role = cleaned_data.get('role')
        custom_role = cleaned_data.get('custom_role')
        
        # Check password match
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match.")
        
        # If role is 'other', custom_role is required
        if role == 'other' and not custom_role:
            raise forms.ValidationError("Custom role is required when selecting 'Other' role.")
        
        return cleaned_data
    
    def save(self, commit=True):
        sub_authority = super().save(commit=False)
        
        # Set the creator
        sub_authority.creator = self.creator
        
        # Hash and store the password
        password = self.cleaned_data['password1']
        sub_authority.password_hash = make_password(password)
        
        if commit:
            sub_authority.save()
        return sub_authority


class TeamMemberCreationForm(forms.ModelForm):
    """Form for creating team members with all required fields"""
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput,
        help_text='Enter a strong password.'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput,
        help_text='Enter the same password as before, for verification.'
    )
    
    class Meta:
        model = TeamMember
        fields = [
            'first_name', 'middle_name', 'last_name', 'email', 'phone_number',
            'designation', 'state', 'district', 'nagar_panchayat', 
            'village', 'address', 'government_service_id', 'document_proof',
            'can_view_reports', 'can_approve_reports', 'can_manage_teams',
            'password1', 'password2'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.authority = kwargs.pop('authority', None)
        super().__init__(*args, **kwargs)
        
        # Set location fields based on authority's level
        if self.authority:
            if self.authority.state:
                self.fields['state'].initial = self.authority.state
            if self.authority.district:
                self.fields['district'].initial = self.authority.district
            if self.authority.nagar_panchayat:
                self.fields['nagar_panchayat'].initial = self.authority.nagar_panchayat
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and (len(phone_number) < 10 or len(phone_number) > 15 or not phone_number.isdigit()):
            raise forms.ValidationError('Phone number must be between 10-15 digits.')
        return phone_number
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        # Check password match
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match.")
        
        return cleaned_data
    
    def save(self, commit=True):
        team_member = super().save(commit=False)
        
        # Set the authority
        team_member.authority = self.authority
        
        # Set role as team_member
        team_member.role = 'team_member'
        
        # Hash and store the password
        password = self.cleaned_data['password1']
        team_member.password_hash = make_password(password)
        
        if commit:
            team_member.save()
        return team_member


class SubAuthorityTeamMemberCreationForm(forms.ModelForm):
    """Form for creating sub-authority team members with all required fields"""
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput,
        help_text='Enter a strong password.'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput,
        help_text='Enter the same password as before, for verification.'
    )
    
    class Meta:
        model = SubAuthorityTeamMember
        fields = [
            'first_name', 'middle_name', 'last_name', 'email', 'phone_number',
            'designation', 'state', 'district', 'nagar_panchayat', 
            'village', 'address', 'government_service_id', 'document_proof',
            'can_view_reports', 'can_approve_reports', 'can_manage_teams',
            'password1', 'password2'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.sub_authority = kwargs.pop('sub_authority', None)
        super().__init__(*args, **kwargs)
        
        # Set location fields based on sub-authority's level
        if self.sub_authority:
            if self.sub_authority.state:
                self.fields['state'].initial = self.sub_authority.state
            if self.sub_authority.district:
                self.fields['district'].initial = self.sub_authority.district
            if self.sub_authority.nagar_panchayat:
                self.fields['nagar_panchayat'].initial = self.sub_authority.nagar_panchayat
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and (len(phone_number) < 10 or len(phone_number) > 15 or not phone_number.isdigit()):
            raise forms.ValidationError('Phone number must be between 10-15 digits.')
        return phone_number
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        # Check password match
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match.")
        
        return cleaned_data
    
    def save(self, commit=True):
        team_member = super().save(commit=False)
        
        # Set the sub-authority
        team_member.sub_authority = self.sub_authority
        
        # Set role as team_member
        team_member.role = 'team_member'
        
        # Hash and store the password
        password = self.cleaned_data['password1']
        team_member.password_hash = make_password(password)
        
        if commit:
            team_member.save()
        return team_member


