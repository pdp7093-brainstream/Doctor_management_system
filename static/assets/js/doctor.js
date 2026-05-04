
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


// ===== Low Stock Alert System =====

// Bell dropdown toggle
function toggleBellDropdown() {
    const dropdown = document.getElementById('bellDropdown');
    if (dropdown.style.display === 'none') {
        dropdown.style.display = 'block';
        loadBellAlerts();
    } else {
        dropdown.style.display = 'none';
    }
}

// Bahar click karne pe close
document.addEventListener('click', function(e) {
    const bell = document.getElementById('bellBtn');
    const dropdown = document.getElementById('bellDropdown');
    if (bell && dropdown && !bell.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.style.display = 'none';
    }
});

// Low stock count fetch karo
function fetchLowStockCount() {
    fetch('/medicine/low-stock-count/')
        .then(res => res.json())
        .then(data => {
            const count = data.count;

            // Bell badge
            const badge = document.getElementById('bellBadge');
            if (badge) {
                badge.textContent = count;
                badge.style.display = count > 0 ? 'inline' : 'none';
            }

            // Sidebar badge
            const sidebarBadge = document.getElementById('sidebarLowStockBadge');
            const sidebarCount = document.getElementById('sidebarLowStockCount');
            if (sidebarBadge) {
                sidebarBadge.textContent = count;
                sidebarBadge.style.display = count > 0 ? 'inline' : 'none';
            }
            if (sidebarCount) {
                sidebarCount.textContent = count;
                sidebarCount.style.display = count > 0 ? 'inline' : 'none';
            }
        });
}

// Bell dropdown alerts load karo
function loadBellAlerts() {
    fetch('/medicine/low-stock-list/')
        .then(res => res.json())
        .then(data => {
            const list = document.getElementById('bellAlertList');
            if (!data.alerts.length) {
                list.innerHTML = `
                    <div class="text-center py-4 text-muted small">
                        <i class="bi bi-check-circle text-success d-block mb-2"
                            style="font-size:1.5rem;"></i>
                        All medicines well stocked!
                    </div>`;
                return;
            }

            list.innerHTML = data.alerts.map(a => `
                <div style="padding:10px 16px; border-bottom:1px solid #f0f0f0;
                            display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-size:0.88rem; font-weight:600; color:#1a2744;">
                            ${a.name}
                            <span style="font-size:0.75rem; color:#888; font-weight:400;">
                                ${a.power}
                            </span>
                        </div>
                        <div style="font-size:0.78rem; color:#888;">
                            Alert at: ${a.low_alert}
                        </div>
                    </div>
                    <span style="
                        background:${a.is_out ? '#dc3545' : '#fd7e14'};
                        color:#fff; border-radius:20px;
                        padding:3px 10px; font-size:0.75rem; font-weight:700;">
                        ${a.is_out ? 'OUT' : a.stock + ' left'}
                    </span>
                </div>
            `).join('');
        });
}

// Page load pe aur har 60 second pe check karo
fetchLowStockCount();
setInterval(fetchLowStockCount, 60000);
