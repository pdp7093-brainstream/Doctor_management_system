import re

with open('doctor/urls.py', 'r') as f:
    urls_content = f.read()

if 'path(\'register/\',' not in urls_content:
    urls_content = urls_content.replace(
        "path('login/', views.login_view, name='login'),",
        "path('login/', views.login_view, name='login'),\n    path('register/', views.register_view, name='register'),\n    path('staff/approve/<int:member_id>/', views.approve_doctor, name='approve_doctor'),\n    path('staff/reject/<int:member_id>/', views.reject_doctor, name='reject_doctor'),"
    )
    with open('doctor/urls.py', 'w') as f:
        f.write(urls_content)

with open('doctor/views.py', 'r') as f:
    views_content = f.read()

login_replacement = """def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Pre-check for pending approval
        try:
            pending_user = User.objects.get(username=username)
            if not pending_user.is_active and InnerMember.objects.filter(user=pending_user).exists():
                return render(request, 'doctor/login.html', {'error': 'Your account is pending approval by the clinic owner.'})
        except User.DoesNotExist:
            pass

        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                member = InnerMember.objects.get(user=user)
                role = member.role
            except InnerMember.DoesNotExist:
                return render(request, 'doctor/login.html', {'error': 'Role not assigned'})
            
            login(request, user)

            if role == 'doctor':
                return redirect('doctor:dashboard')
            else:
                return redirect('billing:bill_list')
        else:
            return render(request, 'doctor/login.html', {'error': 'Invalid credentials'})

    return render(request, 'doctor/login.html')"""

if '# Pre-check for pending approval' not in views_content:
    # Use regex to find and replace login_view
    views_content = re.sub(
        r'def login_view\(request\):[\s\S]*?(?=\n@never_cache\ndef forgot_password)', 
        login_replacement + '\n', 
        views_content
    )
    
new_views = """

@never_cache
def register_view(request):
    if request.user.is_authenticated:
        return redirect('doctor:dashboard')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not all([name, username, email, phone, password, confirm_password]):
            return render(request, 'doctor/register.html', {'error': 'All fields are required.'})
        
        if password != confirm_password:
            return render(request, 'doctor/register.html', {'error': 'Passwords do not match.'})
            
        if not phone.isdigit() or len(phone) != 10:
            return render(request, 'doctor/register.html', {'error': 'Phone must be exactly 10 digits.'})
            
        if User.objects.filter(username=username).exists():
            return render(request, 'doctor/register.html', {'error': 'Username already exists.'})
            
        if User.objects.filter(email__iexact=email).exists():
            return render(request, 'doctor/register.html', {'error': 'Email already in use.'})
            
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        try:
            validate_password(password)
        except ValidationError as e:
            return render(request, 'doctor/register.html', {'error': ' '.join(e.messages)})

        name_parts = name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=False
                )
                
                # Find owner doctor if exists
                owner = InnerMember.objects.filter(role='doctor', is_owner=True).first()
                owner_user = owner.user if owner else None
                
                InnerMember.objects.create(
                    user=user,
                    role='doctor',
                    is_owner=False,
                    phone=phone,
                    doctor=owner_user
                )
                
            messages.success(request, 'Registration submitted. You can log in after the clinic owner approves your account.')
            return redirect('doctor:login')
        except Exception as e:
            return render(request, 'doctor/register.html', {'error': 'Registration failed. Please try again.'})

    return render(request, 'doctor/register.html')

@require_POST
@role_required('doctor')
def approve_doctor(request, member_id):
    if not hasattr(request.user, 'innermember') or not request.user.innermember.is_owner:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
        
    try:
        member = InnerMember.objects.get(id=member_id)
        member.user.is_active = True
        member.user.save()
        return JsonResponse({'success': True})
    except InnerMember.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Member not found.'})

@require_POST
@role_required('doctor')
def reject_doctor(request, member_id):
    if not hasattr(request.user, 'innermember') or not request.user.innermember.is_owner:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
        
    try:
        member = InnerMember.objects.get(id=member_id)
        member.user.delete()
        return JsonResponse({'success': True})
    except InnerMember.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Member not found.'})

"""

if 'def register_view' not in views_content:
    views_content += new_views
    with open('doctor/views.py', 'w') as f:
        f.write(views_content)
        
print("Python update script executed.")
