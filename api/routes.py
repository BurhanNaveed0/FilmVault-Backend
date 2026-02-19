import os

from flask import Flask, jsonify, request
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


@app.route("/api/films/search")
def search_films():
    """Search films by title, actor name, or genre."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        search_term = f"%{q}%"
        query = """
        SELECT DISTINCT
            f.film_id,
            f.title,
            f.description,
            f.release_year,
            f.rating,
            GROUP_CONCAT(DISTINCT c.name ORDER BY c.name SEPARATOR ', ') AS categories,
            GROUP_CONCAT(DISTINCT CONCAT(a.first_name, ' ', a.last_name) ORDER BY a.last_name SEPARATOR ', ') AS actors
        FROM film f
        LEFT JOIN film_actor fa ON f.film_id = fa.film_id
        LEFT JOIN actor a ON fa.actor_id = a.actor_id
        LEFT JOIN film_category fc ON f.film_id = fc.film_id
        LEFT JOIN category c ON fc.category_id = c.category_id
        WHERE f.title LIKE %s
           OR CONCAT(a.first_name, ' ', a.last_name) LIKE %s
           OR c.name LIKE %s
        GROUP BY f.film_id, f.title, f.description, f.release_year, f.rating
        ORDER BY f.title
        """
        cursor.execute(query, (search_term, search_term, search_term))
        films = cursor.fetchall()

        cursor.close()
        conn.close()

        for row in films:
            cats = row.get("categories") or ""
            row["categories"] = [c.strip() for c in cats.split(",") if c.strip()]
            acts = row.get("actors") or ""
            row["actors"] = [a.strip() for a in acts.split(",") if a.strip()]

        return jsonify(films)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/films/<int:film_id>")
def film_detail(film_id: int):
    """Single film details: description, year, length, rating, genres, actors."""
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

        if not row:
            cursor.close()
            conn.close()
            return jsonify({"error": "Film not found"}), 404

        cats = row.get("categories") or ""
        row["categories"] = [c for c in (s.strip() for s in cats.split(",")) if c]

        actors_query = """
        SELECT a.actor_id, a.first_name, a.last_name
        FROM actor a
        JOIN film_actor fa ON a.actor_id = fa.actor_id
        WHERE fa.film_id = %s
        ORDER BY a.last_name, a.first_name
        """
        cursor.execute(actors_query, (film_id,))
        row["actors"] = cursor.fetchall()

        cursor.close()
        conn.close()
        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/films/<int:film_id>/availability")
def film_availability(film_id: int):
    """Return how many copies are total, rented, and available for a film."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT film_id, title FROM film WHERE film_id = %s", (film_id,))
        film = cursor.fetchone()
        if not film:
            cursor.close()
            conn.close()
            return jsonify({"error": "Film not found"}), 404

        query = """
        SELECT
            COUNT(i.inventory_id) AS total_copies,
            SUM(CASE WHEN r.rental_id IS NOT NULL THEN 1 ELSE 0 END) AS rented,
            SUM(CASE WHEN r.rental_id IS NULL THEN 1 ELSE 0 END) AS available
        FROM inventory i
        LEFT JOIN (
            SELECT inventory_id, rental_id
            FROM rental
            WHERE return_date IS NULL
        ) r ON i.inventory_id = r.inventory_id
        WHERE i.film_id = %s
        """
        cursor.execute(query, (film_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        result = {
            "film_id": film_id,
            "title": film["title"],
            "total_copies": row["total_copies"] or 0,
            "rented": row["rented"] or 0,
            "available": row["available"] or 0,
        }
        return jsonify(result)
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


@app.route("/api/rentals", methods=["POST"])
def create_rental():
    """Rent a film to a customer. Requires film_id, customer_id, and staff_id."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    film_id = data.get("film_id")
    customer_id = data.get("customer_id")
    staff_id = data.get("staff_id")

    if film_id is None or customer_id is None or staff_id is None:
        return jsonify({
            "error": "Missing required fields: film_id, customer_id, and staff_id are required"
        }), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT film_id FROM film WHERE film_id = %s", (film_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Film not found"}), 404

        cursor.execute("SELECT customer_id FROM customer WHERE customer_id = %s", (customer_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Customer not found"}), 404

        cursor.execute("SELECT staff_id FROM staff WHERE staff_id = %s", (staff_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Staff not found"}), 404

        availability_query = """
        SELECT i.inventory_id
        FROM inventory i
        LEFT JOIN rental r ON i.inventory_id = r.inventory_id AND r.return_date IS NULL
        WHERE i.film_id = %s AND r.rental_id IS NULL
        LIMIT 1
        """
        cursor.execute(availability_query, (film_id,))
        inv_row = cursor.fetchone()

        if not inv_row:
            cursor.close()
            conn.close()
            return jsonify({"error": "No inventory available for this film"}), 409

        inventory_id = inv_row["inventory_id"]

        insert_query = """
        INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id, return_date)
        VALUES (NOW(), %s, %s, %s, NULL)
        """
        cursor.execute(insert_query, (inventory_id, customer_id, staff_id))
        conn.commit()
        rental_id = cursor.lastrowid

        cursor.execute(
            "SELECT rental_id, rental_date, inventory_id, customer_id, return_date FROM rental WHERE rental_id = %s",
            (rental_id,),
        )
        rental = cursor.fetchone()
        rental["film_id"] = film_id

        cursor.close()
        conn.close()

        return jsonify(rental), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)