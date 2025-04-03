import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Options Trading P&L Dashboard", layout="wide")

# Sidebar navigation
tab = st.sidebar.radio("Go to", ["Upload Trades", "Script-Wise Summary", "Daily P&L", "Monthly Report", "All Trades"])

# Initialize session state for storing trades
if 'all_trades' not in st.session_state:
    st.session_state.all_trades = pd.DataFrame()

if tab == "Upload Trades":
    st.header("📤 Upload Your Trade File")
    uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = df.columns.str.strip()

            # Extract metadata from file name
            trade_date = uploaded_file.name.replace("TRADES", "").replace(".xlsx", "")
            trade_date = datetime.strptime(trade_date, "%d%m%Y").date()
            df['Trade Date'] = trade_date

            # Keep only relevant columns
            df = df[['Symbol/ScripId', 'Ser/Exp/Group', 'Strike Price', 'Option Type', 'B/S', 'Quantity', 'Price', 'Trade Date']]
            df.columns = ['Symbol', 'Expiry', 'Strike', 'Type', 'Side', 'Quantity', 'Price', 'Date']
            df = df[(df['Quantity'] > 0) & (df['Price'] > 0)]
            df['Value'] = df['Quantity'] * df['Price']
            st.session_state.all_trades = pd.concat([st.session_state.all_trades, df], ignore_index=True)
            st.success("Trade file uploaded and processed successfully!")
        except Exception as e:
            st.error(f"Error processing file: {e}")

elif tab == "Script-Wise Summary":
    st.header("📋 Script-Wise P&L Summary")
    if st.session_state.all_trades.empty:
        st.info("No trades uploaded yet.")
    else:
        df = st.session_state.all_trades.copy()
        df['OT'] = df['Type'].map({'CE': 'C', 'PE': 'P'})
        df['Leg'] = df['Symbol'] + "_" + df['Expiry'].astype(str) + "_" + df['Strike'].astype(str) + "_" + df['OT']

        summary = df.groupby(['Leg']).agg(
            Date=('Date', 'min'),
            Symbol=('Symbol', 'first'),
            Expiry=('Expiry', 'first'),
            Strike=('Strike', 'first'),
            Type=('OT', 'first'),
            Buy_Qty=('Quantity', lambda x: x[df.loc[x.index, 'Side'] == 'B'].sum()),
            Buy_Amt=('Value', lambda x: x[df.loc[x.index, 'Side'] == 'B'].sum()),
            Sell_Qty=('Quantity', lambda x: x[df.loc[x.index, 'Side'] == 'S'].sum()),
            Sell_Amt=('Value', lambda x: x[df.loc[x.index, 'Side'] == 'S'].sum())
        ).reset_index()

        summary['Net_Qty'] = summary['Sell_Qty'] - summary['Buy_Qty']
        summary['P&L'] = summary['Sell_Amt'] - summary['Buy_Amt']
        summary['Status'] = summary['Net_Qty'].apply(lambda x: 'Closed' if x == 0 else 'Open Position')
        summary.loc[summary['Status'] == 'Open Position', 'P&L'] = None

        summary = summary.sort_values(by=['Date', 'Symbol', 'Strike'])

        st.dataframe(summary, use_container_width=True)

elif tab == "Daily P&L":
    st.header("📅 Daily P&L")
    if st.session_state.all_trades.empty:
        st.info("No trades uploaded yet.")
    else:
        df = st.session_state.all_trades.copy()
        df['Value'] = df['Quantity'] * df['Price']

        grouped = df.groupby(['Symbol', 'Date', 'Type', 'Strike', 'Side']).agg(
            Qty=('Quantity', 'sum'),
            Amount=('Value', 'sum')
        ).reset_index()

        # Placeholder for daily net P&L (requires full ledger logic)
        st.dataframe(grouped)

elif tab == "Monthly Report":
    st.header("📊 Monthly Report")
    st.info("Coming soon – this will include monthly totals, win/loss stats, and export to Excel/PDF.")

elif tab == "All Trades":
    st.header("📂 All Trades Uploaded")
    if st.session_state.all_trades.empty:
        st.info("No trades uploaded yet.")
    else:
        st.dataframe(st.session_state.all_trades.sort_values(by=['Date', 'Symbol', 'Strike']), use_container_width=True)
