import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from pandas.tseries.offsets import BDay
from concurrent.futures import ThreadPoolExecutor

#api key below

# Load the Excel file
excel_file_path = 'BBands_ETFs_2024-08-05_v2.xlsx'
sheets_dict = pd.read_excel(excel_file_path, sheet_name=None)

# Sidebar for sector selection
st.sidebar.title("Select Sector")
selected_sector = st.sidebar.radio("Sectors", list(sheets_dict.keys()))

# Color mapping for different bands
color_map = {
    'LBand 1STD': 'background-color: lightcoral',  # light red
    'LBand 2STD': 'background-color: red',  # stronger red
    'UBand 1STD': 'color: black; background-color: lightgreen',  # light green with black text
    'UBand 2STD': 'background-color: green',  # stronger green
    'Mid Zone': '',  # no color
}

def highlight_cells(val):
    return color_map.get(val, '')

def prioritize_bands(df):
    band_priority = {
        'UBand 2STD': 1,
        'UBand 1STD': 2,
        'LBand 1STD': 3,
        'LBand 2STD': 4,
        'Mid Zone': 5
    }
    df['Priority'] = df[['Crossing Daily Band', 'Crossing Weekly Band', 'Crossing Monthly Band']].apply(
        lambda x: min(band_priority[x[0]], band_priority[x[1]], band_priority[x[2]]), axis=1
    )
    return df.sort_values('Priority').drop(columns='Priority')

def generate_tradingview_embed(ticker):
    return f"""
    <iframe src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_c2a09&symbol={ticker}&interval=D&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[%7B%22id%22%3A%22BB%40tv-basicstudies%22%2C%22inputs%22%3A%5B20%2C2%5D%7D]&theme=Dark&style=1&timezone=exchange&withdateranges=1&hideideas=1&studies_overrides={{}}&overrides={{}}&enabled_features=[]&disabled_features=[]&locale=en&utm_source=www.tradingview.com&utm_medium=widget&utm_campaign=chart&utm_term={ticker}" width="100%" height="600" frameborder="0" allowfullscreen></iframe>
    """

def fetch_current_price(symbol, api_token):
    url = f'https://eodhd.com/api/real-time/{symbol}.US?api_token={api_token}&fmt=json'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        current_price = data.get('close', None)
        if current_price is not None:
            current_price = pd.to_numeric(current_price, errors='coerce')
        return current_price
    else:
        print(f"Failed to fetch current price for {symbol}: {response.status_code}, {response.text}")
        return None

def fetch_previous_close_price(symbol, api_token):
    end_date = datetime.now() - BDay(1)
    start_date = end_date - BDay(5)
    url = f'https://eodhistoricaldata.com/api/eod/{symbol}.US?api_token={api_token}&from={start_date.strftime("%Y-%m-%d")}&to={end_date.strftime("%Y-%m-%d")}&fmt=json&adjusted=true'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data)
        df['adjusted_close'] = pd.to_numeric(df['adjusted_close'], errors='coerce')
        df.dropna(subset=['adjusted_close'], inplace=True)
        previous_close_price = df['adjusted_close'].iloc[-1] if not df.empty else None
        return previous_close_price
    else:
        print(f"Failed to fetch previous close price for {symbol}: {response.status_code}, {response.text}")
        return None

def fetch_historical_data(symbol, api_token, start_date, end_date):
    url = f'https://eodhistoricaldata.com/api/eod/{symbol}.US?api_token={api_token}&from={start_date}&to={end_date}&fmt=json&adjusted=true'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df['adjusted_close'] = pd.to_numeric(df['adjusted_close'], errors='coerce')
        df.dropna(subset=['adjusted_close'], inplace=True)
        return df
    else:
        print(f"Failed to fetch data for {symbol}: {response.status_code}, {response.text}")
        return pd.DataFrame()

def analyze_symbol(symbol, api_token):
    current_date = datetime.now()
    start_of_month = current_date.replace(day=1)
    start_of_quarter = (current_date - pd.offsets.QuarterBegin(startingMonth=1)).strftime('%Y-%m-%d')
    start_of_year = current_date.replace(month=1, day=1)
    start_of_30_days = current_date - timedelta(days=30)
    start_of_5_days = current_date - BDay(5)

    with ThreadPoolExecutor() as executor:
        current_price_future = executor.submit(fetch_current_price, symbol, api_token)
        previous_close_price_future = executor.submit(fetch_previous_close_price, symbol, api_token)
        df_month_future = executor.submit(fetch_historical_data, symbol, api_token, start_of_month.strftime('%Y-%m-%d'), current_date.strftime('%Y-%m-%d'))
        df_quarter_future = executor.submit(fetch_historical_data, symbol, api_token, start_of_quarter, current_date.strftime('%Y-%m-%d'))
        df_year_future = executor.submit(fetch_historical_data, symbol, api_token, start_of_year.strftime('%Y-%m-%d'), current_date.strftime('%Y-%m-%d'))
        df_5_days_future = executor.submit(fetch_historical_data, symbol, api_token, start_of_5_days.strftime('%Y-%m-%d'), current_date.strftime('%Y-%m-%d'))

        current_price = current_price_future.result()
        previous_close_price = previous_close_price_future.result()
        df_month = df_month_future.result()
        df_quarter = df_quarter_future.result()
        df_year = df_year_future.result()
        df_5_days = df_5_days_future.result()

    if current_price is None:
        return symbol, None, None, None, None, None

    if previous_close_price is None:
        today_percentage = None
    else:
        today_percentage = round(((current_price - previous_close_price) / previous_close_price) * 100, 2)

    start_month_price = df_month['adjusted_close'].iloc[0] if not df_month.empty else None
    start_quarter_price = df_quarter['adjusted_close'].iloc[0] if not df_quarter.empty else None
    start_year_price = df_year['adjusted_close'].iloc[0] if not df_year.empty else None
    start_5_days_price = df_5_days['adjusted_close'].iloc[0] if not df_5_days.empty else None

    mtd_percentage = round(((current_price - start_month_price) / start_month_price) * 100, 2) if start_month_price is not None else None
    qtd_percentage = round(((current_price - start_quarter_price) / start_quarter_price) * 100, 2) if start_quarter_price is not None else None
    ytd_percentage = round(((current_price - start_year_price) / start_year_price) * 100, 2) if start_year_price is not None else None
    five_day_percentage = round(((current_price - start_5_days_price) / start_5_days_price) * 100, 2) if start_5_days_price is not None else None

    return symbol, current_price, today_percentage, mtd_percentage, qtd_percentage, ytd_percentage, five_day_percentage

# Main code
df = sheets_dict[selected_sector]
sorted_df = prioritize_bands(df)
highlighted_df = sorted_df.style.applymap(highlight_cells, subset=['Crossing Daily Band', 'Crossing Weekly Band', 'Crossing Monthly Band'])

st.title(f"{selected_sector} - Bollinger Bands Analysis")
st.dataframe(highlighted_df, height=500, width=1000)

# Display chart and data for selected symbol
selected_ticker = st.selectbox("Select Ticker to View Chart", sorted_df['Symbol'])

# Generate and display the TradingView chart
col1, col2 = st.columns([3, 1])

with col1:
    chart_html = generate_tradingview_embed(selected_ticker)
    st.components.v1.html(chart_html, height=600)

# Perform and display the analysis for the selected ticker
symbol, current_price, today_percentage, mtd_percentage, qtd_percentage, ytd_percentage, five_day_percentage = analyze_symbol(selected_ticker, api_token)

if current_price is not None:
    with col2:
        st.subheader(f"{selected_ticker}")
        st.write(f"**Current Price:** {current_price}")
        st.write(f"**Today:** {today_percentage}%")
        st.write(f"**5-Day:** {five_day_percentage}%")
        st.write(f"**MTD:** {mtd_percentage}%")
        st.write(f"**QTD:** {qtd_percentage}%")
        st.write(f"**YTD:** {ytd_percentage}%")
else:
    st.write(f"Could not fetch data for {selected_ticker}. Please try again later.")
