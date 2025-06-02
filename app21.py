import pandas as pd
from pymongo import MongoClient
import streamlit as st
import seaborn as sns
import matplotlib.pyplot as plt
import plotly.express as px

sns.set(style="whitegrid")
st.set_page_config(page_title="Flight Dashboard", layout="wide")

# ✅ Define month_map globally so it’s accessible everywhere
month_map = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}

# --- MongoDB Data Load and Clean ---
@st.cache_data
def load_mongo_data():
    client = MongoClient("mongodb+srv://zeded646:zeded646@cluster0.sludtqs.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    db = client['Data']
    collection = db['1']
    documents = list(collection.find())
    flat_data = []

    for doc in documents:
        booking_responses = doc.get("BookingResponse", [])
        for response in booking_responses:
            segments = response.get("segments", [])
            fare_quotes = response.get("fareQuotes", [])

            total_price_internal = None
            total_price_external = doc.get("TotalPrice")

            for fq in fare_quotes:
                for pricing in fq.get("pricingInfos", []):
                    if pricing.get("totalPrice"):
                        if total_price_internal is None:
                            total_price_internal = pricing.get("totalPrice")
                        if total_price_external is None:
                            total_price_external = pricing.get("totalPrice")

            for segment in segments:
                departure_raw = segment.get("departure")
                if not departure_raw:
                    continue
                departure_time = pd.to_datetime(departure_raw, errors='coerce')
                if pd.isna(departure_time):
                    continue

                booked_by = doc.get("BookedBy")
                if isinstance(booked_by, list) and booked_by:
                    booked_by = booked_by[0]
                elif not isinstance(booked_by, str):
                    booked_by = "Unknown"

                flat_data.append({
                    "from": segment.get("from", "").upper(),
                    "to": segment.get("to", "").upper(),
                    "departure": departure_raw,
                    "arrival": segment.get("arrival"),
                    "airline": segment.get("airline"),
                    "duration": segment.get("duration")[0] if segment.get("duration") else None,
                    "serviceClass": segment.get("serviceClass"),
                    "TotalPrice_Internal": total_price_internal,
                    "TotalPrice_External": total_price_external,
                    "paymentStatus": doc.get("PaymentStatus"),
                    "Bank": doc.get("PaymentMethod", "Unknown"),
                    "BookedBy": booked_by,
                    "Ticket": str(doc.get("Ticket")) if doc.get("Ticket") else "[]",
                    "departure_year": departure_time.year,
                    "departure_month": departure_time.month,
                    "departure_day": departure_time.day,
                })

    df = pd.DataFrame(flat_data)

    def clean_price(value):
        if isinstance(value, str) and value.startswith("ETB"):
            value = value.replace("ETB", "").strip()
        return pd.to_numeric(value, errors='coerce')

    df["TotalPrice_Internal"] = df["TotalPrice_Internal"].apply(clean_price)
    df["TotalPrice_External"] = df["TotalPrice_External"].apply(clean_price)
    df.dropna(subset=["TotalPrice_Internal", "TotalPrice_External"], inplace=True)
    df["Revenue"] = df["TotalPrice_External"] - df["TotalPrice_Internal"]

    df["Bank"] = df["Bank"].fillna("Unknown")
    df["BookedBy"] = df["BookedBy"].fillna("Unknown")
    df["serviceClass"] = df["serviceClass"].fillna("Unknown")

    df["departure_month_name"] = df["departure_month"].map(month_map)

    ethiopian_airports = ['ADD', 'AMH', 'ASO', 'AWA', 'AXU', 'BCO', 'BJR', 'DEM', 'DIR', 'DSE', 
                      'GDE', 'GDQ', 'GMB', 'GOB', 'JIM', 'JIJ', 'LLI', 'MQX', 'MZX', 'SHC', 
                      'SZE', 'TIE', 'NEJ', 'MYB', 'SOU', 'DBM', 'DBT', 'ALE']

    def classify_route(row):
        if row['from'] in ethiopian_airports and row['to'] in ethiopian_airports:
            return 'Domestic'
        else:
            return 'International'
    df['route_type'] = df.apply(classify_route, axis=1)

    return df

# --- Load Data ---
df = load_mongo_data()

# --- Sidebar Filters ---
st.sidebar.header("Filter Data")
years = sorted(df["departure_year"].dropna().unique())
months = sorted(df["departure_month_name"].dropna().unique(), key=lambda x: list(month_map.values()).index(x))

selected_year = st.sidebar.selectbox("Select Year", years)
selected_month = st.sidebar.selectbox("Select Month", months)

filtered_df = df[(df["departure_year"] == selected_year) & (df["departure_month_name"] == selected_month)]

# --- Dashboard Title ---
st.title("✈️ Flight Booking Dashboard")

# --- KPI Metrics ---
col1, col2, col3 = st.columns(3)
col1.metric("📦 Total Bookings", f"{len(filtered_df):,}")
col2.metric("💰 Total Revenue (ETB)", f"{filtered_df['Revenue'].sum():,.0f}")
col3.metric("🎫 Avg. Revenue from Ticket", f"{filtered_df['Revenue'].mean():,.0f} ETB")

st.markdown("### 💸 Metrics Based on Sells")

col4, col5, col6 = st.columns(3)
col4.metric("🎟️ Max Ticket Price (ETB)", f"{filtered_df['TotalPrice_Internal'].max():,.0f}")
col5.metric("📊 Total Sells (ETB)", f"{filtered_df['TotalPrice_Internal'].sum():,.0f}")
col6.metric("🎫 Avg. Ticket Price", f"{filtered_df['TotalPrice_Internal'].mean():,.0f}")

st.markdown("---")

# --- Route Type Breakdown ---
st.subheader("Route Type Distribution")
fig_route = px.pie(filtered_df, names="route_type", title="Domestic vs International")
st.plotly_chart(fig_route, use_container_width=True)

# --- Revenue Over Time ---
st.subheader(f"Daily Revenue - {selected_month} {selected_year}")
fig_revenue = px.histogram(
    filtered_df,
    x="departure_day",
    y="Revenue",
    histfunc="sum",
    labels={"departure_day": "Day of Month"},
    title="Revenue by Day",
)
st.plotly_chart(fig_revenue, use_container_width=True)

# --- Top 10 Destinations ---
st.subheader("Top 10 Destinations by Revenue")
top_dests = (
    filtered_df.groupby("to")["TotalPrice_External"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)
fig_dest = px.bar(
    top_dests,
    x="to",
    y="TotalPrice_External",
    labels={"to": "Destination", "TotalPrice_External": "Revenue (ETB)"},
)
st.plotly_chart(fig_dest, use_container_width=True)

# --- Airline Revenue ---
st.subheader("Airline Performance")
airline_rev = (
    filtered_df.groupby("airline")["Revenue"]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
)
fig_airline = px.bar(
    airline_rev,
    x="airline",
    y="Revenue",
    labels={"Revenue": "Revenue (ETB)", "airline": "Airline"},
)
st.plotly_chart(fig_airline, use_container_width=True)

# --- Service Class Distribution ---
st.subheader("Service Class Breakdown")
fig_service = px.pie(
    filtered_df,
    names="serviceClass",
    title="Ticket Class Distribution",
)
st.plotly_chart(fig_service, use_container_width=True)
