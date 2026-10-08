// Self-contained mobile nav toggle — works on all patient pages
  document.addEventListener('DOMContentLoaded', function () {
    var oldBtn = document.getElementById('mobileNavToggleBtn');
    if (!oldBtn) {
      oldBtn = document.querySelector('.mobile-nav-toggle');
    }
    if (!oldBtn) return;

    // Clone the button to wipe out duplicate event listeners (e.g. from main.js)
    var btn = oldBtn.cloneNode(true);
    oldBtn.parentNode.replaceChild(btn, oldBtn);

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      document.body.classList.toggle('mobile-nav-active');
      btn.classList.toggle('bi-list');
      btn.classList.toggle('bi-x');
    });

    // Close nav when overlay (body background) is clicked
    document.addEventListener('click', function (e) {
      if (document.body.classList.contains('mobile-nav-active')) {
        var navmenu = document.getElementById('navmenu');
        if (navmenu && !navmenu.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
          document.body.classList.remove('mobile-nav-active');
          btn.classList.add('bi-list');
          btn.classList.remove('bi-x');
        }
      }
    });

    // Close nav when a menu link is clicked
    document.querySelectorAll('#navmenu a').forEach(function (link) {
      link.addEventListener('click', function () {
        if (document.body.classList.contains('mobile-nav-active')) {
          document.body.classList.remove('mobile-nav-active');
          btn.classList.add('bi-list');
          btn.classList.remove('bi-x');
        }
      });
    });
  });



  window.hasMobileNavHandler = true;

  function initHeaderNav() {
    const profileTrigger = document.querySelector('.profile-nav .profile-nav-trigger');
    const profileNavItem = document.querySelector('.profile-nav');

    if (profileTrigger && profileNavItem) {
      profileTrigger.addEventListener('click', function (e) {
        if (window.innerWidth > 1199) return;
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        const isOpen = profileNavItem.classList.toggle('dropdown-active');
        profileTrigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      }, true);
    }

    const logoutBtn = document.getElementById('logoutBtn');

    if (logoutBtn) {

      logoutBtn.addEventListener('click', function (e) {

        e.preventDefault();

        Swal.fire({
          title: 'Logout Confirmation',
          text: 'Are you sure you want to logout from your account?',
          icon: 'warning',
          showCancelButton: true,
          confirmButtonText: 'Yes, Logout',
          cancelButtonText: 'Cancel',
          confirmButtonColor: '#1977cc',
          cancelButtonColor: '#dc3545',
          reverseButtons: true,
          backdrop: `
            rgba(0,0,0,0.45)
          `,
          customClass: {
            popup: 'rounded-4 shadow-lg',
            confirmButton: 'px-4 py-2',
            cancelButton: 'px-4 py-2'
          }

        }).then((result) => {

          if (result.isConfirmed) {

            Swal.fire({
              title: 'Logging Out...',
              html: 'Please wait ',
              timer: 1500,
              allowOutsideClick: false,
              showConfirmButton: false,
              didOpen: () => {
                Swal.showLoading();
              }
            });

            setTimeout(() => {
              window.location.href = logoutBtn.href;
            }, 1500);

          }

        });

      });

    }

    const mobileNavToggleBtn = document.querySelector('.mobile-nav-toggle');
    const pageBody = document.body;

    function toggleMobileNav() {
      if (!mobileNavToggleBtn) return;
      pageBody.classList.toggle('mobile-nav-active');
      mobileNavToggleBtn.classList.toggle('bi-list');
      mobileNavToggleBtn.classList.toggle('bi-x');
    }

    window.toggleHeaderMobileNav = function (e) {
      if (e && typeof e.preventDefault === 'function') {
        e.preventDefault();
      }
      toggleMobileNav();
    };

    if (mobileNavToggleBtn) {
      window.hasMobileNavHandler = true;
    }

    document.querySelectorAll('#navmenu a').forEach((link) => {
      link.addEventListener('click', () => {
        if (pageBody.classList.contains('mobile-nav-active')) {
          pageBody.classList.remove('mobile-nav-active');
          if (mobileNavToggleBtn) {
            mobileNavToggleBtn.classList.add('bi-list');
            mobileNavToggleBtn.classList.remove('bi-x');
          }
        }
      });
    });

    window.addEventListener('resize', function () {
      if (window.innerWidth > 1199 && pageBody.classList.contains('mobile-nav-active')) {
        pageBody.classList.remove('mobile-nav-active');
        if (mobileNavToggleBtn) {
          mobileNavToggleBtn.classList.add('bi-list');
          mobileNavToggleBtn.classList.remove('bi-x');
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHeaderNav);
  } else {
    initHeaderNav();
  }
