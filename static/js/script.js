// CNC Pricing System - Main JavaScript

let extractedData = null;
let currentJobData = null;
let currentPrice = null;
let bulkItems = [];

// Global variables for discount state
let selectedDiscountPercent = 0;
let discountAppliedToCurrentQuote = false;

// ========================================
// MODAL DIALOG FUNCTIONS
// ========================================

/**
 * Show a beautiful modal dialog for user input (replaces prompt())
 * @param {string} title - Modal title
 * @param {string} message - Message to display
 * @param {string} placeholder - Input placeholder text
 * @param {string} defaultValue - Default input value
 * @returns {Promise<string>} - User input or empty string if cancelled
 */
function showModalInput(title, message, placeholder = '', defaultValue = '') {
    return new Promise((resolve) => {
        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'modal-dialog';
        modal.innerHTML = `
            <div class="modal-header">
                <span>${title}</span>
                <button class="modal-close-btn">×</button>
            </div>
            <div class="modal-body">
                <div class="modal-message">${message}</div>
                <input type="text" class="modal-input" placeholder="${placeholder}" value="${defaultValue}">
            </div>
            <div class="modal-footer">
                <button class="modal-btn modal-btn-secondary cancel-btn">Cancel</button>
                <button class="modal-btn modal-btn-primary ok-btn">OK</button>
            </div>
        `;
        
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
        
        const inputField = modal.querySelector('.modal-input');
        const okBtn = modal.querySelector('.ok-btn');
        const cancelBtn = modal.querySelector('.cancel-btn');
        const closeBtn = modal.querySelector('.modal-close-btn');
        
        // Focus input
        setTimeout(() => inputField.focus(), 100);
        
        // Handle OK
        const handleOK = () => {
            resolve(inputField.value);
            overlay.remove();
        };
        
        // Handle Cancel/Close
        const handleCancel = () => {
            resolve('');
            overlay.remove();
        };
        
        okBtn.addEventListener('click', handleOK);
        cancelBtn.addEventListener('click', handleCancel);
        closeBtn.addEventListener('click', handleCancel);
        
        // Enter key to submit
        inputField.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleOK();
        });
        
        // Escape key to cancel
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && overlay.parentElement) handleCancel();
        });
    });
}

/**
 * Show a modal with custom buttons for selection (e.g., machine type choice)
 * @param {string} title - Modal title
 * @param {string} message - Message to display
 * @param {Array} buttons - Array of {label, value} objects
 * @returns {Promise<string>} - Selected button value or empty string
 */
function showModalChoice(title, message, buttons = []) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        
        const modal = document.createElement('div');
        modal.className = 'modal-dialog';
        
        let buttonsHTML = '';
        buttons.forEach((btn, idx) => {
            const btnClass = idx === buttons.length - 1 ? 'modal-btn-primary' : 'modal-btn-secondary';
            buttonsHTML += `<button class="modal-btn ${btnClass}" data-value="${btn.value}">${btn.label}</button>`;
        });
        
        modal.innerHTML = `
            <div class="modal-header">
                <span>${title}</span>
                <button class="modal-close-btn">×</button>
            </div>
            <div class="modal-body">
                <div class="modal-message">${message}</div>
            </div>
            <div class="modal-footer">
                ${buttonsHTML}
            </div>
        `;
        
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
        
        const closeBtn = modal.querySelector('.modal-close-btn');
        const btnElements = modal.querySelectorAll('[data-value]');
        
        const handleClose = () => {
            resolve('');
            overlay.remove();
        };
        
        btnElements.forEach(btn => {
            btn.addEventListener('click', () => {
                resolve(btn.dataset.value);
                overlay.remove();
            });
        });
        
        closeBtn.addEventListener('click', handleClose);
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && overlay.parentElement) handleClose();
        });
    });
}

/**
 * Show a modal alert (info, success, error, warning)
 * @param {string} title - Modal title
 * @param {string} message - Message to display
 * @param {string} type - Type: 'info', 'success', 'error', 'warning'
 */
function showModalAlert(title, message, type = 'info') {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    
    const modal = document.createElement('div');
    modal.className = 'modal-dialog';
    
    // Add icon based on type
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    else if (type === 'error') icon = '❌';
    else if (type === 'warning') icon = '⚠️';
    
    modal.innerHTML = `
        <div class="modal-header">
            <span>${icon} ${title}</span>
            <button class="modal-close-btn">×</button>
        </div>
        <div class="modal-body">
            <div class="modal-message">${message}</div>
        </div>
        <div class="modal-footer">
            <button class="modal-btn modal-btn-primary ok-btn">OK</button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    const okBtn = modal.querySelector('.ok-btn');
    const closeBtn = modal.querySelector('.modal-close-btn');
    
    const handleClose = () => overlay.remove();
    
    okBtn.addEventListener('click', handleClose);
    closeBtn.addEventListener('click', handleClose);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === 'Escape') handleClose();
    });
}

let bulkItemCounter = 0;

// ========================================
// TAB MANAGEMENT FUNCTIONS
// ========================================

function showTab(tabName) {
    // Remove active class from all tabs and contents
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    // Add active class to clicked tab and content
    const activeTab = document.querySelector(`.tab[onclick*="${tabName}"]`);
    const activeContent = document.getElementById(tabName);
    
    if (activeTab && activeContent) {
        activeTab.classList.add('active');
        activeContent.classList.add('active');
    }
    
    // Hide result box when switching tabs (only on main page)
    const resultBox = document.getElementById('resultBox');
    if (resultBox) {
        resultBox.classList.remove('show');
    }
    
    // Load data for specific tabs
    if (tabName === 'quotes') {
        loadQuotes();
    } else if (tabName === 'inventory') {
        loadInventory();
    } else if (tabName === 'addjob') {
        updateTrainingStats();
    }
}

// ========================================
// FILE UPLOAD AND ANALYSIS FUNCTIONS
// ========================================

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');

// Only attach listeners if elements exist (not on admin pages)
if (uploadArea && fileInput) {
    uploadArea.addEventListener('click', () => fileInput.click());

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
}

// ========================================
// FILE UPLOAD FUNCTIONS
// ========================================

async function handleFile(file) {
    const isSVG = file.name.toLowerCase().endsWith('.svg');
    const isDXF = file.name.toLowerCase().endsWith('.dxf');
    
    if (!isSVG && !isDXF) {
        showNotification('Please upload a DXF or SVG file!', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    showLoading('uploadLoading');
    hideElement('fileInfo');
    hideElement('multiItemInfo');
    document.getElementById('uploadCalcBtn').disabled = true;
    
    try {
        const endpoint = isDXF ? '/analyze_dxf_file' : '/analyze_file';
        const response = await fetch(endpoint, { method: 'POST', body: formData });
        const result = await response.json();
        
        hideLoading('uploadLoading');
        
        if (result.success) {
            if (result.file_type === 'dxf' && result.multiple_items && result.total_items > 1) {
                showNotification(`${result.message}`, 'success');
                displayDxfMultiItemResults(result);
            } else {
                extractedData = result.items ? result.items[0] : result;
                displayExtractedInfo(extractedData);
                document.getElementById('uploadCalcBtn').disabled = false;
                if (result.file_type === 'dxf') {
                    showNotification(`${result.message}`, 'success');
                }
            }
        } else {
            showNotification(`Error: ${result.error}`, 'error');
        }
    } catch (error) {
        hideLoading('uploadLoading');
        showNotification(`Upload failed: ${error.message}`, 'error');
    }
}

async function displayDxfMultiItemResults(result) {
    console.log("Displaying DXF multi-item results:", result);
    
    try {
        // Ask user to select cutting type for all items using modal
        const selected = await showModalChoice(
            '🔧 Select Machine Type',
            'Which machine type should be used for all jobs in this file?',
            [
                { label: 'Laser Cutting', value: '1' },
                { label: 'CNC Router', value: '2' }
            ]
        );
        
        const selectedCutting = selected === '2' ? 'CNC Router' : 'Laser Cutting';
        
        // Convert DXF items to bulk items format
        bulkItems = result.items.map((item, index) => ({
            id: index,
            name: item.name,
            material: '',
            thickness: 0,
            color: '',
            width: item.width_mm,
            height: item.height_mm,
            letters: item.num_letters,
            shapes: item.num_shapes,
            complexity: item.complexity_score,
            details: item.has_intricate_details,
            cuttingType: selectedCutting,
            time: item.cutting_time_minutes,
            quantity: 1,
            rush: 0,
            price: 0,
            inventory: null
        }));
        
        updateBulkItemsDisplay();
        showTab('bulk');
        showNotification(`Using ${selectedCutting} for all jobs`, 'success');
        
    } catch (error) {
        console.error("Error displaying DXF multi-items:", error);
        showNotification('Error displaying multiple jobs', 'error');
    }
}

function displayExtractedInfo(data) {
    document.getElementById('extractedWidth').textContent = data.width_mm + 'mm';
    document.getElementById('extractedHeight').textContent = data.height_mm + 'mm';
    document.getElementById('extractedShapes').textContent = data.num_shapes;
    document.getElementById('extractedLetters').textContent = data.num_letters;
    document.getElementById('extractedComplexity').textContent = data.complexity_score + '/5';
    document.getElementById('extractedTime').textContent = data.cutting_time_minutes + ' minutes';
    
    showElement('fileInfo');
}

async function calculateFromUpload() {
    const material = document.getElementById('uploadMaterial').value;
    const thickness = document.getElementById('uploadThickness').value;
    const color = document.getElementById('uploadColor').value;
    const cuttingType = document.getElementById('uploadCuttingType').value;
    const quantity = document.getElementById('uploadQuantity').value;
    const rush = document.getElementById('uploadRush').checked ? 1 : 0;
    
    if (!material || !thickness || !color) {
        showNotification('Please select material, thickness, and color!', 'warning');
        return;
    }
    
    if (!extractedData) {
        showNotification('Please upload a file first!', 'warning');
        return;
    }
    
    const jobData = {
        material: material,
        thickness: parseFloat(thickness),
        color: color,
        letters: extractedData.num_letters,
        shapes: extractedData.num_shapes,
        complexity: extractedData.complexity_score,
        details: extractedData.has_intricate_details,
        width: extractedData.width_mm,
        height: extractedData.height_mm,
        cuttingType: cuttingType,
        time: extractedData.cutting_time_minutes,
        quantity: parseInt(quantity),
        rush: rush
    };
    
    await sendPriceRequest(jobData);
}

async function calculatePrice() {
    const material = document.getElementById('material').value;
    const thickness = document.getElementById('thickness').value;
    const color = document.getElementById('manualColor').value;
    const width = document.getElementById('width').value;
    const height = document.getElementById('height').value;
    const time = document.getElementById('time').value;
    const cuttingType = document.getElementById('cuttingType').value;
    const quantity = document.getElementById('quantity').value;
    const letters = document.getElementById('letters').value;
    const shapes = document.getElementById('shapes').value;
    const complexity = document.getElementById('complexity').value;
    const details = document.getElementById('details').checked ? 1 : 0;
    const rush = document.getElementById('rush').checked ? 1 : 0;
    
    if (!material || !thickness || !color || !width || !height || !time) {
        showNotification('Please fill in all required fields (including color)!', 'warning');
        return;
    }
    
    const jobData = {
        material: material,
        thickness: parseFloat(thickness),
        color: color,  // NEW
        letters: parseInt(letters),
        shapes: parseInt(shapes),
        complexity: parseInt(complexity),
        details: details,
        width: parseFloat(width),
        height: parseFloat(height),
        cuttingType: cuttingType,
        time: parseFloat(time),
        quantity: parseInt(quantity),
        rush: rush
    };
    
    await sendPriceRequest(jobData);
}


// ========================================
// UPDATED PRICE REQUEST FUNCTION
// ========================================

async function sendPriceRequest(jobData) {
    try {
        const response = await fetch('/calculate_price', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(jobData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            displayResultWithInventory(result.price, jobData, result.inventory, result.warnings);
        } else {
            showNotification('Error calculating price: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

// ========================================
// NEW DISPLAY FUNCTION WITH INVENTORY INFO
// ========================================

function displayResultWithInventory(price, jobData, inventory, warnings) {
    // Store current quote data
    currentJobData = jobData;
    currentPrice = price;
    discountAppliedToCurrentQuote = false;
    
    // Display price
    document.getElementById('priceDisplay').textContent = '₦' + price.toLocaleString('en-NG', {
        minimumFractionDigits: 2, 
        maximumFractionDigits: 2
    });
    
    // Display basic job details
    document.getElementById('resultMaterial').textContent = jobData.material + ' (' + jobData.thickness + 'mm)';
    document.getElementById('resultSize').textContent = jobData.width + 'mm × ' + jobData.height + 'mm';
    document.getElementById('resultComplexity').textContent = jobData.complexity + '/5';
    document.getElementById('resultCutting').textContent = jobData.cuttingType;
    document.getElementById('resultQuantity').textContent = jobData.quantity;
    document.getElementById('resultTime').textContent = jobData.time + ' minutes';
    
    // Reset discount UI
    document.getElementById('discountBreakdown').style.display = 'none';
    document.getElementById('applyDiscountBtn').disabled = false;
    document.getElementById('applyDiscountBtn').textContent = 'Apply Discount';
    document.getElementById('applyDiscountBtn').style.opacity = '1';

    // Create or update inventory status section
    let inventorySection = document.getElementById('inventoryStatus');
    if (!inventorySection) {
        inventorySection = document.createElement('div');
        inventorySection.id = 'inventoryStatus';
        inventorySection.style.cssText = 'margin: 20px 0; padding: 15px; border-radius: 10px;';
        
        const detailsDiv = document.querySelector('.details');
        if (detailsDiv && detailsDiv.parentNode) {
            detailsDiv.parentNode.insertBefore(inventorySection, detailsDiv.nextSibling);
        } else {
            // Fallback: append to result box if .details not found
            const resultBox = document.getElementById('resultBox');
            if (resultBox) {
                resultBox.appendChild(inventorySection);
            }
        }
    }
    
    // Build inventory status HTML - Initialize statusHTML first
    let statusHTML = '';
    
    // Add material cost header if in stock
    if (inventory.in_stock){
        statusHTML += ` 
        <div style="text-align: center; margin-bottom: 15px;">
           <h3 style="margin-bottom: 15px; font-size: 20px;">Material Status</h3>
           <strong style="font-size: 30px;">Material Cost: ₦${inventory.material_cost}</strong>
        </div>
        `;
    }
    
    // Add stock status section
    if (inventory.in_stock) {
        statusHTML += `
            <div style="background: rgba(76, 175, 80, 0.2); padding: 15px; border-radius: 8px; border-left: 4px solid #4CAF50;">
                <div style="font-weight: bold; color: #2e7d32; margin-bottom: 10px;">
                    ${inventory.message}
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9em;">
                    <div><strong>Material:</strong> ${jobData.material}</div>
                    <div><strong>Color:</strong> ${jobData.color || 'N/A'}</div>
                    <div><strong>Area Needed:</strong> ${inventory.area_sq_ft} sq ft</div>
                    <div><strong>Price/sq ft:</strong> ₦${inventory.price_per_sq_ft.toLocaleString()}</div>
                </div>
            </div>
        `;
    } else {
        statusHTML += `
            <div style="background: rgba(244, 67, 54, 0.2); padding: 15px; border-radius: 8px; border-left: 4px solid #F44336;">
                <div style="font-weight: bold; color: #c62828; margin-bottom: 10px;">
                    ❌ ${inventory.message}
                </div>
                <div style="font-size: 0.9em; color: #d32f2f;">
                    ${inventory.warning || 'This material needs to be added to inventory or restocked.'}
                </div>
            </div>
        `;
    }
    
    inventorySection.innerHTML = statusHTML;

    // Display warnings if any
    if (warnings && warnings.length > 0) {
        let warningSection = document.getElementById('warningSection');
        if (!warningSection) {
            warningSection = document.createElement('div');
            warningSection.id = 'warningSection';
            
            // Insert after inventory section or at the end of result box
            if (inventorySection && inventorySection.parentNode) {
                inventorySection.parentNode.insertBefore(warningSection, inventorySection.nextSibling);
            } else {
                const resultBox = document.getElementById('resultBox');
                if (resultBox) {
                    resultBox.appendChild(warningSection);
                }
            }
        }
        
        warningSection.innerHTML = `
            <div style="margin: 20px 0; padding: 15px; background: rgba(255, 152, 0, 0.2); border-left: 4px solid #FF9800; border-radius: 8px;">
                <h4 style="margin: 0 0 10px 0; color: #e65100;">⚠️ Warnings</h4>
                <ul style="margin: 0; padding-left: 20px;">
                    ${warnings.map(w => `<li style="color: #e65100;">${w}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    // Reset customer form
    document.getElementById('customerForm').style.display = 'none';
    document.getElementById('saveQuoteBtn').style.display = 'block';
    
    const resultBox = document.getElementById('resultBox');
    resultBox.style.display = 'block'; // Explicitly make the box visible
    resultBox.classList.add('show');
    resultBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Save Quote Functions
function toggleCustomerForm() {
    const form = document.getElementById('customerForm');
    const btn = document.getElementById('saveQuoteBtn');
    
    if (form.style.display === 'none') {
        form.style.display = 'block';
        btn.style.display = 'none';
    } else {
        form.style.display = 'none';
        btn.style.display = 'block';
    }
}

async function saveCurrentQuote() {
    if (!currentJobData || !currentPrice) {
        showNotification('No quote to save!', 'warning');
        return;
    }
    
    const quoteData = {
        ...currentJobData,
        price: currentPrice,
        customer_name: document.getElementById('customerName').value,
        customer_email: document.getElementById('customerEmail').value,
        customer_phone: document.getElementById('customerPhone').value,
        customer_whatsapp: document.getElementById('customerWhatsApp').value,
        notes: document.getElementById('quoteNotes').value,
        discount_applied: discountAppliedToCurrentQuote,
        discount_percentage: currentJobData.discount_percentage || 0,
        discount_amount: currentJobData.discount_amount || 0,
        original_price: currentJobData.original_price || null
    };
    
    try {
        const response = await fetch('/save_quote', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(quoteData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Quote saved successfully!', 'success');
            
            // Clear form
            document.getElementById('customerName').value = '';
            document.getElementById('customerEmail').value = '';
            document.getElementById('customerPhone').value = '';
            document.getElementById('quoteNotes').value = '';
            document.getElementById('customerForm').style.display = 'none';
            document.getElementById('saveQuoteBtn').style.display = 'block';
            
            // Reset discount state
            discountAppliedToCurrentQuote = false;
            
            // Clear job data to reset everything
            currentJobData = null;
            currentPrice = null;
            document.getElementById('resultBox').style.display = 'none';
            
            // Clear upload tab form if it was used
            document.getElementById('uploadMaterial').value = '';
            document.getElementById('uploadThickness').value = '';
            document.getElementById('uploadColor').value = '';
            document.getElementById('uploadCuttingType').value = 'Laser Cutting';
            document.getElementById('uploadQuantity').value = '1';
            document.getElementById('uploadRush').checked = false;
            document.getElementById('fileInfo').style.display = 'none';
            document.getElementById('uploadArea').style.display = 'block';
            
            // Clear extracted data
            extractedData = null;

            // Refresh quotes list if on quotes tab (only if element exists)
            const quotesTab = document.getElementById('quotes');
            if (quotesTab && quotesTab.classList.contains('active')) {
                loadQuotes();
            }
        } else {
            showNotification('Error saving quote: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

// Load and display quotes
async function loadQuotes() {
    const container = document.getElementById('quotesContainer');
    const loading = document.getElementById('quotesLoading');
    
    loading.style.display = 'block';
    container.innerHTML = '';
    
    try {
        const response = await fetch('/get_quotes');
        const result = await response.json();
        
        loading.style.display = 'none';
        
        if (result.success && result.quotes.length > 0) {
            container.innerHTML = result.quotes.map(quote => createQuoteCard(quote)).join('');
        } else {
            container.innerHTML = '<p style="text-align: center; color: #999;">No quotes saved yet.</p>';
        }
    } catch (error) {
        loading.style.display = 'none';
        container.innerHTML = '<p style="text-align: center; color: #d9534f;">Error loading quotes: ' + error.message + '</p>';
    }
}


function createQuoteCard(quote) {
    const rushBadge = quote.rush_job ? '<span style="background: #ff6b6b; color: white; padding: 3px 8px; border-radius: 5px; font-size: 0.8em; margin-left: 10px;">⚡ RUSH</span>' : '';
    const discountBadge = quote.discount_applied ? `<span style="background: #28a745; color: white; padding: 3px 8px; border-radius: 5px; font-size: 0.8em; margin-left: 10px;">${quote.discount_percentage}% OFF</span>` : '';
    
    // Status badge
    const statusMap = { 'draft': 'Draft', 'confirmed': 'Confirmed', 'completed': 'Completed', 'cancelled': 'Cancelled' };
    const statusClass = `status-${quote.status || 'draft'}`;
    const statusBadge = `<span class="status-badge ${statusClass}">${statusMap[quote.status || 'draft']}</span>`;

    // Price display (shown for both single and bulk quotes)
    let priceHTML = '';
    if (quote.discount_applied && quote.original_price) {
        priceHTML = `
            <div style="text-align: right;">
                <div style="font-size: 0.9em; color: #999; text-decoration: line-through; margin-bottom:6px;">₦${Number(quote.original_price).toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
                <div style="font-size: 1.3em; font-weight: bold; color: #28a745; margin-bottom:6px;">₦${Number(quote.quoted_price).toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
                <div style="font-size: 0.9em; color: #28a745;">Removed ₦${Number(quote.discount_amount || 0).toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
            </div>
        `;
    } else {
        priceHTML = `
            <div style="text-align: right;">
                <div style="font-size: 1.3em; font-weight: bold; color: #E89D3C;">₦${Number(quote.quoted_price).toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
            </div>
        `;
    }

    // Items list for bulk orders (if present)
    let itemsHTML = '';
    if (Array.isArray(quote.items) && quote.items.length > 0) {
        const listItems = quote.items.map((it, i) => {
            const name = it.item_name || it.name || `Job ${i + 1}`;
            const material = it.material || 'Unknown';
            const color = it.material_color ? ` (${it.material_color})` : '';
            const thickness = it.thickness_mm || it.thickness || '';
            const w = it.width_mm || it.width || it.w || '';
            const h = it.height_mm || it.height || it.h || '';
            const price = Number(it.item_price || it.price || 0).toLocaleString('en-NG', {minimumFractionDigits: 2});
            return `<li style="margin-bottom:6px;">• ${name} - ${material}${color} (${thickness}mm) - ${w}×${h}mm - Price: ₦${price}</li>`;
        }).join('');

        itemsHTML = `
            <div style="margin-top: 15px;">
                <strong>Items (${quote.items.length}):</strong>
                <ul style="margin: 8px 0 0 18px; padding: 0; list-style: none;">
                    ${listItems}
                </ul>
            </div>
        `;
    }

    // For single-item quotes without items array, show details grid
    const singleDetailsHTML = (!Array.isArray(quote.items) || quote.items.length === 0) ? `
        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9em;">
                <div><strong>Material:</strong> ${quote.material} ${quote.material_color ? `(${quote.material_color})` : ''} (${quote.thickness_mm || ''}mm)</div>
                <div><strong>Size:</strong> ${quote.width_mm || ''}×${quote.height_mm || ''}mm</div>
                <div><strong>Cutting:</strong> ${quote.cutting_type || ''}</div>
                <div><strong>Quantity:</strong> ${quote.quantity || ''}</div>
                <div><strong>Time:</strong> ${quote.cutting_time_minutes || ''} min</div>
                <div><strong>Complexity:</strong> ${quote.complexity_score || ''}/5</div>
            </div>
        </div>
    ` : '';
    
    // Action buttons based on status
    let actionButtonsHTML = `
        <button onclick="downloadQuotePDF(${quote.id})" style="background: #E89D3C; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; flex: 1; min-width: 120px;">Download PDF</button>
        <button onclick="shareQuoteOnWhatsApp(${quote.id}, {whatsapp_number: '${quote.customer_whatsapp || ''}'})" style="background: #28a745; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; flex: 1; min-width: 120px;">Share</button>
        <button onclick="deleteQuote(${quote.id})" style="background: #dc3545; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer;">Delete</button>
    `;
    
    // Add confirm/cancel buttons based on status
    if (quote.status === 'draft' || !quote.status) {
        actionButtonsHTML = `
            <button onclick="showMaterialBreakdown(${quote.id})" style="background: #28a745; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; flex: 1; min-width: 120px;">Confirm Order</button>
            <button onclick="downloadQuotePDF(${quote.id})" style="background: #E89D3C; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; flex: 1; min-width: 120px;">Download PDF</button>
            <button onclick="shareQuoteOnWhatsApp(${quote.id}, {whatsapp_number: '${quote.customer_whatsapp || ''}'})" style="background: #28a745; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; flex: 1; min-width: 120px;">Share</button>
            <button onclick="deleteQuote(${quote.id})" style="background: #dc3545; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer;">Delete</button>
        `;
    } else if (quote.status === 'confirmed') {
        actionButtonsHTML = `
            <button onclick="markQuoteCompleted(${quote.id})" style="background: #ffc107; color: #333; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; flex: 1; min-width: 120px;">Mark Completed</button>
            <button onclick="cancelQuoteOrder(${quote.id})" style="background: #dc3545; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; flex: 1; min-width: 120px;">Cancel Order</button>
            <button onclick="downloadQuotePDF(${quote.id})" style="background: #E89D3C; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer;">Download</button>
        `;
    } else if (quote.status === 'completed') {
        actionButtonsHTML = `
            <button onclick="downloadQuotePDF(${quote.id})" style="background: #E89D3C; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer;">Download PDF</button>
            <button onclick="deleteQuote(${quote.id})" style="background: #dc3545; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer;">Archive</button>
        `;
    } else if (quote.status === 'cancelled') {
        actionButtonsHTML = `
            <button onclick="downloadQuotePDF(${quote.id})" style="background: #E89D3C; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer;">Download PDF</button>
        `;
    }

    return `
        <div style="background: #f9f9f9; border-left: 4px solid #E89D3C; padding: 20px; margin-bottom: 15px; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px;">
                <div style="flex:1;">
                    <h3 style="margin: 0; color: #E89D3C;">${quote.quote_number}${statusBadge}${rushBadge}${discountBadge}</h3>
                    <div style="font-size: 0.9em; color: #999; margin-bottom:6px;">${quote.created_at}</div>
                </div>
                ${priceHTML}
            </div>

            ${quote.customer_name ? `<p style="margin: 5px 0;"><strong>Customer:</strong> ${quote.customer_name}</p>` : ''}
            ${quote.customer_email ? `<p style="margin: 5px 0;"><strong>Email:</strong> ${quote.customer_email}</p>` : ''}
            ${quote.customer_phone ? `<p style="margin: 5px 0;"><strong>Phone:</strong> ${quote.customer_phone}</p>` : ''}

            ${itemsHTML}

            ${singleDetailsHTML}

            ${quote.notes ? `<div style="margin-top: 15px; padding: 10px; background: #fff; border-radius: 5px;"><strong>Notes:</strong> ${quote.notes}</div>` : ''}

            <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                ${actionButtonsHTML}
            </div>
        </div>
    `;
}

function downloadQuotePDF(quoteId) {
    /**
     * Download quote as PDF
     */
    window.location.href = `/download_quote_pdf/${quoteId}`;
}

async function searchQuotes() {
    const query = document.getElementById('searchQuotes').value;
    const container = document.getElementById('quotesContainer');
    
    if (query.length < 2) {
        loadQuotes();
        return;
    }
    
    try {
        const response = await fetch(`/search_quotes?q=${encodeURIComponent(query)}`);
        const result = await response.json();
        
        if (result.success && result.quotes.length > 0) {
            container.innerHTML = result.quotes.map(quote => createQuoteCard(quote)).join('');
        } else {
            container.innerHTML = '<p style="text-align: center; color: #999;">No quotes found.</p>';
        }
    } catch (error) {
        container.innerHTML = '<p style="text-align: center; color: #d9534f;">Error searching: ' + error.message + '</p>';
    }
}

async function deleteQuote(quoteId) {
    // Show confirmation modal instead of plain confirm()
    const confirmed = await showModalChoice(
        'Delete Quote',
        'Are you sure you want to delete this quote? This action cannot be undone.',
        [
            { label: 'Cancel', value: 'no' },
            { label: 'Delete', value: 'yes' }
        ]
    );
    
    if (confirmed !== 'yes') {
        return;
    }
    
    try {
        const response = await fetch(`/delete_quote/${quoteId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('✅ Quote deleted successfully', 'success');
            loadQuotes();
        } else {
            showNotification('Error: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

// Load quotes when quotes tab is clicked
document.addEventListener('DOMContentLoaded', function() {
    // Override showTab to load quotes when switching to quotes tab
    const originalShowTab = window.showTab;
    window.showTab = function(tabName) {
        originalShowTab.call(this, tabName);
        if (tabName === 'quotes') {
            loadQuotes();
        } else if (tabName === 'inventory') {
            loadInventory();
        }
    };
});

// Add Training Job Functions
async function addTrainingJob() {
    const material = document.getElementById('jobMaterial').value;
    const thickness = document.getElementById('jobThickness').value;
    const width = document.getElementById('jobWidth').value;
    const height = document.getElementById('jobHeight').value;
    const time = document.getElementById('jobTime').value;
    const price = document.getElementById('jobPrice').value;
    
    if (!material || !thickness || !width || !height || !time || !price) {
        showNotification('Please fill in all required fields (marked with *)!', 'warning');
        return;
    }
    
    // Helper function to clean numbers (remove commas)
    const cleanNum = (val) => {
        if (typeof val === 'string') {
            return val.replace(/,/g, '');
        }
        return val;
    };
    
    const jobData = {
        material: material,
        thickness: cleanNum(thickness),
        letters: cleanNum(document.getElementById('jobLetters').value),
        shapes: cleanNum(document.getElementById('jobShapes').value),
        complexity: document.getElementById('jobComplexity').value,
        details: document.getElementById('jobDetails').checked ? 1 : 0,
        width: cleanNum(width),
        height: cleanNum(height),
        cuttingType: document.getElementById('jobCuttingType').value,
        time: cleanNum(time),
        quantity: cleanNum(document.getElementById('jobQuantity').value),
        rush: document.getElementById('jobRush').checked ? 1 : 0,
        price: cleanNum(price)
    };
    
    // Rest of the function stays the same...
    try {
        const response = await fetch('/add_training_job', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(jobData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('✅ ' + result.message, 'success');
            
            // Clear form
            document.getElementById('jobMaterial').value = '';
            document.getElementById('jobThickness').value = '';
            document.getElementById('jobWidth').value = '';
            document.getElementById('jobHeight').value = '';
            document.getElementById('jobLetters').value = '0';
            document.getElementById('jobShapes').value = '1';
            document.getElementById('jobComplexity').value = '3';
            document.getElementById('jobTime').value = '';
            document.getElementById('jobQuantity').value = '1';
            document.getElementById('jobPrice').value = '';
            document.getElementById('jobDetails').checked = false;
            document.getElementById('jobRush').checked = false;
            
            // Update job count
            updateTrainingStats();
        } else {
            showNotification('Error: ' + result.error, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

async function updateTrainingStats() {
    try {
        const response = await fetch('/get_training_stats');
        const result = await response.json();
        
        if (result.success) {
            document.getElementById('jobCount').textContent = result.total_jobs;
            document.getElementById('modelAccuracy').textContent = result.r2_score;
        }
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}

async function retrainModel() {
    if (!confirm('Retrain the pricing model with current data? This may take 10-30 seconds.')) {
        return;
    }
    
    const statusDiv = document.getElementById('retrainStatus');
    statusDiv.innerHTML = '<div class="spinner"></div><p>Retraining model... Please wait.</p>';
    
    try {
        const response = await fetch('/retrain_model', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            statusDiv.innerHTML = `
                <div class="success-box">
                    <strong>${result.message}</strong>
                    <p style="margin-top: 10px;">
                        Total Jobs: ${result.total_jobs}<br>
                        New R² Score: ${result.r2_score}<br>
                        Average Error: ₦${result.mae.toLocaleString('en-NG', {minimumFractionDigits: 2})}
                    </p>
                </div>
            `;
            
            // Update stats display
            updateTrainingStats();
        } else {
            statusDiv.innerHTML = `
                <div class="error-box">
                    <strong>Error:</strong> ${result.error}
                </div>
            `;
        }
    } catch (error) {
        statusDiv.innerHTML = `
            <div class="error-box">
                <strong>Error:</strong> ${error.message}
            </div>
        `;
    }
}

// Load training stats when Add Job tab is opened
document.addEventListener('DOMContentLoaded', function() {
    const originalShowTab = window.showTab;
    window.showTab = function(tabName) {
        originalShowTab.call(this, tabName);
        
        if (tabName === 'quotes') {
            loadQuotes();
        } else if (tabName === 'inventory') {
            loadInventory();
        } else if (tabName === 'addjob') {
            updateTrainingStats();
        }
    };
});

// ========================================
// BULK ORDER FUNCTIONS
// ========================================

async function addItemToBulk() {
    const material = document.getElementById('bulkMaterial').value;
    const thickness = document.getElementById('bulkThickness').value;
    const color = document.getElementById('bulkColor').value;
    const width = document.getElementById('bulkWidth').value;
    const height = document.getElementById('bulkHeight').value;
    const time = document.getElementById('bulkTime').value;
    
    if (!material || !thickness || !width || !height || !time) {
        showNotification('Please fill in all required fields (Material, Thickness, Dimensions, and Time)!', 'warning');
        return;
    }
    
    const itemName = document.getElementById('bulkItemName').value || `Item ${bulkItemCounter + 1}`;
    
    const itemData = {
        id: bulkItemCounter++,
        name: itemName,
        material: material,
        thickness: parseFloat(thickness),
        color: color || '',
        letters: parseInt(document.getElementById('bulkLetters').value),
        shapes: parseInt(document.getElementById('bulkShapes').value),
        complexity: parseInt(document.getElementById('bulkComplexity').value),
        details: document.getElementById('bulkDetails').checked ? 1 : 0,
        width: parseFloat(width),
        height: parseFloat(height),
        cuttingType: document.getElementById('bulkCuttingType').value,
        time: parseFloat(time),
        quantity: parseInt(document.getElementById('bulkQuantity').value),
        rush: document.getElementById('bulkRush').checked ? 1 : 0,
        price: 0,
        inventory: null
    };
    
    try {
        const response = await fetch('/calculate_price', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(itemData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            itemData.price = result.price;
            itemData.inventory = result.inventory;
            bulkItems.push(itemData);
            updateBulkItemsDisplay();
            clearBulkForm();
            showNotification(`✅ "${itemName}" added! Price: ₦${result.price.toLocaleString()}`, 'success');
        } else {
            showNotification(`❌ Error: ${result.error}`, 'error');
        }
    } catch (error) {
        showNotification(`❌ Error: ${error.message}`, 'error');
    }
}

// ========================================
// UPDATED BULK ITEMS DISPLAY FUNCTION
// ========================================

// NOTE: Bulk item UI relies on these functions being async (so we can await pricing)
// and NOT being redefined later in the file.

// Update material for a bulk item (async + re-render)
async function updateBulkItemMaterial(itemId, material) {
    const item = bulkItems.find(i => i.id === itemId);
    if (!item) return;

    item.material = material || '';
    // Re-render immediately so the selected values show right away
    updateBulkItemsDisplay();

    // If thickness is already selected, load colors
    if (item.material && item.thickness) {
        await loadBulkItemColors(itemId);
    }
}

// Update thickness for a bulk item (async + re-render)
async function updateBulkItemThickness(itemId, thickness) {
    const item = bulkItems.find(i => i.id === itemId);
    if (!item) return;

    item.thickness = thickness ? parseFloat(thickness) : 0;
    // Re-render immediately so the selected values show right away
    updateBulkItemsDisplay();

    // If material is already selected, load colors
    if (item.material && item.thickness) {
        await loadBulkItemColors(itemId);
    }
}

// Update color for a bulk item (async + re-render)
async function updateBulkItemColor(itemId, color) {
    const item = bulkItems.find(i => i.id === itemId);
    if (!item) return;

    item.color = color || '';
    // Re-render immediately so the selected values show right away
    updateBulkItemsDisplay();

    // Trigger price recalculation if we have material and thickness
    if (item.material && item.thickness) {
        await calculateBulkItemPrice(itemId);
    }
}

// Load available colors for a bulk item
async function loadBulkItemColors(itemId) {
    const item = bulkItems.find(i => i.id === itemId);
    if (!item || !item.material || !item.thickness) return;

    try {
        const response = await fetch(`/api/inventory/colors?material=${encodeURIComponent(item.material)}&thickness=${item.thickness}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const result = await response.json();
        const colorSelect = document.getElementById(`colorSelect_${item.id}`);
        
        if (!colorSelect) return;  // Element not in DOM yet
        
        if (result.success && result.colors.length > 0) {
            // Clear loading message
            colorSelect.innerHTML = '<option value="">Select color...</option>';
            
            // Add color options
            result.colors.forEach(color => {
                const option = document.createElement('option');
                option.value = color.color;
                
                // Show stock status in option text
                if (color.in_stock) {
                    option.textContent = `${color.color} (${color.stock} sheets)`;
                } else {
                    option.textContent = `${color.color} (Out of stock)`;
                    option.disabled = true;
                    option.style.color = '#999';
                }
                
                colorSelect.appendChild(option);
            });
        } else {
            colorSelect.innerHTML = '<option value="">No colors available</option>';
        }
    } catch (error) {
        console.error('Error loading colors for bulk item:', error);
        const colorSelect = document.getElementById(`colorSelect_${item.id}`);
        if (colorSelect) {
            colorSelect.innerHTML = '<option value="">Error loading colors</option>';
        }
    }
}

// Calculate / refresh price for a single bulk item
async function calculateBulkItemPrice(itemId) {
    const item = bulkItems.find(i => i.id === itemId);
    if (!item) return;

    // Require both

    if (!item.material || !item.thickness) return;

    const jobData = {
        material: item.material,
        thickness: item.thickness,
        color: item.color || '',
        letters: item.letters,
        shapes: item.shapes,
        complexity: item.complexity,
        details: item.details,
        width: item.width,
        height: item.height,
        cuttingType: item.cuttingType,
        time: item.time,
        quantity: item.quantity,
        rush: item.rush
    };

    try {
        const response = await fetch('/calculate_price', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(jobData)
        });

        const result = await response.json();

        if (!result.success) {
            showNotification(`Error calculating price for ${item.name}: ${result.error}`, 'error');
            return;
        }

        item.price = result.price;
        item.inventory = result.inventory;

        updateBulkItemsDisplay();

        if (result.inventory && result.inventory.in_stock === false) {
            showNotification(`${item.name}: ${result.inventory.message}`, 'warning');
        } else {
            showNotification(`${item.name}: Price calculated - ₦${result.price.toLocaleString()}`, 'success');
        }
    } catch (error) {
        showNotification(`Error calculating price for ${item.name}: ${error.message}`, 'error');
    }
}

// Update your display function to pre-select material and thickness if they exist
function updateBulkItemsDisplay() {
    const container = document.getElementById('itemsContainer');
    const countSpan = document.getElementById('itemCount');
    const totalDiv = document.getElementById('bulkTotal');
    const grandTotalSpan = document.getElementById('grandTotal');
    
    // If bulk tab DOM isn't present (or was replaced), fail safely
    if (!container || !countSpan || !totalDiv) {
        console.warn('Bulk UI elements missing. Skipping updateBulkItemsDisplay().');
        return;
    }
    
    countSpan.textContent = bulkItems.length;
    
    if (bulkItems.length === 0) {
        container.innerHTML = '<div class="empty-state">No items added yet. Add your first item below!</div>';
        hideElement('bulkTotal');
        return;
    }
    
    const grandTotal = bulkItems.reduce((sum, item) => sum + (item.price || 0), 0);
    const totalMaterialCost = bulkItems.reduce((sum, item) => {
        return sum + (item.inventory?.material_cost * item.quantity || 0);
    }, 0);
    
    showElement('bulkTotal');
    // grandTotalSpan can be null if #bulkTotal content got replaced; we render totals below anyway
    if (grandTotalSpan) {
        grandTotalSpan.textContent = '₦' + grandTotal.toLocaleString('en-NG', {minimumFractionDigits: 2});
    }
    
    container.innerHTML = bulkItems.map((item, index) => {
        const hasMaterialSet = item.material && item.thickness && item.color;
        
        let stockBadge = '';
        if (hasMaterialSet && item.price) {
            stockBadge = item.inventory?.in_stock 
                ? `<span style="background: #4CAF50; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em;">✅ In Stock</span>`
                : `<span style="background: #F44336; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em;">❌ Out of Stock</span>`;
        }
        
        return `
        <div class="bulk-item-card">
            <div class="bulk-item-header">
                <div>
                    <h4>${item.name} ${stockBadge}</h4>
                    <small>Item #${index + 1}</small>
                </div>
                <div class="bulk-item-price">
                    <div class="price">${item.price ? '₦' + item.price.toLocaleString('en-NG', {minimumFractionDigits: 2}) : 'Price pending...'}</div>
                    <button onclick="removeItemFromBulk(${item.id})" class="btn-remove">Remove</button>
                </div>
            </div>
            <div class="bulk-item-details">
                <div><strong>Material:</strong> ${item.material || 'Not selected'} ${ (item.color || item.material_color) ? `(${item.color || item.material_color})` : '' } (${item.thickness ? item.thickness : '--'}mm)</div>
                <div><strong>Size:</strong> ${item.width}×${item.height}mm</div>
                <div><strong>Shapes:</strong> ${item.shapes}</div>
                <div><strong>Letters:</strong> ${item.letters}</div>
                <div><strong>Complexity:</strong> ${item.complexity}/5</div>
            </div>

            ${!item.price ? `
            <div class="material-prompt">
                <strong>Set Material & Thickness:</strong>
                <div class="material-selection">
                    <select onchange="updateBulkItemMaterial(${item.id}, this.value)" class="form-control-sm">
                        <option value="">Select Material</option>
                        <option value="Acrylic" ${item.material === 'Acrylic' ? 'selected' : ''}>Acrylic</option>
                        <option value="Wood" ${item.material === 'Wood' ? 'selected' : ''}>Wood</option>
                        <option value="Metal" ${item.material === 'Metal' ? 'selected' : ''}>Metal</option>
                        <option value="MDF" ${item.material === 'MDF' ? 'selected' : ''}>MDF</option>
                        <option value="ACP" ${item.material === 'ACP' ? 'selected' : ''}>ACP</option>
                    </select>
                    <select onchange="updateBulkItemThickness(${item.id}, this.value)" class="form-control-sm">
                        <option value="">Thickness</option>
                        <option value="3" ${item.thickness === 3 ? 'selected' : ''}>3mm</option>
                        <option value="4" ${item.thickness === 4 ? 'selected' : ''}>4mm</option>
                        <option value="6" ${item.thickness === 6 ? 'selected' : ''}>6mm</option>
                        <option value="8" ${item.thickness === 8 ? 'selected' : ''}>8mm</option>
                        <option value="9" ${item.thickness === 9 ? 'selected' : ''}>9mm</option>
                        <option value="10" ${item.thickness === 10 ? 'selected' : ''}>10mm</option>
                        <option value="12" ${item.thickness === 12 ? 'selected' : ''}>12mm</option>
                    </select>
                </div>
                ${item.material && item.thickness ? `
                <div style="margin-top: 10px;">
                    <strong>Select Color:</strong>
                    <select onchange="updateBulkItemColor(${item.id}, this.value)" class="form-control-sm" id="colorSelect_${item.id}">
                        <option value="">Loading colors...</option>
                    </select>
                </div>
                ` : ''}
            </div>
            ` : ''}

            ${item.inventory && item.inventory.material_cost ? `
                <div style="margin-top: 10px; padding: 10px; background: #f5f5f5; border-radius: 5px; font-size: 0.9em;">
                    <strong>Material Cost:</strong> ₦${(item.inventory.material_cost * item.quantity).toLocaleString()} 
                    <span style="color: #666;">(${item.inventory.area_sq_ft.toFixed(2)} sq ft @ ₦${item.inventory.price_per_sq_ft}/sq ft) ${item.color || ''} ${item.material || ''}</span>
                </div>
            ` : ''}
        </div>
        `;
    }).join('');
    
    // Update total section with cost breakdown
    let bulkTotalHTML = `
        <div style="background: #FFF8F0; padding: 25px; border-radius: 12px; margin-top: 20px; border: 2px solid #E89D3C;">
    `;
    
    if (window.bulkOrderDiscount && window.bulkOrderDiscount.applied) {
        // Show discount breakdown
        const discountInfo = window.bulkOrderDiscount;
        const subtotal = discountInfo.original_price || grandTotal;
        const discountPercent = discountInfo.discount_percentage || 0;
        const discountAmount = discountInfo.discount_amount || 0;
        const finalPrice = subtotal - discountAmount;  // Calculate final discounted price
        
        bulkTotalHTML += `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                <div>
                    <div style="font-size: 0.9em; color: #666;">Original Price</div>
                    <div style="font-size: 1.1em; font-weight: bold; text-decoration: line-through; color: #999;">₦${subtotal.toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
                </div>
                <div>
                    <div style="font-size: 0.9em; color: #666;">Discount (${discountPercent}%)</div>
                    <div style="font-size: 1.1em; font-weight: bold; color: #28a745;">-₦${discountAmount.toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
                </div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: rgba(40, 167, 69, 0.1); border-radius: 8px; border-left: 4px solid #28a745; margin-top: 15px;">
                <div style="font-size: 1.3em; font-weight: bold;">Grand Total</div>
                <div style="font-size: 2em; font-weight: bold; color: #28a745;">₦${finalPrice.toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
            </div>
        `;
    } else {
        // No discount - show normal total
        bulkTotalHTML += `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                <div>
                    <div style="font-size: 0.9em; color: #666;">Total Material Cost</div>
                    <div style="font-size: 1.3em; font-weight: bold; color: #333;">₦${totalMaterialCost.toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
                </div>
                <div>
                    <div style="font-size: 0.9em; color: #666;">Grand Total</div>
                    <div style="font-size: 2em; font-weight: bold; color: #E89D3C;">₦${grandTotal.toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
                </div>
            </div>
            <button class="btn" onclick="showBulkDiscountModal()" style="margin-top: 10px; background: linear-gradient(135deg, #28a745 0%, #20963b 100%);">
               Apply Discount
            </button>
        `;
    }
    
    bulkTotalHTML += `
            <button class="btn" onclick="saveBulkQuote()" style="margin-top: 10px;">
                💾 Save Complete Order
            </button>
        </div>
    `;
    
    totalDiv.innerHTML = bulkTotalHTML;
    showElement('bulkTotal');
}

// ========================================
// UTILITY FUNCTIONS
// ========================================

function showNotification(message, type = 'info') {
    // Remove existing notifications
    document.querySelectorAll('.notification').forEach(notif => notif.remove());
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-message">${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) element.classList.add('show');
}

function hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) element.classList.remove('show');
}

function showElement(elementId) {
    const element = typeof elementId === 'string' ? document.getElementById(elementId) : elementId;
    if (element) element.style.display = 'block';
}

function hideElement(elementId) {
    const element = typeof elementId === 'string' ? document.getElementById(elementId) : elementId;
    if (element) element.style.display = 'none';
}

function removeItemFromBulk(itemId) {
    if (!confirm('Remove this item from the order?')) {
        return;
    }
    
    bulkItems = bulkItems.filter(item => item.id !== itemId);
    updateBulkItemsDisplay();
}

function clearBulkForm() {
    document.getElementById('bulkItemName').value = '';
    document.getElementById('bulkMaterial').value = '';
    document.getElementById('bulkThickness').value = '';
    document.getElementById('bulkWidth').value = '';
    document.getElementById('bulkHeight').value = '';
    document.getElementById('bulkLetters').value = '0';
    document.getElementById('bulkShapes').value = '1';
    document.getElementById('bulkComplexity').value = '3';
    document.getElementById('bulkTime').value = '';
    document.getElementById('bulkQuantity').value = '1';
    document.getElementById('bulkDetails').checked = false;
    document.getElementById('bulkRush').checked = false;
}

async function saveBulkQuote() {
    if (bulkItems.length === 0) {
        showNotification('Please add at least one item to the order!', 'warning');
        return;
    }
    
    // Calculate prices for any items missing them
    const itemsWithPrices = await Promise.all(
        bulkItems.map(async (item) => {
            if (item.price && item.price > 0) {
                return item;
            }
            
            try {
                const priceResponse = await fetch('/calculate_price', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        material: item.material,
                        thickness: item.thickness,
                        color: item.color,
                        width: item.width,
                        height: item.height,
                        letters: item.letters || 0,
                        shapes: item.shapes || 1,
                        complexity: item.complexity || 3,
                        details: item.details || 0,
                        cuttingType: item.cuttingType,
                        time: item.time || 10,
                        quantity: item.quantity || 1,
                        rush: item.rush || 0
                    })
                });
                
                const priceData = await priceResponse.json();
                if (priceData.success) {
                    return { ...item, price: priceData.price };
                }
            } catch (error) {
                console.error('Error calculating price for item:', error);
            }
            
            return item;
        })
    );
    
    // Calculate total
    const subtotal = itemsWithPrices.reduce((sum, item) => sum + (item.price || 0), 0);
    let finalTotal = subtotal;
    
    // Include discount if applied
    let discountData = {
        discount_applied: false,
        discount_percentage: 0,
        discount_amount: 0,
        original_price: null
    };
    
    if (window.bulkOrderDiscount && window.bulkOrderDiscount.applied) {
        discountData = {
            discount_applied: true,
            discount_percentage: window.bulkOrderDiscount.discount_percentage || 0,
            discount_amount: window.bulkOrderDiscount.discount_amount || 0,
            original_price: window.bulkOrderDiscount.original_price || subtotal
        };
        finalTotal = window.bulkOrderDiscount.new_price || (subtotal - (window.bulkOrderDiscount.discount_amount || 0));
    }
    
    // Ask for customer info
    const customerName = await showModalInput('👤 Customer Name', 'Enter customer name (optional):', 'e.g., John Doe', '') || '';
    const customerEmail = await showModalInput('📧 Customer Email', 'Enter customer email (optional):', 'e.g., john@example.com', '') || '';
    const customerPhone = await showModalInput('☎️ Customer Phone', 'Enter customer phone (optional):', 'e.g., +234 803 123 4567', '') || '';
    const customerWhatsApp = await showModalInput('📱 Customer WhatsApp', 'Enter customer WhatsApp number (optional):', 'e.g., +234XXXXXXXXXX', '') || '';
    const notes = await showModalInput('📝 Order Notes', 'Add any special notes or instructions (optional):', 'e.g., Rush order, special requirements', '') || '';
    
    const quoteData = {
        items: itemsWithPrices,
        customer_name: customerName,
        customer_email: customerEmail,
        customer_phone: customerPhone,
        customer_whatsapp: customerWhatsApp,
        notes: notes,
        price: finalTotal,  // Add final price
        ...discountData  // Include discount data
    };
    
    try {
        const response = await fetch('/save_bulk_quote', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(quoteData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            let message = `Quote Number: ${result.quote_number}\nTotal Items: ${result.items_count}\n`;
            
            if (discountData.discount_applied && discountData.original_price) {
                message += `Subtotal: ₦${Number(discountData.original_price).toLocaleString('en-NG', {minimumFractionDigits: 2})}\n`;
                message += `Discount (${discountData.discount_percentage}%): -₦${Number(discountData.discount_amount || 0).toLocaleString('en-NG', {minimumFractionDigits: 2})}\n`;
                message += `Final Price: ₦${Number(finalTotal).toLocaleString('en-NG', {minimumFractionDigits: 2})}`;
            } else {
                message += `Final Price: ₦${Number(result.total_price || finalTotal).toLocaleString('en-NG', {minimumFractionDigits: 2})}`;
            }
            
            showModalAlert('Quote Saved Successfully!', message, 'success');
            
            // Clear bulk order
            bulkItems = [];
            bulkItemCounter = 0;
            window.bulkOrderDiscount = null;
            updateBulkItemsDisplay();
        } else {
            showModalAlert('❌ Error Saving Quote', result.error, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

async function shareQuoteOnWhatsApp(quoteId, customerData) {
    /**
     * Share quote PDF on WhatsApp from Saved Quotes tab
     * If customer WhatsApp number exists, uses it; otherwise prompts for input
     * Fallback to generic WhatsApp share if number not provided
     */
    
    let whatsappNumber = customerData?.whatsapp_number || '';
    
    // If no WhatsApp number, prompt user with modal
    if (!whatsappNumber) {
        whatsappNumber = await showModalInput(
            '📱 Enter WhatsApp Number',
            'Enter the customer\'s WhatsApp number or leave blank for standard share:',
            'e.g., +234XXXXXXXXXX',
            ''
        ) || '';
    }
    
    const sharePayload = whatsappNumber ? 
        { whatsapp_number: whatsappNumber } : 
        {};
    
    fetch(`/share_quote_whatsapp/${quoteId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(sharePayload)
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                let whatsappUrl;
                
                if (data.has_customer_number && data.whatsapp_link) {
                    // Direct message to customer
                    whatsappUrl = data.whatsapp_link;
                    showNotification('Opening WhatsApp to message customer directly...', 'success');
                } else {
                    // Fallback: general WhatsApp share
                    const message = data.message;
                    const encodedMessage = encodeURIComponent(message);
                    
                    // Use WhatsApp Web on desktop, WhatsApp app on mobile
                    const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                    whatsappUrl = isMobile 
                        ? `whatsapp://send?text=${encodedMessage}`
                        : `https://web.whatsapp.com/send?text=${encodedMessage}`;
                }
                
                // Open WhatsApp
                window.open(whatsappUrl, '_blank');
            } else {
                showNotification('Error sharing on WhatsApp: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Failed to share on WhatsApp', 'error');
        });
}

function formatQuoteForWhatsApp(quote) {
    /**
     * Format quote data into WhatsApp message
     */
    
    const rushBadge = quote.rush_job ? '⚡ RUSH JOB' : '';
    
    let message = `🔷 *PRICE QUOTATION* 🔷\n`;
    message += `_BrainGain Tech Innovation Solutions_\n\n`;
    
    message += `📋 *Quote:* ${quote.quote_number} ${rushBadge}\n`;
    message += `📅 *Date:* ${quote.created_at}\n\n`;
    
    // Customer info
    if (quote.customer_name) {
        message += `👤 *Customer:* ${quote.customer_name}\n`;
    }
    if (quote.customer_email) {
        message += `📧 *Email:* ${quote.customer_email}\n`;
    }
    if (quote.customer_phone) {
        message += `📱 *Phone:* ${quote.customer_phone}\n`;
    }
    if (quote.customer_name || quote.customer_email || quote.customer_phone) {
        message += `\n`;
    }
    
    // Job specifications
    message += `🔧 *JOB SPECIFICATIONS*\n`;
    message += `━━━━━━━━━━━━━━━━━\n`;
    message += `• *Material:* ${quote.material} (${quote.thickness_mm}mm)\n`;
    message += `• *Dimensions:* ${quote.width_mm} × ${quote.height_mm} mm\n`;
    message += `• *Cutting Type:* ${quote.cutting_type}\n`;
    message += `• *Quantity:* ${quote.quantity}\n`;
    message += `• *Complexity:* ${quote.complexity_score}/5\n`;
    message += `• *Shapes:* ${quote.num_shapes}\n`;
    message += `• *Letters:* ${quote.num_letters}\n`;
    message += `• *Est. Time:* ${quote.cutting_time_minutes} minutes\n\n`;
    
    // Price
    message += `💰 *TOTAL AMOUNT*\n`;
    message += `━━━━━━━━━━━━━━━━━\n`;
    message += `*₦${parseFloat(quote.quoted_price).toLocaleString('en-NG', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    })}*\n\n`;
    
    // Notes
    if (quote.notes) {
        message += `📝 *Notes:* ${quote.notes}\n\n`;
    }
    
    message += `_Quote valid for 7 days_\n`;
    message += `_Generated by BrainGain Tech Pricing System_`;
    
    return message;
}

function shareCurrentQuoteOnWhatsApp() {
    /**
     * Share the currently displayed quote as PDF via WhatsApp
     * If customer WhatsApp number provided, sends direct message to customer
     * Otherwise opens general WhatsApp
     */
    
    if (!currentJobData || !currentPrice) {
        showNotification('No quote to share! Please generate a quote first.', 'warning');
        return;
    }
    
    // Get customer WhatsApp number if provided
    const customerWhatsAppNumber = document.getElementById('customerWhatsApp')?.value?.trim() || '';
    
    // Prepare quote data
    const quoteData = {
        ...currentJobData,
        price: currentPrice,
        customer_name: document.getElementById('customerName')?.value || '',
        customer_email: document.getElementById('customerEmail')?.value || '',
        customer_phone: document.getElementById('customerPhone')?.value || '',
        customer_whatsapp: customerWhatsAppNumber,
        notes: document.getElementById('quoteNotes')?.value || ''
    };
    
    // First, save the quote
    fetch('/save_quote', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(quoteData)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            // Quote saved! Now share on WhatsApp with PDF link
            const quoteId = result.quote_id;
            const quoteNumber = result.quote_number;
            
            // Call backend to get WhatsApp share link
            const sharePayload = customerWhatsAppNumber ? 
                { whatsapp_number: customerWhatsAppNumber } : 
                {};
            
            fetch(`/share_quote_whatsapp/${quoteId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(sharePayload)
            })
            .then(response => response.json())
            .then(shareResult => {
                if (shareResult.success) {
                    let whatsappUrl;
                    let alertMsg;
                    
                    if (shareResult.has_customer_number && shareResult.whatsapp_link) {
                        // Direct message to customer
                        whatsappUrl = shareResult.whatsapp_link;
                        alertMsg = `Quote ${quoteNumber} saved!\n\nOpening WhatsApp to message customer directly...`;
                    } else {
                        // Fallback: general WhatsApp share
                        const message = shareResult.message;
                        const encodedMessage = encodeURIComponent(message);
                        const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                        whatsappUrl = isMobile 
                            ? `whatsapp://send?text=${encodedMessage}`
                            : `https://web.whatsapp.com/send?text=${encodedMessage}`;
                        alertMsg = `Quote ${quoteNumber} saved!\n\nOpening WhatsApp to share PDF...`;
                    }
                    
                    // Open WhatsApp
                    window.open(whatsappUrl, '_blank');
                    showNotification(alertMsg, 'success');
                } else {
                    showNotification('Error generating share link: ' + shareResult.error, 'error');
                }
            })
            .catch(error => {
                console.error('Error sharing:', error);
                showNotification('Failed to generate WhatsApp share link', 'error');
            });
        } else {
            showNotification('Error saving quote: ' + result.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Failed to save and share quote', 'error');
    });
}

function shareQuoteToContact(quoteId, phoneNumber) {
    /**
     * Share quote directly to a specific WhatsApp number
     * @param quoteId - The quote ID
     * @param phoneNumber - Customer's phone number (with country code)
     */
    
    fetch(`/get_quote/${quoteId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const quote = data.quote;
                const message = formatQuoteForWhatsApp(quote);
                const encodedMessage = encodeURIComponent(message);
                
                // Clean phone number (remove spaces, dashes, etc.)
                const cleanNumber = phoneNumber.replace(/[^\d+]/g, '');
                
                // Generate WhatsApp URL with specific number
                const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                const whatsappUrl = isMobile 
                    ? `whatsapp://send?phone=${cleanNumber}&text=${encodedMessage}`
                    : `https://web.whatsapp.com/send?phone=${cleanNumber}&text=${encodedMessage}`;
                
                window.open(whatsappUrl, '_blank');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Failed to share on WhatsApp', 'error');
        });
}

// ========================================
// INVENTORY FUNCTIONS
// ========================================

// 1. Toggle the "Add Stock" form visibility
function toggleInventoryForm() {
    const form = document.getElementById('inventoryForm');
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

// 2. Load Inventory from Database
function loadInventory() {
    fetch('/api/inventory')
        .then(res => res.json())
        .then(data => {
            const tbody = document.getElementById('inventoryTableBody');
            tbody.innerHTML = '';
            
            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 20px;">No inventory yet. Add some stock!</td></tr>';
                return;
            }

            data.forEach(item => {
                const tr = document.createElement('tr');
                tr.style.borderBottom = "1px solid #eee";
                
                // Format prices
                const priceSheet = new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(item.price_sheet || 0);
                const priceSqFt = new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(item.price_sq_ft || 0);

                tr.innerHTML = `
                    <td style="padding: 12px;"><strong>${item.material}</strong> (${item.thickness}mm)</td>
                    <td style="padding: 12px;">${item.color}</td>
                    <td style="padding: 12px;">${item.size}</td>
                    <td style="padding: 12px; text-align: center;">
                        <span style="background: ${item.stock < 5 ? '#ffebee' : '#e8f5e9'}; color: ${item.stock < 5 ? '#c62828' : '#2e7d32'}; padding: 4px 8px; border-radius: 12px; font-weight: bold;">
                            ${item.stock}
                        </span>
                    </td>
                    <td style="padding: 12px; text-align: right;">${priceSheet}</td>
                    <td style="padding: 12px; text-align: right;">${priceSqFt}</td>
                    <td style="padding: 12px; text-align: center;">
                        <button onclick="viewHistory(${item.id})" style="cursor: pointer; background: none; border: none;">📜</button>
                    </td>
                    <td style="padding: 12px; text-align: center;">
                        <button onclick="deleteInventory(${item.id})" style="color: red; border: none; background: none; cursor: pointer;">🗑️</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        })
        .catch(err => console.error('Error loading inventory:', err));
}

// View Inventory History
async function viewHistory(id) {
    // No password needed - backend already requires authentication
    fetch(`/api/inventory/history/${id}`)
    .then(res => {
        if (!res.ok) {
            if (res.status === 401) {
                showNotification('Authentication required. Please login again.', 'error');
                window.location.href = '/admin/login';
                return;
            }
            throw new Error('Failed to load history');
        }
        return res.json();
    })
    .then(data => {
        const list = document.getElementById('historyList');
        if (!list) {
            console.error('History list element not found');
            return;
        }
        list.innerHTML = '';
        if(data.length === 0) list.innerHTML = '<li>No history yet.</li>';
        
        data.forEach(t => {
            const color = t.change > 0 ? 'green' : 'red';
            const symbol = t.change > 0 ? '📥' : '📤';
            const item = document.createElement('li');
            item.style.padding = "8px 0";
            item.style.borderBottom = "1px solid #eee";
            item.innerHTML = `
                <span style="color:#888; font-size:0.8em">${t.date}</span><br>
                <strong>${symbol} ${t.type.toUpperCase()}</strong>: 
                <span style="color:${color}; font-weight:bold">${t.change}</span> 
                <br><em>${t.note || ''}</em>
            `;
            list.appendChild(item);
        });
        const historyModal = document.getElementById('historyModal');
        if (historyModal) {
            historyModal.style.display = 'block';
        }
    })
    .catch(error => {
        console.error('Error loading history:', error);
        showNotification('Failed to load inventory history', 'error');
    });
}

async function submitInventory() {
    const data = {
        material: document.getElementById('inv_material').value,
        color: document.getElementById('inv_color').value,
        thickness: document.getElementById('inv_thickness').value,
        width: document.getElementById('inv_width').value,
        height: document.getElementById('inv_height').value,
        quantity: document.getElementById('inv_quantity').value,
        price_sheet: document.getElementById('inv_price_sheet').value,
        price_sq_ft: document.getElementById('inv_price').value,
        note: document.getElementById('inv_note').value
    };

    // Validation
    if (!data.material || !data.color || !data.thickness || !data.width || !data.height || !data.price_sheet) {
        showNotification("Please fill in all required fields (marked with *)", "error");
        return;
    }
    
    // Auto-calculate price_sq_ft if not provided
    if (!data.price_sq_ft || parseFloat(data.price_sq_ft) === 0) {
        const width_mm = parseFloat(data.width);
        const height_mm = parseFloat(data.height);
        const price_sheet = parseFloat(data.price_sheet);
        
        // Calculate sheet area in sq ft
        const area_sq_mm = width_mm * height_mm;
        const area_sq_ft = area_sq_mm / 92903; // Convert mm² to sq ft
        
        // Calculate price per sq ft
        data.price_sq_ft = (price_sheet / area_sq_ft).toFixed(2);
        
        console.log(`Auto-calculated price/sq ft: ₦${data.price_sq_ft}`);
    }

    try {
        const response = await fetch('/api/inventory/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showNotification("✅ Stock Updated Successfully!", "success");
            toggleInventoryForm();
            loadInventory();
            
            // Clear form
            document.getElementById('inv_material').value = '';
            document.getElementById('inv_color').value = '';
            document.getElementById('inv_thickness').value = '';
            document.getElementById('inv_width').value = '';
            document.getElementById('inv_height').value = '';
            document.getElementById('inv_quantity').value = '';
            document.getElementById('inv_price_sheet').value = '';
            document.getElementById('inv_price').value = '';
            document.getElementById('inv_note').value = '';
        } else {
            showNotification(result.message, "error");
        }
    } catch (error) {
        showNotification("Server error: " + error.message, "error");
    }
}

// 4. Delete Item
async function deleteInventory(id) {
    // Use modal confirmation instead of plain confirm
    const confirmed = await showModalChoice(
        '🗑️ Delete Inventory Item',
        'Are you sure you want to delete this inventory item? This action cannot be undone.',
        [
            { label: 'Cancel', value: 'no' },
            { label: 'Delete', value: 'yes' }
        ]
    );
    
    if (confirmed !== 'yes') {
        return;
    }
    
    // No password needed - backend already requires authentication
    fetch(`/api/inventory/delete/${id}`, {
        method: 'DELETE'
    })
    .then(res => {
        if (!res.ok) {
            if (res.status === 401) {
                showNotification('Authentication required. Please login again.', 'error');
                window.location.href = '/admin/login';
                return;
            }
            return res.json().then(err => { throw new Error(err.message || 'Failed to delete inventory item'); });
        }
        return res.json();
    })
    .then(result => {
        if (result.status === 'success') {
            showNotification("Item deleted", "success");
            loadInventory();
        } else {
            showNotification(result.message, "error");
        }
    })
    .catch(error => {
        console.error('Error deleting inventory:', error);
        showNotification(error.message || 'Failed to delete inventory item', 'error');
    });
}

// ========================================
// COLOR SELECTOR FUNCTIONS
// ========================================

/**
 * Load available colors for selected material and thickness
 * @param {string} context - 'upload', 'manual', or 'bulk'
 */
async function loadColorsForMaterial(context) {
    let material, thickness, colorSelect, helpText;
    
    // Get form fields based on context
    if (context === 'upload') {
        material = document.getElementById('uploadMaterial').value;
        thickness = document.getElementById('uploadThickness').value;
        colorSelect = document.getElementById('uploadColor');
        helpText = document.getElementById('uploadColorHelp');
    } else if (context === 'manual') {
        material = document.getElementById('material').value;
        thickness = document.getElementById('thickness').value;
        colorSelect = document.getElementById('manualColor');
        helpText = document.getElementById('manualColorHelp');
    } else if (context === 'bulk') {
        material = document.getElementById('bulkMaterial').value;
        thickness = document.getElementById('bulkThickness').value;
        colorSelect = document.getElementById('bulkColor');
        helpText = document.getElementById('bulkColorHelp');
    }
    
    // Clear previous options
    colorSelect.innerHTML = '<option value="">Loading colors...</option>';
    if (helpText) helpText.textContent = '';
    
    // Validate inputs
    if (!material || !thickness) {
        colorSelect.innerHTML = '<option value="">Select material and thickness first...</option>';
        return;
    }
    
    try {
        // Fetch available colors
        const response = await fetch(`/api/inventory/colors?material=${encodeURIComponent(material)}&thickness=${thickness}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success && result.colors.length > 0) {
            // Clear loading message
            colorSelect.innerHTML = '<option value="">Select color...</option>';
            
            // Add color options
            result.colors.forEach(color => {
                const option = document.createElement('option');
                option.value = color.color;
                
                // Show stock status in option text
                if (color.in_stock) {
                    option.textContent = `${color.color} (${color.stock} sheets available)`;
                } else {
                    option.textContent = `${color.color} (Out of stock)`;
                    option.disabled = true;
                    option.style.color = '#999';
                }
                
                colorSelect.appendChild(option);
            });
            
            // Update help text
            if (helpText) {
                const inStockCount = result.colors.filter(c => c.in_stock).length;
                helpText.textContent = `${inStockCount} color(s) available in stock`;
                helpText.style.color = inStockCount > 0 ? '#28a745' : '#dc3545';
            }
        } else {
            colorSelect.innerHTML = '<option value="">No colors available for this material</option>';
            if (helpText) {
                helpText.textContent = '⚠️ This material is not in inventory. Add it first.';
                helpText.style.color = '#ffc107';
            }
        }
    } catch (error) {
        console.error('Error loading colors:', error);
        colorSelect.innerHTML = '<option value="">Error loading colors</option>';
        if (helpText) {
            helpText.textContent = `❌ Error: ${error.message || 'Failed to load colors'}`;
            helpText.style.color = '#dc3545';
        }
    }
}

// ========================================
// DISCOUNT MODAL FUNCTIONS
// ========================================

/**
 * Show the discount modal
 */
function showDiscountModal() {
    // Check if price is calculated
    if (!currentPrice || currentPrice === 0) {
        showNotification('Please calculate a price first!', 'warning');
        return;
    }
    
    // Check if discount already applied
    if (discountAppliedToCurrentQuote) {
        showNotification('Discount already applied to this quote!', 'warning');
        return;
    }
    
    // Check minimum amount
    if (currentPrice < 10500) {
        showNotification(`Discount cannot be applied. Minimum amount: ₦10,500. Current: ₦${currentPrice.toLocaleString()}`, 'error');
        return;
    }
    
    // Reset modal state
    selectedDiscountPercent = 0;
    document.getElementById('customDiscountInput').value = '';
    document.querySelectorAll('.discount-option-btn').forEach(btn => {
        btn.classList.remove('selected');
    });
    document.getElementById('discountPreview').style.display = 'none';
    document.getElementById('confirmDiscountBtn').disabled = true;
    
    // Show modal
    document.getElementById('discountModal').style.display = 'flex';
}

/**
 * Close the discount modal
 */
function closeDiscountModal() {
    document.getElementById('discountModal').style.display = 'none';
}

/**
 * Select a discount percentage
 */
function selectDiscountPercent(percent) {
    selectedDiscountPercent = parseFloat(percent);
    
    // Validate
    if (isNaN(selectedDiscountPercent) || selectedDiscountPercent <= 0 || selectedDiscountPercent > 100) {
        document.getElementById('discountPreview').style.display = 'none';
        document.getElementById('confirmDiscountBtn').disabled = true;
        return;
    }
    
    // Update button states
    document.querySelectorAll('.discount-option-btn').forEach(btn => {
        if (parseFloat(btn.dataset.percent) === selectedDiscountPercent) {
            btn.classList.add('selected');
        } else {
            btn.classList.remove('selected');
        }
    });
    
    // If custom input, clear button selection
    if (percent !== 2 && percent !== 5 && percent !== 10) {
        document.querySelectorAll('.discount-option-btn').forEach(btn => {
            btn.classList.remove('selected');
        });
    }
    
    // Calculate preview
    const discountAmount = currentPrice * (selectedDiscountPercent / 100);
    const newPrice = currentPrice - discountAmount;
    
    // Update preview
    document.getElementById('previewOriginal').textContent = '₦' + currentPrice.toLocaleString('en-NG', {minimumFractionDigits: 2});
    document.getElementById('previewPercent').textContent = selectedDiscountPercent.toFixed(1);
    document.getElementById('previewDiscount').textContent = '-₦' + discountAmount.toLocaleString('en-NG', {minimumFractionDigits: 2});
    document.getElementById('previewNewPrice').textContent = '₦' + newPrice.toLocaleString('en-NG', {minimumFractionDigits: 2});
    
    // Show preview and enable confirm button
    document.getElementById('discountPreview').style.display = 'block';
    document.getElementById('confirmDiscountBtn').disabled = false;
}

/**
 * Apply the discount to current quote
 */
async function applyDiscount() {
    if (selectedDiscountPercent <= 0) {
        showNotification('Please select a discount percentage', 'warning');
        return;
    }
    
    try {
        // Calculate discount
        const response = await fetch('/api/calculate-discount', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                current_price: currentPrice,
                discount_percentage: selectedDiscountPercent
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Check if this is a bulk order
            const isBulkOrder = currentJobData && currentJobData.isBulkOrder;
            
            if (isBulkOrder) {
                // Apply discount to bulk order
                applyDiscountToBulkOrder(result);
            } else {
                // Apply discount to single quote
                applyDiscountToSingleQuote(result);
            }
            
            // Close modal
            closeDiscountModal();
            
            // Show success notification
            showNotification(`✅ ${result.discount_percentage}% discount applied! New total: ₦${result.new_price.toLocaleString()}`, 'success');
            
        } else {
            showNotification(result.error || 'Failed to apply discount', 'error');
        }
        
    } catch (error) {
        console.error('Error applying discount:', error);
        showNotification('Error applying discount: ' + error.message, 'error');
    }
}

/**
 * Apply discount to single quote
 */
function applyDiscountToSingleQuote(result) {
    const originalPrice = currentPrice;
    currentPrice = result.new_price;
    
    // Store discount info in currentJobData
    currentJobData.discount_applied = true;
    currentJobData.discount_percentage = result.discount_percentage;
    currentJobData.discount_amount = result.discount_amount;
    currentJobData.original_price = result.original_price;
    
    // Update UI
    document.getElementById('priceDisplay').textContent = '₦' + result.new_price.toLocaleString('en-NG', {minimumFractionDigits: 2});
    
    // Show discount breakdown
    document.getElementById('originalPriceDisplay').textContent = '₦' + result.original_price.toLocaleString('en-NG', {minimumFractionDigits: 2});
    document.getElementById('discountPercentDisplay').textContent = result.discount_percentage.toFixed(1);
    document.getElementById('discountAmountDisplay').textContent = '-₦' + result.discount_amount.toLocaleString('en-NG', {minimumFractionDigits: 2});
    document.getElementById('finalPriceDisplay').textContent = '₦' + result.new_price.toLocaleString('en-NG', {minimumFractionDigits: 2});
    
    document.getElementById('discountBreakdown').style.display = 'block';
    
    // Disable the discount button
    document.getElementById('applyDiscountBtn').disabled = true;
    document.getElementById('applyDiscountBtn').textContent = '✓ Discount Applied';
    document.getElementById('applyDiscountBtn').style.opacity = '0.6';
    
    // Mark as applied
    discountAppliedToCurrentQuote = true;
}

/**
 * Apply discount to bulk order
 */
function applyDiscountToBulkOrder(result) {
    // Store discount info globally for bulk order
    window.bulkOrderDiscount = {
        applied: true,
        discount_percentage: result.discount_percentage,
        discount_amount: result.discount_amount,
        original_price: result.original_price,
        new_price: result.new_price
    };
    
    // Update bulk order display
    updateBulkItemsDisplay();
    
    // Mark as applied
    discountAppliedToCurrentQuote = true;
}

// ========================================
// BULK ORDER DISCOUNT BUTTON
// ========================================

/**
 * Show discount modal for bulk order
 * This replaces the single quote discount logic for bulk
 */
function showBulkDiscountModal() {
    // Check if there are items
    if (bulkItems.length === 0) {
        showNotification('Please add items to the bulk order first!', 'warning');
        return;
    }
    
    // Calculate total price
    const totalPrice = bulkItems.reduce((sum, item) => sum + (item.price || 0), 0);
    
    // Check minimum amount
    if (totalPrice < 10500) {
        showNotification(`Discount cannot be applied. Minimum amount: ₦10,500. Current total: ₦${totalPrice.toLocaleString()}`, 'error');
        return;
    }
    
    // Set current price for discount calculation
    currentPrice = totalPrice;
    currentJobData = { isBulkOrder: true }; // Flag this as bulk order
    discountAppliedToCurrentQuote = false;
    
    // Reset modal state
    selectedDiscountPercent = 0;
    document.getElementById('customDiscountInput').value = '';
    document.querySelectorAll('.discount-option-btn').forEach(btn => {
        btn.classList.remove('selected');
    });
    document.getElementById('discountPreview').style.display = 'none';
    document.getElementById('confirmDiscountBtn').disabled = true;
    
    // Show modal
    document.getElementById('discountModal').style.display = 'flex';
}