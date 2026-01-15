function toggleDropdown() {
        const menu = document.getElementById('platform-menu');
        const chevron = document.getElementById('dropdown-chevron');
        
        if (menu.classList.contains('hidden')) {
            // Show menu
            menu.classList.remove('hidden');
            menu.classList.add('opacity-100', 'visible', 'translate-y-0');
            menu.classList.remove('opacity-0', 'invisible', '-translate-y-2');
            chevron.style.transform = 'rotate(180deg)';
        } else {
            // Hide menu
            closeDropdown();
        }
    }

    function closeDropdown() {
        const menu = document.getElementById('platform-menu');
        const chevron = document.getElementById('dropdown-chevron');
        
        menu.classList.add('hidden');
        menu.classList.remove('opacity-100', 'visible', 'translate-y-0');
        menu.classList.add('opacity-0', 'invisible', '-translate-y-2');
        chevron.style.transform = 'rotate(0deg)';
    }

    function selectPlatform(platformName) {
        // 1. Update the visible text immediately (for UX)
        document.getElementById('current-platform-label').innerText = platformName;
        
        // 2. Close the dropdown
        closeDropdown();

        // 3. HTMX automatically submits the form because the clicked element was type="submit"
    }

    // Close if clicking outside
    window.addEventListener('click', function(e) {
        const container = document.getElementById('platform-dropdown-container');
        if (!container.contains(e.target)) {
            closeDropdown();
        }
    });