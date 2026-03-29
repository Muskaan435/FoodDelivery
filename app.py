from flask import Flask, render_template, request, redirect, session
import mysql.connector

# ML imports
from MachineLearning.recommend import get_recommendations
from MachineLearning.recommender import train_model, recommend as ml_recommend

app = Flask(__name__)
app.secret_key = "secret123"

# ================= DB CONNECTION =================
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="food_delivery"
)

cursor = db.cursor(buffered=True)

# ================= HOME =================
@app.route('/')
def home():
    return render_template('index.html')

# ================= AUTH =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, password)
        )
        db.commit()
        return redirect('/login')

    return render_template('register.html')

# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            return redirect('/dashboard')

        return "Invalid credentials"

    return render_template('login.html')

# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ================= DASHBOARD (ML + DATA) =================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    # ================= FAVOURITE CATEGORY =================
    cursor.execute("""
        SELECT i.category, COUNT(*) as freq
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN menu i ON oi.item_id = i.item_id
        WHERE o.user_id = %s
        GROUP BY i.category
        ORDER BY freq DESC
        LIMIT 1
    """, (user_id,))
    
    fav = cursor.fetchone()
    fav_category = fav[0] if fav else None

    # ================= PERSONALIZED RECOMMENDATION =================
    cursor.execute("""
        SELECT r.restaurant_id, r.name, r.location, COUNT(*) as freq
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN menu m ON oi.item_id = m.item_id
        JOIN restaurants r ON m.restaurant_id = r.restaurant_id
        WHERE o.user_id = %s
        GROUP BY r.restaurant_id
        ORDER BY freq DESC
        LIMIT 3
    """, (user_id,))

    recommended = cursor.fetchall()

    # ================= NEW USER FALLBACK =================
    if not recommended:
        cursor.execute("""
            SELECT restaurant_id, name, location
            FROM restaurants
            ORDER BY RAND()
            LIMIT 4
        """)
        recommended = cursor.fetchall()

    # ================= OUR RESTAURANTS =================
    cursor.execute("""
        SELECT restaurant_id, name, location 
        FROM restaurants 
        ORDER BY name ASC 
        LIMIT 4
    """)
    our_restaurants = cursor.fetchall()

    # ================= RENDER =================
    return render_template(
        'dashboard.html',
        recommended=recommended,
        our_restaurants=our_restaurants,
        name=session['user_name'],
        fav_category=fav_category
    )

# ================= RECOMMEND =================
@app.route('/recommend')
def recommend():
    items = get_recommendations()
    return render_template('recommend.html', items=items)

# ================= RESTAURANTS =================
@app.route('/restaurants')
def restaurants():
    cursor.execute("SELECT * FROM restaurants")
    data = cursor.fetchall()
    return render_template('restaurants.html', restaurants=data)

# ================= MENU =================
@app.route('/menu/<int:restaurant_id>')
def menu(restaurant_id):
    cursor.execute("SELECT * FROM menu WHERE restaurant_id=%s", (restaurant_id,))
    items = cursor.fetchall()
    return render_template('menu.html', items=items)

# ================= SINGLE ITEM ORDER =================
@app.route('/order/<int:item_id>')
def order(item_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    cursor.execute("INSERT INTO orders (user_id) VALUES (%s)", (user_id,))
    db.commit()
    order_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO order_items (order_id, item_id, quantity) VALUES (%s, %s, %s)",
        (order_id, item_id, 1)
    )
    db.commit()

    return "Order placed successfully 🎉"

# ================= CART ORDER =================
@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user_id' not in session:
        return "Not logged in", 401

    data = request.get_json()
    cart = data.get('cart')

    user_id = session['user_id']

    cursor.execute("INSERT INTO orders (user_id) VALUES (%s)", (user_id,))
    db.commit()
    order_id = cursor.lastrowid

    for item in cart:
        cursor.execute(
            "INSERT INTO order_items (order_id, item_id, quantity) VALUES (%s, %s, %s)",
            (order_id, item['id'], 1)
        )

    db.commit()
    return {"message": "Order placed successfully"}

# ================= VIEW ORDERS =================
@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    cursor.execute("""
        SELECT o.order_id, m.item_name, m.price, oi.quantity
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN menu m ON oi.item_id = m.item_id
        WHERE o.user_id = %s
    """, (user_id,))

    data = cursor.fetchall()
    return render_template('orders.html', orders=data)

# ================= ANALYTICS =================
@app.route('/analytics')
def analytics():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    # 👤 Total users (optional - agar dikhana hai)
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # 📦 Total orders (sirf logged-in user ke)
    cursor.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id = %s",
        (user_id,)
    )
    total_orders = cursor.fetchone()[0]

    # 🔥 Top 3 favourite items (user ke)
    cursor.execute("""
        SELECT m.item_name, COUNT(*) as count
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        JOIN menu m ON oi.item_id = m.item_id
        WHERE o.user_id = %s
        GROUP BY oi.item_id
        ORDER BY count DESC
        LIMIT 3
    """, (user_id,))
    
    popular_items = cursor.fetchall()

    return render_template(
        'analytics.html',
        users=total_users,      # optional (remove if not needed)
        orders=total_orders,
        popular_items=popular_items
    )

# ================= RUN =================
if __name__ == '__main__':
    app.run(debug=True)