/* TechGear eCommerce - Main App Logic */

const API_BASE = 'http://localhost:5001';
let currentCart = [];
let userId = 'user_' + Math.random().toString(36).substr(2, 9);

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadProducts();
    loadRecommendations();
    loadCart();
});

// Load all products
async function loadProducts() {
    try {
        const response = await fetch(`${API_BASE}/api/products`);
        const products = await response.json();
        renderProducts(products, 'products-grid');
    } catch (error) {
        console.error('Error loading products:', error);
        showToast('Failed to load products', 'error');
    }
}

// Load AI recommendations
async function loadRecommendations() {
    try {
        const response = await fetch(`${API_BASE}/api/recommendations`);
        const products = await response.json();
        renderProducts(products, 'recommendations-grid');
    } catch (error) {
        console.error('Error loading recommendations:', error);
    }
}

// Render products grid
function renderProducts(products, gridId) {
    const grid = document.getElementById(gridId);
    
    if (!products || products.length === 0) {
        grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: #555;">No products found</p>';
        return;
    }

    grid.innerHTML = products.map(product => `
        <div class="product-card" onclick="viewProductDetails(${product.id})">
            <div class="product-image">📦</div>
            <div class="product-content">
                <div class="product-category">${product.category}</div>
                <h3 class="product-name">${product.name}</h3>
                <p class="product-description">${product.description}</p>
                <div class="product-footer">
                    <span class="product-price">$${product.price}</span>
                    <div class="product-rating">
                        ⭐ ${product.rating} <span style="color: #999; font-size: 0.9rem;">(${product.reviews})</span>
                    </div>
                </div>
                <div style="display: flex; gap: 0.5rem; margin-top: 1rem;">
                    ${product.inStock ? 
                        `<button class="btn-add" onclick="addToCart(event, ${product.id}, '${product.name}', ${product.price})">Add to Cart</button>` :
                        `<button class="btn-add" style="background: #ccc; cursor: not-allowed;">Out of Stock</button>`
                    }
                    <button class="btn-outline" onclick="viewProductDetails(event, ${product.id})">Details</button>
                </div>
            </div>
        </div>
    `).join('');
}

// Search products
async function performSearch() {
    const query = document.getElementById('search-input').value;
    if (!query.trim()) {
        loadProducts();
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        const data = await response.json();
        renderProducts(data.results, 'products-grid');
        showToast(`Found ${data.results.length} products matching "${query}"`, 'success');
    } catch (error) {
        console.error('Search error:', error);
        showToast('Search failed', 'error');
    }
}

// Filter by category
async function filterByCategory(category) {
    try {
        const url = category === 'All' 
            ? `${API_BASE}/api/products`
            : `${API_BASE}/api/products?category=${category}`;
        
        const response = await fetch(url);
        const products = await response.json();
        renderProducts(products, 'products-grid');

        // Update active filter tag
        document.querySelectorAll('.filter-tag').forEach(tag => {
            tag.classList.remove('active');
            if (tag.textContent === category) {
                tag.classList.add('active');
            }
        });
    } catch (error) {
        console.error('Filter error:', error);
    }
}

// View product details
async function viewProductDetails(e, productId) {
    if (e && e.stopPropagation) {
        e.stopPropagation();
    }

    try {
        const response = await fetch(`${API_BASE}/api/products`);
        const products = await response.json();
        const product = products.find(p => p.id === productId);

        if (!product) return;

        const modalBody = document.getElementById('modal-body');
        modalBody.innerHTML = `
            <h2>${product.name}</h2>
            <div style="display: flex; justify-content: space-between; align-items: center; margin: 1rem 0;">
                <div>
                    <div style="font-size: 3rem; color: #0078D4;">📦</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 2rem; color: #0078D4; font-weight: 700;">$${product.price}</div>
                    <div style="color: #FF9500;">⭐ ${product.rating} (${product.reviews} reviews)</div>
                </div>
            </div>
            
            <p style="color: #555; margin-bottom: 1rem;">${product.description}</p>
            
            <div class="modal-specs">
                <h4>Specifications</h4>
                <ul class="specs-list">
                    ${product.specs.map(spec => `<li><span>✓</span> <span>${spec}</span></li>`).join('')}
                </ul>
            </div>

            <div style="display: flex; gap: 1rem; margin-top: 2rem;">
                ${product.inStock ? 
                    `<button class="btn-add" style="flex: 1;" onclick="addToCart(null, ${product.id}, '${product.name}', ${product.price}); closeModal();">Add to Cart</button>` :
                    `<button class="btn-add" style="flex: 1; background: #ccc; cursor: not-allowed;">Out of Stock</button>`
                }
                <button class="btn-outline" style="flex: 1;" onclick="closeModal();">Close</button>
            </div>
        `;

        openModal();
    } catch (error) {
        console.error('Error loading product details:', error);
    }
}

// Add to cart
async function addToCart(e, productId, productName, price) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }

    try {
        const response = await fetch(`${API_BASE}/api/cart?user_id=${userId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                product_id: productId,
                quantity: 1
            })
        });

        if (response.ok) {
            showToast(`✓ Added ${productName} to cart`, 'success');
            loadCart();
        }
    } catch (error) {
        console.error('Error adding to cart:', error);
        showToast('Failed to add to cart', 'error');
    }
}

// Load cart
async function loadCart() {
    try {
        const response = await fetch(`${API_BASE}/api/cart?user_id=${userId}`);
        const cart = await response.json();
        
        // Update cart count
        const cartCount = document.getElementById('cart-count');
        cartCount.textContent = cart.item_count || 0;

        // Update cart items
        const cartItems = document.getElementById('cart-items');
        if (!cart.items || cart.items.length === 0) {
            cartItems.innerHTML = '<div class="cart-empty">🛒 Your cart is empty</div>';
        } else {
            cartItems.innerHTML = cart.items.map(item => `
                <div class="cart-item">
                    <div class="cart-item-info">
                        <h4>${item.name}</h4>
                        <p>Qty: ${item.quantity}</p>
                    </div>
                    <div style="flex: 1; text-align: right;">
                        <div class="cart-item-price">$${(item.price * item.quantity).toFixed(2)}</div>
                        <button class="cart-remove" onclick="removeFromCart(${item.product_id})">Remove</button>
                    </div>
                </div>
            `).join('');
        }

        // Update totals
        const subtotal = cart.total || 0;
        const tax = subtotal * 0.08;
        const shipping = cart.items.length > 0 ? 9.99 : 0;
        const total = subtotal + tax + shipping;

        document.getElementById('cart-subtotal').textContent = `$${subtotal.toFixed(2)}`;
        document.getElementById('cart-tax').textContent = `$${tax.toFixed(2)}`;
        document.getElementById('cart-shipping').textContent = shipping > 0 ? `$${shipping.toFixed(2)}` : 'Free';
        document.getElementById('cart-total').textContent = `$${total.toFixed(2)}`;
    } catch (error) {
        console.error('Error loading cart:', error);
    }
}

// Remove from cart
async function removeFromCart(productId) {
    try {
        const response = await fetch(`${API_BASE}/api/cart?user_id=${userId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: productId })
        });

        if (response.ok) {
            showToast('✓ Item removed from cart', 'success');
            loadCart();
        }
    } catch (error) {
        console.error('Error removing from cart:', error);
    }
}

// Checkout
async function checkout() {
    try {
        const response = await fetch(`${API_BASE}/api/checkout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });

        if (response.ok) {
            const data = await response.json();
            showToast(`✓ Order placed! Order ID: ${data.order.order_id}`, 'success');
            loadCart();
            setTimeout(() => {
                toggleCart();
                alert(`Order Confirmed!\n\nOrder ID: ${data.order.order_id}\nTotal: $${data.order.total}\n\nEstimated Delivery: ${data.order.estimated_delivery}`);
            }, 500);
        } else {
            showToast('Failed to complete checkout', 'error');
        }
    } catch (error) {
        console.error('Checkout error:', error);
        showToast('Checkout failed', 'error');
    }
}

// Toggle cart visibility
function toggleCart() {
    const sidebar = document.getElementById('cart-sidebar');
    const overlay = document.getElementById('cart-overlay');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
}

// Open modal
function openModal() {
    const modal = document.getElementById('product-modal');
    const overlay = document.getElementById('modal-overlay');
    modal.classList.add('open');
    overlay.classList.add('open');
}

// Close modal
function closeModal() {
    const modal = document.getElementById('product-modal');
    const overlay = document.getElementById('modal-overlay');
    modal.classList.remove('open');
    overlay.classList.remove('open');
}

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        if (document.getElementById('cart-sidebar').classList.contains('open')) {
            toggleCart();
        }
    }
});
