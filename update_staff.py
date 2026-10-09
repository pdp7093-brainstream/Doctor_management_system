import re

with open('doctor/views.py', 'r') as f:
    views_content = f.read()

# Update staff_view to include inactive users and pass is_owner
staff_replacement = """def staff_view(request):
    billers = InnerMember.objects.filter(role='biller').select_related('user')
    pending_doctors = InnerMember.objects.filter(role='doctor', user__is_active=False).select_related('user')
    is_owner = hasattr(request.user, 'innermember') and request.user.innermember.is_owner
    return render(request, 'doctor/staff.html', {'billers': billers, 'pending_doctors': pending_doctors, 'is_owner': is_owner})"""

views_content = re.sub(
    r'def staff_view\(request\):[\s\S]*?(?=\n# ─────────────────────────────────────────\n# Add Staff)', 
    staff_replacement + '\n', 
    views_content
)

with open('doctor/views.py', 'w') as f:
    f.write(views_content)
    
print("Updated staff view.")
