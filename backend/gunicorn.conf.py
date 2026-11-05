"""Production Gunicorn settings with a privacy-safe access log."""

bind = "0.0.0.0:8000"
workers = 3
timeout = 60
accesslog = "-"

# ``U`` is the request path without its query string. Do not replace it with
# ``r`` (the full request line), ``q`` (the query string), or ``f`` (a referrer
# URL that can itself carry sensitive query parameters).
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)s'
