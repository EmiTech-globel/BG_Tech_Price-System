// CNC Pricing System - Main JavaScript

let extractedData = null;
let currentJobData = null;
let currentPrice = null;

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
        <div style="background: #f9f9f9; border-left: 4px solid #667eea; padding: 20px; margin-bottom: 15px; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <div>
                    <h3 style="margin: 0; color: #667eea;">${quote.quote_number}${rushBadge}</h3>
                    <small style="color: #999;">${quote.created_at}</small>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.5em; font-weight: bold; color: #667eea;">₦${quote.quoted_price.toLocaleString('en-NG', {minimumFractionDigits: 2})}</div>
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