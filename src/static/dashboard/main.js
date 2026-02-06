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


// CREATE FUNCTIONS
document.addEventListener('DOMContentLoaded', function () {
    // Handle custom button selectors (Tone/Style)
    const selectorGroups = document.querySelectorAll('.selector-group');

    selectorGroups.forEach(group => {
        const inputId = group.dataset.inputId;
        const hiddenInput = document.getElementById(inputId);
        const buttons = group.querySelectorAll('.selection-btn');

        // Set initial state based on hidden input value (if form valid failed)
        if (hiddenInput.value) {
            const activeBtn = group.querySelector(`[data-value="${hiddenInput.value}"]`);
            if (activeBtn) setActiveStyle(activeBtn);
        }

        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                // Update Hidden Input
                hiddenInput.value = btn.dataset.value;

                // Reset all buttons in this group
                buttons.forEach(b => setInactiveStyle(b));

                // Set active style
                setActiveStyle(btn);
            });
        });
    });

    function setActiveStyle(btn) {
        // Remove inactive classes
        btn.classList.remove('bg-[#0f0f0f]', 'border-border-subtle', 'text-white/50');
        // Add active classes (Primary Color)
        btn.classList.add('bg-primary/10', 'border-primary/40', 'text-primary');
    }

    function setInactiveStyle(btn) {
        // Remove active classes
        btn.classList.remove('bg-primary/10', 'border-primary/40', 'text-primary');
        // Add inactive classes
        btn.classList.add('bg-[#0f0f0f]', 'border-border-subtle', 'text-white/50');
    }
});

/**
 * Handles dynamic sub-niche filtering and custom niche input toggling
 */
function initNicheHandler(nicheData) {
    const nicheSelect = document.getElementById('nicheSelect');
    const subNicheSelect = document.getElementById('subNicheSelect');
    const customWrapper = document.getElementById('customSubNicheWrapper');
    const customInput = document.getElementById('customSubNicheInput');

    if (!nicheSelect || !subNicheSelect) return;

    // Listen for Niche Change
    nicheSelect.addEventListener('change', function() {
        const selectedId = this.value;
        
        // Reset sub-niche dropdown
        subNicheSelect.innerHTML = '<option value="" disabled selected>Select Sub-Niche</option>';
        subNicheSelect.disabled = false;
        customWrapper.classList.add('hidden');
        customInput.required = false;

        // Populate from data
        if (nicheData[selectedId]) {
            nicheData[selectedId].forEach(sub => {
                const opt = document.createElement('option');
                opt.value = sub.id;
                opt.textContent = sub.name;
                subNicheSelect.appendChild(opt);
            });
        }

        // Add the "Other" option
        const otherOpt = document.createElement('option');
        otherOpt.value = "OTHER";
        otherOpt.textContent = "+ Add Custom Sub-Niche";
        otherOpt.classList.add('text-primary', 'font-bold');
        subNicheSelect.appendChild(otherOpt);
    });

    // Listen for Sub-Niche Change (to show custom input)
    subNicheSelect.addEventListener('change', function() {
        if (this.value === "OTHER") {
            customWrapper.classList.remove('hidden');
            customInput.required = true;
            customInput.focus();
        } else {
            customWrapper.classList.add('hidden');
            customInput.required = false;
        }
    });
}