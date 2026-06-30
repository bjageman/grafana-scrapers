from influxdb_client import Point
from config import BUCKET
from db import write_api
from client import fetch_observations
from utils import to_ns

GROCERY_NAMES = {
    "APU0000708111": "Eggs Grade A Large per Dozen",
    "APU0000703112": "Ground Beef 100% per Pound",
    "APU0000709112": "Milk Fresh Whole per Gallon",
    "APU0000FF1101": "Chicken Breast Boneless per Pound",
    "APU0000702111": "White Bread per Pound",
    "APU0000711211": "Bananas per Pound",
    "APU0000FS1101": "Butter per Pound",
    "APU0000701312": "White Rice per Pound",
    "APU0000717311": "Coffee per Pound",
    "APU0000715211": "Sugar per Pound",
    "APU0000704111": "Bacon per Pound",
    "APU0000701111": "Flour per Pound",
    "APU0000712112": "Potatoes per Pound",
    "APU0300703213": "Chuck Roast per Pound",
    "PURANUSDM": "Uranium per Pound"
}

HOME_NAMES = {
    "MSPUS": "Median Sales Price of Houses Sold",
    "ASPUS": "Average Sales Price of Houses Sold",
    "MELIPRCOUNTY42101": "Median Listing Price in Philadelphia County",
    "MEDLISPRI38900": "Median Listing Price in Portland"
}

POWER_NAMES = {
        "APU000072610": "Electricity per Kilowatt-Hour",
        "APUS37A72610": "Electricity per Kilowatt-Hour in Texas"
}

PPI_NAMES = {
    "PPIACO": "All Commodities",
    "PCU325311325311A": "Nitrogenous Fertilizer",
    "WPU0652026A": "Phosphate Fertilizer",
    "PCUOMFGOMFG": "Total Manufacturing",
    "PCUATRNWRATRNWR": "Transportation and Warehousing",
    "PCUOMINOMIN": "Total Mining",
    "PCUAINFOAINFO": "Information",
    "PCUARETTRARETTR": "Retail Trade",
    "PCUASHCASHC": "Healthcare"
}

CPI_NAMES = {
    "CPIAUCSL": "All Items in U.S. City Average ",
    "CPILFESL": "All Items Less Food and Energy",
    "CPIMEDNS": "Medical Care",
    "CUUR0000SA0R": "Purchasing Power of the Consumer Dollar",
    "CUSR0000SETA02": "Used Cars and Trucks",
    "CUUR0000SETA01": "New Vehicles",
    "CUSR0000SETG01": "Airline Fares",
    "CUSR0000SETD": "Motor Vehicle Maintenance and Repair",
    "CUUR0000SETC": "Motor Vehicle Parts and Equipment",
    "CUSR0000SETG": "Public Transportation",
    "CPIEHOUSE": "Housing"
}

INFLATION_NAMES = {
    "FPCPITOTLZGUSA": "Consumer prices for the United States"
}

def scrape_grocery_prices():
    for series_id, name in GROCERY_NAMES.items():
        for obs in fetch_observations(series_id, frequency="m", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("grocery_prices")
                .field("value", float(value))
                .tag("name", name)
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def scrape_home_prices():
    for series_id, name in HOME_NAMES.items():
        for obs in fetch_observations(series_id, frequency="q", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("home_prices")
                .field("value", float(value))
                .tag("name", name)
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def scrape_power_prices():
    for series_id, name in POWER_NAMES.items():
        for obs in fetch_observations(series_id, frequency="q", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("power_prices")
                .field("value", float(value))
                .tag("name", name)
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def scrape_ppi():
    for series_id, name in PPI_NAMES.items():
        for obs in fetch_observations(series_id, frequency="m", limit=5000):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("producer_price_index")
                .field("value", float(value))
                .tag("name", name)
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def scrape_cpi():
    for series_id, name in CPI_NAMES.items():
        for obs in fetch_observations(series_id, frequency="m", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("consumer_price_index")
                .field("value", float(value))
                .tag("name", name)
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)

def scrape_inflation():
    for series_id, name in INFLATION_NAMES.items():
        for obs in fetch_observations(series_id, frequency="a", limit=5):
            value = obs["value"]
            if value == ".":
                continue

            point = (
                Point("inflation")
                .field("percentage", float(value))
                .tag("name", name)
                .tag("type", series_id)
                .time(to_ns(obs["date"]))
            )
            write_api.write(bucket=BUCKET, record=point)