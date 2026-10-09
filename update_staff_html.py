with open('templates/doctor/staff.html', 'r') as f:
    html = f.read()

pending_section = """
    {% if is_owner and pending_doctors %}
    <div class="card mb-4">
        <div class="card-header d-flex justify-content-between align-items-center bg-warning bg-opacity-10">
            <div class="d-flex align-items-center gap-2" style="font-size: 0.98rem; font-weight: 700; color: #854d0e;">
                <i class="bi bi-person-exclamation"></i> Pending Doctor Approvals
            </div>
            <span class="badge bg-warning text-dark">{{ pending_doctors|length }} pending</span>
        </div>
        <div class="card-body p-0">
            <div style="overflow-x:auto; display:block; width:100%;">
                <table class="table table-hover mb-0" style="min-width:900px; width:100%;">
                    <thead>
                        <tr>
                            <th>Doctor</th>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Phone</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for member in pending_doctors %}
                        <tr id="row-{{ member.id }}">
                            <td>
                                <div class="d-flex align-items-center gap-2">
                                    <div class="user-avatar" style="width: 40px; height: 40px; font-size: 0.9rem; background: #eab308; color: white;">
                                        {{member.user.first_name|slice:":1"|upper|default:member.user.username|slice:":1"|upper}}
                                    </div>
                                    <div>
                                        <div style="font-weight:600;">{{member.user.get_full_name|default:member.user.username }}</div>
                                        <div style="font-size:0.78rem;color:#888;">Doctor (Pending)</div>
                                    </div>
                                </div>
                            </td>
                            <td>{{ member.user.username }}</td>
                            <td>{{ member.user.email|default:"—" }}</td>
                            <td>{{ member.phone|default:"—" }}</td>
                            <td>
                                <span class="badge bg-warning text-dark">Pending</span>
                            </td>
                            <td>
                                <div class="d-flex align-items-center gap-2">
                                    <button class="btn btn-sm btn-success btn-approve-doc" data-id="{{ member.id }}" title="Approve">
                                        <i class="bi bi-check-circle"></i><span>Approve</span>
                                    </button>
                                    <button class="btn btn-sm btn-danger btn-reject-doc" data-id="{{ member.id }}" data-name="{{ member.user.get_full_name|default:member.user.username }}" title="Reject">
                                        <i class="bi bi-x-circle"></i><span>Reject</span>
                                    </button>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    {% endif %}
"""

if 'Pending Doctor Approvals' not in html:
    html = html.replace('<div class="card">', pending_section + '\n    <div class="card">', 1)
    
    js_addition = """
    <script>
        document.querySelectorAll('.btn-approve-doc').forEach(btn => {
            btn.addEventListener('click', function() {
                const id = this.dataset.id;
                fetch(`/doctor/staff/approve/${id}/`, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }
                }).then(r => r.json()).then(res => {
                    if (res.success) location.reload();
                    else alert(res.error || 'Approval failed');
                });
            });
        });

        document.querySelectorAll('.btn-reject-doc').forEach(btn => {
            btn.addEventListener('click', function() {
                const id = this.dataset.id;
                const name = this.dataset.name;
                Swal.fire({
                    title: 'Reject Registration?',
                    text: `Are you sure you want to reject and delete the application for ${name}?`,
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#dc2626',
                    cancelButtonColor: '#6b7280',
                    confirmButtonText: 'Yes, reject it!'
                }).then((result) => {
                    if (result.isConfirmed) {
                        fetch(`/doctor/staff/reject/${id}/`, {
                            method: 'POST',
                            headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }
                        }).then(r => r.json()).then(res => {
                            if (res.success) location.reload();
                            else Swal.fire('Error!', res.error || 'Rejection failed', 'error');
                        });
                    }
                });
            });
        });
    </script>
    """
    html = html.replace('</main>', js_addition + '\n</main>')
    
    with open('templates/doctor/staff.html', 'w') as f:
        f.write(html)
        
print("Updated staff html.")
