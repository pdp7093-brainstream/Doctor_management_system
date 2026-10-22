// Get CSRF token from DOM instead of template tag since this is a static JS file
function getCsrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
}

document.addEventListener('click', async (event) => {
    const button = event.target.closest('.js-delete-feedback');
    if (!button) return;

    const result = await Swal.fire({
        title: 'Delete Feedback?',
        text: `Remove feedback from "${button.dataset.name}"?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Yes, Delete',
        cancelButtonText: 'Cancel',
    });

    if (!result.isConfirmed) return;

    button.disabled = true;

    try {
        const response = await fetch(button.dataset.url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Could not delete feedback.');
        }

        button.closest('.feedback-card')?.remove();
        Swal.fire({
            toast: true,
            position: 'top-end',
            icon: 'success',
            title: 'Feedback deleted',
            showConfirmButton: false,
            timer: 1800,
        });
    } catch (error) {
        button.disabled = false;
        Swal.fire('Error', error.message || 'Network error.', 'error');
    }
});


function updateBulkDeleteBtn() {
    const checkboxes = document.querySelectorAll('.feedback-checkbox:checked');
    const btn = document.getElementById('bulkDeleteBtn');
    const countSpan = document.getElementById('selectedCount');
    if (!btn) return;
    if (checkboxes.length > 0) {
        btn.classList.remove('d-none');
        if (countSpan) countSpan.textContent = checkboxes.length;
    } else {
        btn.classList.add('d-none');
        if (countSpan) countSpan.textContent = '0';
    }
}

document.addEventListener('change', function(e) {
    if (e.target.id === 'selectAllFeedback') {
        const isChecked = e.target.checked;
        document.querySelectorAll('.feedback-checkbox').forEach(cb => {
            cb.checked = isChecked;
        });
        updateBulkDeleteBtn();
    } else if (e.target.classList.contains('feedback-checkbox')) {
        updateBulkDeleteBtn();
        const allCheckboxes = document.querySelectorAll('.feedback-checkbox');
        const allChecked = document.querySelectorAll('.feedback-checkbox:checked');
        const selectAll = document.getElementById('selectAllFeedback');
        if (selectAll) {
            selectAll.checked = allCheckboxes.length > 0 && allCheckboxes.length === allChecked.length;
        }
    }
});

async function bulkDeleteFeedback() {
    const checkboxes = document.querySelectorAll('.feedback-checkbox:checked');
    const ids = Array.from(checkboxes).map(cb => cb.value);
    
    if (ids.length === 0) return;
    
    const result = await Swal.fire({
        title: 'Delete Selected Feedback?',
        text: `Are you sure you want to delete ${ids.length} feedback record(s)?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Yes, Delete',
        cancelButtonText: 'Cancel',
    });

    if (!result.isConfirmed) return;

    try {
        // Need csrf token which might not be set in this JS file depending on how it's loaded. 
        // We'll extract it from the DOM just in case the constant isn't properly evaluated.
        let token = getCsrfToken();

        const response = await fetch('/doctor/feedback/bulk-delete/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token,
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({ feedback_ids: ids })
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Could not delete feedback.');
        }
        
        Swal.fire({
            title: 'Deleted!',
            text: data.message || `${ids.length} feedback(s) deleted successfully.`,
            icon: 'success',
            confirmButtonColor: '#4f46e5'
        }).then(() => {
            window.location.reload();
        });
        
    } catch (error) {
        Swal.fire('Error', error.message || 'Network error.', 'error');
    }
}
