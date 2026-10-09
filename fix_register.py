import re

with open('doctor/views.py', 'r') as f:
    content = f.read()

# Replace the overly broad auth check in register_view
old_check = """def register_view(request):
    if request.user.is_authenticated:
        return redirect('doctor:dashboard')"""

new_check = """def register_view(request):
    # Only redirect if they are actually a logged-in doctor/staff
    if request.user.is_authenticated:
        try:
            if request.user.innermember:
                return redirect('doctor:dashboard')
        except:
            pass"""

if old_check in content:
    content = content.replace(old_check, new_check)
    with open('doctor/views.py', 'w') as f:
        f.write(content)
    print("Fixed register_view")
else:
    print("Check not found or already fixed")
