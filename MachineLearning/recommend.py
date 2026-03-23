import mysql.connector
import pandas as pd

def get_recommendations():
    # DB connect
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",   # XAMPP me mostly empty
        database="food_delivery"
    )

    query = """
    SELECT oi.item_id, m.item_name
    FROM order_items oi
    JOIN menu m ON oi.item_id = m.item_id
    """

    df = pd.read_sql(query, db)

    if df.empty:
        return ["No data available"]

    # most ordered items
    popular_items = df['item_name'].value_counts().head(3)

    return list(popular_items.index)