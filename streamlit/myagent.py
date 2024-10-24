from langchain.agents import tool, Tool
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import talib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

#general functions
def calculateRsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculateMacd(prices, short_window=12, long_window=26, signal_window=9):
    short_ema = prices.ewm(span=short_window, adjust=False).mean()
    long_ema = prices.ewm(span=long_window, adjust=False).mean()
    macd = short_ema - long_ema
    signal_line = macd.ewm(span=signal_window, adjust=False).mean()
    return macd, signal_line
  
@tool
def get_company_symbol(symbol:str) -> str:
  """Returns the ticker of the company inputted"""
  ticker = yf.Ticker(symbol)
  return ticker

@tool
def get_stock_price(symbol: str) -> float:
    """
    Returns the latest stock price for the given ticker symbol.
    If today's data is not available, returns the previous day's closing price.
    Raises ValueError if no data can be retrieved.
    """
    try:
        symbol=symbol.strip()
        ticker = yf.Ticker(symbol)
        # Fetch data for the past 2 days (in case today's data is missing)
        data = ticker.history(period='5d')

        if data.empty:
            raise ValueError(f"No data available for symbol: {symbol}")

        # Check if we have at least one day of data
        latest_available_day = data['Close'].iloc[-1] 
        return round(latest_available_day, 2)

    except Exception as e:
        raise ValueError(f"Error getting price for {symbol}: {str(e)}")

@tool
def calculate_rsi(symbol:str) -> float:
    """Return RSI Calculation of ticker"""
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=100)).strftime('%Y-%m-%d')
    data = yf.download(symbol, start=start_date, end=end_date)
    delta = data['Adj Close'].diff(1)
    delta = delta[1:]
    up = delta.copy()
    down = delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    avg_gain = up.rolling(window=14).mean()
    avg_loss = abs(down.rolling(window=14).mean())
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    data['RSI'] = rsi
    temp = data['RSI'].iloc[-1]
    rsi = format(temp,".2f")
    return rsi

@tool
def moving_average(ticker:str) -> str:
    """Returns Moving Average of ticker"""
    # Define the function to calculate WMA
    def calculate_wma(prices):
        weights = np.arange(1, 15)
        wma = np.convolve(prices.flatten(), weights.flatten(), mode='valid') / weights.sum()
        return np.concatenate((np.full(13, np.nan), wma), axis=0)

    # Download stock data
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=100)).strftime('%Y-%m-%d')
    data = yf.download(ticker, start=start_date, end=end_date)

    if data.empty:
        return None  # Return None if no data is retrieved

    # Calculate SMA
    data['SMA'] = data['Close'].rolling(window=14).mean()

    # Calculate EMA
    data['EMA'] = data['Close'].ewm(span=14, adjust=False).mean()

    # Calculate WMA
    data['WMA'] = calculate_wma(data['Close'].values)
    mac = format(data['Close'].iloc[-1].item(), ".2f")
    mas = format(data['SMA'].iloc[-1].item(), ".2f")
    mae = format(data['EMA'].iloc[-1].item(), ".2f")
    maw = format(data['WMA'].iloc[-1].item(), ".2f")
    
    if (mac < mas):
      ta1 = f"Closing Value is less than SMA, It may indicate a downtrend. Closing Value : {mac} , SMA : {mas}. "
    else:
      ta1 = f"Closing Value is greater than SMA, It may indicate a uptrend. Closing Value : {mac} , SMA : {mas}. "
    if (mac < mas):
      ta2 = f"Closing Value is less than EMA, It may indicate a downtrend. Closing Value : {mac} , EMA : {mae}. "
    else:
      ta2 = f"Closing Value is greater than EMA, It may indicate a uptrend. Closing Value : {mac} , EMA : {mae}. "
    if (mac < mas):
      ta3 = f"Closing Value is less than WMA, It may indicate a downtrend. Closing Value : {mac} , WMA : {maw}. "
    else:
      ta3 = f"Closing Value is greater than WMA, It may indicate a uptrend. Closing Value : {mac} , WMA : {maw}. "

    x = ta1 + "\n" + ta2 + "\n" + ta3 + "\n"
    return x

@tool
def predict_stock(ticker: str) -> float:
    """Predicts the next day's closing value using ticker"""
    # Fetch historical stock data from Yahoo Finance
    stock_data = yf.download(ticker, period='max')
    
    # Calculate additional features
    stock_data['SMA_50'] = stock_data['Close'].rolling(window=50).mean()
    stock_data['SMA_200'] = stock_data['Close'].rolling(window=200).mean()
    stock_data['Daily_Return'] = stock_data['Close'].pct_change()
    stock_data['Volatility'] = stock_data['Daily_Return'].rolling(window=20).std()
    
    # Add more features
    stock_data['RSI'] = calculateRsi(stock_data['Close'], window=14)
    stock_data['MACD'], stock_data['Signal_Line'] = calculateMacd(stock_data['Close'])
    
    # Drop rows with NaN values
    stock_data.dropna(inplace=True)
    
    # Define features and target variable
    X = stock_data.drop(['Adj Close', 'Close'], axis=1)  # Features
    y = stock_data['Close']  # Target
    
    # Create and train the model using all data
    regressor = RandomForestRegressor(n_estimators=100, max_depth=None, random_state=42)
    regressor.fit(X, y)
    
    # Evaluate the model on all data
    train_score = regressor.score(X, y)
    print(f"R-squared on all data: {train_score:.4f}")
    
    # Make prediction for the next day
    X_latest = X.iloc[-1].to_frame().T
    predicted_price = regressor.predict(X_latest)[0]
    
    return round(predicted_price, 2)

@tool
def candlestick(ticker:str) -> str:
  """ReturnReturns the candlestick pattern as well as its learning by ticker"""
  candlestick_patterns = {
    'CDL2CROWS':'Two Crows',
    'CDL3BLACKCROWS':'Three Black Crows',
    'CDL3INSIDE':'Three Inside Up/Down',
    'CDL3LINESTRIKE':'Three-Line Strike',
    'CDL3OUTSIDE':'Three Outside Up/Down',
    'CDL3STARSINSOUTH':'Three Stars In The South',
    'CDL3WHITESOLDIERS':'Three Advancing White Soldiers',
    'CDLABANDONEDBABY':'Abandoned Baby',
    'CDLADVANCEBLOCK':'Advance Block',
    'CDLBELTHOLD':'Belt-hold',
    'CDLBREAKAWAY':'Breakaway',
    'CDLCLOSINGMARUBOZU':'Closing Marubozu',
    'CDLCONCEALBABYSWALL':'Concealing Baby Swallow',
    'CDLCOUNTERATTACK':'Counterattack',
    'CDLDARKCLOUDCOVER':'Dark Cloud Cover',
    'CDLDOJI':'Doji',
    'CDLDOJISTAR':'Doji Star',
    'CDLDRAGONFLYDOJI':'Dragonfly Doji',
    'CDLENGULFING':'Engulfing Pattern',
    'CDLEVENINGDOJISTAR':'Evening Doji Star',
    'CDLEVENINGSTAR':'Evening Star',
    'CDLGAPSIDESIDEWHITE':'Up/Down-gap side-by-side white lines',
    'CDLGRAVESTONEDOJI':'Gravestone Doji',
    'CDLHAMMER':'Hammer',
    'CDLHANGINGMAN':'Hanging Man',
    'CDLHARAMI':'Harami Pattern',
    'CDLHARAMICROSS':'Harami Cross Pattern',
    'CDLHIGHWAVE':'High-Wave Candle',
    'CDLHIKKAKE':'Hikkake Pattern',
    'CDLHIKKAKEMOD':'Modified Hikkake Pattern',
    'CDLHOMINGPIGEON':'Homing Pigeon',
    'CDLIDENTICAL3CROWS':'Identical Three Crows',
    'CDLINNECK':'In-Neck Pattern',
    'CDLINVERTEDHAMMER':'Inverted Hammer',
    'CDLKICKING':'Kicking',
    'CDLKICKINGBYLENGTH':'Kicking - bull/bear determined by the longer marubozu',
    'CDLLADDERBOTTOM':'Ladder Bottom',
    'CDLLONGLEGGEDDOJI':'Long Legged Doji',
    'CDLLONGLINE':'Long Line Candle',
    'CDLMARUBOZU':'Marubozu',
    'CDLMATCHINGLOW':'Matching Low',
    'CDLMATHOLD':'Mat Hold',
    'CDLMORNINGDOJISTAR':'Morning Doji Star',
    'CDLMORNINGSTAR':'Morning Star',
    'CDLONNECK':'On-Neck Pattern',
    'CDLPIERCING':'Piercing Pattern',
    'CDLRICKSHAWMAN':'Rickshaw Man',
    'CDLRISEFALL3METHODS':'Rising/Falling Three Methods',
    'CDLSEPARATINGLINES':'Separating Lines',
    'CDLSHOOTINGSTAR':'Shooting Star',
    'CDLSHORTLINE':'Short Line Candle',
    'CDLSPINNINGTOP':'Spinning Top',
    'CDLSTALLEDPATTERN':'Stalled Pattern',
    'CDLSTICKSANDWICH':'Stick Sandwich',
    'CDLTAKURI':'Takuri (Dragonfly Doji with very long lower shadow)',
    'CDLTASUKIGAP':'Tasuki Gap',
    'CDLTHRUSTING':'Thrusting Pattern',
    'CDLTRISTAR':'Tristar Pattern',
    'CDLUNIQUE3RIVER':'Unique 3 River',
    'CDLUPSIDEGAP2CROWS':'Upside Gap Two Crows',
    'CDLXSIDEGAP3METHODS':'Upside/Downside Gap Three Methods'
  }
  start_date = datetime.today() - timedelta(days=100)
  df = yf.download(ticker, start=start_date, end=datetime.today())
  df = df.reset_index()
  df=df.drop(columns=['Adj Close','Volume'])
  for pattern, pattern_name in candlestick_patterns.items():
      pattern_result = getattr(talib, pattern)(df['Open'], df['High'], df['Low'], df['Close'])
      df[pattern_name] = pattern_result.astype(bool)
  data=df
  data['PositiveEngulfing'] = data['Engulfing Pattern'] > 0
  data['NegativeEngulfing'] = data['Engulfing Pattern'] < 0
  data.drop(columns=['Engulfing Pattern'])
  pattern_trend = {
    'Two Crows': 'bearish',
    'Three Black Crows': 'bearish',
    'Three Inside Up/Down': 'bullish/bearish',
    'Three-Line Strike': 'bullish/bearish',
    'Three Outside Up/Down': 'bullish/bearish',
    'Three Stars In The South': 'bullish',
    'Three Advancing White Soldiers': 'bullish',
    'Abandoned Baby': 'bullish',
    'Advance Block': 'bearish',
    'Belt-hold': 'bullish',
    'Breakaway': 'bullish',
    'Closing Marubozu': 'bullish',
    'Concealing Baby Swallow': 'bullish',
    'Counterattack': 'bullish',
    'Dark Cloud Cover': 'bearish',
    'Doji': 'neutral',
    'Doji Star': 'neutral',
    'Dragonfly Doji': 'bullish',
    'Engulfing Pattern': 'bullish',
    'Evening Doji Star': 'bearish',
    'Evening Star': 'bearish',
    'Up/Down-gap side-by-side white lines': 'bullish',
    'Gravestone Doji': 'bearish',
    'Hammer': 'bullish',
    'Hanging Man': 'bearish',
    'Harami Pattern': 'bullish',
    'Harami Cross Pattern': 'bullish',
    'High-Wave Candle': 'neutral',
    'Hikkake Pattern': 'neutral',
    'Modified Hikkake Pattern': 'neutral',
    'Homing Pigeon': 'bullish',
    'Identical Three Crows': 'bearish',
    'In-Neck Pattern': 'bearish',
    'Inverted Hammer': 'bullish',
    'Kicking': 'bullish',
    'Kicking - bull/bear determined by the longer marubozu': 'bullish',
    'Ladder Bottom': 'bullish',
    'Long Legged Doji': 'neutral',
    'Long Line Candle': 'neutral',
    'Marubozu': 'bullish',
    'Matching Low': 'bullish',
    'Mat Hold': 'bullish',
    'Morning Doji Star': 'bullish',
    'Morning Star': 'bullish',
    'On-Neck Pattern': 'bearish',
    'Piercing Pattern': 'bullish',
    'Rickshaw Man': 'neutral',
    'Rising/Falling Three Methods': 'bullish',
    'Separating Lines': 'bullish',
    'Shooting Star': 'bearish',
    'Short Line Candle': 'neutral',
    'Spinning Top': 'neutral',
    'Stalled Pattern': 'neutral',
    'Stick Sandwich': 'neutral',
    'Takuri (Dragonfly Doji with very long lower shadow)': 'bullish',
    'Tasuki Gap': 'neutral',
    'Thrusting Pattern': 'bullish',
    'Tristar Pattern': 'neutral',
    'Unique 3 River': 'bullish',
    'Upside Gap Two Crows': 'bearish',
    'Upside/Downside Gap Three Methods': 'bullish',
    'PositiveEngulfing': 'bullish',
    'NegativeEngulfing': 'bearish'
  }
  pattern_columns = data.columns[5:]

  latest_dates = {}

  for column in pattern_columns:
      pattern_data = data[data[column]]
      if not pattern_data.empty:
          latest_date = pattern_data['Date'].iloc[-1]
          latest_dates[column] = latest_date

  Candle_DF = pd.DataFrame(list(latest_dates.items()), columns=['Date','Pattern'])
  Candle_DF_sorted = Candle_DF.sort_values(by='Date', ascending=True)
  latest_row = Candle_DF_sorted.loc[2]
  latest_date = latest_row['Date']
  latest_pattern = latest_row['Pattern']
  if not latest_pattern:
    x=f'Latest Date: {latest_pattern} \nPattern: {latest_date} \nTrend: {pattern_trend[latest_date]}'
    return x
  else:
    return "No significant candlestick patterns detected."
