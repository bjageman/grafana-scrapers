from scrapers import (
    scrape_unemployment, scrape_employment,
    scrape_job_postings,
    scrape_treasury_yields,
    scrape_fuel_prices_by_gallon,
    scrape_fuel_prices_by_barrel,
    scrape_metal_prices,
    scrape_currency,
    scrape_income, scrape_income_inequality,
    scrape_markets,
    scrape_population,
    scrape_grocery_prices,
    scrape_home_prices,
    scrape_power_prices,
    scrape_ppi, scrape_cpi, scrape_inflation,
    scrape_delinquency_rate,
    scrape_credit_card_balances,
    scrape_consumer_sentiment,
    scrape_fed_rate
)
from db import write_api, influx

if __name__ == "__main__":
    scrape_unemployment()
    scrape_employment()
    scrape_job_postings()
    scrape_treasury_yields()
    scrape_fuel_prices_by_gallon()
    scrape_fuel_prices_by_barrel()
    scrape_metal_prices()
    scrape_currency()
    scrape_income()
    scrape_income_inequality()
    scrape_markets()
    scrape_population()
    scrape_grocery_prices()
    scrape_power_prices()
    scrape_home_prices()
    scrape_ppi()
    scrape_cpi()
    scrape_inflation()
    scrape_delinquency_rate()
    scrape_credit_card_balances()
    scrape_consumer_sentiment()
    scrape_fed_rate()
    write_api.close()
    influx.close()

