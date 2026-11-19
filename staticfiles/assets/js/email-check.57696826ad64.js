document.addEventListener('DOMContentLoaded', function () {
  var re = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  document.querySelectorAll('input[type="email"]:not([readonly])').forEach(function (input) {
    var fb = document.createElement('div');
    fb.className = 'invalid-feedback';
    fb.textContent = 'Enter a valid email address (e.g. name@example.com).';
    input.insertAdjacentElement('afterend', fb);
    function check() {
      var v = input.value.trim();
      var bad = v !== '' && !re.test(v);
      input.classList.toggle('is-invalid', bad);
      input.setCustomValidity(bad ? 'Enter a valid email address.' : '');
      return !bad;
    }
    input.addEventListener('blur', check);
    input.addEventListener('input', function () { if (input.classList.contains('is-invalid')) check(); });
    if (input.form) {
      input.form.addEventListener('submit', function (e) {
        if (!check()) { e.preventDefault(); input.focus(); }
      });
    }
  });
});
