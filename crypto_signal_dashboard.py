
import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# === Google Sheets Setup with Streamlit Secrets ===
SHEET_NAME = "CryptoSignals"
WORKSHEET_NAME = "Signals"

@st.cache_data(ttl=60)
def load_data():
    # Load creds from secrets
    creds_dict = {
        "type": st.secrets["type"],
        "project_id": st.secrets["project_id"],
        "private_key_id": st.secrets["private_key_id"],
        "private_key": st.secrets["private_key"].replace("\n", "
"),
        "client_email": st.secrets["client_email"],
        "client_id": st.secrets["client_id"],
        "auth_uri": st.secrets["auth_uri"],
        "token_uri": st.secrets["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["client_x509_cert_url"]
    }
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
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
