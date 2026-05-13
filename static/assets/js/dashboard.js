// profile.html js code
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
const csrfToken = getCookie('csrftoken');

// ── Edit Profile Modal ──────────────────────────────────
const editProfileModal = document.getElementById('editProfileModal');

document.getElementById('openEditProfile').addEventListener('click', () => {
    editProfileModal.classList.add('active');
});
document.getElementById('closeEditProfile').addEventListener('click', () => {
    editProfileModal.classList.remove('active');
});
editProfileModal.addEventListener('click', e => {
    if (e.target === editProfileModal) editProfileModal.classList.remove('active');
});

// Photo preview in modal
document.getElementById('modalPhotoUpload').addEventListener('change', function (e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
        // Replace initials div with img if needed
        let preview = document.getElementById('modalPreview');
        const initials = document.getElementById('modalInitials');
        if (!preview) {
            preview = document.createElement('img');
            preview.id = 'modalPreview';
            preview.className = 'modal-avatar';
            if (initials) initials.replaceWith(preview);
        }
        preview.src = reader.result;
    };
    reader.readAsDataURL(file);
});


// ── Edit Family Member Modal ────────────────────────────
const editModal = document.getElementById('editMemberModal');
const editError = document.getElementById('editError');

document.querySelectorAll('.btn-edit-fm').forEach(btn => {
    btn.addEventListener('click', function () {
        document.getElementById('editMemberId').value  = this.dataset.id;
        document.getElementById('editName').value       = this.dataset.name;
        document.getElementById('editRelation').value  = this.dataset.relation;
        document.getElementById('editGender').value    = this.dataset.gender;
        document.getElementById('editDob').value       = this.dataset.dob;
        document.getElementById('editBldGrop').value   = this.dataset.bldgrop;
        document.getElementById('editPhone').value     = this.dataset.phone;
        editError.style.display = 'none';
        editModal.classList.add('active');
    });
});

document.getElementById('closeEditModal').addEventListener('click', () => editModal.classList.remove('active'));
editModal.addEventListener('click', e => { if (e.target === editModal) editModal.classList.remove('active'); });

document.getElementById('saveEditMember').addEventListener('click', function () {
    const id       = document.getElementById('editMemberId').value;
    const name     = document.getElementById('editName').value.trim();
    const relation = document.getElementById('editRelation').value;
    const gender   = document.getElementById('editGender').value;
    const dob      = document.getElementById('editDob').value;
    const bld_grop = document.getElementById('editBldGrop').value;
    const phone    = document.getElementById('editPhone').value.trim();

    if (!name || !relation) {
        editError.textContent   = 'Name and Relation are required.';
        editError.style.display = 'block';
        return;
    }

    this.disabled    = true;
    this.textContent = 'Saving...';

    fetch(`/update-family-member/${id}/`, {
        method : 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
        },
        body   : JSON.stringify({ name, relation, gender, dob, bld_grop, phone }),
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) { location.reload(); }
        else {
            editError.textContent   = data.error || 'Something went wrong.';
            editError.style.display = 'block';
        }
    })
    .catch(() => {
        editError.textContent   = 'Network error. Please try again.';
        editError.style.display = 'block';
    })
    .finally(() => {
        this.disabled    = false;
        this.textContent = 'Save Changes';
    });
});

// ── Delete Family Member ────────────────────────────────
document.querySelectorAll('.btn-delete-fm').forEach(btn => {

    btn.addEventListener('click', function () {

        const id = this.dataset.id;
        const name = this.dataset.name;

        Swal.fire({
            title: 'Are you sure?',
            text: `Remove "${name}" from family members?`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#6c757d',
            confirmButtonText: 'Yes, Delete',
            cancelButtonText: 'Cancel',
            reverseButtons: true
        }).then((result) => {

            if (result.isConfirmed) {

                fetch(`/delete-family-member/${id}/`, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                })
                .then(r => r.json())
                .then(data => {

                    if (data.success) {

                        Swal.fire({
                            icon: 'success',
                            title: 'Deleted!',
                            text: `"${name}" removed successfully.`,
                            timer: 1800,
                            showConfirmButton: false
                        });

                        setTimeout(() => {
                            location.reload();
                        }, 1800);

                    } else {

                        Swal.fire({
                            icon: 'error',
                            title: 'Error',
                            text: data.error || 'Could not delete member.'
                        });

                    }

                })
                .catch(() => {

                    Swal.fire({
                        icon: 'error',
                        title: 'Network Error',
                        text: 'Please try again.'
                    });

                });

            }

        });

    });

});
// dashboardd.html js code

const ROWS_PER_PAGE = 10;
    const tbody = document.getElementById('tableBody');
    const allRows = Array.from(tbody.querySelectorAll('tr:not(#emptyRow)'));
    const pagination = document.getElementById('pagination');
    const pageInfo = document.getElementById('pageInfo');
    const paginationWrapper = document.getElementById('paginationWrapper');
    let currentPage = 1;

    function totalPages() { return Math.ceil(allRows.length / ROWS_PER_PAGE); }

    function showPage(page) {
        currentPage = page;
        const start = (page - 1) * ROWS_PER_PAGE;
        const end = start + ROWS_PER_PAGE;
        allRows.forEach((row, i) => { row.style.display = (i >= start && i < end) ? '' : 'none'; });
        pageInfo.textContent = `Showing ${start + 1}–${Math.min(end, allRows.length)} of ${allRows.length} appointments`;
        renderPagination();
    }

    function renderPagination() {
        pagination.innerHTML = '';
        const total = totalPages();
        const prev = document.createElement('li');
        prev.className = 'page-item' + (currentPage === 1 ? ' disabled' : '');
        prev.innerHTML = `<a class="page-link" href="#">&lsaquo;</a>`;
        prev.addEventListener('click', e => { e.preventDefault(); if (currentPage > 1) showPage(currentPage - 1); });
        pagination.appendChild(prev);
        for (let i = 1; i <= total; i++) {
            if (i === 1 || i === total || (i >= currentPage - 1 && i <= currentPage + 1)) {
                const li = document.createElement('li');
                li.className = 'page-item' + (i === currentPage ? ' active' : '');
                li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
                li.addEventListener('click', e => { e.preventDefault(); showPage(i); });
                pagination.appendChild(li);
            } else if (i === currentPage - 2 || i === currentPage + 2) {
                const li = document.createElement('li');
                li.className = 'page-item disabled';
                li.innerHTML = `<span class="page-link">…</span>`;
                pagination.appendChild(li);
            }
        }
        const next = document.createElement('li');
        next.className = 'page-item' + (currentPage === total ? ' disabled' : '');
        next.innerHTML = `<a class="page-link" href="#">&rsaquo;</a>`;
        next.addEventListener('click', e => { e.preventDefault(); if (currentPage < total) showPage(currentPage + 1); });
        pagination.appendChild(next);
    }

    if (allRows.length > ROWS_PER_PAGE) {
        paginationWrapper.style.display = 'flex';
        showPage(1);
    }


