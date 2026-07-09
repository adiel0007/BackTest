import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- הגדרות הבוט ---
TICKER = "MNQU26.CME"      # חוזה מיקרו נאסדק לספטמבר 2026
POINT_VALUE = 2             # 2$ לנקודה בחוזה מיקרו
DAYS_BACK = 30               # נבדוק לאחור 30 ימים
INTERVAL = "15m"             # נרות 15 דקות
TIMEZONE = "America/New_York"  # שעון ניו יורק

st.set_page_config(page_title="בקטסט - פריצת נר פתיחה", layout="wide", page_icon="📈")

# ---------------------------------------------------------------------------
# עיצוב (CSS)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    html, body, [class*="css"]  {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', Tahoma, sans-serif;
    }
    .main {
        background: linear-gradient(180deg, #0e1117 0%, #10141c 100%);
    }
    .hero {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #2d3646;
        border-radius: 18px;
        padding: 28px 32px;
        margin-bottom: 24px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.35);
    }
    .hero h1 {
        margin: 0;
        font-size: 30px;
        background: linear-gradient(90deg, #60a5fa, #34d399);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero p {
        color: #9ca3af;
        margin-top: 8px;
        font-size: 15px;
    }
    div[data-testid="stMetric"] {
        background: #161b26;
        border: 1px solid #2d3646;
        border-radius: 14px;
        padding: 14px 18px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.25);
    }
    div[data-testid="stMetricLabel"] { color: #9ca3af; }
    .stButton>button {
        background: linear-gradient(90deg, #2563eb, #10b981);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 26px;
        font-weight: 600;
        font-size: 15px;
    }
    .stButton>button:hover {
        opacity: 0.9;
        color: white;
    }
    .stDataFrame { border-radius: 12px; overflow: hidden; }
    .section-title {
        font-size: 20px;
        font-weight: 700;
        margin: 22px 0 10px 0;
        color: #e5e7eb;
        border-right: 4px solid #34d399;
        padding-right: 10px;
    }
</style>
""", unsafe_allow_html=True)


def get_data_and_calculate():
    """מושך נתונים ומריץ את אסטרטגיית פריצת נר הפתיחה.
    מחזיר: (df_trades, debug_log) — הלוג מסביר מה קרה בכל יום, כולל ימים ללא עסקה."""

    end_date = datetime.now()
    start_date = end_date - timedelta(days=DAYS_BACK)

    ticker_obj = yf.Ticker(TICKER)
    df = ticker_obj.history(start=start_date, end=end_date, interval=INTERVAL)

    if df.empty:
        st.error("לא נמצאו נתונים. נסה לשנות את הסימול ל-'MNQ=F' עבור החוזה הרציף.")
        return pd.DataFrame(), []

    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert(TIMEZONE)
    else:
        df.index = df.index.tz_convert(TIMEZONE)

    trades = []
    debug_log = []

    df['Date'] = df.index.date
    grouped = df.groupby('Date')

    for date, day_data in grouped:
        market_hours = day_data.between_time('09:30', '16:00')

        if len(market_hours) < 4:
            debug_log.append({
                'תאריך': date.strftime('%Y-%m-%d'),
                'תוצאה': 'דולג',
                'סיבה': f'רק {len(market_hours)} נרות זמינים ביום זה (נדרשים 4+)'
            })
            continue

        c1 = market_hours.iloc[0]
        c2 = market_hours.iloc[1]
        c3 = market_hours.iloc[2]
        c4 = market_hours.iloc[3]

        trade_type = None
        entry_price = stop_loss = exit_price = 0
        reason = ""

        is_green_c1 = c1['Close'] > c1['Open']
        is_red_c1 = c1['Close'] < c1['Open']

        # -- לונג --
        if is_green_c1:
            if c2['High'] > c1['High']:
                trade_type = 'Long'
                entry_price = c1['High']
                stop_loss = c1['Low']
                if c2['Low'] <= stop_loss or c3['Low'] <= stop_loss:
                    exit_price = stop_loss
                else:
                    best_price = max(c3['High'], c4['High'])
                    exit_price = best_price if best_price > entry_price else c4['Open']
            else:
                reason = 'נר 1 ירוק, אך נר 2 לא פרץ את השיא שלו — אין כניסה'

        # -- שורט --
        elif is_red_c1:
            if c2['Low'] < c1['Low']:
                trade_type = 'Short'
                entry_price = c1['Low']
                stop_loss = c1['High']
                if c2['High'] >= stop_loss or c3['High'] >= stop_loss:
                    exit_price = stop_loss
                else:
                    best_price = min(c3['Low'], c4['Low'])
                    exit_price = best_price if best_price < entry_price else c4['Open']
            else:
                reason = 'נר 1 אדום, אך נר 2 לא פרץ את השפל שלו — אין כניסה'

        else:
            reason = 'נר 1 ניטרלי (דוג׳י, Close==Open) — אין ירוק ואין אדום, האסטרטגיה לא מוגדרת ליום כזה'

        if trade_type:
            if trade_type == 'Long':
                points = exit_price - entry_price
            else:
                points = entry_price - exit_price
            pct_return = (points / entry_price) * 100
            pnl = points * POINT_VALUE

            trades.append({
                'תאריך': date.strftime('%Y-%m-%d'),
                'סוג עסקה': trade_type,
                'מחיר כניסה': round(entry_price, 2),
                'סטופ לוס': round(stop_loss, 2),
                'מחיר יציאה': round(exit_price, 2),
                'נקודות (רווח/הפסד)': round(points, 2),
                'אחוזים (%)': round(pct_return, 2),
                'דולרים ($)': round(pnl, 2)
            })
            debug_log.append({
                'תאריך': date.strftime('%Y-%m-%d'),
                'תוצאה': f'עסקת {trade_type}',
                'סיבה': f"נר1 {'ירוק' if is_green_c1 else 'אדום'}, פריצה אושרה בנר 2"
            })
        else:
            debug_log.append({
                'תאריך': date.strftime('%Y-%m-%d'),
                'תוצאה': 'ללא עסקה',
                'סיבה': reason
            })

    return pd.DataFrame(trades), debug_log


# ---------------------------------------------------------------------------
# ממשק המשתמש
# ---------------------------------------------------------------------------
st.markdown("""
<div class="hero">
    <h1>🤖 בוט בקטסט — פריצת נר פתיחה בנאסדק</h1>
    <p>אסטרטגיה: לונג/שורט בפריצת נר ראשון (15 דק'). יציאה מקסימלית ברווח בנרות 3-4 או בפתיחת נר 4, בכפוף לסטופ.</p>
</div>
""", unsafe_allow_html=True)

run = st.button("🚀 הרץ בדיקת בקטסט עכשיו", type="primary")

if run:
    with st.spinner("מושך נתונים ומחשב..."):
        df_trades, debug_log = get_data_and_calculate()

    if not df_trades.empty:
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades['דולרים ($)'] > 0])
        win_rate = (winning_trades / total_trades) * 100
        total_profit = df_trades['דולרים ($)'].sum()
        avg_win = df_trades[df_trades['דולרים ($)'] > 0]['דולרים ($)'].mean() if winning_trades else 0
        avg_loss = df_trades[df_trades['דולרים ($)'] <= 0]['דולרים ($)'].mean() if (total_trades - winning_trades) else 0

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("כמות עסקאות", total_trades)
        col2.metric("אחוזי הצלחה", f"{win_rate:.1f}%")
        col3.metric("רווח/הפסד כולל", f"${total_profit:,.2f}")
        col4.metric("רווח ממוצע", f"${avg_win:,.2f}" if winning_trades else "—")
        col5.metric("הפסד ממוצע", f"${avg_loss:,.2f}" if (total_trades - winning_trades) else "—")

        st.markdown('<div class="section-title">📈 עקומת הון (Equity Curve)</div>', unsafe_allow_html=True)
        eq = df_trades['דולרים ($)'].cumsum()
        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(
            x=df_trades['תאריך'], y=eq, mode='lines+markers',
            line=dict(color='#34d399', width=3),
            marker=dict(size=6, color='#60a5fa'),
            fill='tozeroy', fillcolor='rgba(52,211,153,0.08)'
        ))
        fig_eq.update_layout(
            template='plotly_dark', height=380,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(fig_eq, use_container_width=True)

        c_a, c_b = st.columns([1, 1])
        with c_a:
            st.markdown('<div class="section-title">🥧 יחס הצלחה/כישלון</div>', unsafe_allow_html=True)
            fig_pie = go.Figure(data=[go.Pie(
                labels=['רווחיות', 'הפסדיות'],
                values=[winning_trades, total_trades - winning_trades],
                marker=dict(colors=['#34d399', '#f87171']),
                hole=0.55
            )])
            fig_pie.update_layout(
                template='plotly_dark', height=320,
                paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with c_b:
            st.markdown('<div class="section-title">📊 לונג מול שורט</div>', unsafe_allow_html=True)
            counts = df_trades['סוג עסקה'].value_counts()
            fig_bar = go.Figure(data=[go.Bar(
                x=counts.index, y=counts.values,
                marker_color=['#60a5fa', '#f472b6']
            )])
            fig_bar.update_layout(
                template='plotly_dark', height=320,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown('<div class="section-title">📋 יומן עסקאות מלא</div>', unsafe_allow_html=True)
        st.dataframe(df_trades, use_container_width=True)

        st.markdown('<div class="section-title">🔍 לוג אבחון יומי (עונה על: "למה לא נכנס?")</div>', unsafe_allow_html=True)
        st.caption("כאן רואים לכל יום — כולל ימים ללא עסקה — מה בדיוק הבוט ראה ולמה החליט להיכנס או לא.")
        st.dataframe(pd.DataFrame(debug_log), use_container_width=True)

    else:
        st.warning("לא היו עסקאות בטווח שנבדק התואמות לתנאים.")
        if debug_log:
            st.markdown('<div class="section-title">🔍 לוג אבחון יומי</div>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(debug_log), use_container_width=True)
else:
    st.info("לחץ על הכפתור כדי להריץ את הבקטסט.")