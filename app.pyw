import streamlit as st
import pandas as pd
import numpy as np
from pytrends.request import TrendReq
import plotly.express as px
import country_converter as coco
import warnings

# Suppress pandas future warnings from pytrends
warnings.simplefilter(action='ignore', category=FutureWarning)
pd.set_option('future.no_silent_downcasting', True)

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Google Trends Real-Time Simulator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- HELPER & CACHING FUNCTIONS ---
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_live_trends(keywords, timeframe, geo):
    """Fetches real-time data from Google Trends using pytrends."""
    pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
    pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo=geo, gprop='')
    
    time_df = pytrends.interest_over_time()
    region_df = pytrends.interest_by_region(resolution='COUNTRY', inc_low_vol=True, inc_geo_code=False)
    
    related_kw = []
    try:
        related_queries = pytrends.related_queries()
        main_kw = keywords[0]
        if related_queries and main_kw in related_queries:
            top_df = related_queries[main_kw].get('top')
            if top_df is not None and not top_df.empty:
                # Filter out terms that are just variations of the main keyword
                filtered = [q for q in top_df['query'].tolist() if main_kw.lower() not in q.lower()][:3]
                related_kw = filtered if filtered else top_df['query'].head(3).tolist()
    except Exception:
        pass
        
    return time_df, region_df, related_kw

def generate_simulated_data(keywords):
    """Fallback generator so your project showcase never crashes due to Google 429 rate limits."""
    dates = pd.date_range(end=pd.Timestamp.today(), periods=52, freq='W')
    np.random.seed(sum(ord(c) for c in keywords[0]))
    
    time_data = {}
    for kw in keywords:
        base = np.linspace(np.random.randint(30, 60), np.random.randint(50, 95), 52)
        noise = np.random.normal(0, 8, 52)
        time_data[kw] = np.clip(base + noise, 5, 100).astype(int)
    time_df = pd.DataFrame(time_data, index=dates)
    time_df.index.name = 'date'
    
    countries = [
        'United States', 'India', 'China', 'United Kingdom', 'Germany', 
        'Canada', 'Australia', 'Brazil', 'Japan', 'France', 
        'Singapore', 'South Korea', 'Nigeria', 'Pakistan', 'Philippines',
        'Indonesia', 'Vietnam', 'Mexico', 'Spain', 'Italy'
    ]
    region_data = {
        kw: np.random.randint(15, 100, size=len(countries)) for kw in keywords
    }
    region_df = pd.DataFrame(region_data, index=countries)
    region_df.index.name = 'geoName'
    
    main_kw = keywords[0]
    related_kw = [f"alternative to {main_kw}", f"best {main_kw}", f"{main_kw} 2026"]
    return time_df, region_df, related_kw

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.title("⚙️ Tracker Controls")
    
    main_keyword = st.text_input("🔍 Primary Keyword", value="Machine Learning", help="Enter the main topic you want to track.")
    
    timeframe_map = {
        "Past 12 Months": "today 12-m",
        "Past 3 Months": "today 3-m",
        "Past 30 Days": "today 1-m",
        "Past 5 Years": "today 5-y"
    }
    selected_tf_label = st.selectbox("📅 Timeframe", list(timeframe_map.keys()), index=0)
    timeframe = timeframe_map[selected_tf_label]
    
    geo_map = {
        "Worldwide": "",
        "United States": "US",
        "India": "IN",
        "United Kingdom": "GB",
        "Canada": "CA",
        "Australia": "AU"
    }
    selected_geo_label = st.selectbox("🌍 Region Filter", list(geo_map.keys()), index=0)
    geo = geo_map[selected_geo_label]
    
    st.divider()

# --- FETCH DATA & AUTO-SUGGEST SIMILAR WORDS ---
is_simulated = False
# Initial temporary payload just to get smart suggestions if user hasn't typed custom comparison yet
temp_kw = [main_keyword.strip()]

with st.spinner(f"Analyzing trends and finding similar terms for **{main_keyword}**..."):
    if st.sidebar.checkbox("⚡ Force Simulator Mode", value=False):
        time_df, region_df, auto_related = generate_simulated_data(temp_kw)
        is_simulated = True
    else:
        try:
            time_df, region_df, auto_related = fetch_live_trends(temp_kw, timeframe, geo)
            if time_df.empty:
                time_df, region_df, auto_related = generate_simulated_data(temp_kw)
                is_simulated = True
        except Exception:
            time_df, region_df, auto_related = generate_simulated_data(temp_kw)
            is_simulated = True

# Fallback smart suggestions if API didn't return any
if not auto_related:
    auto_related = ["Artificial Intelligence", "Data Science", "Cloud Computing"]

# --- SIDEBAR COMPARISON SECTION ---
with st.sidebar:
    st.subheader("🔄 Comparison Keywords")
    st.markdown("Select suggested similar terms or type your own:")
    
    # Let user pick from intelligent auto-suggestions
    selected_suggestions = st.multiselect(
        "Auto-suggested similar words:",
        options=auto_related,
        default=auto_related[:2] if len(auto_related) >= 2 else auto_related
    )
    
    custom_comp = st.text_input(
        "Or add custom keywords (comma-separated):", 
        value="",
        help="E.g., Python, R, SQL"
    )

# Combine main keyword + selected suggestions + manual custom inputs (limit total to 5 for Google Trends)
extra_kw = selected_suggestions + [k.strip() for k in custom_comp.split(",") if k.strip()]
# Remove duplicates and main keyword from comparison list
unique_extras = list(dict.fromkeys([k for k in extra_kw if k.lower() != main_keyword.lower()]))
kw_list = [main_keyword.strip()] + unique_extras[:4]

# Fetch full multi-keyword dataset if comparison terms changed
if len(kw_list) > 1:
    with st.spinner("Fetching comparison data..."):
        if is_simulated:
            time_df, region_df, _ = generate_simulated_data(kw_list)
        else:
            try:
                time_df, region_df, _ = fetch_live_trends(kw_list, timeframe, geo)
            except Exception:
                time_df, region_df, _ = generate_simulated_data(kw_list)
                is_simulated = True

if 'isPartial' in time_df.columns:
    time_df = time_df.drop(columns=['isPartial'])

# --- MAIN PAGE HEADER ---
st.title("📈 Real-Time Google Keyword Trend Tracker & Simulator")
st.markdown("Compare search queries contextually with automated similar-word discovery.")

# --- KPI METRICS ROW ---
st.subheader(f"📊 Quick Insights: '{main_keyword}'")
col1, col2, col3, col4 = st.columns(4)

peak_interest = int(time_df[main_keyword].max()) if main_keyword in time_df else 0
avg_interest = round(time_df[main_keyword].mean(), 1) if main_keyword in time_df else 0
top_country = region_df[main_keyword].idxmax() if not region_df.empty and main_keyword in region_df else "N/A"
status_badge = "🧪 Simulated Data" if is_simulated else "🟢 Live Google Data"

col1.metric("Peak Search Interest", f"{peak_interest} / 100")
col2.metric("Average Interest", f"{avg_interest} / 100")
col3.metric("Top Searching Country", top_country)
col4.metric("Data Source", status_badge)

st.divider()

# --- TABS FOR VISUALIZATIONS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "🌍 Geographic Distribution", 
    "📈 Interest Over Time", 
    "⚔️ Keyword Comparison", 
    "📋 Raw Data & Export"
])

# TAB 1: WORLD MAP & BAR CHART
with tab1:
    st.subheader(f"Global Reach for '{main_keyword}'")
    top_regions = region_df[[main_keyword]].sort_values(by=main_keyword, ascending=False).head(15)
    
    map_df = region_df[[main_keyword]].reset_index()
    map_df = map_df[map_df[main_keyword] > 0]
    map_df['iso_alpha'] = coco.convert(names=map_df['geoName'].tolist(), to='ISO3', not_found=None)
    map_df = map_df.dropna(subset=['iso_alpha'])

    map_col, bar_col = st.columns([3, 2])
    
    with map_col:
        fig_map = px.choropleth(
            map_df,
            locations='iso_alpha',
            locationmode='ISO-3',
            color=main_keyword,
            hover_name='geoName',
            title=f"World Map: Search Interest for '{main_keyword}'",
            color_continuous_scale='Blues',
            projection='natural earth'
        )
        fig_map.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=450)
        st.plotly_chart(fig_map, use_container_width=True)
        
    with bar_col:
        fig_bar = px.bar(
            top_regions.reset_index(),
            x=main_keyword,
            y='geoName',
            orientation='h',
            color=main_keyword,
            color_continuous_scale='Blues',
            title=f"Top 15 Countries Searching '{main_keyword}'",
            labels={'geoName': 'Country', main_keyword: 'Interest Score'}
        )
        fig_bar.update_layout(yaxis={'categoryorder': 'total ascending'}, height=450, coloraxis_showscale=False)
        st.plotly_chart(fig_bar, use_container_width=True)

# TAB 2: SINGLE KEYWORD TREND
with tab2:
    st.subheader(f"Search Interest Over Time: '{main_keyword}'")
    fig_time = px.line(
        time_df,
        x=time_df.index,
        y=main_keyword,
        markers=True,
        title=f"Timeline Trend for '{main_keyword}' ({selected_tf_label})",
        labels={'date': 'Date', main_keyword: 'Search Interest'}
    )
    fig_time.update_traces(line_color='#1f77b4', line_width=2.5)
    fig_time.update_layout(hovermode="x unified", height=450)
    st.plotly_chart(fig_time, use_container_width=True)

# TAB 3: MULTI-KEYWORD COMPARISON
with tab3:
    st.subheader("Multi-Keyword Comparison")
    if len(kw_list) > 1:
        fig_comp = px.line(
            time_df,
            x=time_df.index,
            y=kw_list,
            title="Comparative Search Interest Over Time",
            labels={'value': 'Interest Score', 'date': 'Date', 'variable': 'Keywords'}
        )
        fig_comp.update_layout(hovermode="x unified", height=450)
        st.plotly_chart(fig_comp, use_container_width=True)
        
        st.markdown("#### Average Interest Share")
        avg_df = time_df[kw_list].mean().reset_index()
        avg_df.columns = ['Keyword', 'Average Interest']
        fig_avg = px.bar(
            avg_df, 
            x='Keyword', 
            y='Average Interest', 
            color='Keyword',
            text_auto='.1f'
        )
        fig_avg.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig_avg, use_container_width=True)
    else:
        st.info("Select or add comparison keywords in the sidebar to view comparative charts!")

# TAB 4: RAW DATA & CSV EXPORT
with tab4:
    st.subheader("Inspect & Download Data")
    d_col1, d_col2 = st.columns(2)
    
    with d_col1:
        st.markdown("**Time Series Data**")
        st.dataframe(time_df.sort_index(ascending=False), use_container_width=True, height=300)
        csv_time = time_df.to_csv().encode('utf-8')
        st.download_button("⬇️ Download Timeline CSV", data=csv_time, file_name=f"{main_keyword}_timeline.csv", mime="text/csv")
        
    with d_col2:
        st.markdown("**Regional Data (Top 50)**")
        st.dataframe(region_df.sort_values(by=main_keyword, ascending=False).head(50), use_container_width=True, height=300)
        csv_reg = region_df.to_csv().encode('utf-8')
        st.download_button("⬇️ Download Regional CSV", data=csv_reg, file_name=f"{main_keyword}_regions.csv", mime="text/csv")