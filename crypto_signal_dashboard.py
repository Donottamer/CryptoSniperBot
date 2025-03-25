
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# === Google Sheets Setup ===
SHEET_NAME = "CryptoSignals"
WORKSHEET_NAME = "Signals"
CREDENTIALS_FILE = "google_creds.json"

@st.cache_data(ttl=60)
def load_data():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df.sort_values(by='Timestamp', ascending=False, inplace=True)
    return df

# === Streamlit Dashboard ===
st.set_page_config(page_title="Crypto Signal Dashboard", layout="wide")
st.title("📈 Crypto Trading Signal Dashboard")

df = load_data()

# Filters
st.sidebar.header("🔍 Filters")
symbol_filter = st.sidebar.multiselect("Symbol", options=df["Symbol"].unique(), default=df["Symbol"].unique())
signal_filter = st.sidebar.multiselect("Signal", options=df["Signal"].unique(), default=df["Signal"].unique())
min_conf = st.sidebar.slider("Min Confidence (%)", 0, 100, 70)

filtered_df = df[
    (df["Symbol"].isin(symbol_filter)) &
    (df["Signal"].isin(signal_filter)) &
    (df["Confidence"] >= min_conf)
]

# Display Table
st.subheader(f"Showing {len(filtered_df)} Signals")
st.dataframe(filtered_df, use_container_width=True)

# Charts
st.subheader("📊 Confidence Over Time")
st.line_chart(filtered_df.set_index("Timestamp")["Confidence"])

st.subheader("📈 Signal Count by Symbol")
st.bar_chart(filtered_df["Symbol"].value_counts())
