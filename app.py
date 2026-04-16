from flask import Flask, render_template, request, redirect, session
import mysql.connector
import random

from recipes import get_lazy_recipe
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

# ================= HOME + SEARCH =================

@app.route('/', methods=['GET', 'POST'])
def home():
    query = ""
    results = []

    cursor = db.cursor(dictionary=True)

    # 🔍 SEARCH
    if request.method == 'POST':
        query = request.form.get('search')

        if query:
            search_cursor = db.cursor(dictionary=True)

            search_term = "%" + query + "%"

            search_cursor.execute("""
                SELECT 
                    r.name AS restaurant_name,
                    r.location,
                    m.item_name,
                    m.item_id,
                    r.restaurant_id
                FROM restaurants r
                JOIN menu m ON r.restaurant_id = m.restaurant_id
                WHERE m.item_name LIKE %s
            """, (search_term,))

            all_results = search_cursor.fetchall()

            final_results = []
            seen = set()

            for item in all_results:
                if item['restaurant_id'] not in seen:
                    final_results.append(item)
                    seen.add(item['restaurant_id'])
                if len(final_results) == 3:
                    break

            if len(final_results) < 3:
                for item in all_results:
                    if item not in final_results:
                        final_results.append(item)
                    if len(final_results) == 3:
                        break

            results = final_results

    # 🔥 MOST ORDERED
    cursor.execute("""
        SELECT 
            m.item_name,
            m.item_id,
            m.restaurant_id,
            SUM(oi.quantity) as total_orders
        FROM order_items oi
        JOIN menu m ON oi.item_id = m.item_id
        GROUP BY m.item_id, m.item_name, m.restaurant_id
        ORDER BY total_orders DESC
        LIMIT 3
    """)
    most_ordered = cursor.fetchall()

    # 🏆 FAMOUS RESTAURANTS
    cursor.execute("""
        SELECT 
            r.name,
            r.restaurant_id,
            SUM(oi.quantity) as total_orders
        FROM order_items oi
        JOIN menu m ON oi.item_id = m.item_id
        JOIN restaurants r ON m.restaurant_id = r.restaurant_id
        GROUP BY r.restaurant_id, r.name
        ORDER BY total_orders DESC
        LIMIT 3
    """)
    famous_restaurants = cursor.fetchall()

    return render_template(
        'index.html',
        results=results,
        query=query,
        most_ordered=most_ordered,
        famous_restaurants=famous_restaurants
    )
# ================= REGISTER =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

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
        email = request.form.get('email')
        password = request.form.get('password')

        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['user_name'] = user[1]

            session['clear_cart'] = True

            return redirect('/dashboard')
        else:
            return "Invalid credentials ❌"

    return render_template('login.html')

# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ================= DASHBOARD =================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    # Favourite category
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

    # Personalized recommendation
    cursor.execute("""
    SELECT r.restaurant_id, r.name, r.location, SUM(oi.quantity) as freq
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

    # New user fallback
    if not recommended:
        cursor.execute("""
            SELECT restaurant_id, name, location
            FROM restaurants
            ORDER BY RAND()
            LIMIT 4
        """)
        recommended = cursor.fetchall()

    # Our restaurants
    cursor.execute("""
        SELECT restaurant_id, name, location 
        FROM restaurants 
        ORDER BY name ASC 
        LIMIT 4
    """)
    our_restaurants = cursor.fetchall()

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
    cursor.execute(
        "SELECT * FROM menu WHERE restaurant_id=%s",
        (restaurant_id,)
    )
    items = cursor.fetchall()
    return render_template('menu.html', items=items)


# ================= SINGLE ORDER =================
@app.route('/order/<int:item_id>', methods=['POST'])
def order(item_id):
    try:
        # LOGIN CHECK
        if 'user_id' not in session:
            return {"message": "Not logged in"}, 401

        user_id = session['user_id']

        # CREATE ORDER
        cursor.execute(
            "INSERT INTO orders (user_id) VALUES (%s)",
            (user_id,)
        )
        db.commit()
        order_id = cursor.lastrowid

        # ADD ITEM
        cursor.execute(
            "INSERT INTO order_items (order_id, item_id, quantity) VALUES (%s, %s, %s)",
            (order_id, item_id, 1)
        )
        db.commit()

        return {"message": "Order placed successfully"}

    except Exception as e:
        print("Order Error:", e)
        return {"message": "Something went wrong"}, 500


# ================= CART ORDER =================
@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        # ✅ LOGIN CHECK
        if 'user_id' not in session:
            return {"message": "Not logged in"}, 401

        data = request.get_json()
        cart = data.get('cart')

        # ✅ EMPTY CART CHECK
        if not cart or len(cart) == 0:
            return {"message": "Cart is empty"}, 400

        user_id = session['user_id']

        # ✅ CREATE ORDER
        cursor.execute(
            "INSERT INTO orders (user_id) VALUES (%s)",
            (user_id,)
        )
        db.commit()

        order_id = cursor.lastrowid

        # ✅ GROUP ITEMS (quantity count)
        grouped = {}
        for item in cart:
            if item['id'] not in grouped:
                grouped[item['id']] = 1
            else:
                grouped[item['id']] += 1

        # ✅ INSERT ITEMS WITH QUANTITY
        for item_id, qty in grouped.items():
            cursor.execute(
                "INSERT INTO order_items (order_id, item_id, quantity) VALUES (%s, %s, %s)",
                (order_id, item_id, qty)
            )

        db.commit()

        return {
            "message": "Order placed successfully",
            "order_id": order_id
        }

    except Exception as e:
        print("Cart Order Error:", e)
        return {"message": "Something went wrong"}, 500
# ================= RECIPE =================
@app.route('/recipe/<int:order_id>')
def recipe(order_id):

    import json, os

    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "recipes.json")

    with open(file_path, "r", encoding="utf-8") as file:
        recipes = json.load(file)

    return render_template('recipe.html', recipes=recipes)
# ================= VIEW ORDERS =================
@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    cursor.execute("""
        SELECT 
            o.order_id AS order_id,
            GROUP_CONCAT(m.item_name) AS items,
            GROUP_CONCAT(oi.quantity) AS qtys,
            SUM(m.price * oi.quantity) AS total
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN menu m ON oi.item_id = m.item_id
        WHERE o.user_id = %s
        GROUP BY o.order_id
        ORDER BY o.order_id DESC
    """, (user_id,))

    data = cursor.fetchall()
    return render_template('orders.html', orders=data)

# ================= ANALYTICS =================
@app.route('/analytics')
def analytics():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id = %s",
        (user_id,)
    )
    total_orders = cursor.fetchone()[0]

    cursor.execute("""
    SELECT m.item_name, SUM(oi.quantity) as count
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
        users=total_users,
        orders=total_orders,
        popular_items=popular_items
    )
@app.route('/cart')
def cart():
    return render_template('cart.html')

# ================= RUN =================
if __name__ == '__main__':
    app.run(debug=True)