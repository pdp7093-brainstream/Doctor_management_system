
// CSRF helper (Django docs)
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

document.addEventListener('click', function (e) {
    const btn = e.target.closest('.delete-doc-btn');
    if (!btn) return;
    const docType = btn.dataset.type;
    const docId = btn.dataset.id;

    const csrftoken = getCookie('csrftoken');
    let url = '';
    if (docType === 'lab') url = '/delete-lab-document/' + docId + '/';
    else url = '/delete-profile-document/' + docId + '/';

    const doDelete = () => {
        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken,
                'Accept': 'application/json'
            }
        }).then(r => {
            if (!r.ok) return r.text().then(t => { throw new Error(t || 'Server error'); });
            return r.json();
        })
            .then(data => {
                if (data && data.success) {
                    const row = btn.closest('tr');
                    if (row) row.remove();
                    (typeof Swal !== 'undefined') && Swal.fire({ icon: 'success', title: 'Deleted', timer: 1200, showConfirmButton: false });
                } else {
                    (typeof Swal !== 'undefined') ? Swal.fire('Error', data.error || 'Failed to delete document', 'error') : alert(data.error || 'Failed to delete document');
                }
            }).catch(err => {
                console.error(err);
                const message = err && err.message ? err.message.replace(/\n/g, '') : 'Network error while deleting document';
                (typeof Swal !== 'undefined') ? Swal.fire('Error', message, 'error') : alert(message || 'Network error while deleting document');
            });
    };

    if (typeof Swal !== 'undefined') {
        Swal.fire({
            title: 'Delete document?',
            text: 'This action cannot be undone.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Delete',
            confirmButtonColor: '#d33'
        }).then(result => {
            if (result.isConfirmed) doDelete();
        });
    } else {
        if (confirm('Are you sure you want to delete this document? This action cannot be undone.')) doDelete();
    }
});


function deleteOldDocument(docId, btnElement) {
    const doDelete = () => {
        const tr = btnElement.closest("tr");
        tr.style.opacity = '0.5';

        fetch(`/doctor/old-data/delete/${docId}/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCookie('csrftoken'),
                "Content-Type": "application/json"
            }
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    tr.remove();
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'success',
                            title: 'Deleted!',
                            text: 'The document has been deleted.',
                            timer: 1500,
                            showConfirmButton: false
                        });
                    }
                } else {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire('Error', data.error || 'Failed to delete document', 'error');
                    } else {
                        alert("Failed to delete document: " + (data.error || "Unknown error"));
                    }
                    tr.style.opacity = '1';
                }
            })
            .catch(err => {
                console.error("Error deleting document:", err);
                if (typeof Swal !== 'undefined') {
                    Swal.fire('Error', 'An error occurred. Please try again.', 'error');
                } else {
                    alert("An error occurred. Please try again.");
                }
                tr.style.opacity = '1';
            });
    };

    if (typeof Swal !== 'undefined') {
        Swal.fire({
            title: 'Are you sure?',
            text: "You want to delete this old document?",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Yes, delete it!'
        }).then((result) => {
            if (result.isConfirmed) {
                doDelete();
            }
        });
    } else {
        if (confirm("Are you sure you want to delete this old document?")) {
            doDelete();
        }
    }
}
