import yfinance as yf
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# --- הגדרות תצוגת העמוד ועיצוב יוקרתי ---
st.set_page_config(page_title="Quantum Institutional Backtest", layout="wide", initial_sidebar_state="expanded")

# קוד CSS מתקדם לעיצוב פרימיום
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Heebo', sans-serif;
    }
    
    /* רקע המערכת - מעבר צבעים כהה ויוקרתי */
    .stApp {
        background: linear-gradient(135deg, #0B0E14 0%, #1A1E29 100%);
        color: #E2E8F0;
    }
    
    /* עיצוב כותרות בזהב פלטינה */
    h1, h2, h3 {
        color: #D4AF37 !important;
        text-shadow: 0px 2px 4px rgba(0,0,0,0.5);
    }
    
    /* עיצוב סרגל הצד (Sidebar) באפקט זכוכית */
    [data-testid="stSidebar"] {
        background-color: rgba(11, 14, 20, 0.85);
        border-right: 1px solid rgba(212, 175, 55, 0.2);
        backdrop-filter: blur(10px);
    }
    
    /* כפתור הרצה יוקרתי */
    .stButton>button {
        background: linear-gradient(90deg, #D4AF37 0%, #F9E596 50%, #D4AF37 100%);
        color: #000000 !important;
        font-weight: 800;
        font-size: 1.1rem;
        border: none;
        border-radius: 8px;
        padding: 10px 0;
        transition: all 0.4s ease;
        box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3);
        width: 100%;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(212, 175, 55, 0.6);
    }
    
    /* קוביות נתונים (Metrics) עם אפקט מודרני */
    div[data-testid="metric-container"] {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-right: 4px solid #D4AF37;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(4px);
        transition: transform 0.3s;
    }
    div[data-testid="metric-container"]:hover {
        transform: scale(1.02);
        border-right-color: #F9E596;
    }
    
    /* קווים מפרידים */
    hr {
        border-color: rgba(212, 175, 55, 0.2) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- מאגר נכסים ---
ASSETS = {
    "מיקרו נאסד''ק רציף (MNQ=F)": {"ticker": "MNQ=F", "point_value": 2},
    "נאסד''ק רציף (NQ=F)": {"ticker": "NQ=F", "point_value": 20},
    "S&P 500 מיקרו (MES=F)": {"ticker": "MES=F", "point_value": 5},
    "זהב (GC=F)": {"ticker": "GC=F", "point_value": 100}
}

# --- מנוע הבקטסט הכולל מעקב שקיפות ---
def run_strategy(ticker, point_value, period):
    asset = yf.Ticker(ticker)
    data = asset.history(period=period, interval="15m")
        
    if data.empty:
        return pd.DataFrame(), pd.DataFrame()

    if data.index.tz is None:
        data.index = data.index.tz_localize('UTC').tz_convert('America/New_York')
    else:
        data.index = data.index.tz_convert('America/New_York')

    trades_results = []
    daily_log = [] # יומן שקוף שעוקב אחרי כל יום מסחר
    
    grouped = data.groupby(data.index.date)
    
    for date, df_day in grouped:
        date_str = date.strftime('%Y-%m-%d')
        df_day = df_day.between_time('09:30', '16:00')
        
        # סינון ימים ללא מספיק נרות
        if len(df_day) < 4:
            daily_log.append({'תאריך': date_str, 'סטטוס': 'התעלמות', 'פירוט/סיבה': 'אין מספיק נרות שוק ביום זה (חג/סגירה מוקדמת)'})
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
        reason = ""
        
        # --- בדיקת לונג ---
        if c1_close > c1_open:
            if c2_high > c1_high:
                trade_type = 'Long'
                reason = "כניסה ללונג (פריצת נר ראשון ירוק)"
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
            else:
                daily_log.append({'תאריך': date_str, 'סטטוס': 'ללא עסקה', 'פירוט/סיבה': 'הנר הראשון היה ירוק, אך הנר השני לא הצליח לפרוץ את הגבוה שלו'})

        # --- בדיקת שורט ---
        elif c1_close < c1_open:
            if c2_low < c1_low:
                trade_type = 'Short'
                reason = "כניסה לשורט (שבירת נר ראשון אדום)"
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
            else:
                daily_log.append({'תאריך': date_str, 'סטטוס': 'ללא עסקה', 'פירוט/סיבה': 'הנר הראשון היה אדום, אך הנר השני לא שבר את הנמוך שלו'})
        else:
            daily_log.append({'תאריך': date_str, 'סטטוס': 'ללא עסקה', 'פירוט/סיבה': "הנר הראשון היה דוג'י (שער פתיחה = שער סגירה). אין כיוון."})

        # אם התבצעה עסקה, נוסיף ליומן ולרשימת התוצאות
        if trade_type:
            pnl_money = pnl_points * point_value
            
            # הוספה ליומן המעקב
            daily_log.append({
                'תאריך': date_str, 
                'סטטוס': 'בוצעה עסקה ✓', 
                'פירוט/סיבה': f"{reason}. תוצאה: {'רווח' if pnl_money > 0 else 'הפסד'} של ${round(pnl_money, 2)}"
            })
            
            # הוספה לטבלת העסקאות הפעילות
            trades_results.append({
                'Date': date_str,
                'Type': trade_type,
                'Entry Price': round(entry_price, 2),
                'Exit Price': round(exit_price, 2),
                'Stop Loss': round(stop_loss, 2),
                'PnL ($)': round(pnl_money, 2)
            })

    return pd.DataFrame(trades_results), pd.DataFrame(daily_log)

# --- ממשק משתמש (UI) ---
st.title("🏦 Quantum Analytics | Backtest Engine")
st.markdown("מערכת אלגוריתמית מתקדמת לניתוח מומנטום פתיחה בשוק האמריקאי (09:30 EST).")

with st.sidebar:
    st.header("⚙️ קונפיגורציית אלגוריתם")
    
    selected_assets = st.multiselect(
        "בחר נכס לבדיקה:",
        list(ASSETS.keys()),
        default=["מיקרו נאסד''ק רציף (MNQ=F)"]
    )
    
    selected_period = st.selectbox(
        "בחר טווח זמן לאחור:",
        options=["5d", "1mo", "60d"],
        index=1,
        help="שימו לב: API חינמי (Yahoo) תומך בנרות של 15 דקות עד 60 ימים לאחור בלבד."
    )
    
    run_btn = st.button("הפעל מנוע חישוב 🚀")

if run_btn:
    if not selected_assets:
        st.warning("אנא בחר לפחות נכס אחד לבדיקה.")
    else:
        with st.spinner("מנתח נתוני עומק, מחשב הסתברויות ומכין דוחות..."):
            
            for asset_name in selected_assets:
                ticker = ASSETS[asset_name]["ticker"]
                pt_val = ASSETS[asset_name]["point_value"]
                
                df_trades, df_log = run_strategy(ticker, pt_val, selected_period)
                
                st.markdown(f"### דו''ח ביצועים: {asset_name}")
                
                if df_trades.empty:
                    st.info("לא נמצאו עסקאות שעמדו בתנאים הקשיחים בטווח הזמן שנבחר.")
                    if not df_log.empty:
                        st.write("יומן מעקב לימים שנבדקו:")
                        st.dataframe(df_log, use_container_width=True, hide_index=True)
                else:
                    total_pnl = df_trades['PnL ($)'].sum()
                    win_pct = (len(df_trades[df_trades['PnL ($)'] > 0]) / len(df_trades)) * 100
                    
                    # קוביות נתונים יוקרתיות
                    col1, col2, col3 = st.columns(3)
                    col1.metric("סה''כ רווח/הפסד נקי ($)", f"${total_pnl:,.2f}")
                    col2.metric("אחוזי הצלחה (Win Rate)", f"{win_pct:.1f}%")
                    col3.metric("מספר עסקאות שהושלמו", len(df_trades))
                    
                    st.divider()
                    
                    # טאבים מודרניים
                    tab1, tab2 = st.tabs(["📊 יומן עסקאות פעילות", "🔍 יומן שקיפות מלא (כל ימי המסחר)"])
                    
                    with tab1:
                        # צביעת רווחים/הפסדים בטבלת העסקאות
                        styled_trades = df_trades.style.map(
                            lambda x: 'color: #00FF00; font-weight: bold;' if x > 0 else 'color: #FF4444; font-weight: bold;', 
                            subset=['PnL ($)']
                        )
                        st.dataframe(styled_trades, use_container_width=True, hide_index=True)
                        
                        # גרף עקומת הון (Equity Curve) יוקרתי
                        df_trades['Cumulative PnL'] = df_trades['PnL ($)'].cumsum()
                        fig = px.area(df_trades, x='Date', y='Cumulative PnL', title="עקומת הון מצטברת (Equity Curve)")
                        fig.update_traces(line_color='#D4AF37', fillcolor='rgba(212, 175, 55, 0.1)')
                        fig.update_layout(
                            plot_bgcolor="rgba(0,0,0,0)", 
                            paper_bgcolor="rgba(0,0,0,0)", 
                            font_color="#E2E8F0",
                            xaxis_title="תאריך",
                            yaxis_title="רווח מצטבר ($)"
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    with tab2:
                        st.markdown("כאן ניתן לראות מעקב מדויק על **כל יום מסחר**, ולהבין מדוע האלגוריתם החליט שלא להיכנס לפוזיציה בימים מסוימים.")
                        # עיצוב טבלת השקיפות
                        def color_status(val):
                            if 'בוצעה עסקה' in str(val): return 'color: #D4AF37; font-weight: bold;'
                            if 'ללא עסקה' in str(val): return 'color: #888888;'
                            return ''
                        
                        styled_log = df_log.style.map(color_status, subset=['סטטוס'])
                        st.dataframe(styled_log, use_container_width=True, hide_index=True)
