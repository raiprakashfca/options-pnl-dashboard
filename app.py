import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime
from io import BytesIO
from oauth2client.service_account import ServiceAccountCredentials
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

st.set_page_config(page_title="Options Trading P&L Dashboard", layout="wide")

# Authenticate with Google Sheets using service account
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Use sheet by ID instead of name
SHEET_ID = "1Siith5tw8m-aNOAcwqG1I7L1e_kt8qBX1OOKuAkCpb4"
sheet = client.open_by_key(SHEET_ID).sheet1

@st.cache_data
def load_trades():
    records = sheet.get_all_records()
    return pd.DataFrame(records)

def append_trades(new_df):
    existing = load_trades()
    updated = pd.concat([existing, new_df], ignore_index=True)
    sheet.clear()
    sheet.update([updated.columns.values.tolist()] + updated.values.tolist())

def export_to_excel(df):
    output = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "P&L Summary"

    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
        ws.append(row)
        for c_idx, cell in enumerate(ws[r_idx], 1):
            col_name = ws[1][c_idx - 1].value
            cell.alignment = Alignment(horizontal="right" if col_name in ['Buy_Amt', 'Sell_Amt', 'P&L'] else "center")

            if r_idx == 1:
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="D9E1F2", fill_type="solid")
            elif row[df.columns.get_loc("Status")] == "Open Position":
                cell.fill = PatternFill(start_color="FFF2CC", fill_type="solid")
            elif col_name == "P&L":
                if isinstance(cell.value, (int, float)):
                    if cell.value > 0:
                        cell.fill = PatternFill(start_color="C6EFCE", fill_type="solid")
                    elif cell.value < 0:
                        cell.fill = PatternFill(start_color="FFC7CE", fill_type="solid")

    for col in ws.columns:
        max_len = max(len(str(cell.value) if cell.value else "") for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 2

    wb.save(output)
    output.seek(0)
    return output

st.title("📊 Options Trading P&L Dashboard")
tab = st.sidebar.radio("Navigation", ["📤 Upload Trades", "📋 Script-Wise Summary"])

if tab == "📤 Upload Trades":
    uploaded_file = st.file_uploader("Upload your trade Excel file (e.g., TRADES01042025.xlsx)", type="xlsx")
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = df.columns.str.strip()

            trade_date = uploaded_file.name.replace("TRADES", "").replace(".xlsx", "")
            trade_date = datetime.strptime(trade_date, "%d%m%Y").date()
            df['Trade Date'] = trade_date

            df = df[['Symbol/ScripId', 'Ser/Exp/Group', 'Strike Price', 'Option Type', 'B/S', 'Quantity', 'Price', 'Trade Date']]
            df.columns = ['Symbol', 'Expiry', 'Strike', 'Type', 'Side', 'Quantity', 'Price', 'Date']
            df = df[(df['Quantity'] > 0) & (df['Price'] > 0)]
            df['Value'] = df['Quantity'] * df['Price']

            append_trades(df)
            st.success("✅ Trade file uploaded and saved to Google Sheets.")
        except Exception as e:
            st.error(f"Error reading file: {e}")

elif tab == "📋 Script-Wise Summary":
    st.header("📋 Script-Wise Summary")

    df = load_trades()
    if df.empty:
        st.info("No trade data available.")
    else:
        df['OT'] = df['Type'].map({'CE': 'C', 'PE': 'P'})
        df['Leg'] = df['Symbol'] + '_' + df['Expiry'].astype(str) + '_' + df['Strike'].astype(str) + '_' + df['OT']

        summary = df.groupby(['Date', 'Symbol', 'Expiry', 'Strike', 'OT']).agg(
            Buy_Qty=('Quantity', lambda x: x[df.loc[x.index, 'Side'] == 'B'].sum()),
            Buy_Amt=('Value', lambda x: x[df.loc[x.index, 'Side'] == 'B'].sum()),
            Sell_Qty=('Quantity', lambda x: x[df.loc[x.index, 'Side'] == 'S'].sum()),
            Sell_Amt=('Value', lambda x: x[df.loc[x.index, 'Side'] == 'S'].sum())
        ).reset_index()

        summary['Net_Qty'] = summary['Sell_Qty'] - summary['Buy_Qty']
        summary['P&L'] = summary['Sell_Amt'] - summary['Buy_Amt']
        summary['Status'] = summary['Net_Qty'].apply(lambda x: "Closed" if x == 0 else "Open Position")
        summary.loc[summary['Status'] == 'Open Position', 'P&L'] = None

        summary = summary.rename(columns={'OT': 'Type', 'Date': 'Trade Date'})
        summary = summary.sort_values(by=['Trade Date', 'Symbol', 'Strike'])

        st.dataframe(summary, use_container_width=True)

        excel_file = export_to_excel(summary)
        st.download_button("📥 Download Excel Summary", excel_file, "PnL_Summary.xlsx")
