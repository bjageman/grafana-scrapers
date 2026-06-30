# grafana-scrapers

Personal data scrapers for Grafana — Fitbit, Google Health, Hevy, Daylio, FRED, and more. Writes to InfluxDB v2.

Runs as a single Docker container on a cron schedule via [supercronic](https://github.com/aptible/supercronic).

## Scrapers

| Script | Data source | Cadence |
|---|---|---|
| `fitbit.py` | Heart rate, steps, calories, sleep, HRV, SpO2, breathing rate, skin temp, weight, activities | Hourly |
| `google_health.py` | Google Fit / Health Connect | Hourly |
| `hevy.py` | Hevy workout logs | Hourly |
| `daylio.py` | Daylio mood/journal CSV export | Daily at 4:05 AM |
| `fred/main.py` | FRED economic data (rates, debt, employment, etc.) | Hourly |
| `imf.py` | IMF World Economic Outlook indicators | Hourly |
| `yahoo.py` | Yahoo Finance quotes | Hourly |
| `metal_prices.py` | Metal spot prices | Mon/Wed/Fri at 8 AM |
| `oil_prices.py` | Oil prices | Mon/Wed/Fri at 9 AM |
| `waqi.py` | WAQI air quality index | Every 15 min |
| `pollen_google.py` | Google Pollen API | Daily at 9:30 AM |

## Requirements

- Docker
- InfluxDB v2
- API keys for whichever scrapers you use (see below)

## Configuration

All configuration is via environment variables. Create a `.env` file:

```env
# InfluxDB v2
INFLUXDB_URL=http://your-influxdb:8086
INFLUXDB_TOKEN=your-token
INFLUXDB_ORG=your-org
INFLUXDB_BUCKET=your-bucket

# Timezone
TZ=America/New_York

# Fitbit (https://dev.fitbit.com)
FITBIT_CLIENT_ID=
FITBIT_CLIENT_SECRET=

# Google (Health + Pollen)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_POLLEN_TOKEN=

# Hevy (https://hevy.com/settings -> API)
HEVY_API_KEY=
INFLUX_URL=           # can reuse INFLUXDB_URL
INFLUX_TOKEN=         # can reuse INFLUXDB_TOKEN
INFLUX_ORG=           # can reuse INFLUXDB_ORG

# FRED (https://fred.stlouisfed.org/docs/api/api_key.html)
FRED_TOKEN=

# WAQI (https://aqicn.org/api)
WAQI_API_TOKEN=

# Metals / Oil (https://metalpriceapi.com, https://oilpriceapi.com)
METAL_PRICE_TOKEN=
OIL_PRICE_TOKEN=

# Daylio
DAYLIO_CSV_GLOB=/app/exports/daylio_export*.csv
```

## Running

```bash
docker build -t grafana-scrapers .
docker run -d --env-file .env grafana-scrapers
```

Or with Docker Compose alongside your Grafana stack.

## Fitbit authorization

Fitbit uses OAuth2. On first run, use the included auth helper:

```bash
docker run --rm -p 8080:8080 --env-file .env -v ./tokens:/app/tokens grafana-scrapers \
  python3 /app/scripts/fitbit_authorize.py
```

Then open `http://localhost:8080` and follow the prompts. The token is saved to `/app/tokens/fitbit.json` and refreshed automatically.

## Google authorization

```bash
docker run --rm -p 8080:8080 --env-file .env -v ./tokens:/app/tokens grafana-scrapers \
  python3 /app/scripts/authorize.py
```

## License

MIT
