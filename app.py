from flask import Flask, render_template, request, redirect, session
import mysql.connector

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DB CONNECTION ----------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="food_delivery"
)

cursor = db.cursor(dictionary=True)  # IMPORTANT

# ---------------- HOME + SEARCH ----------------
@app.route('/', methods=['GET', 'POST'])
def home():
    results = []
    query = ""

    if request.method == 'POST':
        query = request.form.get('search')

        print("SEARCH:", query)

        cursor.execute("""
            SELECT r.name AS restaurant_name, m.item_name, m.price
            FROM restaurants r
            JOIN menu m ON r.restaurant_id = m.restaurant_id
            WHERE 
                LOWER(m.item_name) LIKE %s
                OR LOWER(r.name) LIKE %s
        """, (f"%{query.lower()}%", f"%{query.lower()}%"))

        results = cursor.fetchall()

        print("RESULTS:", results)

    return render_template('index.html', results=results, query=query)


# ---------------- REGISTER ----------------
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


# ---------------- LOGIN ----------------
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
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            return redirect('/dashboard')
        else:
            return "Invalid credentials ❌"

    return render_template('login.html')


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    cursor.execute("""
        SELECT restaurant_id, name, location
        FROM restaurants
        LIMIT 4
    """)
    restaurants = cursor.fetchall()

    return render_template(
        'dashboard.html',
        restaurants=restaurants,
        name=session['user_name']
    )


# ---------------- RESTAURANTS ----------------
@app.route('/restaurants')
def restaurants():
    cursor.execute("SELECT * FROM restaurants")
    data = cursor.fetchall()
    return render_template('restaurants.html', restaurants=data)


# ---------------- MENU ----------------
@app.route('/menu/<int:restaurant_id>')
def menu(restaurant_id):
    cursor.execute(
        "SELECT * FROM menu WHERE restaurant_id=%s",
        (restaurant_id,)
    )
    items = cursor.fetchall()
    return render_template('menu.html', items=items)


# ---------------- ORDER ----------------
@app.route('/order/<int:item_id>')
def order(item_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    cursor.execute("INSERT INTO orders (user_id) VALUES (%s)", (user_id,))
    db.commit()

    order_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO order_items (order_id, item_id, quantity)
        VALUES (%s, %s, %s)
    """, (order_id, item_id, 1))
    db.commit()

    return "Order placed successfully 🎉"


# ---------------- ORDERS ----------------
@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect('/login')

    cursor.execute("""
        SELECT o.order_id, m.item_name, m.price, oi.quantity
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN menu m ON oi.item_id = m.item_id
        WHERE o.user_id = %s
    """, (session['user_id'],))

    data = cursor.fetchall()

    return render_template('orders.html', orders=data)


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)