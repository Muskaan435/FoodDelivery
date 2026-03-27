from flask import Flask, render_template, request, redirect, session
import mysql.connector
from MachineLearning.recommend import get_recommendations
from MachineLearning.recommender import train_model, recommend as ml_recommend

app = Flask(__name__)
app.secret_key = "secret123" 

# DB Connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",  
    database="food_delivery"
)

cursor = db.cursor(buffered=True)

@app.route('/')
def home():
    return render_template('index.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        query = "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)"
        values = (name, email, password)

        cursor.execute(query, values)
        db.commit()

        return redirect('/login')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        query = "SELECT * FROM users WHERE email=%s AND password=%s"
        cursor.execute(query, (email, password))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]   # 🔥 store id
            session['user_name'] = user[1] # 🔥 store name
            return redirect('/dashboard')
        else:
            return "Invalid credentials"

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    # 1️⃣ User ka favourite category nikal
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
    fav_cat = cursor.fetchone()
    fav_category = fav_cat[0] if fav_cat else None

    # ML-based recommendation
    df, sim_df = train_model(cursor)
    recommended_ids = ml_recommend(user_id, df, sim_df)

    if recommended_ids:
        format_strings = ','.join(['%s'] * len(recommended_ids))
        cursor.execute(f"""
            SELECT restaurant_id, name, location
            FROM restaurants
            WHERE restaurant_id IN ({format_strings})
        """, tuple(recommended_ids))
        recommended = cursor.fetchall()
    else:
        recommended = []

    # All restaurants (optional)
    cursor.execute("SELECT restaurant_id, name, location FROM restaurants ORDER BY name ASC LIMIT 4")
    our_restaurants = cursor.fetchall()

    return render_template(
        'dashboard.html',
        recommended=recommended,
        our_restaurants=our_restaurants,
        name=session['user_name'],
        fav_category=fav_category
    )

@app.route('/recommend')
def recommend():
    items = get_recommendations()
    return render_template('recommend.html', items=items)


@app.route('/restaurants')
def restaurants():
    cursor.execute("SELECT * FROM restaurants")
    data = cursor.fetchall()
    return render_template('restaurants.html', restaurants=data)

@app.route('/menu/<int:restaurant_id>')
def menu(restaurant_id):
    cursor.execute("SELECT * FROM menu WHERE restaurant_id=%s", (restaurant_id,))
    items = cursor.fetchall()
    return render_template('menu.html', items=items)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

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

@app.route('/analytics')
def analytics():
    if 'user_id' not in session:
        return redirect('/login')

    # total users
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # total orders
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]

    # most popular item
    cursor.execute("""
        SELECT m.item_name, COUNT(*) as count
        FROM order_items oi
        JOIN menu m ON oi.item_id = m.item_id
        GROUP BY oi.item_id
        ORDER BY count DESC
        LIMIT 3
    """)
    popular_items = cursor.fetchall()

    return render_template(
        'analytics.html',
        users=total_users,
        orders=total_orders,
        popular_items=popular_items
    )

if __name__ == '__main__':
    app.run(debug=True)
