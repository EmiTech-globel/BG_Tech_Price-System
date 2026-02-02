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

// ========================================
// DASHBOARD STATS AND ACTIVITY FEED
// ========================================
async function loadDashboardStats() {
    try {
        const response = await fetch('/api/admin/stats', {
            headers: { 'Authorization': 'Bearer ' + sessionStorage.getItem('access_token') }
        });
        const data = await response.json();
        
        if (data.success) {
            // Update Stats Cards
            document.getElementById('stat_today_value').textContent = '₦' + data.stats.today_value.toLocaleString(undefined, {minimumFractionDigits: 2});
            document.getElementById('stat_week_orders').textContent = data.stats.week_orders;
            
            const lowStockEl = document.getElementById('stat_low_stock');
            lowStockEl.textContent = data.stats.low_stock;
            if (data.stats.low_stock > 0) lowStockEl.style.color = '#F44336';

            // Update Activity Feed
            const feedContainer = document.getElementById('activityFeed');
            if (data.activity.length === 0) {
                feedContainer.innerHTML = '<p style="color:#999; text-align:center;">No recent activity.</p>';
                return;
            }

            let html = '<div style="display: flex; flex-direction: column; gap: 15px;">';
            data.activity.forEach(act => {
                html += `
                    <div style="display: flex; align-items: start; gap: 15px; padding-bottom: 15px; border-bottom: 1px solid #f5f5f5;">
                        <div style="background: ${act.color}20; color: ${act.color}; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.2em; flex-shrink: 0;">
                            ${act.icon}
                        </div>
                        <div style="flex-grow: 1;">
                            <div style="font-weight: 600; color: #333;">${act.title}</div>
                            <div style="font-size: 0.9em; color: #666; margin-top: 2px;">${act.desc}</div>
                        </div>
                        <div style="font-size: 0.8em; color: #999; white-space: nowrap;">
                            ${act.time_str}
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            feedContainer.innerHTML = html;
        }
    } catch (error) {
        console.error('Error loading dashboard stats:', error);
    }
}

// Set default dates (First day of month to Today)
function initReportDates() {
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    
    document.getElementById('reportEndDate').valueAsDate = today;
    document.getElementById('reportStartDate').valueAsDate = firstDay;
}

// Update description when report type changes
document.getElementById('reportType')?.addEventListener('change', function() {
    const desc = document.getElementById('reportDesc');
    switch(this.value) {
        case 'revenue':
            desc.textContent = "Generates a detailed PDF listing all approved quotes and total revenue for the selected period.";
            break;
        case 'material_usage':
            desc.textContent = "Shows a history of all materials used (Stock Out transactions) to help track consumption.";
            break;
        case 'inventory_health':
            desc.textContent = "Snapshot of current stock levels, calculating total asset value and highlighting low-stock items.";
            break;
    }
});

function downloadReport() {
    const type = document.getElementById('reportType').value;
    const start = document.getElementById('reportStartDate').value;
    const end = document.getElementById('reportEndDate').value;
    
    if (!start || !end) {
        alert("Please select a valid date range.");
        return;
    }

    const btn = document.querySelector('#reports button');
    if (!btn) {
        alert("Download button not found");
        return;
    }
    
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Generating...';
    btn.disabled = true;

    fetch(`/api/admin/report/download?type=${type}&start_date=${start}&end_date=${end}`, {
        credentials: 'include'
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(JSON.parse(text).error || 'Failed to generate report');
            });
        }
        return response.blob();
    })
    .then(blob => {
        // Create download link and trigger download
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `Report_${type}_${start}.pdf`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        
        btn.innerHTML = originalText;
        btn.disabled = false;
    })
    .catch(err => {
        alert("Error generating report: " + err.message);
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

// ========================================
// INITIALIZATION
// ========================================
window.addEventListener('load', () => {
    checkAuth(); // Ensure auth check runs first
    
    // Load Dashboard data
    loadDashboardStats();
    
    // Load other tabs in background
    loadQuotes();
    loadInventory();
    updateTrainingStats();
    initReportDates();
});