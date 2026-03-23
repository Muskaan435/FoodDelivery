from flask import Flask, render_template, request, redirect
import mysql.connector
from MachineLearning.recommend import get_recommendations

app = Flask(__name__)

# DB Connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",  
    database="food_delivery"
)

cursor = db.cursor()
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
        values = (email, password)

        cursor.execute(query, values)
        user = cursor.fetchone()

        if user:
            return redirect('/dashboard')
        else:
            return "Invalid credentials"

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/recommend')
def recommend():
    items = get_recommendations()
    return render_template('recommend.html', items=items)

if __name__ == '__main__':
    app.run(debug=True)


@app.route('/recommend')
def recommend():
    items = get_recommendations()
    return render_template('recommend.html', items=items)