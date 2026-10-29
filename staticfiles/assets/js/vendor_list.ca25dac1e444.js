
// Search functionality
const searchInput = document.getElementById('searchInput');
const vendorRows = document.querySelectorAll('.vendor-row');

searchInput.addEventListener('input', function () {
    const searchValue = this.value.toLowerCase().trim();

    vendorRows.forEach(row => {
        const name = row.getAttribute('data-vendor-name');
        const phone = row.getAttribute('data-vendor-phone');
        const email = row.getAttribute('data-vendor-email');

        if (name.includes(searchValue) || phone.includes(searchValue) || email.includes(searchValue)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });

    // Show empty state if no results
    const visibleRows = Array.from(vendorRows).filter(row => row.style.display !== 'none');
    const tbody = document.querySelector('#tableBody');
    let emptyState = tbody.querySelector('.empty-state');

    if (visibleRows.length === 0 && !emptyState) {
        const emptyRow = document.createElement('tr');
        emptyRow.classList.add('empty-state-row');
        emptyRow.innerHTML = `
                <td colspan="6" class="text-center py-5">
                    <div class="empty-state">
                        <i class="bi bi-search" style="font-size: 2.5rem; color: #ccc;"></i>
                        <p class="text-muted mt-3">No vendors match your search</p>
                    </div>
                </td>
            `;
        tbody.appendChild(emptyRow);
    } else if (visibleRows.length > 0) {
        const emptyRow = tbody.querySelector('.empty-state-row');
        if (emptyRow) emptyRow.remove();
    }
});

async function confirmDelete(event, vendorName) {
    event.preventDefault();

    const result = await Swal.fire({
        title: 'Delete Vendor?',
        text: `Are you sure you want to delete ${vendorName}?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Yes, Delete',
        cancelButtonText: 'Cancel'
    });

    if (result.isConfirmed) {
        event.target.submit();
    }

    return false;
}
