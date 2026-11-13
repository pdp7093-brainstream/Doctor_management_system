document.addEventListener('DOMContentLoaded', function () {
  var mq = window.matchMedia('(max-width: 767.98px)');
  document.querySelectorAll('[data-filter-collapse]').forEach(function (card) {
    var head = card.querySelector(':scope > .card-header, :scope > .dc-card-header');
    var body = card.querySelector(':scope > .card-body, :scope > .dc-card-body');
    if (!head || !body) return;
    head.classList.add('filter-collapse-head');
    head.setAttribute('role', 'button');
    head.setAttribute('tabindex', '0');
    var icon = document.createElement('i');
    icon.className = 'bi bi-chevron-down filter-collapse-icon';
    head.appendChild(icon);
    var hasValue = Array.prototype.some.call(body.querySelectorAll('input, select'), function (el) {
      if (el.type === 'checkbox' || el.type === 'radio') return el.checked;
      if (['hidden', 'button', 'submit', 'reset'].indexOf(el.type) !== -1) return false;
      var v = (el.value || '').trim().toLowerCase();
      return v !== '' && v !== 'all';
    });
    function setOpen(open) {
      card.classList.toggle('filter-open', open);
      head.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    setOpen(hasValue);
    function toggle() { if (mq.matches) setOpen(!card.classList.contains('filter-open')); }
    head.addEventListener('click', toggle);
    head.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
    });
  });
});
