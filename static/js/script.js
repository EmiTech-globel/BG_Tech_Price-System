// CNC Pricing System - Main JavaScript

let extractedData = null;
let currentJobData = null;
let currentPrice = null;
let bulkItems = [];
let bulkItemCounter = 0;

// Tab switching
function showTab(tabName) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    event.target.classList.add('active');
    document.getElementById(tabName).classList.add('active');
    
    document.getElementById('resultBox').classList.remove('show');
}

// File upload handling
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

async function handleFile(file) {
    if (!file.name.toLowerCase().endsWith('.svg')) {
        alert('Please upload an SVG file!');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    document.getElementById('uploadLoading').classList.add('show');
    document.getElementById('fileInfo').classList.remove('show');
    document.getElementById('uploadCalcBtn').disabled = true;
    
    try {
        const response = await fetch('/analyze_file', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        document.getElementById('uploadLoading').classList.remove('show');
        
        if (result.success) {
            extractedData = result;
            displayExtractedInfo(result);
            document.getElementById('uploadCalcBtn').disabled = false;
        } else {
            alert('Error analyzing file: ' + result.error);
        }
    } catch (error) {
        document.getElementById('uploadLoading').classList.remove('show');
        alert('Error uploading file: ' + error.message);
    }
}

function displayExtractedInfo(data) {
    document.getElementById('extractedWidth').textContent = data.width_mm + 'mm';
    document.getElementById('extractedHeight').textContent = data.height_mm + 'mm';
    document.getElementById('extractedShapes').textContent = data.num_shapes;
    document.getElementById('extractedLetters').textContent = data.num_letters;
    document.getElementById('extractedComplexity').textContent = data.complexity_score + '/5';
    document.getElementById('extractedTime').textContent = data.cutting_time_minutes + ' minutes';
    
    document.getElementById('fileInfo').classList.add('show');
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
            alert('❌ Error saving quote: ' + result.error);
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
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
            
            <div style="margin-top: 15px; text-align: right;">
                <button onclick="deleteQuote(${quote.id})" style="background: #dc3545; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer;">🗑️ Delete</button>
            </div>
        </div>
    `;
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
            alert('✅ Quote deleted successfully');
            loadQuotes();
        } else {
            alert('❌ Error: ' + result.error);
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
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
            alert('❌ Error: ' + result.error);
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
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
                    <strong>❌ Error:</strong> ${result.error}
                </div>
            `;
        }
    } catch (error) {
        statusDiv.innerHTML = `
            <div class="error-box">
                <strong>❌ Error:</strong> ${error.message}
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
        alert('Please fill in all required fields (marked with *)!');
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
    
    // Calculate price for this item
    try {
        const response = await fetch('/calculate_price', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(itemData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Add price to item data
            itemData.price = result.price;
            itemData.id = bulkItemCounter++;
            
            // Add to bulk items array
            bulkItems.push(itemData);
            
            // Update display
            updateBulkItemsDisplay();
            
            // Clear form
            clearBulkForm();
            
            alert(`✅ "${itemName}" added! Price: ₦${result.price.toLocaleString('en-NG', {minimumFractionDigits: 2})}`);
        } else {
            alert('❌ Error calculating price: ' + result.error);
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
    }
}

function updateBulkItemsDisplay() {
    const container = document.getElementById('itemsContainer');
    const countSpan = document.getElementById('itemCount');
    const totalDiv = document.getElementById('bulkTotal');
    const grandTotalSpan = document.getElementById('grandTotal');
    
    countSpan.textContent = bulkItems.length;
    
    if (bulkItems.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #999; padding: 20px;">No items added yet. Add your first item below!</p>';
        totalDiv.style.display = 'none';
        return;
    }
    
    // Calculate grand total
    const grandTotal = bulkItems.reduce((sum, item) => sum + item.price, 0);
    grandTotalSpan.textContent = '₦' + grandTotal.toLocaleString('en-NG', {minimumFractionDigits: 2});
    
    // Display items
    container.innerHTML = bulkItems.map((item, index) => `
        <div style="background: #f9f9f9; border-left: 4px solid #E89D3C; padding: 20px; margin-bottom: 15px; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <div>
                    <h4 style="margin: 0; color: #E89D3C;">${item.name}</h4>
                    <small style="color: #999;">Item #${index + 1}</small>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.5em; font-weight: bold; color: #E89D3C;">₦${item.price.toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
                    <button onclick="removeItemFromBulk(${item.id})" style="background: #dc3545; color: white; border: none; padding: 5px 10px; border-radius: 5px; cursor: pointer; margin-top: 5px;">🗑️ Remove</button>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9em;">
                <div><strong>Material:</strong> ${item.material} (${item.thickness}mm)</div>
                <div><strong>Size:</strong> ${item.width}×${item.height}mm</div>
                <div><strong>Cutting:</strong> ${item.cuttingType}</div>
                <div><strong>Quantity:</strong> ${item.quantity}</div>
                <div><strong>Time:</strong> ${item.time} min</div>
                <div><strong>Complexity:</strong> ${item.complexity}/5</div>
            </div>
        </div>
    `).join('');
    
    totalDiv.style.display = 'block';
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