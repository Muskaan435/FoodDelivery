import json
import random
import os

def get_lazy_recipe():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_dir, "recipes.json")

        with open(file_path, "r", encoding="utf-8") as file:
            recipes = json.load(file)

        return random.choice(recipes)

    except Exception as e:
        print("Recipe Error:", e)

        return {
            "title": "🍞 Bread & Butter",
            "time": "1 min",
            "ingredients": ["Bread", "Butter"],
            "steps": ["Apply butter", "Eat 😄"]
        }