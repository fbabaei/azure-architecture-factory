"""
TechGear eCommerce Platform - Backend API
Powered by Azure AI Foundry and Cognitive Services
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
from datetime import datetime, timedelta
import random
from pathlib import Path

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Sample products catalog
PRODUCTS = [
    {
        "id": 1,
        "name": "Pro Wireless Headphones",
        "category": "Audio",
        "price": 299.99,
        "rating": 4.8,
        "reviews": 1250,
        "image": "headphones.jpg",
        "description": "Premium noise-cancelling wireless headphones with 30-hour battery life",
        "inStock": True,
        "specs": ["Active Noise Cancellation", "30-hour battery", "Bluetooth 5.0", "Foldable design"]
    },
    {
        "id": 2,
        "name": "Ultra Fast SSD 2TB",
        "category": "Storage",
        "price": 199.99,
        "rating": 4.9,
        "reviews": 840,
        "image": "ssd.jpg",
        "description": "Lightning-fast NVMe SSD with read speeds up to 7,500 MB/s",
        "inStock": True,
        "specs": ["7,500 MB/s read speed", "PCIe 4.0", "2TB capacity", "5-year warranty"]
    },
    {
        "id": 3,
        "name": "4K Webcam Pro",
        "category": "Video",
        "price": 149.99,
        "rating": 4.7,
        "reviews": 520,
        "image": "webcam.jpg",
        "description": "Professional 4K resolution webcam perfect for streaming and video calls",
        "inStock": True,
        "specs": ["4K resolution", "Auto focus", "Built-in mic", "Wide angle lens"]
    },
    {
        "id": 4,
        "name": "Mechanical Gaming Keyboard",
        "category": "Peripherals",
        "price": 179.99,
        "rating": 4.6,
        "reviews": 1890,
        "image": "keyboard.jpg",
        "description": "RGB mechanical gaming keyboard with custom switches and macro keys",
        "inStock": True,
        "specs": ["Cherry MX switches", "RGB lighting", "Programmable", "Aluminum frame"]
    },
    {
        "id": 5,
        "name": "Portable Power Bank 65W",
        "category": "Power",
        "price": 89.99,
        "rating": 4.5,
        "reviews": 2100,
        "image": "powerbank.jpg",
        "description": "Ultra-compact 65W power bank charges laptops and phones simultaneously",
        "inStock": True,
        "specs": ["65W output", "30000mAh", "USB-C", "Lightweight design"]
    },
    {
        "id": 6,
        "name": "Ergonomic Gaming Mouse",
        "category": "Peripherals",
        "price": 79.99,
        "rating": 4.7,
        "reviews": 1450,
        "image": "mouse.jpg",
        "description": "Precision gaming mouse with customizable DPI and ergonomic grip",
        "inStock": True,
        "specs": ["16,000 DPI", "Wireless 2.4GHz", "8-hour battery", "8 programmable buttons"]
    },
    {
        "id": 7,
        "name": "USB-C Hub 7-in-1",
        "category": "Connectivity",
        "price": 59.99,
        "rating": 4.4,
        "reviews": 890,
        "image": "hub.jpg",
        "description": "Multi-port USB-C hub with HDMI, USB 3.0, and SD card reader",
        "inStock": True,
        "specs": ["7 ports", "4K HDMI", "USB 3.0 x3", "SD/TF card reader"]
    },
    {
        "id": 8,
        "name": "Curved Gaming Monitor 32\"",
        "category": "Displays",
        "price": 399.99,
        "rating": 4.8,
        "reviews": 620,
        "image": "monitor.jpg",
        "description": "144Hz curved gaming monitor with 1ms response time and HDR support",
        "inStock": False,
        "specs": ["1440p resolution", "144Hz", "1ms response", "HDR10"]
    },
    {
        "id": 9,
        "name": "Laptop Stand Premium",
        "category": "Accessories",
        "price": 49.99,
        "rating": 4.6,
        "reviews": 540,
        "image": "stand.jpg",
        "description": "Adjustable aluminum laptop stand for ergonomic computing",
        "inStock": True,
        "specs": ["Aluminum construction", "Adjustable height", "Foldable", "Non-slip base"]
    },
    {
        "id": 10,
        "name": "Wireless Charging Pad",
        "category": "Power",
        "price": 39.99,
        "rating": 4.5,
        "reviews": 1200,
        "image": "charger.jpg",
        "description": "Fast wireless charging pad compatible with all Qi-enabled devices",
        "inStock": True,
        "specs": ["15W fast charge", "Qi certified", "LED indicator", "Non-slip surface"]
    }
]

# Mock user cart storage
shopping_carts = {}

class ShoppingCart:
    def __init__(self, cart_id):
        self.id = cart_id
        self.items = []
        self.created_at = datetime.now()
    
    def add_item(self, product_id, quantity=1):
        existing = next((item for item in self.items if item['product_id'] == product_id), None)
        if existing:
            existing['quantity'] += quantity
        else:
            product = next((p for p in PRODUCTS if p['id'] == product_id), None)
            if product:
                self.items.append({
                    'product_id': product_id,
                    'quantity': quantity,
                    'price': product['price'],
                    'name': product['name']
                })
        return True
    
    def remove_item(self, product_id):
        self.items = [item for item in self.items if item['product_id'] != product_id]
        return True
    
    def get_total(self):
        return sum(item['price'] * item['quantity'] for item in self.items)
    
    def get_item_count(self):
        return sum(item['quantity'] for item in self.items)

@app.route('/')
def index():
    """Render main ecommerce page"""
    return render_template('index.html')

@app.route('/architecture')
def architecture():
    """Render architecture page"""
    return render_template('architecture.html')

@app.route('/api/products')
def get_products():
    """Get all products or search by query"""
    category = request.args.get('category')
    search = request.args.get('search', '').lower()
    
    products = PRODUCTS
    
    if category:
        products = [p for p in products if p['category'].lower() == category.lower()]
    
    if search:
        products = [p for p in products if search in p['name'].lower() or search in p['description'].lower()]
    
    return jsonify(products)

@app.route('/api/categories')
def get_categories():
    """Get unique product categories"""
    categories = list(set(p['category'] for p in PRODUCTS))
    return jsonify(sorted(categories))

@app.route('/api/recommendations')
def get_recommendations():
    """Get AI-powered product recommendations"""
    product_id = request.args.get('product_id', type=int)
    
    # Mock recommendation using product category
    if product_id:
        product = next((p for p in PRODUCTS if p['id'] == product_id), None)
        if product:
            # Return products from same category + higher rated items
            recommendations = [
                p for p in PRODUCTS 
                if p['category'] == product['category'] and p['id'] != product_id
            ][:3]
            # Add top-rated products
            top_rated = sorted(PRODUCTS, key=lambda x: x['rating'], reverse=True)[:2]
            recommendations.extend([p for p in top_rated if p not in recommendations])
            return jsonify(recommendations[:3])
    
    # Default recommendations: top rated products
    top_products = sorted(PRODUCTS, key=lambda x: x['rating'], reverse=True)[:6]
    return jsonify(top_products)

@app.route('/api/search', methods=['POST'])
def search_products():
    """Semantic search using AI Search (mocked)"""
    data = request.json
    query = data.get('query', '').lower()
    
    # Mock semantic search
    results = []
    for product in PRODUCTS:
        score = 0
        if query in product['name'].lower():
            score += 10
        if query in product['description'].lower():
            score += 5
        if query in ' '.join(product['specs']).lower():
            score += 3
        
        if score > 0:
            results.append({**product, 'relevance_score': score})
    
    # Sort by relevance score
    results.sort(key=lambda x: x['relevance_score'], reverse=True)
    
    return jsonify({
        'query': query,
        'results': results[:6],
        'total_results': len(results)
    })

@app.route('/api/cart', methods=['GET', 'POST', 'DELETE'])
def manage_cart():
    """Manage shopping cart"""
    user_id = request.args.get('user_id', 'default_user')
    
    if user_id not in shopping_carts:
        shopping_carts[user_id] = ShoppingCart(user_id)
    
    cart = shopping_carts[user_id]
    
    if request.method == 'GET':
        return jsonify({
            'items': cart.items,
            'total': cart.get_total(),
            'item_count': cart.get_item_count(),
            'created_at': cart.created_at.isoformat()
        })
    
    elif request.method == 'POST':
        data = request.json
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        
        cart.add_item(product_id, quantity)
        
        return jsonify({
            'success': True,
            'message': f'Product added to cart',
            'items': cart.items,
            'total': cart.get_total(),
            'item_count': cart.get_item_count()
        })
    
    elif request.method == 'DELETE':
        data = request.json or {}
        product_id = data.get('product_id')
        
        if product_id:
            cart.remove_item(product_id)
        else:
            cart.items = []
        
        return jsonify({
            'success': True,
            'message': 'Cart updated',
            'items': cart.items,
            'total': cart.get_total(),
            'item_count': cart.get_item_count()
        })

@app.route('/api/checkout', methods=['POST'])
def checkout():
    """Process checkout"""
    data = request.json
    user_id = data.get('user_id', 'default_user')
    
    if user_id not in shopping_carts or not shopping_carts[user_id].items:
        return jsonify({'success': False, 'error': 'Cart is empty'}), 400
    
    cart = shopping_carts[user_id]
    
    # Mock checkout process
    order = {
        'order_id': f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'user_id': user_id,
        'items': cart.items,
        'subtotal': cart.get_total(),
        'tax': round(cart.get_total() * 0.08, 2),
        'shipping': 9.99,
        'total': round(cart.get_total() * 1.08 + 9.99, 2),
        'status': 'Confirmed',
        'created_at': datetime.now().isoformat(),
        'estimated_delivery': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    }
    
    # Clear cart
    shopping_carts[user_id] = ShoppingCart(user_id)
    
    return jsonify({
        'success': True,
        'order': order,
        'message': 'Order placed successfully!'
    })

@app.route('/api/analytics')
def get_analytics():
    """Get platform analytics (mocked AI insights)"""
    return jsonify({
        'total_products': len(PRODUCTS),
        'categories': len(set(p['category'] for p in PRODUCTS)),
        'avg_rating': round(sum(p['rating'] for p in PRODUCTS) / len(PRODUCTS), 2),
        'in_stock': len([p for p in PRODUCTS if p['inStock']]),
        'trending': [
            {'name': 'Pro Wireless Headphones', 'views': 1250, 'conversions': 156},
            {'name': 'Ultra Fast SSD 2TB', 'views': 1100, 'conversions': 132},
            {'name': 'Mechanical Gaming Keyboard', 'views': 950, 'conversions': 114}
        ],
        'insights': [
            "Pro Wireless Headphones are trending this week (AI detected 45% increase in views)",
            "Storage category shows 3.2% higher conversion rate than average",
            "Users who view headphones are 8x more likely to purchase gaming keyboards",
            "Recommended: Stock up on gaming peripherals for upcoming event"
        ]
    })

@app.route('/api/architecture')
def get_architecture_details():
    """Get architecture component details"""
    return jsonify({
        'services': {
            'frontend': {
                'name': 'Static Web App',
                'icon': '🌐',
                'description': 'Global content delivery with CDN edge caching',
                'benefits': ['99.95% uptime', '<100ms global latency', 'Automatic SSL', 'DDoS protection']
            },
            'api': {
                'name': 'API Management + Container Apps',
                'icon': '🔗',
                'description': 'Scalable microservices with intelligent routing',
                'benefits': ['Auto-scaling', 'Rate limiting', 'API versioning', 'Built-in monitoring']
            },
            'ai': {
                'name': 'Azure AI Foundry',
                'icon': '🤖',
                'description': 'AI-powered features: recommendations, search, insights',
                'services': ['Azure OpenAI', 'AI Search', 'Document AI', 'Content Safety'],
                'benefits': ['Personalized recommendations', 'Semantic search', 'Intelligent insights']
            },
            'data': {
                'name': 'Data Layer',
                'icon': '💾',
                'description': 'Multi-tier data storage with caching',
                'services': ['Cosmos DB (NoSQL)', 'Blob Storage', 'Redis Cache'],
                'benefits': ['Global distribution', 'Millisecond latency', 'Multi-region failover']
            },
            'monitoring': {
                'name': 'Observability',
                'icon': '📊',
                'description': 'Comprehensive monitoring and security',
                'services': ['Application Insights', 'Key Vault', 'Defender for Cloud'],
                'benefits': ['Real-time telemetry', 'Distributed tracing', 'Security alerts']
            }
        },
        'deployment_model': 'Cloud-Native, Serverless/Managed Services',
        'sla': '99.95% availability',
        'regions': ['East US', 'West Europe', 'Southeast Asia'],
        'scalability': 'Auto-scales from 0 to 1M+ concurrent users'
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'api': 'operational',
            'search': 'operational',
            'recommendations': 'operational',
            'database': 'operational'
        }
    })

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5001)
