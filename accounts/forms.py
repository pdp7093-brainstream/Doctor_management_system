from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re

class RegistrationForm(forms.Form):
    name = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Full Name',
            'required': 'required'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Email Address',
            'required': 'required'
        })
    )
    phone = forms.CharField(
        max_length=15, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '9876543210',
            'required': 'required',
            'type': 'tel'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Password',
            'required': 'required',
            'autocomplete': 'new-password'
        })
    )

    def clean_name(self):
        """Name validation"""
        name = self.cleaned_data.get('name', '').strip()
        
        if len(name) < 3:
            raise ValidationError("Name must be at least 3 characters long.")
        
        if not re.match(r'^[a-zA-Z\s]+$', name):
            raise ValidationError("Name can only contain letters and spaces.")
        
        return name

    def clean_email(self):
        """Email validation - unique check"""
        email = self.cleaned_data.get('email', '').lower().strip()
        
        if not email:
            raise ValidationError("Email is required.")
        
        # Check if email already exists in User table
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered!")
        
        return email

    def clean_phone(self):
        """Phone validation - format + unique check in Patient table"""
        phone = self.cleaned_data.get('phone', '').strip()
        
        if not phone:
            raise ValidationError("Phone number is required.")
        
        # Remove common formatting characters
        cleaned_phone = re.sub(r'[\s\-\+\(\)]', '', phone)
        
        # Validate format (10-15 digits)
        if not re.match(r'^\d{10,15}$', cleaned_phone):
            raise ValidationError(
                "Enter a valid phone number (10-15 digits). "
                "Format: 9876543210 or +919876543210"
            )
        
        # Make sure it's at least 10 digits
        if len(cleaned_phone) < 10:
            raise ValidationError("Phone number must be at least 10 digits.")
        
        #  UNIQUE CHECK IN PATIENT TABLE ONLY
        from accounts.models import Patient
        if Patient.objects.filter(phone=cleaned_phone).exists():
            raise ValidationError("This phone number is already registered!")
        
        return cleaned_phone

    def clean_password(self):
        """Strong password validation"""
        password = self.cleaned_data.get('password', '')
        
        if not password:
            raise ValidationError("Password is required.")
        
        # Length check
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        
        # Uppercase check
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter (A-Z).")
        
        # Lowercase check
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter (a-z).")
        
        # Digit check
        if not re.search(r'[0-9]', password):
            raise ValidationError("Password must contain at least one number (0-9).")
        
        # Special character check
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError(
                "Password must contain at least one special character "
                "(!@#$%^&*(),.?\":{{}}|<>)."
            )
        
        return password

    def clean(self):
        """Form-level validation"""
        cleaned_data = super().clean()
        name = cleaned_data.get("name", '').strip()
        password = cleaned_data.get("password", '')
        
        # Check password similarity to name
        if password and name:
            if name.lower() in password.lower():
                raise ValidationError("Password should not contain your name.")
            if password.lower() in name.lower():
                raise ValidationError("Password should not be contained in your name.")

        return cleaned_data


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Current Password',
            'required': 'required'
        })
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'New Password (Min 8 chars)',
            'required': 'required'
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Confirm New Password',
            'required': 'required'
        })
    )

    def clean_new_password(self):
        """Strong password validation for new password"""
        new_password = self.cleaned_data.get("new_password", '')
        
        if not new_password:
            raise ValidationError("New password is required.")
        
        if len(new_password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        
        if not re.search(r'[A-Z]', new_password):
            raise ValidationError("Password must contain at least one uppercase letter (A-Z).")
        
        if not re.search(r'[a-z]', new_password):
            raise ValidationError("Password must contain at least one lowercase letter (a-z).")
        
        if not re.search(r'[0-9]', new_password):
            raise ValidationError("Password must contain at least one number (0-9).")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            raise ValidationError("Password must contain at least one special character.")
        
        return new_password

    def clean(self):
        """Form-level validation"""
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password", '')
        confirm_password = cleaned_data.get("confirm_password", '')

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError("New passwords do not match!")

        return cleaned_data


class ProfileUpdateForm(forms.Form):
    """Form for updating patient profile"""
    first_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Address'
        })
    )
    phone = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '9876543210',
            'type': 'tel'
        })
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Your Address',
            'rows': 3
        })
    )
    dob = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    gender = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Select Gender'),
            ('male', 'Male'),
            ('female', 'Female'),
            ('other', 'Other'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    bld_grop = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Select Blood Group'),
            ('A+', 'A+'), ('A-', 'A-'),
            ('B+', 'B+'), ('B-', 'B-'),
            ('O+', 'O+'), ('O-', 'O-'),
            ('AB+', 'AB+'), ('AB-', 'AB-'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    def clean_phone(self):
        """Phone validation when updating"""
        phone = self.cleaned_data.get('phone', '').strip()
        
        if not phone:
            return phone  # Optional field
        
        # Remove formatting
        cleaned_phone = re.sub(r'[\s\-\+\(\)]', '', phone)
        
        # Validate format
        if not re.match(r'^\d{10,15}$', cleaned_phone):
            raise ValidationError(
                "Enter a valid phone number (10-15 digits). "
                "Format: 9876543210"
            )
        
        return cleaned_phone

    def clean_email(self):
        """Email validation when updating"""
        email = self.cleaned_data.get('email', '').strip()
        
        if not email:
            return email  # Optional field
        
        email = email.lower()
        
        # Check if email exists (excluding current user)
        if User.objects.filter(email=email).exclude(id=self.user_id).exists():
            raise ValidationError("This email is already in use!")
        
        return email
