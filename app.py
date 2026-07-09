import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- הגדרות כלליות ---
TIMEZONE = "America/New_York"
INTERVAL = "15m"          # yahoo מגביל נתוני 15 דק' ל-60 יום אחורה בלבד

INSTRUMENTS = {
    "נאסדק 100 (Micro - MNQ)": {"ticker": "MNQ=F", "point_value": 2,   "color": "#60a5fa"},
    "S&P 500 (Micro - MES)":    {"ticker": "MES=F", "point_value": 5,   "color": "#34d399"},
    "זהב (Micro Gold - MGC)":   {"ticker": "MGC=F", "point_value": 10,  "color": "#d4af37"},
    "נפט גולמי (Micro - MCL)":  {"ticker": "MCL=F", "point_value": 100, "color": "#f87171"},
}

LOOKBACK_OPTIONS = {
    "7 ימים": 7, "14 ימים": 14, "30 ימים": 30, "45 ימים": 45, "60 ימים": 60
}

st.set_page_config(page_title="Quant Desk | בקטסט אסטרטגיות", layout="wide", page_icon="💎")

# ---------------------------------------------------------------------------
# עיצוב יוקרתי
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        direction: rtl;
        text-align: right;
        font-family: 'Inter', sans-serif;
    }
    .stApp {
        background: radial-gradient(circle at 20% 0%, #14131a 0%, #07070b 55%, #050506 100%);
    }
    #MainMenu, footer, header {visibility: hidden;}

    .hero {
        background: linear-gradient(135deg, rgba(212,175,55,0.10) 0%, rgba(15,15,20,0.9) 60%);
        border: 1px solid rgba(212,175,55,0.35);
        border-radius: 20px;
        padding: 34px 40px;
        margin-bottom: 28px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04);
        position: relative;
        overflow: hidden;
    }
    .hero::before {
        content: "";
        position: absolute; top: -60%; right: -10%;
        width: 300px; height: 300px;
        background: radial-gradient(circle, rgba(212,175,55,0.25) 0%, transparent 70%);
    }
    .hero .kicker {
        color: #d4af37;
        letter-spacing: 4px;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    .hero h1 {
        margin: 0;
        font-family: 'Playfair Display', serif;
        font-size: 36px;
        font-weight: 700;
        color: #f5f2e9;
        letter-spacing: 0.5px;
    }
    .hero p {
        color: #9a978d;
        margin-top: 10px;
        font-size: 15px;
    }

    .panel {
        background: linear-gradient(180deg, #121116 0%, #0c0b10 100%);
        border: 1px solid rgba(212,175,55,0.18);
        border-radius: 16px;
        padding: 22px 24px;
        margin-bottom: 22px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.4);
    }

    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, #16151b 0%, #0e0d12 100%);
        border: 1px solid rgba(212,175,55,0.25);
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.4);
    }
    div[data-testid="stMetricLabel"] { color: #a7a396; font-weight: 500; }
    div[data-testid="stMetricValue"] { color: #f5f2e9; font-family: 'Playfair Display', serif; }

    .stButton>button {
        background: linear-gradient(90deg, #d4af37, #b8860b);
        color: #0a0a0c;
        border: none;
        border-radius: 10px;
        padding: 12px 30px;
        font-weight: 700;
        font-size: 15px;
        letter-spacing: 0.5px;
        box-shadow: 0 8px 20px rgba(212,175,55,0.25);
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 26px rgba(212,175,55,0.4);
        color: #0a0a0c;
    }

    .section-title {
        font-family: 'Playfair Display', serif;
        font-size: 22px;
        font-weight: 700;
        margin: 26px 0 12px 0;
        color: #f0ede4;
        border-right: 3px solid #d4af37;
        padding-right: 12px;
    }
    .gold-caption { color: #a7a396; font-size: 13px; margin-bottom: 14px; }

    .stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid rgba(212,175,55,0.15); }

    div[data-baseweb="select"] > div {
        background-color: #121116;
        border-color: rgba(212,175,55,0.3);
    }

    hr.gold-divider {
        border: none; height: 1px;
        background: linear-gradient(90deg, transparent, rgba(212,175,55,0.5), transparent);
        margin: 30px 0;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# לוגיקת האסטרטגיה
# ---------------------------------------------------------------------------
@st.cache_data(ttl=900, show_spinner=False)
def run_backtest(ticker: str, point_value: float, days_back: int):
    """מריץ את אסטרטגיית פריצת נר הפתיחה על מכשיר נתון.
    מחזיר: (df_trades, debug_log)"""

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    ticker_obj = yf.Ticker(ticker)
    df = ticker_obj.history(start=start_date, end=end_date, interval=INTERVAL)

    if df.empty:
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
            debug_log.append({'תאריך': date.strftime('%Y-%m-%d'), 'תוצאה': 'דולג',
                               'סיבה': f'רק {len(market_hours)} נרות זמינים ביום זה (נדרשים 4+)'})
            continue

        c1, c2, c3, c4 = market_hours.iloc[0], market_hours.iloc[1], market_hours.iloc[2], market_hours.iloc[3]

        trade_type = None
        entry_price = stop_loss = exit_price = 0
        reason = ""

        is_green_c1 = c1['Close'] > c1['Open']
        is_red_c1 = c1['Close'] < c1['Open']

        if is_green_c1:
            if c2['High'] > c1['High']:
                trade_type = 'Long'
                entry_price, stop_loss = c1['High'], c1['Low']
                if c2['Low'] <= stop_loss or c3['Low'] <= stop_loss:
                    exit_price = stop_loss
                else:
                    best_price = max(c3['High'], c4['High'])
                    exit_price = best_price if best_price > entry_price else c4['Open']
            else:
                reason = 'נר 1 ירוק, אך נר 2 לא פרץ את השיא שלו — אין כניסה'
        elif is_red_c1:
            if c2['Low'] < c1['Low']:
                trade_type = 'Short'
                entry_price, stop_loss = c1['Low'], c1['High']
                if c2['High'] >= stop_loss or c3['High'] >= stop_loss:
                    exit_price = stop_loss
                else:
                    best_price = min(c3['Low'], c4['Low'])
                    exit_price = best_price if best_price < entry_price else c4['Open']
            else:
                reason = 'נר 1 אדום, אך נר 2 לא פרץ את השפל שלו — אין כניסה'
        else:
            reason = 'נר 1 ניטרלי (Close==Open) — אין ירוק ואין אדום'

        if trade_type:
            points = (exit_price - entry_price) if trade_type == 'Long' else (entry_price - exit_price)
            pct_return = (points / entry_price) * 100
            pnl = points * point_value

            trades.append({
                'תאריך': date.strftime('%Y-%m-%d'), 'סוג עסקה': trade_type,
                'מחיר כניסה': round(entry_price, 2), 'סטופ לוס': round(stop_loss, 2),
                'מחיר יציאה': round(exit_price, 2), 'נקודות (רווח/הפסד)': round(points, 2),
                'אחוזים (%)': round(pct_return, 2), 'דולרים ($)': round(pnl, 2)
            })
            debug_log.append({'תאריך': date.strftime('%Y-%m-%d'), 'תוצאה': f'עסקת {trade_type}',
                               'סיבה': f"נר1 {'ירוק' if is_green_c1 else 'אדום'}, פריצה אושרה בנר 2"})
        else:
            debug_log.append({'תאריך': date.strftime('%Y-%m-%d'), 'תוצאה': 'ללא עסקה', 'סיבה': reason})

    return pd.DataFrame(trades), debug_log


def summarize(df_trades: pd.DataFrame) -> dict:
    if df_trades.empty:
        return {'עסקאות': 0, 'הצלחה %': 0, 'רווח כולל $': 0, 'רווח ממוצע $': 0, 'הפסד ממוצע $': 0}
    wins = df_trades[df_trades['דולרים ($)'] > 0]
    losses = df_trades[df_trades['דולרים ($)'] <= 0]
    return {
        'עסקאות': len(df_trades),
        'הצלחה %': round(len(wins) / len(df_trades) * 100, 1),
        'רווח כולל $': round(df_trades['דולרים ($)'].sum(), 2),
        'רווח ממוצע $': round(wins['דולרים ($)'].mean(), 2) if len(wins) else 0,
        'הפסד ממוצע $': round(losses['דולרים ($)'].mean(), 2) if len(losses) else 0,
    }


# ---------------------------------------------------------------------------
# ממשק המשתמש
# ---------------------------------------------------------------------------
st.markdown("""
<div class="hero">
    <div class="kicker">QUANT DESK · OPENING RANGE BREAKOUT</div>
    <h1>💎 בוט בקטסט — פריצת נר פתיחה</h1>
    <p>אסטרטגיה: לונג/שורט בפריצת נר ראשון (15 דק'). יציאה מקסימלית ברווח בנרות 3-4 או בפתיחת נר 4, בכפוף לסטופ.
    ניתן לבדוק על מספר מכשירים במקביל ולהשוות ביניהם.</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="panel">', unsafe_allow_html=True)
c1, c2 = st.columns([2, 1])
with c1:
    selected_instruments = st.multiselect(
        "בחר מכשיר / מכשירים למבחן",
        options=list(INSTRUMENTS.keys()),
        default=["נאסדק 100 (Micro - MNQ)"]
    )
with c2:
    lookback_label = st.selectbox("טווח זמן אחורה", options=list(LOOKBACK_OPTIONS.keys()), index=2)
    days_back = LOOKBACK_OPTIONS[lookback_label]

st.caption("⚠️ נתוני 15 דקות זמינים ב-Yahoo Finance עד 60 יום אחורה בלבד.")
run = st.button("🚀 הרץ בדיקת בקטסט", type="primary")
st.markdown('</div>', unsafe_allow_html=True)

if run:
    if not selected_instruments:
        st.warning("בחר לפחות מכשיר אחד להרצה.")
    else:
        results = {}
        with st.spinner("מושך נתונים ומחשב עבור כל המכשירים שנבחרו..."):
            for name in selected_instruments:
                cfg = INSTRUMENTS[name]
                df_trades, debug_log = run_backtest(cfg["ticker"], cfg["point_value"], days_back)
                results[name] = {"trades": df_trades, "debug": debug_log, "cfg": cfg}

        # ---------------- מצב השוואה (כמה מכשירים) ----------------
        if len(selected_instruments) > 1:
            st.markdown('<div class="section-title">⚖️ השוואת מכשירים</div>', unsafe_allow_html=True)
            summary_rows = []
            for name, res in results.items():
                s = summarize(res["trades"])
                s_row = {'מכשיר': name}
                s_row.update(s)
                summary_rows.append(s_row)
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)

            st.markdown('<div class="section-title">📈 עקומות הון — השוואה</div>', unsafe_allow_html=True)
            fig = go.Figure()
            for name, res in results.items():
                dft = res["trades"]
                if dft.empty:
                    continue
                eq = dft['דולרים ($)'].cumsum()
                fig.add_trace(go.Scatter(
                    x=dft['תאריך'], y=eq, mode='lines+markers', name=name,
                    line=dict(width=3, color=res["cfg"]["color"])
                ))
            fig.update_layout(
                template='plotly_dark', height=440,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="h", y=-0.15),
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown('<hr class="gold-divider">', unsafe_allow_html=True)

        # ---------------- פירוט לכל מכשיר ----------------
        for name, res in results.items():
            df_trades, debug_log, cfg = res["trades"], res["debug"], res["cfg"]
            st.markdown(f'<div class="section-title">🔎 פירוט — {name}</div>', unsafe_allow_html=True)

            if df_trades.empty:
                st.warning(f"לא היו עסקאות עבור {name} בטווח שנבדק.")
                with st.expander("לוג אבחון יומי"):
                    st.dataframe(pd.DataFrame(debug_log), use_container_width=True)
                continue

            s = summarize(df_trades)
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("כמות עסקאות", s['עסקאות'])
            m2.metric("אחוזי הצלחה", f"{s['הצלחה %']}%")
            m3.metric("רווח/הפסד כולל", f"${s['רווח כולל $']:,.2f}")
            m4.metric("רווח ממוצע", f"${s['רווח ממוצע $']:,.2f}")
            m5.metric("הפסד ממוצע", f"${s['הפסד ממוצע $']:,.2f}")

            eq = df_trades['דולרים ($)'].cumsum()
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=df_trades['תאריך'], y=eq, mode='lines+markers',
                line=dict(color=cfg["color"], width=3),
                marker=dict(size=6, color="#d4af37"),
                fill='tozeroy', fillcolor='rgba(212,175,55,0.08)'
            ))
            fig_eq.update_layout(
                template='plotly_dark', height=340,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig_eq, use_container_width=True)

            cc1, cc2 = st.columns(2)
            with cc1:
                winning = len(df_trades[df_trades['דולרים ($)'] > 0])
                fig_pie = go.Figure(data=[go.Pie(
                    labels=['רווחיות', 'הפסדיות'],
                    values=[winning, len(df_trades) - winning],
                    marker=dict(colors=['#d4af37', '#3a3a42']),
                    hole=0.6
                )])
                fig_pie.update_layout(template='plotly_dark', height=300, paper_bgcolor='rgba(0,0,0,0)',
                                       margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_pie, use_container_width=True)
            with cc2:
                counts = df_trades['סוג עסקה'].value_counts()
                fig_bar = go.Figure(data=[go.Bar(x=counts.index, y=counts.values,
                                                  marker_color=['#60a5fa', '#f472b6'])])
                fig_bar.update_layout(template='plotly_dark', height=300, paper_bgcolor='rgba(0,0,0,0)',
                                       plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_bar, use_container_width=True)

            with st.expander("📋 יומן עסקאות מלא"):
                st.dataframe(df_trades, use_container_width=True)
            with st.expander("🔍 לוג אבחון יומי"):
                st.dataframe(pd.DataFrame(debug_log), use_container_width=True)

            st.markdown('<hr class="gold-divider">', unsafe_allow_html=True)
else:
    st.info("בחר מכשיר/ים, טווח זמן, ולחץ על הכפתור כדי להריץ את הבקטסט.")
