from prometheus_client import Counter, Gauge

HTTP_REQUESTS = Counter(
    "afisha_http_requests_total",
    "Total HTTP requests handled by the API process.",
    ("method", "route", "status"),
)
REDIS_AVAILABLE = Gauge(
    "afisha_redis_available",
    "Whether the non-authoritative Redis dependency is reachable.",
)
NOMINATIM_AVAILABLE = Gauge(
    "afisha_nominatim_available",
    "Whether the optional internal Nominatim adapter is reachable.",
)
