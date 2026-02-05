// ========================================
// QUOTE STATUS MANAGEMENT & OFFCUTS UI
// ========================================

// Show material breakdown before confirming order
async function showMaterialBreakdown(quoteId) {
    // Show modal immediately with loading skeleton so admin sees quick feedback
    const breakdownEl = document.getElementById('materialBreakdown');
    const confirmBtn = document.getElementById('confirmDeductBtn');
    breakdownEl.innerHTML = '<div style="text-align:center; padding:30px;">Loading details...</div>';
    document.getElementById('confirmMaterialModal').style.display = 'flex';
    confirmBtn.disabled = true;

    try {
        const response = await fetch(`/get_quotes?id=${quoteId}`);
        const result = await response.json();
        
        if (!result.success || !result.quotes[0]) {
            showNotification('Quote not found', 'error');
            closeMaterialModal();
            return;
        }
        
        const quote = result.quotes[0];
        let breakdown = '';
        
        // Build material breakdown HTML
        if (Array.isArray(quote.items) && quote.items.length > 0) {
            // Bulk order
            breakdown = '<div style="font-size: 0.95em;">';

            // Fetch inventory to estimate number of sheets needed for each item
            let inventories = [];
            try {
                const invResp = await fetch('/api/inventory');
                inventories = await invResp.json();
            } catch (e) {
                // ignore - we'll fall back to simple display
                inventories = [];
            }

            quote.items.forEach((item, i) => {
                const material = item.material || 'Unknown';
                const color = item.material_color || 'N/A';
                const thickness = item.thickness_mm || item.thickness || 'N/A';
                const qty = item.quantity || 1;

                // Try to find matching inventory (material + color + thickness)
                let sheetsText = `${qty} × Sheet(s)`;
                try {
                    const invMatch = inventories.find(inv => (inv.material === material && String(inv.color) === String(color) && Number(inv.thickness) === Number(thickness)));
                    if (invMatch && invMatch.sheet_width_mm && invMatch.sheet_height_mm) {
                        const areaNeeded = (item.width_mm || item.width || 0) * (item.height_mm || item.height || 0) * qty;
                        const sheetArea = Number(invMatch.sheet_width_mm) * Number(invMatch.sheet_height_mm);
                        const sheetsNeeded = sheetArea > 0 ? Math.ceil(areaNeeded / sheetArea) : qty;
                        sheetsText = `${sheetsNeeded} × Sheet(s)`;
                    }
                } catch (e) {
                    // ignore and use fallback
                }

                breakdown += `
                    <div style="margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #ddd;">
                        <strong>Item ${i + 1}:</strong> ${material} ${color} (${thickness}mm)<br/>
                        Quantity: ${sheetsText}
                    </div>
                `;
            });
            breakdown += '</div>';
        } else {
            // Single quote
            const material = quote.material || 'Unknown';
            const color = quote.material_color || 'N/A';
            const thickness = quote.thickness_mm || 'N/A';
            breakdown = `
                <div style="font-size: 0.95em;">
                    <div><strong>Material:</strong> ${material}</div>
                    <div><strong>Color:</strong> ${color}</div>
                    <div><strong>Thickness:</strong> ${thickness}mm</div>
                    <div><strong>Size:</strong> ${quote.width_mm || 'N/A'} × ${quote.height_mm || 'N/A'}mm</div>
                    <div><strong>Quantity:</strong> ${quote.quantity || 1}</div>
                </div>
            `;
        }
        
        document.getElementById('materialBreakdown').innerHTML = breakdown;
        document.getElementById('confirmDeductBtn').setAttribute('data-quote-id', quoteId);
        document.getElementById('confirmDeductBtn').disabled = false;
        document.getElementById('confirmMaterialModal').style.display = 'flex';
    } catch (error) {
        showNotification('Error loading quote details: ' + error.message, 'error');
    }
}

// Close material modal
function closeMaterialModal() {
    document.getElementById('confirmMaterialModal').style.display = 'none';
    document.getElementById('materialBreakdown').innerHTML = '';
}

// Confirm quote order and deduct materials
async function confirmQuoteOrder() {
    const quoteId = document.getElementById('confirmDeductBtn').getAttribute('data-quote-id');
    const btn = document.getElementById('confirmDeductBtn');
    const originalText = btn.innerHTML;
    
    btn.innerHTML = 'Processing...';
    btn.disabled = true;
    
    try {
        const response = await fetch(`/api/quote/${quoteId}/confirm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('✅ Order confirmed and materials deducted from inventory', 'success');
            closeMaterialModal();
            loadQuotes();
            loadInventory?.();
        } else {
            showNotification('Error: ' + (data.error || 'Could not confirm order'), 'error');
        }
    } catch (error) {
        showNotification('Error confirming order: ' + error.message, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// Cancel confirmed order
async function cancelQuoteOrder(quoteId) {
    const confirmed = await showModalChoice(
        'Cancel Order',
        'Are you sure? This will restore materials to inventory and change status to cancelled.',
        [
            { label: 'Keep Order', value: 'no' },
            { label: 'Cancel Order', value: 'yes' }
        ]
    );
    
    if (confirmed !== 'yes') return;
    
    try {
        const response = await fetch(`/api/quote/${quoteId}/cancel`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('✅ Order cancelled and materials restored', 'success');
            loadQuotes();
            loadInventory?.();
        } else {
            showNotification('Error: ' + (data.error || 'Could not cancel order'), 'error');
        }
    } catch (error) {
        showNotification('Error cancelling order: ' + error.message, 'error');
    }
}

// Mark quote as completed
async function markQuoteCompleted(quoteId) {
    try {
        const response = await fetch(`/api/quote/${quoteId}/mark-completed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('🎉 Quote marked as completed', 'success');
            loadQuotes();
        } else {
            showNotification('Error: ' + (data.error || 'Could not mark as completed'), 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

// Filter quotes by status
async function filterQuotesByStatus() {
    const status = document.getElementById('statusFilter').value;
    const container = document.getElementById('quotesContainer');
    const loading = document.getElementById('quotesLoading');
    
    loading.style.display = 'block';
    container.innerHTML = '';
    
    try {
        const response = await fetch('/get_quotes');
        const result = await response.json();
        
        loading.style.display = 'none';
        
        if (result.success && result.quotes.length > 0) {
            const filtered = status 
                ? result.quotes.filter(q => (q.status || 'draft') === status)
                : result.quotes;
            
            if (filtered.length > 0) {
                container.innerHTML = filtered.map(quote => createQuoteCard(quote)).join('');
            } else {
                container.innerHTML = `<p style="text-align: center; color: #999;">No quotes with status: ${status}</p>`;
            }
        } else {
            container.innerHTML = '<p style="text-align: center; color: #999;">No quotes found.</p>';
        }
    } catch (error) {
        loading.style.display = 'none';
        container.innerHTML = '<p style="text-align: center; color: #d9534f;">Error loading quotes: ' + error.message + '</p>';
    }
}

// ========================================
// OFFCUT MANAGEMENT
// ========================================

// Show offcut panel
async function showOffcutPanel() {
    const panel = document.getElementById('offcutPanel');
    const list = document.getElementById('offcutsList');
    
    list.innerHTML = '<div style="text-align: center; color: #999;"><div class="spinner" style="margin: 20px auto;"></div>Loading offcuts...</div>';
    panel.style.display = 'block';
    
    try {
        const response = await fetch('/api/offcuts');
        const data = await response.json();
        
        if (data.success && data.offcuts.length > 0) {
            let html = '<div style="display: grid; gap: 15px;">';
            
            data.offcuts.forEach(offcut => {
                const material = offcut.material || 'Unknown';
                const color = offcut.color || 'N/A';
                const thickness = offcut.thickness_mm || 'N/A';
                const dimensions_mm = `${offcut.width_mm || '0'} × ${offcut.height_mm || '0'} mm`;
                const width_ft = (Number(offcut.width_mm || 0) / 304.8);
                const height_ft = (Number(offcut.height_mm || 0) / 304.8);
                const dimensions_ft = `${width_ft.toFixed(1)}ft × ${height_ft.toFixed(1)}ft`;
                const status = offcut.status || 'available';
                
                html += `
                    <div class="offcut-card">
                        <div style="flex: 1;">
                            <div style="font-weight: 600; margin-bottom: 5px;">${material} (${thickness}mm) - ${color}</div>
                            <div style="font-size: 0.9em; color: #666;">
                                Leftover: ${dimensions_ft} (${dimensions_mm})<br/>
                                <div style="margin-top:4px; font-size:0.85em; color:#777;">Area: ${offcut.area_sq_ft ? offcut.area_sq_ft.toFixed(2) : 'N/A'} sq ft</div>
                                <span style="display: inline-block; background: ${status === 'scrap' ? '#ffcdd2' : '#c8e6c9'}; color: ${status === 'scrap' ? '#c62828' : '#388e3c'}; padding: 2px 8px; border-radius: 3px; font-size: 0.8em; margin-top: 5px;">
                                    ${status === 'scrap' ? 'Scrap' : 'Available'}
                                </span>
                            </div>
                        </div>
                        <div style="display: flex; gap: 5px;">
                            ${status !== 'scrap' ? `<button onclick="useOffcut(${offcut.id})" class="action-button" style="background: #4CAF50; color: white;">Use</button>` : ''}
                            ${status !== 'scrap' ? `<button onclick="markOffcutScrap(${offcut.id})" class="action-button" style="background: #F44336; color: white;">Scrap</button>` : `<button disabled style="background: #ccc; color: #999; cursor: not-allowed;">Scrap</button>`}
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            list.innerHTML = html;
        } else {
            list.innerHTML = '<p style="text-align: center; color: #999; padding: 40px 20px;">No offcuts available yet. They will appear after orders are confirmed.</p>';
        }
    } catch (error) {
        list.innerHTML = '<p style="text-align: center; color: #d9534f;">Error loading offcuts: ' + error.message + '</p>';
    }
}

// Close offcut panel
function closeOffcutPanel() {
    document.getElementById('offcutPanel').style.display = 'none';
}

// Mark offcut as scrap
async function markOffcutScrap(offcutId) {
    const confirmed = await showModalChoice(
        'Mark as Scrap',
        'Mark this offcut as scrap? It will no longer be available for reuse.',
        [
            { label: 'Keep', value: 'no' },
            { label: 'Mark Scrap', value: 'yes' }
        ]
    );
    
    if (confirmed !== 'yes') return;
    
    try {
        const response = await fetch(`/api/offcut/${offcutId}/mark-scrap`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('✅ Offcut marked as scrap', 'success');
            showOffcutPanel();
        } else {
            showNotification('Error: ' + (data.error || 'Could not update offcut'), 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

// Use offcut (placeholder for future implementation)
async function useOffcut(offcutId) {
    showNotification('Offcut tracking feature - coming soon! You can use this offcut when creating a new quote.', 'info');
}
