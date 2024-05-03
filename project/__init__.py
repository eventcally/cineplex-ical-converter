import logging
import os

from flask import Flask

# Create app
app = Flask(__name__)

# Proxy handling
if os.getenv("PREFERRED_URL_SCHEME"):  # pragma: no cover
    app.config["PREFERRED_URL_SCHEME"] = os.getenv("PREFERRED_URL_SCHEME")

    if app.config["PREFERRED_URL_SCHEME"] == "https":
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        app.config["REMEMBER_COOKIE_SECURE"] = True
        app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"

from project.reverse_proxied import ReverseProxied

app.wsgi_app = ReverseProxied(app.wsgi_app)


# Gunicorn logging
if __name__ != "__main__":
    gunicorn_logger = logging.getLogger("gunicorn.error")
    if gunicorn_logger.hasHandlers():
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)

# One line logging
from project.one_line_formatter import init_logger_with_one_line_formatter

init_logger_with_one_line_formatter(logging.getLogger())
init_logger_with_one_line_formatter(app.logger)


# Routes
from project.views import root

if __name__ == "__main__":  # pragma: no cover
    app.run()
