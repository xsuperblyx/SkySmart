import re
import airportsdata

from datetime import datetime
from dateparser.search import search_dates

# load airoports from lib
airports = airportsdata.load("IATA")

AIRPORTS_BY_CODE = {}
AIRPORTS_BY_CITY = {}


for code, airport in airports.items():

    code = code.upper()

    AIRPORTS_BY_CODE[code] = airport

    city = airport.get("city")

    if city:
        city = city.strip().lower()
        AIRPORTS_BY_CITY.setdefault(city, []).append(airport)

# airoport search
def find_airport(text):

    text = text.strip().lower()

    if not text:
        return None

    code = text.upper()

    if code in AIRPORTS_BY_CODE:
        return AIRPORTS_BY_CODE[code]

    if text in AIRPORTS_BY_CITY:
        return AIRPORTS_BY_CITY[text][0]

    matches = []

    for city, city_airports in AIRPORTS_BY_CITY.items():

        if text in city:
            matches.extend(city_airports)

    if len(matches) == 1:
        return matches[0]

    return None

# Returns city + IATA code for displaying airport information. Example: AYT -> Antalya (AYT)
def airport_to_display(code):

    if not code:
        return code

    code = code.upper().strip()

    airport = AIRPORTS_BY_CODE.get(code)

    if not airport:
        return code

    city = airport.get("city")

    if city:
        return f"{city} ({code})"

    return code

def find_city_airports(text):

    text = text.strip().lower()

    if not text:
        return []

    # Exact city
    if text in AIRPORTS_BY_CITY:
        return AIRPORTS_BY_CITY[text]

    # Partial city
    matches = []

    for city, city_airports in AIRPORTS_BY_CITY.items():

        if text in city:
            matches.extend(city_airports)

    return matches

def city_to_serpapi_id(text):

    city_airports = find_city_airports(text)

    codes = []

    for airport in city_airports:

        code = airport.get("iata")

        if code and code not in codes:
            codes.append(code.upper())

    if not codes:
        return None

    return ",".join(codes)

def find_locations(text):

    found = []

    lowered = text.lower()

    cities = sorted(
        AIRPORTS_BY_CITY.keys(),
        key=len,
        reverse=True
    )

    for city in cities:

        pattern = r"\b" + re.escape(city) + r"\b"

        if re.search(pattern, lowered):

            airports_for_city = AIRPORTS_BY_CITY[city]

            if airports_for_city:

                found.append({
                    "city": airports_for_city[0].get("city"),
                    "airports": airports_for_city
                })

    return found

def location_to_serpapi_id(location):

    airports_for_city = location.get("airports", [])

    codes = []

    for airport in airports_for_city:

        code = airport.get("iata")

        if code and code not in codes:
            codes.append(code.upper())

    if not codes:
        return None

    return ",".join(codes)

def autocomplete_locations(query, limit=10):

    query = query.strip().lower()

    if not query:
        return []

    results = []

    # SEARCH CITIES

    for city, city_airports in AIRPORTS_BY_CITY.items():

        if not city_airports:
            continue

        airport = city_airports[0]

        city_name = airport.get("city", "")
        country = airport.get("country", "")

        if (
            city.startswith(query)
            or country.lower().startswith(query)
        ):

            codes = []

            for airport_data in city_airports:

                code = airport_data.get("iata")

                if code and code not in codes:
                    codes.append(code.upper())

            if not codes:
                continue

            results.append({
                "city": city_name,
                "country": country,
                "code": ",".join(codes)
            })

    # SEARCH IATA CODES

    for code, airport in AIRPORTS_BY_CODE.items():

        if code.lower().startswith(query):

            city = airport.get("city")

            if not city:
                continue

            city_key = city.strip().lower()

            city_airports = AIRPORTS_BY_CITY.get(
                city_key,
                []
            )

            codes = []

            for airport_data in city_airports:

                airport_code = airport_data.get("iata")

                if (
                    airport_code
                    and airport_code not in codes
                ):
                    codes.append(airport_code.upper())

            if not codes:
                continue

            result = {
                "city": city,
                "country": airport.get("country", ""),
                "code": ",".join(codes)
            }

            # Don't add the same city twice
            if not any(
                item["city"].lower() == city.lower()
                for item in results
            ):
                results.append(result)

    # SORT

    results.sort(
        key=lambda x: (
            not x["city"].lower().startswith(query),
            not x["code"].lower().startswith(query)
        )
    )

    return results[:limit]


# ROUTE

def extract_route(text):

    origin = None
    destination = None

    # FROM ... TO ...

    match = re.search(
        r"\bfrom\s+(.+?)\s+to\s+(.+?)(?=\s+(?:on|for|"
        r"tomorrow|today|next|this)\b|$)",
        text,
        re.IGNORECASE
    )

    if match:

        origin_text = match.group(1).strip()
        destination_text = match.group(2).strip()

        origin = city_to_serpapi_id(origin_text)
        destination = city_to_serpapi_id(destination_text)

    # FROM ...

    if not origin:

        match = re.search(
            r"\bfrom\s+(.+?)(?=\s+(?:to|on|for|"
            r"tomorrow|today|next|this)\b|$)",
            text,
            re.IGNORECASE
        )

        if match:

            origin_text = match.group(1).strip()

            origin = city_to_serpapi_id(origin_text)

    # TO ...

    if not destination:

        match = re.search(
            r"\bto\s+(.+?)(?=\s+(?:on|for|"
            r"tomorrow|today|next|this)\b|$)",
            text,
            re.IGNORECASE
        )

        if match:

            destination_text = match.group(1).strip()

            destination = city_to_serpapi_id(destination_text)

    # IATA AFTER FROM

    if not origin:

        match = re.search(
            r"\bfrom\s+([A-Za-z]{3})\b",
            text,
            re.IGNORECASE
        )

        if match:

            origin = city_to_serpapi_id(
                match.group(1)
            )

    # IATA AFTER TO

    if not destination:

        match = re.search(
            r"\bto\s+([A-Za-z]{3})\b",
            text,
            re.IGNORECASE
        )

        if match:

            destination = city_to_serpapi_id(
                match.group(1)
            )

    return origin, destination


# DATES

def extract_dates(text):

    dates = []

     
    # NUMERIC DATES
    #
    # 30.09
    # 30/09
    # 30-09
    # 30 09
    #
    # 30.09.2026
    # 30/09/2026
    # 30-09-2026
     

    numeric_pattern = (
        r"\b"
        r"(\d{1,2})"
        r"[./\-\s]"
        r"(\d{1,2})"
        r"(?:[./\-\s](\d{2,4}))?"
        r"\b"
    )

    numeric_matches = re.findall(
        numeric_pattern,
        text
    )

    today = datetime.now()

    for day, month, year in numeric_matches:

        try:

            day = int(day)
            month = int(month)

            if year:

                year = int(year)

                if year < 100:
                    year += 2000

            else:

                year = today.year

                candidate = datetime(
                    year,
                    month,
                    day
                )

                if candidate.date() < today.date():
                    year += 1

            dt = datetime(
                year,
                month,
                day
            )

            dates.append(dt)

        except ValueError:
            continue

    # NATURAL LANGUAGE DATES

    text_patterns = [

        # 30 September
        # 30 Sep
        # 30 September 2026

        r"\b\d{1,2}(?:st|nd|rd|th)?\s+"
        r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
        r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
        r"sep(?:t(?:ember)?)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)"
        r"(?:\s+\d{2,4})?\b",

        # September 30
        # Sep 30
        # September 30, 2026

        r"\b"
        r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
        r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
        r"sep(?:t(?:ember)?)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)"
        r"\s+\d{1,2}(?:st|nd|rd|th)?"
        r"(?:,?\s+\d{2,4})?\b",

        # today / tomorrow / tonight

        r"\b(?:today|tomorrow|tonight)\b",

        # next / this weekday

        r"\b(?:next|this)\s+"
        r"(?:monday|tuesday|wednesday|thursday|friday|"
        r"saturday|sunday)\b",

        # standalone weekday

        r"\b(?:monday|tuesday|wednesday|thursday|friday|"
        r"saturday|sunday)\b",

        # in 3 days / in 2 weeks / in 1 month

        r"\bin\s+\d+\s+"
        r"(?:day|days|week|weeks|month|months)\b",

        # next week / next month

        r"\bnext\s+(?:week|month)\b"
    ]

    for pattern in text_patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        for date_text in matches:

            results = search_dates(
                date_text,
                languages=["en"],
                settings={
                    "PREFER_DATES_FROM": "future",
                    "DATE_ORDER": "DMY"
                }
            )

            if results:

                for _, dt in results:

                    if dt:
                        dates.append(dt)

    # REMOVE DUPLICATES

    unique_dates = []
    seen = set()

    for dt in dates:

        key = dt.strftime("%Y-%m-%d")

        if key not in seen:

            seen.add(key)
            unique_dates.append(dt)

    unique_dates.sort()

    return unique_dates


# PARSE MESSAGE

def parse_message(text):

    origin, destination = extract_route(text)

    dates = extract_dates(text)

    locations = find_locations(text)

    return {
        "origin": origin,
        "destination": destination,
        "dates": dates,
        "locations": locations
    }


# STATE

def create_empty_state():

    return {
        "origin": None,
        "destination": None,
        "departure_date": None,
        "waiting_for": None,

        "destination_retry": 0,
        "origin_retry": 0,
        "date_retry": 0
    }


# QUESTIONS

# if bot did not understand the messages
DESTINATION_RETRY_MESSAGES = [
    "I didn't quite catch that. ✈️ Which city would you like to fly to?",
    "Hmm, I'm not sure I understood. Where would you like to fly to?",
    "Could you give me the destination city? ✈️",
    "I'm looking for a city you'd like to fly to. Where should we search?",
    "Sorry, I didn't get that. Which destination are you looking for?"
]


ORIGIN_RETRY_MESSAGES = [
    "I didn't quite catch that. ✈️ Which city would you be flying from?",
    "Hmm, I'm not sure I understood. What's your departure city?",
    "Could you tell me where you'll be flying from?",
    "Which city will you be departing from? ✈️",
    "Sorry, I didn't get that. What's your starting city?"
]


DATE_RETRY_MESSAGES = [
    "I didn't quite catch the date. 📅 When would you like to fly?",
    "Hmm, what date would you like to travel?",
    "Could you give me your departure date? 📅",
    "Which day would you like to fly?",
    "Sorry, I didn't get the date. When would you like to leave?"
]
def get_retry_message(messages, state, key):

    index = state.get(key, 0)

    message = messages[index]

    state[key] = (index + 1) % len(messages)

    return message

# INTRO
def intro_reply():

    return (
        "Hi! I'm SkySmart Assistant ✈️\n\n"
        "Where would you like to fly to?"
    )


# MAIN MESSAGE PROCESSOR

def process_message(state, text):

    text = text.strip()
    lowered = text.lower()

     
    # EMPTY
     

    if not text:

        return {
            "state": state,
            "reply": intro_reply(),
            "search": False
        }

     
    # GREETINGS
     

    greetings = [
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "привет",
        "здравствуйте",
        "здравствуй"
    ]

    if lowered in greetings:

        # Greeting starts a fresh conversation.
        state = create_empty_state()

        state["waiting_for"] = "ask_destination"

        return {
            "state": state,
            "reply": intro_reply(),
            "search": False
        }

     
    # PARSE
     

    parsed = parse_message(text)

    origin = parsed["origin"]
    destination = parsed["destination"]
    dates = parsed["dates"]
    locations = parsed["locations"]

    waiting_for = state.get("waiting_for")


     
    # EXPLICIT ORIGIN
     

    if origin:

        if state.get("origin") != origin:

            state["origin"] = origin

    if destination:

        if state.get("destination") != destination:

            state["destination"] = destination
     
    # TWO CITIES
    #
    # Antalya to Berlin
    # Antalya Berlin
     

    if len(locations) >= 2:

        first_city = location_to_serpapi_id(locations[0])
        second_city = location_to_serpapi_id(locations[1])

        if not state.get("origin"):
            state["origin"] = first_city

        if not state.get("destination"):
            state["destination"] = second_city

    elif len(locations) == 1:

        location = locations[0]

        city_id = location_to_serpapi_id(location)

        if waiting_for == "ask_destination" and not state.get("destination"):

            state["destination"] = city_id

        elif waiting_for == "ask_origin" and not state.get("origin"):

            state["origin"] = city_id

        elif not state.get("destination"):

            state["destination"] = city_id

        elif not state.get("origin"):

            state["origin"] = city_id

     
    # DATE
     

    if dates:

        date = dates[0]

        state["departure_date"] = date.strftime("%Y-%m-%d")

     
    # ALL INFORMATION RECEIVED
     

    if (
        state.get("origin")
        and state.get("destination")
        and state.get("departure_date")
    ):

        state["waiting_for"] = None

        return {
            "state": state,
            "reply": "Searching for flights... ✈️",
            "search": True
        }

     
    # ASK FOR NEXT INFORMATION
     

    if not state.get("destination"):

        state["waiting_for"] = "ask_destination"

        # User was expected to provide destination,
        # but nothing was recognized.
        if waiting_for == "ask_destination":

            return {
                "state": state,
                "reply": get_retry_message(
                    DESTINATION_RETRY_MESSAGES,
                    state,
                    "destination_retry"
                ),
                "search": False
            }

        return {
            "state": state,
            "reply": "Where would you like to fly to?",
            "search": False
        }

    if not state.get("origin"):

        state["waiting_for"] = "ask_origin"

        # User was expected to provide origin,
        # but nothing was recognized.
        if waiting_for == "ask_origin":

            return {
                "state": state,
                "reply": get_retry_message(
                    ORIGIN_RETRY_MESSAGES,
                    state,
                    "origin_retry"
                ),
                "search": False
            }

        return {
            "state": state,
            "reply": "Where would you be flying from?",
            "search": False
        }

    if not state.get("departure_date"):

        state["waiting_for"] = "ask_departure_date"

        # User was expected to provide a date,
        # but nothing was recognized.
        if waiting_for == "ask_departure_date":

            return {
                "state": state,
                "reply": get_retry_message(
                    DATE_RETRY_MESSAGES,
                    state,
                    "date_retry"
                ),
                "search": False
            }

        return {
            "state": state,
            "reply": "When would you like to fly?",
            "search": False
        }

     
    # FALLBACK
     

    return {
        "state": state,
        "reply": "Could you tell me where you'd like to fly? ✈️",
        "search": False
    }
