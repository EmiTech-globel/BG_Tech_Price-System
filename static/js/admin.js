// ========================================
// AUTHENTICATION CHECK AND LOGOUT
// ========================================

// Check if admin is authenticated
async function checkAuth() {
    try {
        const response = await fetch('/api/auth/check');
        if (!response.ok) {
            window.location.href = '/admin/login';
        }
    } catch (error) {
        console.error('Auth check failed:', error);
        window.location.href = '/admin/login';
    }
}

// Handle logout
async function handleLogout() {
    if (!confirm('Are you sure you want to logout?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/auth/logout', {
            method: 'POST'
        });
        
        const data = await response.json();
        window.location.href = data.redirect || '/admin/login';
    } catch (error) {
        console.error('Logout error:', error);
        window.location.href = '/admin/login';
    }
}

// Run auth check on load
checkAuth();

// Load initial data
window.addEventListener('load', () => {
    loadQuotes();
    loadInventory();
    updateTrainingStats();
});
