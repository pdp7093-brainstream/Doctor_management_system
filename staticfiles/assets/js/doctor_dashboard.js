
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

const csrftoken = getCookie('csrftoken');

document.querySelectorAll('.btn-cancel-appointment').forEach(button => {
    button.addEventListener('click', async function () {
        const reasonPrompt = await Swal.fire({
            title: 'Cancel Appointment',
            text: 'Please enter the reason for cancellation.',
            input: 'text',
            inputLabel: 'Cancellation Reason',
            inputPlaceholder: 'Write reason here...',
            inputAttributes: {
                maxlength: 255,
            },
            inputValidator: (value) => {
                if (!value || !value.trim()) {
                    return 'Cancellation reason is required.';
                }
                return null;
            },
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Yes, Cancel',
            cancelButtonText: 'Keep Appointment',
            confirmButtonColor: '#dc3545',
            cancelButtonColor: '#6c757d',
            reverseButtons: true,
            customClass: {
                popup: 'rounded-4 shadow-lg',
                confirmButton: 'px-4 py-2',
                cancelButton: 'px-4 py-2'
            }
        });

        if (!reasonPrompt.isConfirmed) return;

        const url = this.dataset.url;
        const cancellationReason = reasonPrompt.value.trim();

        Swal.fire({
            title: 'Cancelling...',
            html: 'Please wait',
            allowOutsideClick: false,
            showConfirmButton: false,
            didOpen: () => Swal.showLoading()
        });

        let response;
        let data;

        try {
            response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({
                    cancellation_reason: cancellationReason,
                }),
            });

            data = await response.json();
        } catch (error) {
            Swal.fire({
                title: 'Error!',
                text: 'Unable to cancel appointment. Please try again.',
                icon: 'error',
                confirmButtonColor: '#0d6efd'
            });
            return;
        }

        if (!response.ok || !data.success) {
            Swal.fire({
                title: 'Error!',
                text: data.error || 'Unable to cancel appointment.',
                icon: 'error',
                confirmButtonColor: '#0d6efd'
            });
            return;
        }

        const row = this.closest('tr');
        const statusBadge = row.querySelector('.appointment-status');
        if (statusBadge) {
            statusBadge.textContent = data.status;
            statusBadge.className = 'status-badge appointment-status status-' + data.status_raw;
        }

        const startVisitBtn = row.querySelector('.btn-start-visit');
        if (startVisitBtn) {
            startVisitBtn.remove();
        }

        const totalEl = document.getElementById('totalAppointments');
        const remainingEl = document.getElementById('remainingToday');
        if (totalEl) totalEl.textContent = data.total;
        if (remainingEl) remainingEl.textContent = data.remaining_today;

        this.disabled = true;
        this.classList.remove('btn-danger');
        this.classList.add('btn-danger');
        this.innerHTML = '<i class="bi bi-x-circle me-1"></i>Cancelled';

        Swal.fire({
            title: 'Cancelled!',
            text: 'Appointment has been cancelled successfully.',
            icon: 'success',
            confirmButtonColor: '#0d6efd'
        });
    });
});
