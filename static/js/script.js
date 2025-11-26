// CNC Pricing System - Main JavaScript

let extractedData = null;
let currentJobData = null;
let currentPrice = null;
let bulkItems = [];
let bulkItemCounter = 0;

// ========================================
// TAB MANAGEMENT FUNCTIONS
// ========================================

function showTab(tabName) {
    console.log("Switching to tab:", tabName);
    
    // Remove active class from all tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from all tab contents
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Add active class to clicked tab and corresponding content
    const activeTab = document.querySelector(`.tab[onclick*="${tabName}"]`);
    const activeContent = document.getElementById(tabName);
    
    if (activeTab && activeContent) {
        activeTab.classList.add('active');
        activeContent.classList.add('active');
    }
    
    // Hide result box when switching tabs
    document.getElementById('resultBox').classList.remove('show');
    
    // Load data for specific tabs
    if (tabName === 'quotes') {
        loadQuotes();
    } else if (tabName === 'addjob') {
        updateTrainingStats();
    }
}
// ========================================

// FILE UPLOAD AND ANALYSIS FUNCTIONS
// ========================================

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');

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

function displayDxfMultiItemResults(result) {
    console.log("Displaying DXF multi-item results:", result);
    
    try {
        // Convert DXF items to bulk items format
        bulkItems = result.items.map((item, index) => ({
            id: index,
            name: item.name,
            material: '',
            thickness: 0,
            width: item.width_mm,
            height: item.height_mm,
            letters: item.num_letters,
            shapes: item.num_shapes,
            complexity: item.complexity_score,
            details: item.has_intricate_details,
            cuttingType: 'Laser Cutting',
            time: item.cutting_time_minutes,
            quantity: 1,
            rush: 0,
            price: 0
        }));
        
        updateBulkItemsDisplay();
        showTab('bulk');
        
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
    const cuttingType = document.getElementById('uploadCuttingType').value;
    const quantity = document.getElementById('uploadQuantity').value;
    const rush = document.getElementById('uploadRush').checked ? 1 : 0;
    
    if (!material || !thickness) {
        alert('Please select material and thickness!');
        return;
    }
    
    if (!extractedData) {
        alert('Please upload a file first!');
        return;
    }
    
    const jobData = {
        material: material,
        thickness: parseFloat(thickness),
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
    
    if (!material || !thickness || !width || !height || !time) {
        alert('Please fill in all required fields (marked with *)!');
        return;
    }
    
    const jobData = {
        material: material,
        thickness: parseFloat(thickness),
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
            displayResult(result.price, jobData);
        } else {
            alert('Error calculating price: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function displayDxfMultiItemResults(result) {
    console.log("Displaying DXF multi-item results:", result);
    
    try {
        // Convert DXF items to bulk items format
        bulkItems = result.items.map((item, index) => ({
            id: index,
            name: item.name,
            material: '',
            thickness: 0,
            width: item.width_mm,
            height: item.height_mm,
            letters: item.num_letters,
            shapes: item.num_shapes,
            complexity: item.complexity_score,
            details: item.has_intricate_details,
            cuttingType: 'Laser Cutting',
            time: item.cutting_time_minutes,
            quantity: 1,
            rush: 0,
            price: 0 // Will be calculated later
        }));
        
        console.log("Converted bulk items:", bulkItems);
        
        // Update the bulk items display
        updateBulkItemsDisplay();
        
        // Switch to bulk order tab safely
        const bulkTab = document.querySelector('.tab[onclick*="bulk"]');
        if (bulkTab) {
            bulkTab.click(); // Use the existing tab click handler
        } else {
            // Fallback: manually switch to bulk tab
            showTab('bulk');
        }
        
        console.log("Successfully displayed DXF multi-items");
        
    } catch (error) {
        console.error("Error displaying DXF multi-items:", error);
        alert('Error displaying multiple jobs. Please check console for details.');
    }
}

function displayResult(price, jobData) {
    // Store current quote data
    currentJobData = jobData;
    currentPrice = price;
    
    document.getElementById('priceDisplay').textContent = '₦' + price.toLocaleString('en-NG', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    document.getElementById('resultMaterial').textContent = jobData.material + ' (' + jobData.thickness + 'mm)';
    document.getElementById('resultSize').textContent = jobData.width + 'mm × ' + jobData.height + 'mm';
    document.getElementById('resultComplexity').textContent = jobData.complexity + '/5';
    document.getElementById('resultCutting').textContent = jobData.cuttingType;
    document.getElementById('resultQuantity').textContent = jobData.quantity;
    document.getElementById('resultTime').textContent = jobData.time + ' minutes';
    
    // Reset customer form
    document.getElementById('customerForm').style.display = 'none';
    document.getElementById('saveQuoteBtn').style.display = 'block';
    
    document.getElementById('resultBox').classList.add('show');
    document.getElementById('resultBox').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
        alert('No quote to save!');
        return;
    }
    
    const quoteData = {
        ...currentJobData,
        price: currentPrice,
        customer_name: document.getElementById('customerName').value,
        customer_email: document.getElementById('customerEmail').value,
        customer_phone: document.getElementById('customerPhone').value,
        notes: document.getElementById('quoteNotes').value
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
            alert('✅ ' + result.message);
            
            // Clear form
            document.getElementById('customerName').value = '';
            document.getElementById('customerEmail').value = '';
            document.getElementById('customerPhone').value = '';
            document.getElementById('quoteNotes').value = '';
            document.getElementById('customerForm').style.display = 'none';
            document.getElementById('saveQuoteBtn').style.display = 'block';
            
            // Refresh quotes list if on quotes tab
            if (document.getElementById('quotes').classList.contains('active')) {
                loadQuotes();
            }
        } else {
            alert('Error saving quote: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
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
    
    return `
        <div style="background: #f9f9f9; border-left: 4px solid #E89D3C; padding: 20px; margin-bottom: 15px; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <div>
                    <h3 style="margin: 0; color: #E89D3C;">${quote.quote_number}${rushBadge}</h3>
                    <small style="color: #999;">${quote.created_at}</small>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.5em; font-weight: bold; color: #E89D3C;">₦${quote.quoted_price.toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
                </div>
            </div>
            
            ${quote.customer_name ? `<p style="margin: 5px 0;"><strong>Customer:</strong> ${quote.customer_name}</p>` : ''}
            ${quote.customer_email ? `<p style="margin: 5px 0;"><strong>Email:</strong> ${quote.customer_email}</p>` : ''}
            ${quote.customer_phone ? `<p style="margin: 5px 0;"><strong>Phone:</strong> ${quote.customer_phone}</p>` : ''}
            
            <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9em;">
                    <div><strong>Material:</strong> ${quote.material} (${quote.thickness_mm}mm)</div>
                    <div><strong>Size:</strong> ${quote.width_mm}×${quote.height_mm}mm</div>
                    <div><strong>Cutting:</strong> ${quote.cutting_type}</div>
                    <div><strong>Quantity:</strong> ${quote.quantity}</div>
                    <div><strong>Time:</strong> ${quote.cutting_time_minutes} min</div>
                    <div><strong>Complexity:</strong> ${quote.complexity_score}/5</div>
                </div>
            </div>
            
            ${quote.notes ? `<div style="margin-top: 15px; padding: 10px; background: #fff; border-radius: 5px;"><strong>Notes:</strong> ${quote.notes}</div>` : ''}
            
            <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                <button onclick="downloadQuotePDF(${quote.id})" style="background: #E89D3C; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; flex: 1; min-width: 120px;">
                    Download PDF
                </button>
                <button onclick="shareQuoteOnWhatsApp(${quote.id})" style="background: #25D366; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; flex: 1; min-width: 120px;">
                    Share WhatsApp
                </button>
                <button onclick="deleteQuote(${quote.id})" style="background: #dc3545; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer;">
                    Delete
                </button>
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
    if (!confirm('Are you sure you want to delete this quote?')) {
        return;
    }
    
    try {
        const response = await fetch(`/delete_quote/${quoteId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('Quote deleted successfully');
            loadQuotes();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
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
        alert('Please fill in all required fields (marked with *)!');
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
            alert('✅ ' + result.message);
            
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
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
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
                    <strong>✅ ${result.message}</strong>
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
    const width = document.getElementById('bulkWidth').value;
    const height = document.getElementById('bulkHeight').value;
    const time = document.getElementById('bulkTime').value;
    
    if (!material || !thickness || !width || !height || !time) {
        showNotification('Please fill in all required fields!', 'warning');
        return;
    }
    
    const itemName = document.getElementById('bulkItemName').value || `Item ${bulkItemCounter + 1}`;
    
    const itemData = {
        name: itemName,
        material: material,
        thickness: parseFloat(thickness),
        letters: parseInt(document.getElementById('bulkLetters').value),
        shapes: parseInt(document.getElementById('bulkShapes').value),
        complexity: parseInt(document.getElementById('bulkComplexity').value),
        details: document.getElementById('bulkDetails').checked ? 1 : 0,
        width: parseFloat(width),
        height: parseFloat(height),
        cuttingType: document.getElementById('bulkCuttingType').value,
        time: parseFloat(time),
        quantity: parseInt(document.getElementById('bulkQuantity').value),
        rush: document.getElementById('bulkRush').checked ? 1 : 0
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
            itemData.id = bulkItemCounter++;
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

function updateBulkItemsDisplay() {
    const container = document.getElementById('itemsContainer');
    const countSpan = document.getElementById('itemCount');
    const totalDiv = document.getElementById('bulkTotal');
    const grandTotalSpan = document.getElementById('grandTotal');
    
    countSpan.textContent = bulkItems.length;
    
    if (bulkItems.length === 0) {
        container.innerHTML = '<div class="empty-state">No items added yet. Add your first item below!</div>';
        hideElement('bulkTotal');
        return;
    }
    
    const grandTotal = bulkItems.reduce((sum, item) => sum + (item.price || 0), 0);
    grandTotalSpan.textContent = '₦' + grandTotal.toLocaleString('en-NG', {minimumFractionDigits: 2});
    
    container.innerHTML = bulkItems.map((item, index) => `
        <div class="bulk-item-card">
            <div class="bulk-item-header">
                <div>
                    <h4>${item.name}</h4>
                    <small>Item #${index + 1}</small>
                </div>
                <div class="bulk-item-price">
                    <div class="price">${item.price ? '₦' + item.price.toLocaleString('en-NG', {minimumFractionDigits: 2}) : 'Price pending...'}</div>
                    <button onclick="removeItemFromBulk(${item.id})" class="btn-remove">Remove</button>
                </div>
            </div>
            <div class="bulk-item-details">
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
                        <option value="Acrylic">Acrylic</option>
                        <option value="Wood">Wood</option>
                        <option value="Metal">Metal</option>
                        <option value="MDF">MDF</option>
                        <option value="ACP">ACP</option>
                    </select>
                    <select onchange="updateBulkItemThickness(${item.id}, this.value)" class="form-control-sm">
                        <option value="">Thickness</option>
                        <option value="3">3mm</option>
                        <option value="4">4mm</option>
                        <option value="6">6mm</option>
                        <option value="8">8mm</option>
                        <option value="9">9mm</option>
                        <option value="10">10mm</option>
                        <option value="12">12mm</option>
                    </select>
                </div>
            </div>
            ` : ''}
        </div>
    `).join('');
    
    showElement('bulkTotal');
}


function updateBulkItemMaterial(itemId, material) {
    const item = bulkItems.find(item => item.id === itemId);
    if (item) {
        item.material = material;
        calculateBulkItemPrice(itemId);
    }
}

function updateBulkItemThickness(itemId, thickness) {
    const item = bulkItems.find(item => item.id === itemId);
    if (item) {
        item.thickness = parseFloat(thickness);
        calculateBulkItemPrice(itemId);
    }
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

function clearBulkForm() {
    const fields = ['bulkItemName', 'bulkMaterial', 'bulkThickness', 'bulkWidth', 'bulkHeight', 
                   'bulkLetters', 'bulkShapes', 'bulkTime', 'bulkQuantity'];
    
    fields.forEach(field => {
        const element = document.getElementById(field);
        if (element) element.value = field.includes('Quantity') ? '1' : 
                                   field.includes('Letters') ? '0' : 
                                   field.includes('Shapes') ? '1' : '';
    });
    
    document.getElementById('bulkComplexity').value = '3';
    document.getElementById('bulkDetails').checked = false;
    document.getElementById('bulkRush').checked = false;
}

async function calculateBulkItemPrice(itemId) {
    const item = bulkItems.find(item => item.id === itemId);
    if (!item || !item.material || !item.thickness) {
        return;
    }
    
    const jobData = {
        material: item.material,
        thickness: item.thickness,
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
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(jobData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            item.price = result.price;
            updateBulkItemsDisplay();
        }
    } catch (error) {
        console.error('Error calculating bulk item price:', error);
    }
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
        alert('Please add at least one item to the order!');
        return;
    }
    
    // Ask for customer info
    const customerName = prompt('Customer Name (optional):') || '';
    const customerEmail = prompt('Customer Email (optional):') || '';
    const customerPhone = prompt('Customer Phone (optional):') || '';
    const notes = prompt('Order Notes (optional):') || '';
    
    const quoteData = {
        items: bulkItems,
        customer_name: customerName,
        customer_email: customerEmail,
        customer_phone: customerPhone,
        notes: notes
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
            alert(`✅ ${result.message}\n\nQuote Number: ${result.quote_number}\nTotal Items: ${result.items_count}\nTotal Price: ₦${result.total_price.toLocaleString('en-NG', {minimumFractionDigits: 2})}`);
            
            // Clear bulk order
            bulkItems = [];
            bulkItemCounter = 0;
            updateBulkItemsDisplay();
        } else {
            alert('❌ Error saving quote: ' + result.error);
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
    }
}

function shareQuoteOnWhatsApp(quoteId) {
    /**
     * Share quote PDF on WhatsApp
     * Sends PDF link via WhatsApp message
     */
    
    fetch(`/share_quote_whatsapp/${quoteId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const message = data.message;
                
                // Generate WhatsApp URL
                const encodedMessage = encodeURIComponent(message);
                
                // Use WhatsApp Web on desktop, WhatsApp app on mobile
                const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                const whatsappUrl = isMobile 
                    ? `whatsapp://send?text=${encodedMessage}`
                    : `https://web.whatsapp.com/send?text=${encodedMessage}`;
                
                // Open WhatsApp
                window.open(whatsappUrl, '_blank');
            } else {
                alert('Error sharing on WhatsApp: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to share on WhatsApp');
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
     * First saves the quote, then generates PDF share link
     */
    
    if (!currentJobData || !currentPrice) {
        alert('No quote to share! Please generate a quote first.');
        return;
    }
    
    // Prepare quote data
    const quoteData = {
        ...currentJobData,
        price: currentPrice,
        customer_name: document.getElementById('customerName')?.value || '',
        customer_email: document.getElementById('customerEmail')?.value || '',
        customer_phone: document.getElementById('customerPhone')?.value || '',
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
            
            // Generate a message with PDF download link
            const message = `
🔷 *PRICE QUOTATION* 🔷
_BrainGain Tech Innovation Solutions_

📋 *Quote:* ${quoteNumber}
📅 *Date:* ${new Date().toLocaleDateString('en-NG')}

💰 *TOTAL AMOUNT: ₦${currentPrice.toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}*

📎 *Download PDF Quote:*
${window.location.origin}/download_quote_pdf/${quoteId}

_Quote valid for 7 days_
_Generated by BrainGain Tech Pricing System_
            `.trim();
            
            // Generate WhatsApp URL
            const encodedMessage = encodeURIComponent(message);
            const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
            const whatsappUrl = isMobile 
                ? `whatsapp://send?text=${encodedMessage}`
                : `https://web.whatsapp.com/send?text=${encodedMessage}`;
            
            // Open WhatsApp
            window.open(whatsappUrl, '_blank');
            
            alert(`Quote saved as ${quoteNumber}!\n\nOpening WhatsApp to share PDF...`);
        } else {
            alert('Error saving quote: ' + result.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to save and share quote');
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
            alert('Failed to share on WhatsApp');
        });
}