import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

def train_model(cursor):
    cursor.execute("""
        SELECT o.user_id, i.category, r.restaurant_id
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN menu i ON oi.item_id = i.item_id
        JOIN restaurants r ON i.restaurant_id = r.restaurant_id
    """)
    data = cursor.fetchall()

    df = pd.DataFrame(data, columns=['user_id', 'category', 'restaurant_id'])

    # user-category matrix
    user_pref = df.groupby(['user_id', 'category']).size().unstack(fill_value=0)

    # normalize
    user_pref_norm = normalize(user_pref)

    # cosine similarity between users
    similarity = cosine_similarity(user_pref_norm)
    sim_df = pd.DataFrame(similarity, index=user_pref.index, columns=user_pref.index)

    return df, sim_df

def recommend(user_id, df, sim_df):
    if user_id not in sim_df.index:
        return []

    # top 3 similar users
    similar_users = sim_df[user_id].sort_values(ascending=False)[1:4].index

    # restaurants they ordered
    recs = df[df['user_id'].isin(similar_users)]
    top_restaurants = (
        recs.groupby('restaurant_id')
        .size()
        .sort_values(ascending=False)
        .head(3)
        .index.tolist()
    )
    return top_restaurants