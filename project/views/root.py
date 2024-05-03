import os
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

import icalendar
import pytz
from bs4 import BeautifulSoup
from flask import Response, request

from project import app


@app.route("/")
def index():
    city = request.args.get("city", "goslar")
    url = f"https://www.cineplex.de/programm/{city}/"

    req = Request(url)
    response = urlopen(req)
    doc = BeautifulSoup(response.read(), "html.parser")

    days = dict()

    movies = doc.find_all("div", class_="movie-schedule")
    for movie in movies:
        film_info_link = movie.find("a", class_="filmInfoLink")
        location_header = movie.find("h4", class_="schedule__grid-site")

        if not film_info_link or not location_header:
            continue

        film_name = film_info_link.text
        film_url = "https://www.cineplex.de" + film_info_link["href"]

        times = movie.find_all("time", class_="schedule__time")
        for time in times:
            date_str = time["datetime"]
            time_str = time.text

            movies_at_day = days.setdefault(date_str, dict())

            if film_url in movies_at_day:
                movie_at_day = movies_at_day[film_url]
            else:
                movie_at_day = {
                    "name": film_name,
                    "url": film_url,
                    "times": set(),
                }
                movies_at_day[film_url] = movie_at_day
            movie_at_day["times"].add(time_str)

    berlin_tz = pytz.timezone("Europe/Berlin")
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

        for movie in sorted_movies_at_day:
            desc_items.append(movie["name"])
            desc_items.append(" ".join(sorted(movie["times"])))
            desc_items.append(movie["url"])
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
