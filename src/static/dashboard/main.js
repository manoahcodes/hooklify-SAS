// SIDEBAR FUNCTION
(function () {
    const KEY = 'sidebar-collapsed';
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebar-toggle');

    if (!sidebar || !toggle) return;

    // restore state
    sidebar.classList.toggle(
        'sidebar-collapsed',
        localStorage.getItem(KEY) === 'true'
    );

    toggle.addEventListener('click', () => {
        const collapsed = sidebar.classList.toggle('sidebar-collapsed');
        localStorage.setItem(KEY, collapsed);
    });
})();

// TOAST FUNCTION
(function () {
    document.addEventListener('DOMContentLoaded', () => {
    const toast = document.querySelector('.toast');
    if (!toast) return;

    toast.querySelector('.toast-close')?.addEventListener('click', () => {
        toast.remove();
    });

    setTimeout(() => {
        toast.remove();
    }, 6000);
});
})()