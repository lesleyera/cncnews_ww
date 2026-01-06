import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import requests
import re
import concurrent.futures
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import random

# 인증 모듈
from google.oauth2 import service_account 
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest, OrderBy
)

# ----------------- 1. 페이지 설정 -----------------
st.set_page_config(
    layout="wide", 
    page_title="쿡앤셰프 주간 성과보고서", 
    page_icon="📰", 
    initial_sidebar_state="collapsed"
)

# ----------------- 2. CSS 스타일 정의 -----------------
COLOR_NAVY = "#1a237e"
COLOR_RED = "#d32f2f"
COLOR_GREY = "#78909c"
COLOR_BG_ACCENT = "#fffcf7"
CHART_PALETTE = [COLOR_NAVY, COLOR_RED, "#5c6bc0", "#ef5350", "#8d6e63", COLOR_GREY]
COLOR_GENDER = {'여성': '#d32f2f', '남성': '#1a237e'} 

CSS = f"""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css');
body {{ background-color: #ffffff; font-family: 'Pretendard', sans-serif; color: #263238; }}
header[data-testid="stHeader"] {{ visibility: hidden !important; }}
[data-testid="stToolbar"] {{ visibility: hidden !important; }}
.block-container {{ padding-top: 2rem !important; padding-bottom: 5rem; max_width: 1600px; }}
.report-title {{ font-size: 2.6rem; font-weight: 900; color: {COLOR_NAVY}; border-bottom: 4px solid {COLOR_RED}; padding-bottom: 15px; margin-top: 10px; }}
.period-info {{ font-size: 1.2rem; font-weight: 700; color: #455a64; margin-top: 10px; }}
.update-time {{ color: {COLOR_NAVY}; font-weight: 700; font-size: 1.1rem; text-align: right; margin-top: -15px; margin-bottom: 30px; font-family: monospace; }}
.kpi-container {{ background-color: #fff; border: 1px solid #eceff1; border-top: 5px solid {COLOR_RED}; border-radius: 8px; padding: 20px 10px; text-align: center; margin-bottom: 15px; height: 160px; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }}
.kpi-label {{ font-size: 1.1rem; font-weight: 700; color: #455a64; margin-bottom: 10px; white-space: nowrap; letter-spacing: -0.05em; }}
.kpi-value {{ font-size: 2.4rem; font-weight: 900; color: {COLOR_NAVY}; line-height: 1.1; letter-spacing: -0.03em; }}
.kpi-unit {{ font-size: 1.1rem; font-weight: 600; color: #90a4ae; margin-left: 3px; }}
.section-header-container {{ margin-top: 30px; margin-bottom: 25px; padding: 15px 25px; background-color: {COLOR_BG_ACCENT}; border-left: 8px solid {COLOR_NAVY}; border-radius: 4px; }}
.section-header {{ font-size: 1.8rem; font-weight: 800; color: {COLOR_NAVY}; margin: 0; }}
.sub-header {{ font-size: 1.3rem; font-weight: 700; color: {COLOR_NAVY}; margin-top: 30px; margin-bottom: 10px; padding-left: 10px; border-left: 4px solid {COLOR_RED}; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 0px; border-bottom: 2px solid #cfd8dc; display: flex; width: 100%; }}
.stTabs [data-baseweb="tab"] {{ height: 60px; background-color: #f7f9fa; border-right: 1px solid #eceff1; color: #607d8b; font-weight: 700; font-size: 1.1rem; flex-grow: 1; text-align: center; }}
.stTabs [aria-selected="true"] {{ background-color: #fff; color: {COLOR_RED}; border-bottom: 4px solid {COLOR_RED}; }}
.footer-note {{ font-size: 0.85rem; color: #78909c; margin-top: 50px; border-top: 1px solid #eceff1; padding-top: 15px; text-align: center; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------- 3. 진입 보안 화면 -----------------
def check_password():
    if st.session_state.get("password_correct", False): return True
    login_placeholder = st.empty()
    with login_placeholder.container():
        st.markdown('<div style="margin-top: 100px; text-align: center;"><div style="font-size: 24px; font-weight: 700; color: #1a237e;">🔒 쿡앤셰프 주간 성과보고서</div></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            password = st.text_input("Access Code", type="password")
            if password == "cncnews2026":
                st.session_state["password_correct"] = True
                login_placeholder.empty()
                st.rerun()
            elif password: st.error("🚫 코드가 올바르지 않습니다.")
    return False

if not check_password(): st.stop()

# ----------------- 4. GA4 설정 및 크롤링 -----------------
PROPERTY_ID = "370663478" 

@st.cache_resource
def get_ga4_client():
    try:
        key_dict = st.secrets["ga4_credentials"]
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return BetaAnalyticsDataClient(credentials=creds)
    except Exception as e:
        st.error(f"GA4 연결 실패: {e}")
        return None

def clean_author_name(name):
    if not name: return "미상"
    name = name.replace('#', '').replace('기자', '')
    return ' '.join(name.split())

def crawl_single_article(url_path):
    full_url = f"http://www.cooknchefnews.com{url_path}"
    try:
        response = requests.get(full_url, timeout=2)
        soup = BeautifulSoup(response.text, 'html.parser')
        author = "관리자"
        author_tag = soup.select_one('.user-name') or soup.select_one('.writer') or soup.select_one('.byline')
        if author_tag: author = author_tag.text.strip()
        author = clean_author_name(author)
        likes = int(soup.select_one('.sns-like-count').text.replace(',', '')) if soup.select_one('.sns-like-count') else 0
        comments = int(soup.select_one('.comment-count').text.replace(',', '')) if soup.select_one('.comment-count') else 0
        cat, subcat = "뉴스", "이슈"
        breadcrumbs = soup.select('.location a')
        if len(breadcrumbs) >= 2: cat = breadcrumbs[1].text.strip()
        if len(breadcrumbs) >= 3: subcat = breadcrumbs[2].text.strip()
        return (author, likes, comments, cat, subcat)
    except: return ("관리자", 0, 0, "뉴스", "이슈")

def get_sunday_to_saturday_ranges(count=12):
    ranges = {}
    today = datetime.now()
    days_since_sunday = (today.weekday() + 1) % 7
    last_sunday = today - timedelta(days=days_since_sunday)
    for i in range(count):
        start_date = last_sunday - timedelta(weeks=i)
        end_date = start_date + timedelta(days=6)
        label = f"{start_date.isocalendar()[1]}주차"
        ranges[label] = f"{start_date.strftime('%Y.%m.%d')} ~ {end_date.strftime('%Y.%m.%d')}"
    return ranges
WEEK_MAP = get_sunday_to_saturday_ranges()

def run_ga4_report(start_date, end_date, dimensions, metrics, order_by_metric=None, limit=None):
    client = get_ga4_client()
    if not client: return pd.DataFrame()
    order_bys = [OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order_by_metric), desc=True)] if order_by_metric else []
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        order_bys=order_bys,
        limit=limit if limit else 10000
    )
    try:
        response = client.run_report(request)
        data = []
        for row in response.rows:
            row_dict = {dimensions[i]: row.dimension_values[i].value for i in range(len(dimensions))}
            for i, met in enumerate(metrics):
                val = row.metric_values[i].value
                row_dict[met] = float(val) if '.' in val else int(val)
            data.append(row_dict)
        return pd.DataFrame(data)
    except: return pd.DataFrame()

# ----------------- 5. 데이터 로드 및 정렬 수정 -----------------
@st.cache_data(ttl=3600)
def load_all_dashboard_data(selected_week):
    dr = WEEK_MAP[selected_week]
    s_dt, e_dt = dr.split(' ~ ')[0].replace('.', '-'), dr.split(' ~ ')[1].replace('.', '-')
    ls_dt = (datetime.strptime(s_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')
    le_dt = (datetime.strptime(e_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')

    # KPI
    summary = run_ga4_report(s_dt, e_dt, [], ["activeUsers", "screenPageViews", "newUsers"])
    uv = int(summary['activeUsers'].iloc[0]) if not summary.empty else 0
    pv = int(summary['screenPageViews'].iloc[0]) if not summary.empty else 0
    new_ratio = round((int(summary['newUsers'].iloc[0]) / uv * 100), 1) if uv > 0 else 0

    # [수정] 일별 데이터 날짜 포맷 강제 지정 (GA4 YYYYMMDD -> MM-DD)
    df_daily = run_ga4_report(s_dt, e_dt, ["date"], ["activeUsers", "screenPageViews"])
    if not df_daily.empty:
        df_daily = df_daily.rename(columns={'date':'날짜', 'activeUsers':'UV', 'screenPageViews':'PV'})
        df_daily['날짜'] = pd.to_datetime(df_daily['날짜'], format='%Y%m%d').dt.strftime('%m-%d')
        df_daily = df_daily.sort_values('날짜')

    # [수정] 3개월 추이 연도 정렬 및 범례 수정
    def fetch_week_data(week_label, date_str):
        ws, we = date_str.split(' ~ ')[0].replace('.', '-'), date_str.split(' ~ ')[1].replace('.', '-')
        res = run_ga4_report(ws, we, [], ["activeUsers", "screenPageViews"])
        year_prefix = ws.split('-')[0]
        if not res.empty:
            return {
                '원본주차': week_label, 
                '표시주차': f"{year_prefix}년 {week_label}",
                'sort_key': int(year_prefix) * 100 + int(re.search(r'\d+', week_label).group()),
                'UV': int(res['activeUsers'][0]), 
                'PV': int(res['screenPageViews'][0])
            }
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_week_data, wl, dstr) for wl, dstr in list(WEEK_MAP.items())[:12]]
        results = [f.result() for f in concurrent.futures.as_completed(futures) if f.result()]
    df_weekly = pd.DataFrame(results).sort_values('sort_key') if results else pd.DataFrame()

    # 활성 기사 수
    df_pages = run_ga4_report(s_dt, e_dt, ["pagePath"], ["screenPageViews"])
    active_cnt = df_pages[df_pages['pagePath'].str.contains(r'article|news|view|story', case=False, na=False)].shape[0] if not df_pages.empty else 0

    # 유입경로 분석
    def map_source(s):
        s = s.lower()
        if 'naver' in s: return '네이버'
        if 'daum' in s: return '다음'
        if 'google' in s: return '구글'
        if 'facebook' in s: return '페이스북'
        if '(direct)' in s: return '직접'
        return '기타'

    df_t_raw = run_ga4_report(s_dt, e_dt, ["sessionSource"], ["screenPageViews"])
    df_t_raw['유입경로'] = df_t_raw['sessionSource'].apply(map_source)
    df_traffic_curr = df_t_raw.groupby('유입경로')['screenPageViews'].sum().reset_index().rename(columns={'screenPageViews':'조회수'})
    
    # 68.0% 등의 검색 유입 비중 계산용
    search_pv = df_traffic_curr[df_traffic_curr['유입경로'].isin(['네이버','구글','다음'])]['조회수'].sum()
    search_ratio = round((search_pv / df_traffic_curr['조회수'].sum() * 100), 1) if not df_traffic_curr.empty else 0

    # TOP 10 상세 데이터 및 크롤링
    df_top_raw = run_ga4_report(s_dt, e_dt, ["pageTitle", "pagePath"], ["screenPageViews", "activeUsers", "userEngagementDuration", "bounceRate"], "screenPageViews", limit=50)
    if not df_top_raw.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            scraped = list(executor.map(crawl_single_article, df_top_raw['pagePath']))
        df_top_raw['작성자'], df_top_raw['좋아요'], df_top_raw['댓글'], df_top_raw['카테고리'], df_top_raw['세부카테고리'] = zip(*scraped)
        df_top10 = df_top_raw.head(10).copy()
        df_top10['평균체류시간'] = df_top10['userEngagementDuration'].apply(lambda x: f"{int(x)//60}분 {int(x)%60}초")
    else: df_top10 = pd.DataFrame()

    return uv, pv, df_daily, df_weekly, new_ratio, search_ratio, active_cnt, df_traffic_curr, df_top10, df_top_raw

# ----------------- 6. 렌더링 함수들 -----------------
def render_summary(uv, pv, new_ratio, search_ratio, active_cnt, df_daily, df_weekly):
    st.markdown('<div class="section-header-container"><div class="section-header">1. 주간 전체 성과 요약</div></div>', unsafe_allow_html=True)
    c = st.columns(6)
    metrics = [("활성 기사 수", active_cnt, "건"), ("주간 조회수(PV)", pv, "건"), ("주간 방문자(UV)", uv, "명"), 
               ("인당 페이지뷰", round(pv/uv, 1) if uv>0 else 0, "건"), ("신규 방문자 비중", new_ratio, "%"), ("검색 유입 비중", search_ratio, "%")]
    for i, (l, v, u) in enumerate(metrics):
        c[i].markdown(f'<div class="kpi-container"><div class="kpi-label">{l}</div><div class="kpi-value">{v:, if isinstance(v,int) else v}<span class="kpi-unit">{u}</span></div></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="sub-header">📊 주간 일별 방문 추이</div>', unsafe_allow_html=True)
        if not df_daily.empty:
            st.plotly_chart(px.bar(df_daily.melt(id_vars='날짜'), x='날짜', y='value', color='variable', barmode='group', color_discrete_map={'UV': COLOR_GREY, 'PV': COLOR_NAVY}), use_container_width=True)
    with col2:
        st.markdown('<div class="sub-header">📈 최근 3달 간 추이 분석</div>', unsafe_allow_html=True)
        if not df_weekly.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_weekly['표시주차'], y=df_weekly['UV'], name='UV', marker_color=COLOR_GREY))
            fig.add_trace(go.Bar(x=df_weekly['표시주차'], y=df_weekly['PV'], name='PV', marker_color=COLOR_NAVY))
            fig.update_layout(barmode='group', plot_bgcolor='white')
            st.plotly_chart(fig, use_container_width=True)

# ----------------- 7. 메인 실행 영역 -----------------
selected_week = st.selectbox("📅 조회 주차", list(WEEK_MAP.keys()))
uv, pv, df_daily, df_weekly, new_ratio, search_ratio, active_cnt, df_traffic, df_top10, df_all = load_all_dashboard_data(selected_week)

st.markdown(f'<div class="report-title">📰 쿡앤셰프 주간 성과보고서</div>', unsafe_allow_html=True)
st.markdown(f'<div class="period-info">📅 조회 기간: {WEEK_MAP[selected_week]}</div>', unsafe_allow_html=True)
st.markdown(f"<div class='update-time'>최종 집계: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)

tabs = st.tabs(["1.성과요약", "2.접근경로", "3.방문자특성", "4.Top10상세", "5.Top10추이", "6.카테고리", "7.기자(본명)", "8.기자(필명)"])

with tabs[0]: render_summary(uv, pv, new_ratio, search_ratio, active_cnt, df_daily, df_weekly)
with tabs[1]: 
    st.markdown('<div class="section-header-container"><div class="section-header">2. 주간 접근 경로 분석</div></div>', unsafe_allow_html=True)
    st.plotly_chart(px.pie(df_traffic, names='유입경로', values='조회수', hole=0.5, color_discrete_sequence=CHART_PALETTE), use_container_width=True)
with tabs[3]:
    st.markdown('<div class="section-header-container"><div class="section-header">4. 주간 조회수 TOP 10 기사 상세</div></div>', unsafe_allow_html=True)
    if not df_top10.empty:
        st.dataframe(df_top10[['카테고리','제목','작성자','screenPageViews','activeUsers','평균체류시간']].rename(columns={'screenPageViews':'조회수','activeUsers':'방문자'}), use_container_width=True, hide_index=True)
with tabs[6]:
    st.markdown('<div class="section-header-container"><div class="section-header">7. 기자별 실적 분석</div></div>', unsafe_allow_html=True)
    if not df_all.empty:
        writer_stats = df_all.groupby('작성자').agg(기사수=('pageTitle','count'), 총조회수=('screenPageViews','sum')).sort_values('총조회수', ascending=False).reset_index()
        st.dataframe(writer_stats, use_container_width=True, hide_index=True)

st.markdown('<div class="footer-note">※ 쿡앤셰프(Cook&Chef) 주간 데이터 자동 집계 시스템</div>', unsafe_allow_html=True)