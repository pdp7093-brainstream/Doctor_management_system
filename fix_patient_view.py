import re

with open('templates/doctor/view_patient.html', 'r') as f:
    content = f.read()

# Fix corrupted header (lines 14-31)
bad_header = """        <a href="{% url 'doctor:manage_patients' %}" class="patient-link-btn">
            <i class="bi bi-arrow-left me-1"></i> Back to Patients
                            <td style="white-space:nowrap; vertical-align:middle;">
    </div>

    <!-- Family member context banner -->
    {% if is_family %}
                                <button type="button" class="btn btn-sm btn-outline-danger delete-doc-btn" data-type="profile" data-id="{{ document.id }}" title="Delete" style="width:36px;height:36px;display:inline-flex;align-items:center;justify-content:center;border-radius:6px;padding:0.35rem;">
                                    <i class="bi bi-trash"></i>
                                </button>
        <i class="bi bi-people-fill"></i>
        <span>
            <strong>{{ member.name }}</strong> is the
            <strong>{{ member.relation }}</strong> of
            <strong>{{ parent.user.first_name }}</strong>
        </span>
    </div>
    {% endif %}"""

good_header = """        <a href="{% url 'doctor:manage_patients' %}" class="patient-link-btn btn btn-outline-primary btn-sm">
            <i class="bi bi-arrow-left me-1"></i> Back to Patients
        </a>
    </div>

    <!-- Family member context banner -->
    {% if is_family %}
    <div class="alert alert-info d-flex align-items-center gap-2 mb-4 border-0 shadow-sm rounded-3">
        <i class="bi bi-people-fill fs-5"></i>
        <span>
            <strong>{{ member.name }}</strong> is the
            <strong>{{ member.relation }}</strong> of
            <strong>{{ parent.user.first_name }}</strong>
        </span>
    </div>
    {% endif %}"""

content = content.replace(bad_header, good_header)

# Fix typo "<div>2"
content = content.replace("<div>2", "<div>")

# Add row around Profile and Family Members
# Find <!-- Profile Card -->
content = content.replace("    <!-- Profile Card -->", '    <div class="row g-4 mb-4">\n        <div class="{% if is_family %}col-12{% else %}col-lg-6{% endif %}">\n            <!-- Profile Card -->')

# Change Profile Card to have h-100
content = content.replace('<div class="card mb-4">', '<div class="card h-100 border-0 shadow-sm">')

# Close Profile Card div
content = content.replace('    </div>\n\n    <!-- Family Members Card (only for main patients) -->', '    </div>\n        </div>\n\n    <!-- Family Members Card (only for main patients) -->')

# Add col around Family Members
content = content.replace('    {% if not is_family %}\n    <div class="card">', '    {% if not is_family %}\n        <div class="col-lg-6">\n    <div class="card h-100 border-0 shadow-sm">')

# Close Family Members col and row
content = content.replace('    {% endif %}\n\n    <div class="card mt-4">', '    {% endif %}\n        </div>\n    {% endif %}\n    </div>\n\n    <div class="row g-4 mb-4">\n        <div class="col-lg-6">\n    <div class="card h-100 border-0 shadow-sm">')

# Add col around Patient Added Docs
content = content.replace('    <div class="card mt-4">\n        <div class="card-header d-flex justify-content-between align-items-center">\n            <div class="d-flex align-items-center gap-2" style="font-size:0.98rem; font-weight:700;">\n                <i class="bi bi-upload"></i> Patient Added Documents', '        </div>\n        <div class="col-lg-6">\n    <div class="card h-100 border-0 shadow-sm">\n        <div class="card-header d-flex justify-content-between align-items-center">\n            <div class="d-flex align-items-center gap-2" style="font-size:0.98rem; font-weight:700;">\n                <i class="bi bi-upload"></i> Patient Added Documents')

# Close Patient Added Docs col and row
content = content.replace('</main>', '        </div>\n    </div>\n\n</main>')

with open('templates/doctor/view_patient.html', 'w') as f:
    f.write(content)
