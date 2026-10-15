from flask import Flask, render_template, request, jsonify, redirect, session
import requests
import secrets

from flight_nlp import (
    create_empty_state,
    process_message,
    autocomplete_locations,
    airport_to_display
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)


API_KEY = "8251f82306c68b94a697e64a927c6ccd60bc1c9800fecebaf9f65f932ef610a9"

@app.route("/")
def home():

    return render_template("website.html")

@app.route("/autocomplete")
def autocomplete():

    query = request.args.get("q", "")

    results = autocomplete_locations(query)

    return jsonify(results)

@app.route("/search", methods=["POST"])
def search():

    departure = request.form["departure"]
    arrival = request.form["arrival"]
    date = request.form["date"]

    params = {
        "engine": "google_flights",
        "departure_id": departure,
        "arrival_id": arrival,
        "type": "2",
        "outbound_date": date,
        "currency": "USD",
        "hl": "en",
        "gl": "tr",
        "api_key": API_KEY
    }

    response = requests.get(
        "https://serpapi.com/search.json",
        params=params
    )

    data = response.json()

    flights = (
        data.get("best_flights", [])
        +
        data.get("other_flights", [])
    )

    for flight in flights:

        for segment in flight.get("flights", []):

            departure_id = segment.get(
                "departure_airport", {}
            ).get("id")

            arrival_id = segment.get(
                "arrival_airport", {}
            ).get("id")

            if departure_id:
                segment["departure_airport"]["city"] = (
                    airport_to_display(departure_id)
                )

            if arrival_id:
                segment["arrival_airport"]["city"] = (
                    airport_to_display(arrival_id)
                )

    return render_template(
        "website.html",
        flights=flights,
        departure=departure,
        arrival=arrival,
        date=date
    )

@app.route("/chat", methods=["POST"])
def chat():

    text = request.form.get("query", "").strip()

    if not text:
        return jsonify({
            "reply": "Please tell me where you'd like to fly.",
            "search": False
        })

    if session.get("chat_completed"):

        session.pop("flight_state", None)
        session["chat_completed"] = False

    state = session.get("flight_state")

    if not state:
        state = create_empty_state()

    print("\n========== CHAT ==========")
    print("USER:", text)
    print("STATE BEFORE:", state)

    result = process_message(state, text)

    print("STATE AFTER:", result["state"])
    print("REPLY:", result["reply"])
    print("SEARCH:", result["search"])
    print("==========================\n")

    session["flight_state"] = result["state"]

    if result["search"]:
        session["chat_completed"] = True

    return jsonify({
        "reply": result["reply"],
        "search": result["search"],
        "state": result["state"]
    })

@app.route("/chat/reset", methods=["POST"])
def chat_reset():

    session.pop("flight_state", None)

    return jsonify({
        "success": True
    })


@app.route("/chat/search", methods=["POST"])
def chat_search():

    data = request.get_json()

    departure = data.get("departure")
    arrival = data.get("arrival")
    date = data.get("date")

    if not departure or not arrival or not date:
        return jsonify({
            "error": "Missing flight information"
        }), 400

    params = {
        "engine": "google_flights",
        "departure_id": departure,
        "arrival_id": arrival,
        "type": "2",
        "outbound_date": date,
        "currency": "USD",
        "hl": "en",
        "gl": "tr",
        "api_key": API_KEY
    }

    response = requests.get(
        "https://serpapi.com/search.json",
        params=params
    )

    data = response.json()

    flights = (
        data.get("best_flights", [])
        +
        data.get("other_flights", [])
    )
    for flight in flights:

        for segment in flight.get("flights", []):

            departure_id = segment.get("departure_airport", {}).get("id")
            arrival_id = segment.get("arrival_airport", {}).get("id")

            if departure_id:
                segment["departure_airport"]["city"] = airport_to_display(
                    departure_id
                )

            if arrival_id:
                segment["arrival_airport"]["city"] = airport_to_display(
                    arrival_id
                )

    for flight in flights:

        flight["booking_token"] = flight.get(
            "booking_token"
        )

    return jsonify({
        "flights": flights,
        "departure": departure,
        "arrival": arrival,
        "date": date
    })

@app.route("/booking")
def booking():


    token = request.args.get("token")

    departure = request.args.get("departure")

    arrival = request.args.get("arrival")

    date = request.args.get("date")



    if not token:

        return "Booking token missing", 400

    params = {


        "engine": "google_flights",

        "booking_token": token,

        "departure_id": departure,

        "arrival_id": arrival,

        "type": "2",

        "outbound_date": date,

        "currency": "USD",

        "hl": "en",

        "gl": "tr",

        "api_key": API_KEY

    }


    response = requests.get(

        "https://serpapi.com/search.json",

        params=params

    )


    data = response.json()



    print("\nBOOKING RESPONSE:")

    print(data.keys())

    print("======================================")

    google_url = (

        data

        .get("search_metadata", {})

        .get("google_flights_url")

    )

    if not google_url:

        return "Google Flights URL not found", 404





    print("REDIRECT TO:")

    print(google_url)

    return redirect(google_url)

if __name__ == "__main__":

    app.run(

        debug=True

    )