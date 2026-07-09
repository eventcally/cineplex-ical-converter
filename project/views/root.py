import json
import os
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

import icalendar
import pytz
from bs4 import BeautifulSoup
from flask import Response, request

from project import app


def fetch(url):
    req = Request(url)
    return urlopen(req).read()


def get_cinema_id(city):
    kino_de_url = f"https://www.kino.de/kinoprogramm/stadt/{city}/kino/cineplex-{city}/"
    doc = BeautifulSoup(fetch(kino_de_url), "html.parser")
    widget = doc.find(attrs={"data-role": "alice-cinema-widget"})
    return widget["data-cinema-id"]


@app.route("/")
def index():
    city = request.args.get("city", "goslar")
    url = f"https://www.cineplex.de/{city}/programm"

    cinema_id = get_cinema_id(city)
    schedule = json.loads(
        fetch(f"https://kntkapi.apps.stroeermb.de/api/cinema/{cinema_id}/")
    )

    movie_titles = {movie["id"]: movie["title"] for movie in schedule["movies"]}

    berlin_tz = pytz.timezone("Europe/Berlin")

    days = dict()

    for showtime in schedule["showtimes"]:
        movie_id = showtime["movie"]["id"]
        film_name = movie_titles.get(movie_id)

        if not film_name:
            continue

        showtime_local = (
            datetime.strptime(showtime["showtime"], "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=pytz.utc)
            .astimezone(berlin_tz)
        )
        date_str = showtime_local.strftime("%Y-%m-%d")
        time_str = showtime_local.strftime("%H:%M")

        movies_at_day = days.setdefault(date_str, dict())

        if movie_id in movies_at_day:
            movie_at_day = movies_at_day[movie_id]
        else:
            movie_at_day = {
                "name": film_name,
                "times": set(),
            }
            movies_at_day[movie_id] = movie_at_day
        movie_at_day["times"].add(time_str)

    cal = icalendar.Calendar()
    cal.add("prodid", "-//eventcally//github.com/eventcally/cineplex-ical-converter//")
    cal.add("version", "2.0")
    cal.add("x-wr-timezone", berlin_tz.zone)
    cal.add("x-wr-calname", f"Cineplex {city}")

    tzc = icalendar.Timezone()
    tzc.add("tzid", berlin_tz.zone)
    tzc.add("x-lic-location", berlin_tz.zone)

    tzs = icalendar.TimezoneStandard()
    tzs.add("tzname", "CET")
    tzs.add("dtstart", datetime(1970, 10, 25, 3, 0, 0))
    tzs.add("rrule", {"freq": "yearly", "bymonth": 10, "byday": "-1su"})
    tzs.add("TZOFFSETFROM", timedelta(hours=2))
    tzs.add("TZOFFSETTO", timedelta(hours=1))

    tzd = icalendar.TimezoneDaylight()
    tzd.add("tzname", "CEST")
    tzd.add("dtstart", datetime(1970, 3, 29, 2, 0, 0))
    tzd.add("rrule", {"freq": "yearly", "bymonth": 3, "byday": "-1su"})
    tzd.add("TZOFFSETFROM", timedelta(hours=1))
    tzd.add("TZOFFSETTO", timedelta(hours=2))

    tzc.add_component(tzs)
    tzc.add_component(tzd)
    cal.add_component(tzc)

    for date_str, movies_at_day in days.items():
        date_object = berlin_tz.localize(datetime.strptime(date_str, "%Y-%m-%d")).date()
        desc_items = list()
        sorted_movies_at_day = sorted(movies_at_day.values(), key=lambda d: d["name"])

        if len(sorted_movies_at_day) > 1:
            movie_names = [m["name"] for m in sorted_movies_at_day]
            desc_items.append(" | ".join(movie_names))
            desc_items.append("")

        for movie in sorted_movies_at_day:
            desc_items.append(movie["name"])
            desc_items.append(" ".join(sorted(movie["times"])))
            desc_items.append("")

        ical_event = icalendar.Event()
        ical_event.add("dtstart", icalendar.vDate(date_object))
        ical_event.add("uid", f"{url}#{date_str}")
        ical_event.add("summary", "Kinoprogramm")
        ical_event.add("description", os.linesep.join(desc_items))
        ical_event.add("url", url)
        cal.add_component(ical_event)

    return Response(
        cal.to_ical(),
        mimetype="text/calendar",
        headers={"Content-disposition": "attachment; filename=cineplex.ics"},
    )
