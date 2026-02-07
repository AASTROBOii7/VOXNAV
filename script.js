// Core VOXNAV Logic

// Helper to get state
const State = {
    isTrained: () => localStorage.getItem('voxnav_voice_trained') === 'true',
    isActive: () => localStorage.getItem('voxnav_active') === 'true',
    toggleActive: () => {
        const current = State.isActive();
        localStorage.setItem('voxnav_active', (!current).toString());
        return !current;
    }
};

window.onload = function () {
    refreshUI();

    // Restore toggle switches
    const toggles = ['gameplay', 'browser', 'canva', 'docs', 'system', 'home'];
    toggles.forEach(id => {
        const el = document.getElementById('toggle-' + id);
        if (el) { // Only on index page
            if (localStorage.getItem('voxnav_' + id) === 'true') {
                el.checked = true;
            }
            el.addEventListener('change', (e) => {
                localStorage.setItem('voxnav_' + id, e.target.checked);
            });
        }
    });
};

function refreshUI() {
    const btn = document.getElementById('enable-btn');
    const statusInd = document.getElementById('status-indicator');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');

    if (!btn) return; // Not on index page

    if (State.isTrained()) {
        statusInd.style.display = 'flex';

        if (State.isActive()) {
            // GREEN STATE
            btn.innerText = "VOXNAV Enabled";
            btn.className = "btn-primary status-active"; // Green
            statusDot.style.background = "#4caf50";
            statusDot.style.boxShadow = "0 0 10px #4caf50";
            statusText.innerText = "Active";
            statusText.style.color = "#4caf50";
        } else {
            // RED STATE (Disabled but trained)
            btn.innerText = "VOXNAV Disabled";
            btn.className = "btn-primary status-inactive"; // Red
            statusDot.style.background = "#ff4444";
            statusDot.style.boxShadow = "none";
            statusText.innerText = "Inactive";
            statusText.style.color = "#ff4444";
        }
    } else {
        // GOLD STATE (Not trained)
        btn.innerText = "Enable Assistant";
        btn.className = "btn-primary pulse-animation";
        statusInd.style.display = 'none';

        // Remove active/inactive classes if present
        btn.classList.remove('status-active', 'status-inactive');
    }
}

function handleMainButton() {
    if (!State.isTrained()) {
        // Go to training
        window.location.href = 'training.html';
    } else {
        // Toggle Active State
        State.toggleActive();
        refreshUI();
    }
}
