from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re

class RegistrationForm(forms.Form):
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dany jhonson'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'dany@gmail.com '}))
    phone = forms.CharField(max_length=10, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder':'+91 0987654321'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}))
    # address = forms.CharField(
    #     widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': '201, Second Floor, IT Tower 4 InfoCity Gate - 1, Infocity', 'rows': 3}),
    #     required=False 
    # )

    def clean_email(self):
        email = self.cleaned_data.get('email').lower()
        if User.objects.filter(username=email).exists():
            raise ValidationError("Email already registered!")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        # Basic regex to ensure it's not empty and has enough digits
        if not re.match(r'^\+?1?\d{9,15}$', phone.replace(" ", "")):
            raise ValidationError("Enter a valid phone number.")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise ValidationError("Passwords do not match!")

        if password and name:
            if name.lower() in password.lower() or password.lower() in name.lower():
                raise ValidationError("Password is too similar to your name!")

            if len(password) < 8 or not re.search(r'[A-Z]', password) or \
               not re.search(r'[a-z]', password) or not re.search(r'[0-9]', password) or \
               not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                raise ValidationError("Password must be strong (8+ chars, A-Z, a-z, 0-9, special char).")

        return cleaned_data

class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Old Password'}))
    new_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New Password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm New Password'}))

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password != confirm_password:
            raise ValidationError("New passwords do not match!")

        # Strong Password Check (Same as your Registration Logic)
        if new_password:
            if len(new_password) < 8:
                raise ValidationError("Password must be at least 8 characters long.")
            if not re.search(r'[A-Z]', new_password):
                raise ValidationError("Password must contain at least one uppercase letter.")
            if not re.search(r'[0-9]', new_password):
                raise ValidationError("Password must contain at least one digit.")
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
                raise ValidationError("Password must contain at least one special character.")
        
        return cleaned_data