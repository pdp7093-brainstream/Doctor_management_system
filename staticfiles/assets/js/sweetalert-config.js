window.swalSharedCustomClass = {
  confirmButton: 'swal-btn-confirm',
  cancelButton: 'swal-btn-cancel',
  actions: 'swal-actions',
};

window.Swal = window.Swal.mixin({
  buttonsStyling: false,
  customClass: window.swalSharedCustomClass,
  reverseButtons: true,
});