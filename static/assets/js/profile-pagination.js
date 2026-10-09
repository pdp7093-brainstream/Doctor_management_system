(function () {
  const ROWS_PER_PAGE = 5;
  const pagers = [];

  function getRows(table) {
    return Array.from(table.querySelectorAll('tbody tr')).filter(row => {
      return !row.id && !row.classList.contains('empty-row') && row.cells.length > 1;
    });
  }

  function makeButton(label, disabled, active, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'profile-pagination__btn';
    button.textContent = label;
    button.disabled = disabled;
    if (active) button.classList.add('is-active');
    button.addEventListener('click', onClick);
    return button;
  }

  function createPager(table) {
    const bar = document.createElement('div');
    bar.className = 'profile-pagination';

    const info = document.createElement('div');
    info.className = 'profile-pagination__info';

    const buttons = document.createElement('div');
    buttons.className = 'profile-pagination__buttons';

    bar.append(info, buttons);
    table.closest('.table-responsive').after(bar);

    const pager = { table, bar, info, buttons, page: 1 };
    pagers.push(pager);
    return pager;
  }

  function render(pager) {
    const rows = getRows(pager.table);
    const total = rows.length;
    const totalPages = Math.ceil(total / ROWS_PER_PAGE);

    if (total <= ROWS_PER_PAGE) {
      rows.forEach(row => row.style.display = '');
      pager.bar.style.display = 'none';
      pager.page = 1;
      return;
    }

    pager.bar.style.display = 'flex';
    if (pager.page > totalPages) pager.page = totalPages;

    const start = (pager.page - 1) * ROWS_PER_PAGE;
    const end = Math.min(start + ROWS_PER_PAGE, total);

    rows.forEach((row, index) => {
      row.style.display = index >= start && index < end ? '' : 'none';
    });

    pager.info.textContent = `Showing ${start + 1}\u2013${end} of ${total}`;
    pager.buttons.textContent = '';

    pager.buttons.append(makeButton('Prev', pager.page === 1, false, () => {
      pager.page -= 1;
      render(pager);
    }));

    for (let page = 1; page <= totalPages; page += 1) {
      pager.buttons.append(makeButton(String(page), false, page === pager.page, () => {
        pager.page = page;
        render(pager);
      }));
    }

    pager.buttons.append(makeButton('Next', pager.page === totalPages, false, () => {
      pager.page += 1;
      render(pager);
    }));
  }

  function refresh() {
    pagers.forEach(render);
  }

  window.refreshProfilePagination = refresh;

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.profile-page-shell .fm-table').forEach(table => {
      createPager(table);
    });
    refresh();
  });
})();
