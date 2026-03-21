"""
Delhi air quality analysis using OpenAQ (PM2.5 / PM10)
Saves cleaned hourly.csv and daily_summary.csv and produces simple plots.

Note: OpenAQ rate-limits heavy queries. For long historical periods, combine
multiple paginated requests or use their bulk data / Kaggle / CPCB files.
"""
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import time

# --------- PARAMETERS ----------
CITY = "Delhi"
PARAMS = ["pm25", "pm10", "no2", "so2", "co", "o3"]  # pollutants to request
DAYS_BACK = 365  # how many days of historical data to fetch (adjustable)
OUT_HOURLY_CSV = "delhi_hourly_openaq.csv"
OUT_DAILY_CSV = "delhi_daily_summary.csv"
# --------------------------------

BASE_URL = "https://api.openaq.org/v2/measurements"

def fetch_openaq(city, parameter, date_from, date_to, limit=10000):
    """
    Fetch measurements for a single parameter and time window from OpenAQ v2.
    Returns records as a list of dicts.
    """
    records = []
    page = 1
    while True:
        params = {
            "city": city,
            "parameter": parameter,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "limit": 100,   # page size
            "page": page,
            "sort": "desc",
            "order_by": "datetime"
        }
        r = requests.get(BASE_URL, params=params, timeout=30)
        r.raise_for_status()
        js = r.json()
        results = js.get("results", [])
        if not results:
            break
        records.extend(results)
        # pagination: stop if fewer than page size returned
        if len(results) < params["limit"] or page >= js.get("meta", {}).get("found", 0) // params["limit"] + 2:
            break
        page += 1
        time.sleep(0.2)
    return records

def fetch_multi_params(city, params_list, days_back):
    to_time = datetime.utcnow()
    from_time = to_time - timedelta(days=days_back)
    all_rows = []
    for p in params_list:
        print(f"Fetching {p} from {from_time.date()} to {to_time.date()} ...")
        recs = fetch_openaq(city, p, from_time, to_time)
        for r in recs:
            # key fields: date.utc, value, parameter, location
            date_utc = r.get("date", {}).get("utc")
            val = r.get("value")
            loc = r.get("location")
            unit = r.get("unit")
            all_rows.append({
                "datetime_utc": date_utc,
                "parameter": p,
                "value": val,
                "unit": unit,
                "location": loc,
                "source": r.get("sourceName") or r.get("source", {}).get("name")
            })
    df = pd.DataFrame(all_rows)
    return df

def clean_transform(df):
    # parse datetime, drop NA values, pivot to wide format (one column per pollutant)
    df = df.dropna(subset=["datetime_utc", "value"])
    df["datetime_utc"] = pd.to_datetime(df["datetime_utc"], utc=True)
    # round to hour (OpenAQ is often hourly)
    df["datetime_utc"] = df["datetime_utc"].dt.floor("H")
    # pivot
    df_wide = df.pivot_table(index="datetime_utc", columns="parameter", values="value", aggfunc="mean")
    # optionally convert units if required (OpenAQ usually µg/m3 for PM)
    df_wide = df_wide.sort_index()
    return df_wide

def daily_summary(df_hourly):
    df_daily = pd.DataFrame()
    df_daily["pm25_mean"] = df_hourly["pm25"].resample("D").mean()
    df_daily["pm25_median"] = df_hourly["pm25"].resample("D").median()
    df_daily["pm25_count"] = df_hourly["pm25"].resample("D").count()
    df_daily["pm10_mean"] = df_hourly["pm10"].resample("D").mean()
    df_daily["pm10_count"] = df_hourly["pm10"].resample("D").count()
    # other pollutants if present
    for poll in ["no2", "so2", "o3", "co"]:        if poll in df_hourly.columns:
            df_daily[f"{poll}_mean"] = df_hourly[poll].resample("D").mean()
    return df_daily

def quick_plots(df_daily, df_hourly):
    plt.figure(figsize=(12,4))
    if "pm25_mean" in df_daily.columns:
        plt.plot(df_daily.index, df_daily["pm25_mean"], label="PM2.5 daily mean")
    if "pm10_mean" in df_daily.columns:
        plt.plot(df_daily.index, df_daily["pm10_mean"], label="PM10 daily mean")
    plt.legend()
    plt.title(f"Delhi daily mean PM2.5 & PM10 (last {DAYS_BACK} days)")
    plt.xlabel("Date")
    plt.ylabel("µg/m³")
    plt.tight_layout()
    plt.savefig("delhi_daily_pm_timeseries.png")
    plt.show()

    # monthly averages bar
    monthly = df_daily.resample("M").mean()
    plt.figure(figsize=(10,4))
    if "pm25_mean" in monthly.columns:
        plt.bar(monthly.index.strftime("%Y-%m"), monthly["pm25_mean"])
        plt.xticks(rotation=45)
        plt.title("Monthly average PM2.5")
        plt.ylabel("µg/m³")
        plt.tight_layout()
        plt.savefig("delhi_monthly_pm25.png")
        plt.show()

    # Boxplot by month to show seasonality (use hourly pm25)
    if "pm25" in df_hourly.columns:
        df_hourly = df_hourly.copy()
        df_hourly = df_hourly.dropna(subset=["pm25"])
        df_hourly["month"] = df_hourly.index.month
        # prepare month-wise lists
        data_by_month = [df_hourly[df_hourly["month"]==m]["pm25"].values for m in range(1,13)]
        plt.figure(figsize=(10,5))
        plt.boxplot(data_by_month, labels=[str(i) for i in range(1,13)])
        plt.xlabel("Month")
        plt.ylabel("PM2.5 (µg/m³)")
        plt.title("PM2.5 distribution by month (1=Jan ... 12=Dec)")
        plt.tight_layout()
        plt.savefig("delhi_pm25_box_by_month.png")
        plt.show()

def main():
    # 1) Fetch
    df_raw = fetch_multi_params(CITY, PARAMS, DAYS_BACK)
    if df_raw.empty:
        print("No records downloaded. You can try increasing DAYS_BACK or using a file from Kaggle/CPCB.")
        return
    # 2) Clean & pivot
    df_hourly = clean_transform(df_raw)
    # Save hourly wide CSV
    df_hourly.to_csv(OUT_HOURLY_CSV, index_label="datetime_utc")
    print(f"Saved hourly data to {OUT_HOURLY_CSV} (rows: {len(df_hourly)})")

    # 3) Daily summary
    df_daily = daily_summary(df_hourly)
    df_daily.to_csv(OUT_DAILY_CSV, index_label="date")
    print(f"Saved daily summary to {OUT_DAILY_CSV} (rows: {len(df_daily)})")

    # 4) Quick plots
    quick_plots(df_daily, df_hourly)

if __name__ == "__main__":
    main()


