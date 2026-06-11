
const csrfToken = '{{ csrf_token }}';

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
                'X-CSRFToken': csrfToken,
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
