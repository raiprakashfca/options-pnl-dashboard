
import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows

st.set_page_config(page_title="Options Trading P&L Dashboard", layout="wide")

# Initialize or load long-term storage
if 'trade_data' not in st.session_state:
    st.session_state.trade_data = pd.DataFrame()

def stylized_excel_export(df):
    output = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Script-Wise Summary"

    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
        ws.append(row)
        for c_idx, cell in enumerate(ws[r_idx], 1):
            col_name = ws[1][c_idx - 1].value
            cell.alignment = Alignment(horizontal="center")
            if r_idx == 1:
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="D9E1F2", fill_type="solid")
            elif row[df.columns.get_loc("Status")] == "Open Position":
                cell.fill = PatternFill(start_color="FFF2CC", fill_type="solid")
            elif col_name == "P&L" and isinstance(cell.value, (int, float)):
                if cell.value > 0:
                    cell.fill = PatternFill(start_color="C6EFCE", fill_type="solid")
                elif cell.value < 0:
                    cell.fill = PatternFill(start_color="FFC7CE", fill_type="solid")
            if col_name in ["Buy_Amt", "Sell_Amt", "P&L"]:
                cell.alignment = Alignment(horizontal="right")

    for col in ws.columns:
        max_len = max(len(str(cell.value) if cell.value else "") for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 2

    wb.save(output)
    output.seek(0)
    return output

st.title("📊 Options Trading P&L Dashboard")

tab = st.sidebar.radio("Navigation", ["Upload Trades", "Script-Wise Summary"])

if tab == "Upload Trades":
    st.header("📤 Upload Trade File")
    uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            df.columns = df.columns.str.strip()
            trade_date = uploaded_file.name.replace("TRADES", "").replace(".xlsx", "")
            trade_date = datetime.strptime(trade_date, "%d%m%Y").date()
            df['Trade Date'] = trade_date

            df = df[['Symbol/ScripId', 'Ser/Exp/Group', 'Strike Price', 'Option Type', 'B/S', 'Quantity', 'Price', 'Trade Date']]
            df.columns = ['Symbol', 'Expiry', 'Strike', 'Type', 'Side', 'Quantity', 'Price', 'Date']
            df = df[(df['Quantity'] > 0) & (df['Price'] > 0)].copy()
            df['Value'] = df['Quantity'] * df['Price']
            st.session_state.trade_data = pd.concat([st.session_state.trade_data, df], ignore_index=True)
            st.success("✅ Trade file uploaded and stored.")
        except Exception as e:
            st.error(f"❌ Error: {e}")

elif tab == "Script-Wise Summary":
    st.header("📋 Script-Wise Summary")

    if st.session_state.trade_data.empty:
        st.info("No trade data uploaded yet.")
    else:
        df = st.session_state.trade_data.copy()
        df['OT'] = df['Type'].map({'CE': 'C', 'PE': 'P'})
        df['Leg'] = df['Symbol'] + "_" + df['Expiry'].astype(str) + "_" + df['Strike'].astype(str) + "_" + df['OT']

        summary = df.groupby(['Date', 'Leg']).agg(
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

        # Export button
        excel_data = stylized_excel_export(summary)
        st.download_button(
            label="📥 Download Excel Summary",
            data=excel_data,
            file_name="Script_Wise_Summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
