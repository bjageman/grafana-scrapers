import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from config import FRED_TOKEN

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

def make_retry_session(retries=3):
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

_session = make_retry_session()

def fetch_observations(series_id, frequency=None, limit=5, observation_start=None):
    params = {
        "series_id": series_id,
        "api_key": FRED_TOKEN,
        "file_type": "json",
        "sort_order": "desc",
    }
    if limit is not None:
        params["limit"] = limit
    if frequency:
        params["frequency"] = frequency
    if observation_start:
        params["observation_start"] = observation_start
        params["sort_order"] = "asc"

    response = _session.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()["observations"]