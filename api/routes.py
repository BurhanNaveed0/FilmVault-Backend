import os

from flask import Flask, jsonify
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
CORS(app)  

db_config = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "database": os.getenv("DB_NAME", "sakila"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
}

def get_db_connection():
    return mysql.connector.connect(**db_config, connection_timeout=5)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

@app.route("/api/test")
def test():
    return {"message": "Backend is working!", "status": "success"}

@app.route("/api/films")
def top_films():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT f.film_id, f.title, COUNT(r.rental_id) AS rental_count
        FROM film f
        JOIN inventory i ON f.film_id = i.film_id
        JOIN rental r ON i.inventory_id = r.inventory_id
        GROUP BY f.film_id, f.title
        ORDER BY rental_count DESC
        LIMIT 5;

        """

        cursor.execute(query)
        films = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(films)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/films/<int:film_id>")
def film_detail(film_id: int):
    """Single film details: description, year, length, rating, genres."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT
            f.film_id,
            f.title,
            f.description,
            f.release_year,
            f.length,
            f.rating,
            GROUP_CONCAT(DISTINCT c.name ORDER BY c.name SEPARATOR ', ') AS categories
        FROM film f
        LEFT JOIN film_category fc ON f.film_id = fc.film_id
        LEFT JOIN category c ON fc.category_id = c.category_id
        WHERE f.film_id = %s
        GROUP BY
            f.film_id,
            f.title,
            f.description,
            f.release_year,
            f.length,
            f.rating
        LIMIT 1;
        """

        cursor.execute(query, (film_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if not row:
            return jsonify({"error": "Film not found"}), 404

        cats = row.get("categories") or ""
        row["categories"] = [c for c in (s.strip() for s in cats.split(",")) if c]
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/films/details")
def film_details():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT f.*
        FROM film f
        JOIN (
            SELECT i.film_id, COUNT(r.rental_id) AS rental_count
            FROM inventory i
            JOIN rental r ON i.inventory_id = r.inventory_id
            GROUP BY i.film_id
            ORDER BY rental_count DESC
            LIMIT 5
        ) t ON t.film_id = f.film_id
        ORDER BY t.rental_count DESC;
        """

        cursor.execute(query)
        films = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(films)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/actors")
def top_actors():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT a.actor_id, a.first_name, a.last_name,
            COUNT(r.rental_id) AS rental_count
        FROM actor a
        JOIN film_actor fa ON a.actor_id = fa.actor_id
        JOIN inventory i ON fa.film_id = i.film_id
        JOIN rental r ON i.inventory_id = r.inventory_id
        GROUP BY a.actor_id, a.first_name, a.last_name
        ORDER BY rental_count DESC
        LIMIT 5;

        """

        cursor.execute(query)
        actors = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(actors)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/actors/<int:actor_id>/films")
def actor_films(actor_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT f.film_id, f.title,
            COUNT(r.rental_id) AS rental_count
        FROM film f
        JOIN film_actor fa ON f.film_id = fa.film_id
        JOIN inventory i ON f.film_id = i.film_id
        JOIN rental r ON i.inventory_id = r.inventory_id
        WHERE fa.actor_id = %s
        GROUP BY f.film_id, f.title
        ORDER BY rental_count DESC
        LIMIT 5;

        """

        cursor.execute(query, (actor_id,))
        films = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(films)
    except Exception as e:
        return jsonify({"error": str(e)}), 500




if __name__ == "__main__":
    app.run(debug=True, port=5001)