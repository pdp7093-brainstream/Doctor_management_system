
// Get CSRF token from DOM instead of template tag since this is a static JS file
function getCsrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
}

// ── Password toggle ──────────────────────────────────────
function togglePwd(inputId, icon) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.replace('bi-eye', 'bi-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.replace('bi-eye-slash', 'bi-eye');
    }
}

// ── Modal helpers ───────────────────────────────────────
function openModal(id) { document.getElementById(id).classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }

// Close on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
        if (e.target === overlay) overlay.classList.remove('active');
    });
});

function showErr(id, msg) {
    const el = document.getElementById(id);
    el.textContent = msg;
    el.style.display = 'block';
}
function clearErr(id) { document.getElementById(id).style.display = 'none'; }


// ── ADD STAFF ────────────────────────────────────────────
document.getElementById('openAddStaff').addEventListener('click', () => {
    ['addName', 'addPhone', 'addUsername', 'addEmail', 'addPassword'].forEach(id => document.getElementById(id).value = '');
    clearErr('addErr');
    openModal('addStaffModal');
});
document.getElementById('closeAddStaff').addEventListener('click', () => closeModal('addStaffModal'));

document.getElementById('saveAddStaff').addEventListener('click', function () {
    const name = document.getElementById('addName').value.trim();
    const phone = document.getElementById('addPhone').value.trim();
    const username = document.getElementById('addUsername').value.trim();
    const email = document.getElementById('addEmail').value.trim();
    const password = document.getElementById('addPassword').value;

    clearErr('addErr');
    if (!name || !username || !password) { showErr('addErr', 'Name, username and password are required.'); return; }
    if (password.length < 6) { showErr('addErr', 'Password must be at least 6 characters.'); return; }

    this.disabled = true; this.textContent = 'Adding...';

    fetch("/doctor/staff/add/", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ name, phone, username, email, password }),
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) { location.reload(); }
            else { showErr('addErr', data.error || 'Something went wrong.'); }
        })
        .catch(() => showErr('addErr', 'Network error. Please try again.'))
        .finally(() => { this.disabled = false; this.textContent = 'Add Staff'; });
});


// ── EDIT STAFF ───────────────────────────────────────────
document.querySelectorAll('.btn-edit-staff').forEach(btn => {
    btn.addEventListener('click', function () {
        document.getElementById('editStaffId').value = this.dataset.id;
        document.getElementById('editStaffName').value = this.dataset.name;
        document.getElementById('editStaffEmail').value = this.dataset.email;
        document.getElementById('editStaffPhone').value = this.dataset.phone;
        document.getElementById('editStaffActive').value = this.dataset.active;
        clearErr('editErr');
        openModal('editStaffModal');
    });
});
document.getElementById('closeEditStaff').addEventListener('click', () => closeModal('editStaffModal'));

document.getElementById('saveEditStaff').addEventListener('click', function () {
    const id = document.getElementById('editStaffId').value;
    const name = document.getElementById('editStaffName').value.trim();
    const email = document.getElementById('editStaffEmail').value.trim();
    const phone = document.getElementById('editStaffPhone').value.trim();
    const is_active = document.getElementById('editStaffActive').value === 'true';

    clearErr('editErr');
    if (!name) { showErr('editErr', 'Name is required.'); return; }

    this.disabled = true; this.textContent = 'Saving...';

    fetch(`/doctor/staff/edit/${id}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ name, email, phone, is_active }),
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) { location.reload(); }
            else { showErr('editErr', data.error || 'Something went wrong.'); }
        })
        .catch(() => showErr('editErr', 'Network error. Please try again.'))
        .finally(() => { this.disabled = false; this.textContent = 'Save Changes'; });
});


// ── RESET PASSWORD ───────────────────────────────────────
document.querySelectorAll('.btn-reset-pwd').forEach(btn => {
    btn.addEventListener('click', function () {
        document.getElementById('resetPwdId').value = this.dataset.id;
        document.getElementById('resetPwdName').textContent = this.dataset.name;
        document.getElementById('newPwd').value = '';
        document.getElementById('confirmPwd').value = '';
        clearErr('pwdErr');
        openModal('resetPwdModal');
    });
});
document.getElementById('closeResetPwd').addEventListener('click', () => closeModal('resetPwdModal'));

document.getElementById('saveResetPwd').addEventListener('click', function () {

    const id = document.getElementById('resetPwdId').value;
    const password = document.getElementById('newPwd').value;
    const confirm = document.getElementById('confirmPwd').value;

    clearErr('pwdErr');

    if (!password || password.length < 6) {
        showErr('pwdErr', 'Password must be at least 6 characters.');
        return;
    }

    if (password !== confirm) {
        showErr('pwdErr', 'Passwords do not match.');
        return;
    }

    const btn = this;
    btn.disabled = true;
    btn.innerHTML = `
        <span class="spinner-border spinner-border-sm me-2"></span>
        Resetting...
    `;

    fetch(`/doctor/staff/reset-password/${id}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ password }),
    })

        .then(r => r.json())

        .then(data => {

            if (data.success) {

                closeModal('resetPwdModal');

                Swal.fire({
                    icon: 'success',
                    title: 'Password Reset Successful',
                    text: `${document.getElementById('resetPwdName').textContent}'s password has been updated successfully.`,
                    confirmButtonColor: '#0d6efd',
                    confirmButtonText: 'Done',
                    backdrop: `
                    rgba(15,23,42,0.45)
                `,
                    customClass: {
                        popup: 'rounded-4 shadow-lg',
                        confirmButton: 'px-4 py-2'
                    }
                });

            } else {

                showErr('pwdErr', data.error || 'Something went wrong.');

            }

        })

        .catch(() => {

            showErr('pwdErr', 'Network error. Please try again.');

        })

        .finally(() => {

            btn.disabled = false;
            btn.innerHTML = 'Reset Password';

        });

});

// ── DELETE STAFF ─────────────────────────────────────────
document.querySelectorAll('.btn-delete-staff').forEach(btn => {
    btn.addEventListener('click', async function () {
        const id = this.dataset.id;
        const name = this.dataset.name;

        const result = await Swal.fire({
            title: 'Delete Staff?',
            text: `Are you sure you want to delete "${name}"?`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#dc2626',
            cancelButtonColor: '#6b7280',
            confirmButtonText: 'Yes, Delete',
            cancelButtonText: 'Cancel'
        });

        if (!result.isConfirmed) return;

        fetch(`/doctor/staff/delete/${id}/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    document.getElementById(`row-${id}`)?.remove();
                    // agar table empty ho jaye
                    const tbody = document.getElementById('staffTableBody');
                    if (tbody && tbody.querySelectorAll('tr').length === 0) location.reload();
                } else {
                    alert(data.error || 'Could not delete staff member.');
                }
            })
            .catch(() => alert('Network error. Please try again.'));
    });
});
