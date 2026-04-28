
const toggleSidebar = document.getElementById('toggleSidebar');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const mobileBreakpoint = window.matchMedia('(max-width: 768px)');

function setSidebarState(isOpen) {
    if (!mobileBreakpoint.matches) {
        sidebar.classList.remove('active');
        sidebarOverlay.classList.remove('active');
        document.body.classList.remove('sidebar-open');
        toggleSidebar.setAttribute('aria-expanded', 'false');
        return;
    }

    sidebar.classList.toggle('active', isOpen);
    sidebarOverlay.classList.toggle('active', isOpen);
    document.body.classList.toggle('sidebar-open', isOpen);
    toggleSidebar.setAttribute('aria-expanded', String(isOpen));
}

function closeSidebarOnMobile() {
    setSidebarState(false);
}

function handleResize() {
    if (!mobileBreakpoint.matches) {
        closeSidebarOnMobile();
    }
}

toggleSidebar.addEventListener('click', function () {
    if (!mobileBreakpoint.matches) {
        return;
    }

    const isOpen = sidebar.classList.contains('active');
    setSidebarState(!isOpen);
});

sidebarOverlay.addEventListener('click', closeSidebarOnMobile);
window.addEventListener('resize', handleResize);
handleResize();

// Handle Start Visit Button
function startVisit(patientName) {
    alert(`Starting visit with ${patientName}...`);
    // Add actual implementation here
}

// Handle Logout

function handleLogout() {
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = "/doctor/logout/";
    }
}


// Sidebar menu item click handler
const menuItems = document.querySelectorAll('.sidebar-menu a:not(.menu-toggle)');
menuItems.forEach(item => {
    item.addEventListener('click', function (e) {
        // e.preventDefault(); // Uncomment if needed

        // Remove active class from all items
        menuItems.forEach(menu => menu.classList.remove('active'));

        // Add active class to clicked item
        this.classList.add('active');

        closeSidebarOnMobile();
    });
});

// Submenu toggle functionality
const menuToggles = document.querySelectorAll('.menu-toggle');
menuToggles.forEach(toggle => {
    toggle.addEventListener('click', function (e) {
        e.preventDefault();

        const parentLi = this.parentElement;
        const submenu = parentLi.querySelector('.submenu');
        const isActive = submenu.classList.contains('active');

        // Close all other submenus (accordion behavior)
        document.querySelectorAll('.submenu').forEach(menu => {
            menu.classList.remove('active');
        });

        document.querySelectorAll('.menu-toggle').forEach(t => {
            t.classList.remove('expanded');
            t.classList.remove('parent-active');
        });

        // Toggle current submenu
        if (!isActive) {
            submenu.classList.add('active');
            this.classList.add('expanded');
            this.classList.add('parent-active');
        }
    });
});

// Submenu item click handler
const submenuItems = document.querySelectorAll('.submenu a');
submenuItems.forEach(item => {
    item.addEventListener('click', function (e) {
        // e.preventDefault(); // Uncomment if needed

        // Remove active class from all submenu items
        submenuItems.forEach(menu => menu.classList.remove('active'));

        // Add active class to clicked item
        this.classList.add('active');

        // Keep parent menu expanded and highlighted
        const submenu = this.closest('.submenu');
        const parentToggle = submenu.previousElementSibling;
        if (!submenu.classList.contains('active')) {
            submenu.classList.add('active');
        }
        if (!parentToggle.classList.contains('expanded')) {
            parentToggle.classList.add('expanded');
        }
        if (!parentToggle.classList.contains('parent-active')) {
            parentToggle.classList.add('parent-active');
        }

        closeSidebarOnMobile();
    });
});

document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
        closeSidebarOnMobile();
    }
});

// Add smooth scroll behavior
document.documentElement.style.scrollBehavior = 'smooth';
