import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.express as px

# --- הגדרות תצוגת העמוד ועיצוב יוקרתי (CSS) ---
st.set_page_config(page_title="Quantum Backtest Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    /* עיצוב כהה ויוקרתי (Dark & Gold) */
    .stApp {
        background-color: #0E1117;
        color: #C5C5C5;
    }
    h1, h2, h3 {
        color: #D4AF37 !important; /* צבע זהב יוקרתי */
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stButton>button {
        background-color: #D4AF37;
        color: #0E1117;
        font-weight: bold;
        border-radius: 5px;
        border: none;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #F3E5AB;
        color: #000000;
        box-shadow: 0px 0px 15px rgba(212, 175, 55, 0.5);
    }
    div[data-testid="metric-container"] {
        background-color: #1A1C24;
        border: 1px solid #333;
        border-right: 4px solid #D4AF37;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #333;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- מאגר נכסים ושווי נקודה ---
ASSETS = {
    "נאסד''ק (NQ=F)": {"ticker": "NQ=F", "point_value": 20},
    "מיקרו נאסד''ק (MNQ=F)": {"ticker": "MNQ=F", "point_value": 2},
    "S&P 500 (ES=F)": {"ticker": "ES=F", "point_value": 50},
    "מיקרו S&P (MES=F)": {"ticker": "MES=F", "point_value": 5},
    "זהב (GC=F)": {"ticker": "GC=F", "point_value": 100},
    "נפט גולמי (CL=F)": {"ticker": "CL=F", "point_value": 1000}
}

# --- מנוע הבקטסט ---
def run_strategy(ticker, point_value, period):
    asset = yf.Ticker(ticker)
    data = asset.history(period=period, interval="15m")
        
    if data.empty:
        return pd.DataFrame()

    if data.index.tz is None:
        data.index = data.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        data.index = data.index.tz_convert('America/New_York')

    results = []
    grouped = data.groupby(data.index.date)
    
    for date, df_day in grouped:
        # כל הנכסים נבדקים על בסיס שעת פתיחת וול סטריט (09:30 EST)
        df_day = df_day.between_time('09:30', '16:00')
        
        if len(df_day) < 4:
            continue
            
        c1 = df_day.iloc[0] # 09:30
        c2 = df_day.iloc[1] # 09:45
        c3 = df_day.iloc[2] # 10:00
        c4 = df_day.iloc[3] # 10:15
        
        c1_open, c1_close, c1_high, c1_low = c1['Open'], c1['Close'], c1['High'], c1['Low']
        c2_high, c2_low = c2['High'], c2['Low']
        c3_high, c3_low = c3['High'], c3['Low']
        c4_open, c4_high, c4_low = c4['Open'], c4['High'], c4['Low']
        
        trade_type = None
        entry_price, exit_price, stop_loss, pnl_points = 0.0, 0.0, 0.0, 0.0
        
        # --- אסטרטגיית לונג ---
        if c1_close > c1_open:
            if c2_high > c1_high:
                trade_type = 'Long'
                entry_price = c1_high
                stop_loss = c1_low
                
                if c2_low <= stop_loss:
                    exit_price = stop_loss
                else:
                    best_price = max(c3_high, c4_high)
                    if best_price > entry_price:
                        exit_price = best_price
                    else:
                        if c3_low <= stop_loss:
                            exit_price = stop_loss
                        else:
                            exit_price = c4_open
                
                pnl_points = exit_price - entry_price

        # --- אסטרטגיית שורט ---
        elif c1_close < c1_open:
            if c2_low < c1_low:
                trade_type = 'Short'
                entry_price = c1_low
                stop_loss = c1_high
                
                if c2_high >= stop_loss:
                    exit_price = stop_loss
                else:
                    best_price = min(c3_low, c4_low)
                    if best_price < entry_price:
                        exit_price = best_price
                    else:
                        if c3_high >= stop_loss:
                            exit_price = stop_loss
                        else:
                            exit_price = c4_open
                            
                pnl_points = entry_price - exit_price

        if trade_type:
            pnl_money = pnl_points * point_value
            pnl_pct = (pnl_points / entry_price) * 100
            
            results.append({
                'Date': date.strftime('%Y-%m-%d'),
                'Type': trade_type,
                'Entry Price': round(entry_price, 2),
                'Exit Price': round(exit_price, 2),
                'Stop Loss': round(stop_loss, 2),
                'PnL Points': round(pnl_points, 2),
                'PnL %': round(pnl_pct, 3),
                'PnL ($)': round(pnl_money, 2)
            })

    return pd.DataFrame(results)

# --- ממשק משתמש (UI) ---
st.title("🏛️ מערכת בקטסט מוסדית - פריצת טווח פתיחה")
st.markdown("בדוק והשווה ביצועי מומנטום פתיחה (09:30 EST) על חוזים עתידיים שונים.")

# סרגל צד להגדרות
with st.sidebar:
    st.header("⚙️ הגדרות סימולציה")
    
    selected_assets = st.multiselect(
        "בחר נכסים לבדיקה והשוואה:",
        list(ASSETS.keys()),
        default=["נאסד''ק (NQ=F)", "S&P 500 (ES=F)", "זהב (GC=F)"]
    )
    
    selected_period = st.selectbox(
        "בחר טווח זמן לאחור:",
        options=["5d", "1mo", "60d"],
        index=1,
        help="Yahoo Finance מגבילים שליפת נרות של 15 דקות לעד 60 יום לאחור בחינם."
    )
    
    run_btn = st.button("🚀 הפעל סימולציה")

# --- הפעלת הבדיקה והצגת התוצאות ---
if run_btn:
    if not selected_assets:
        st.warning("אנא בחר לפחות נכס אחד לבדיקה.")
    else:
        with st.spinner("מנתח נתוני שוק ומריץ אלגוריתם..."):
            all_results = {}
            summary_data = []
            
            for asset_name in selected_assets:
                ticker = ASSETS[asset_name]["ticker"]
                pt_val = ASSETS[asset_name]["point_value"]
                
                df = run_strategy(ticker, pt_val, selected_period)
                all_results[asset_name] = df
                
                if not df.empty:
                    total_profit = df['PnL ($)'].sum()
                    win_rate = (len(df[df['PnL ($)'] > 0]) / len(df)) * 100 if len(df) > 0 else 0
                    summary_data.append({
                        "נכס": asset_name,
                        "רווח כולל ($)": total_profit,
                        "אחוז הצלחה (%)": win_rate,
                        "מספר עסקאות": len(df)
                    })

            # --- הצגת הנתונים ---
            if summary_data:
                st.success("הסימולציה הושלמה בהצלחה!")
                summary_df = pd.DataFrame(summary_data)
                
                # יצירת טאבים להפרדה ויזואלית
                tabs = st.tabs(["📊 השוואת נכסים"] + selected_assets)
                
                # טאב השוואה מרכזי
                with tabs[0]:
                    st.subheader("סיכום ביצועים כולל")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        # גרף עמודות יוקרתי של רווחים
                        fig = px.bar(summary_df, x="נכס", y="רווח כולל ($)", color="נכס", 
                                     title="השוואת רווחים (PnL) בדולרים", text_auto='.2s')
                        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#D4AF37")
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        st.dataframe(summary_df.style.format({"רווח כולל ($)": "${:,.2f}", "אחוז הצלחה (%)": "{:.1f}%"}), 
                                     use_container_width=True, hide_index=True)

                # טאבים אישיים לכל נכס
                for i, asset_name in enumerate(selected_assets):
                    with tabs[i+1]:
                        df_asset = all_results[asset_name]
                        if df_asset.empty:
                            st.info(f"לא נמצאו עסקאות שעמדו בתנאים עבור {asset_name}.")
                        else:
                            # כרטיסיות נתונים לנכס (Metrics)
                            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
                            total_pnl = df_asset['PnL ($)'].sum()
                            win_pct = (len(df_asset[df_asset['PnL ($)'] > 0]) / len(df_asset)) * 100
                            
                            metrics_col1.metric("רווח נקי ($)", f"${total_pnl:,.2f}")
                            metrics_col2.metric("אחוזי פגיעה", f"{win_pct:.1f}%")
                            metrics_col3.metric("סה''כ עסקאות", len(df_asset))
                            
                            st.divider()
                            st.write("יומן עסקאות מלא:")
                            # עיצוב הטבלה להבלטת רווחים והפסדים
                            st.dataframe(
                                df_asset.style.map(lambda x: 'color: #00FF00' if x > 0 else 'color: #FF0000', subset=['PnL ($)', 'PnL %']),
                                use_container_width=True, 
                                hide_index=True
                            )
            else:
                st.error("לא נמצאו נתונים לאף אחד מהנכסים שנבחרו. נסה לשנות את טווח הזמן.")
