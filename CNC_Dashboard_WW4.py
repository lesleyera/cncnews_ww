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

# ----------------- 2. CSS 스타일 정의 (기본 + 인쇄) -----------------
COLOR_NAVY = "#1a237e"
COLOR_RED = "#d32f2f"
COLOR_GREY = "#78909c"
COLOR_BG_ACCENT = "#fffcf7"
CHART_PALETTE = [COLOR_NAVY, COLOR_RED, "#5c6bc0", "#ef5350", "#8d6e63", COLOR_GREY]
COLOR_GENDER = {'여성': '#d32f2f', '남성': '#1a237e'} 

# 기본 화면 스타일
CSS = f"""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css');
body {{ background-color: #ffffff; font-family: 'Pretendard', sans-serif; color: #263238; }}

/* 헤더 및 툴바 숨김 */
header[data-testid="stHeader"] {{ visibility: hidden !important; }}
[data-testid="stToolbar"] {{ visibility: hidden !important; }}
.block-container {{ padding-top: 2rem !important; padding-bottom: 5rem; max_width: 1600px; }}
[data-testid="stSidebar"] {{ display: none; }}

/* 보고서 스타일 */
.report-title {{ font-size: 2.6rem; font-weight: 900; color: {COLOR_NAVY}; border-bottom: 4px solid {COLOR_RED}; padding-bottom: 15px; margin-top: 10px; }}
.period-info {{ font-size: 1.2rem; font-weight: 700; color: #455a64; margin-top: 10px; }}
.update-time {{ color: {COLOR_NAVY}; font-weight: 700; font-size: 1.1rem; text-align: right; margin-top: -15px; margin-bottom: 30px; font-family: monospace; }}
.kpi-container {{ background-color: #fff; border: 1px solid #eceff1; border-top: 5px solid {COLOR_RED}; border-radius: 8px; padding: 20px 10px; text-align: center; margin-bottom: 15px; height: 160px; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }}
.kpi-label {{ font-size: 1.1rem; font-weight: 700; color: #455a64; margin-bottom: 10px; white-space: nowrap; letter-spacing: -0.05em; }}
.kpi-value {{ font-size: 2.4rem; font-weight: 900; color: {COLOR_NAVY}; line-height: 1.1; letter-spacing: -0.03em; }}
.kpi-unit {{ font-size: 1.1rem; font-weight: 600; color: #90a4ae; margin-left: 3px; }}
.section-header-container {{ margin-top: 30px; margin-bottom: 25px; padding: 15px 25px; background-color: {COLOR_BG_ACCENT}; border-left: 8px solid {COLOR_NAVY}; border-radius: 4px; }}
.section-header {{ font-size: 1.8rem; font-weight: 800; color: {COLOR_NAVY}; margin: 0; }}
.section-desc {{ font-size: 1rem; color: #546e7a; margin-top: 5px; }}
.sub-header {{ font-size: 1.3rem; font-weight: 700; color: {COLOR_NAVY}; margin-top: 30px; margin-bottom: 10px; padding-left: 10px; border-left: 4px solid {COLOR_RED}; }}
.chart-header {{ font-size: 1.2rem; font-weight: 700; color: {COLOR_NAVY}; margin-top: 30px; margin-bottom: 10px; border-left: 4px solid {COLOR_RED}; padding-left: 10px; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 0px; border-bottom: 2px solid #cfd8dc; display: flex; width: 100%; }}
.stTabs [data-baseweb="tab"] {{ height: 60px; background-color: #f7f9fa; border-right: 1px solid #eceff1; color: #607d8b; font-weight: 700; font-size: 1.1rem; flex-grow: 1; text-align: center; }}
.stTabs [aria-selected="true"] {{ background-color: #fff; color: {COLOR_RED}; border-bottom: 4px solid {COLOR_RED}; }}
[data-testid="stDataFrame"] thead th {{ background-color: {COLOR_NAVY} !important; color: white !important; font-size: 1rem !important; font-weight: 600 !important; }}
.footer-note {{ font-size: 0.85rem; color: #78909c; margin-top: 50px; border-top: 1px solid #eceff1; padding-top: 15px; text-align: center; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------- 인쇄 모드 전용 스타일 -----------------
PRINT_CSS = """
<style>
.print-preview-layout { transform: scale(0.85); transform-origin: top center; width: 117%; }
@media print {
    @page { size: A4; margin: 10mm; }
    body { transform: scale(0.8) !important; transform-origin: top left !important; width: 125% !important; }
    .no-print, .stButton, header, footer, [data-testid="stSidebar"] { display: none !important; }
    .page-break { page-break-before: always !important; break-before: page !important; display: block; height: 1px; margin-top: 20px; }
    [data-testid="stDataFrame"] { width: 100% !important; }
    [data-testid="stDataFrame"] > div { width: 100% !important; }
    .section-header-container { margin-top: 10px !important; }
    .block-container { padding-top: 0 !important; }
    .print-footer { position: fixed; bottom: 0; width: 100%; text-align: center; font-size: 10px; color: #999; }
}
</style>
"""
st.markdown(PRINT_CSS, unsafe_allow_html=True)

# ----------------- 3. 진입 보안 화면 -----------------
def check_password():
    if st.session_state.get("password_correct", False): return True
    login_placeholder = st.empty()
    with login_placeholder.container():
        st.markdown("""
            <style>
            .login-container { max-width: 400px; margin: 100px auto; padding: 40px; text-align: center; }
            .login-title { font-size: 24px; font-weight: 700; color: #1a237e; margin-bottom: 20px; text-align: center; }
            .powered-by { font-size: 12px; color: #90a4ae; margin-top: 50px; font-weight: 500; }
            .stTextInput > div > div > input { text-align: center; font-size: 18px; letter-spacing: 2px; }
            </style>
            """, unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown('<div style="margin-top: 100px;"></div>', unsafe_allow_html=True)
            st.markdown('<div class="login-title">🔒 쿡앤셰프 주간 성과보고서</div>', unsafe_allow_html=True)
            password = st.text_input("Access Code", type="password", key="password_input", label_visibility="collapsed")
            if password:
                if password == "cncnews2026":
                    st.session_state["password_correct"] = True
                    login_placeholder.empty()
                    st.rerun()
                else: st.error("🚫 코드가 올바르지 않습니다.")
            st.markdown('<div class="powered-by">Powered by DWG Inc.</div>', unsafe_allow_html=True)
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
        st.error(f"GA4 클라이언트 연결 실패: {e}")
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

# ----------------- 5. 데이터 로딩 (수정 반영) -----------------
@st.cache_data(ttl=3600)
def load_all_dashboard_data(selected_week):
    dr = WEEK_MAP[selected_week]
    s_dt, e_dt = dr.split(' ~ ')[0].replace('.', '-'), dr.split(' ~ ')[1].replace('.', '-')
    ls_dt = (datetime.strptime(s_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')
    le_dt = (datetime.strptime(e_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')

    summary = run_ga4_report(s_dt, e_dt, [], ["activeUsers", "screenPageViews", "newUsers"])
    sel_uv = int(summary['activeUsers'].iloc[0]) if not summary.empty else 0
    sel_pv = int(summary['screenPageViews'].iloc[0]) if not summary.empty else 0
    sel_new = int(summary['newUsers'].iloc[0]) if not summary.empty else 0
    new_visitor_ratio = round((sel_new / sel_uv * 100), 1) if sel_uv > 0 else 0

    # [수정 1] 일별 날짜 포맷
    df_daily = run_ga4_report(s_dt, e_dt, ["date"], ["activeUsers", "screenPageViews"])
    if not df_daily.empty:
        df_daily = df_daily.rename(columns={'date':'날짜', 'activeUsers':'UV', 'screenPageViews':'PV'})
        df_daily['날짜'] = pd.to_datetime(df_daily['날짜'], format='%Y%m%d').dt.strftime('%m-%d')
        df_daily = df_daily.sort_values('날짜')

    # [수정 2] 3개월 추이 연도 정렬
    def fetch_week_data(week_label, date_str):
        ws, we = date_str.split(' ~ ')[0].replace('.', '-'), date_str.split(' ~ ')[1].replace('.', '-')
        res = run_ga4_report(ws, we, [], ["activeUsers", "screenPageViews"])
        year_prefix = ws.split('-')[0]
        if not res.empty:
            return {
                '주차': f"{year_prefix}년 {week_label}",
                'year_week': int(year_prefix) * 100 + int(re.search(r'\d+', week_label).group()),
                'UV': int(res['activeUsers'][0]), 'PV': int(res['screenPageViews'][0])
            }
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_week_data, wl, dstr) for wl, dstr in list(WEEK_MAP.items())[:12]]
        results = [f.result() for f in concurrent.futures.as_completed(futures) if f.result()]
    df_weekly = pd.DataFrame(results).sort_values('year_week') if results else pd.DataFrame()

    df_pages_count = run_ga4_report(s_dt, e_dt, ["pagePath"], ["screenPageViews"], limit=10000)
    active_article_count = df_pages_count[df_pages_count['pagePath'].str.contains(r'article|news|view|story', case=False, na=False)].shape[0] if not df_pages_count.empty else 0

    def map_source(s):
        s = s.lower()
        if 'naver' in s: return '네이버'
        if 'daum' in s: return '다음'
        if 'facebook' in s: return '페이스북'
        if '(direct)' in s: return '직접'
        if 'google' in s: return '구글'
        return '기타'

    df_t_raw = run_ga4_report(s_dt, e_dt, ["sessionSource"], ["screenPageViews"])
    df_t_raw['유입경로'] = df_t_raw['sessionSource'].apply(map_source)
    df_traffic_curr = df_t_raw.groupby('유입경로')['screenPageViews'].sum().reset_index().rename(columns={'screenPageViews':'조회수'})
    search_pv = df_traffic_curr[df_traffic_curr['유입경로'].isin(['네이버','구글','다음'])]['조회수'].sum()
    search_inflow_ratio = round((search_pv / df_traffic_curr['조회수'].sum() * 100), 1) if not df_traffic_curr.empty else 0
    df_tl_raw = run_ga4_report(ls_dt, le_dt, ["sessionSource"], ["screenPageViews"])
    df_tl_raw['유입경로'] = df_tl_raw['sessionSource'].apply(map_source)
    df_traffic_last = df_tl_raw.groupby('유입경로')['screenPageViews'].sum().reset_index().rename(columns={'screenPageViews':'조회수'})

    df_raw_top = run_ga4_report(s_dt, e_dt, ["pageTitle", "pagePath"], ["screenPageViews", "activeUsers", "userEngagementDuration", "bounceRate"], "screenPageViews", limit=100)
    if not df_raw_top.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            scraped_data = list(executor.map(crawl_single_article, df_raw_top['pagePath'].tolist()))
        df_raw_top['작성자'], df_raw_top['좋아요'], df_raw_top['댓글'], df_raw_top['카테고리'], df_raw_top['세부카테고리'] = zip(*scraped_data)
        df_raw_all = df_raw_top[~df_raw_top.apply(lambda r: any(x in str(r['pageTitle']).lower() or x in str(r['작성자']).lower() for x in ['cook&chef', '쿡앤셰프']), axis=1)].copy()
        df_top10 = df_raw_all.sort_values('screenPageViews', ascending=False).head(10)
        df_top10['순위'] = range(1, len(df_top10)+1)
        df_top10 = df_top10.rename(columns={'pageTitle': '제목', 'pagePath': '경로', 'screenPageViews': '전체조회수', 'activeUsers': '전체방문자수', 'userEngagementDuration': '평균체류시간', 'bounceRate': '이탈률'})
        df_top10['체류시간_fmt'] = df_top10['평균체류시간'].apply(lambda x: f"{int(x)//60}분 {int(x)%60}초")
        df_top10['발행일시'], df_top10['신규방문자비율'] = s_dt, f"{new_visitor_ratio}%"
    else: df_top10, df_raw_all = pd.DataFrame(), pd.DataFrame()

    return (sel_uv, sel_pv, df_daily, df_weekly, df_traffic_curr, df_traffic_last, df_top10, df_raw_all, new_visitor_ratio, search_inflow_ratio, active_article_count)

# ----------------- 6. 렌더링 함수 (수정 반영) -----------------
def render_summary(df_weekly, cur_pv, cur_uv, new_ratio, search_ratio, df_daily, active_article_count):
    st.markdown('<div class="section-header-container first-section"><div class="section-header">1. 주간 전체 성과 요약</div></div>', unsafe_allow_html=True)
    # [수정 3] f-string 내 쉼표 오류 수정
    kpis = [
        ("활성 기사 수", f"{active_article_count:,}", "건"), 
        ("주간 전체 조회수(PV)", f"{cur_pv:,}", "건"), 
        ("주간 총 방문자수(UV)", f"{cur_uv:,}", "명"), 
        ("방문자당 페이지뷰", round(cur_pv/cur_uv, 1) if cur_uv>0 else 0, "건"), 
        ("신규 방문자 비율", f"{new_ratio}%", ""), 
        ("검색 유입 비율", f"{search_ratio}%", "")
    ]
    cols = st.columns(6)
    for i, (l, v, u) in enumerate(kpis):
        cols[i].markdown(f'<div class="kpi-container"><div class="kpi-label">{l}</div><div class="kpi-value">{v}<span class="kpi-unit">{u}</span></div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sub-header">📊 주간 일별 방문 추이</div>', unsafe_allow_html=True)
        if not df_daily.empty: st.plotly_chart(px.bar(df_daily.melt(id_vars='날짜'), x='날짜', y='value', color='variable', barmode='group', color_discrete_map={'UV': COLOR_GREY, 'PV': COLOR_NAVY}), use_container_width=True)
    with c2:
        st.markdown('<div class="sub-header">📈 최근 3달 간 추이 분석</div>', unsafe_allow_html=True)
        if not df_weekly.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_weekly['주차'], y=df_weekly['UV'], name='UV', marker_color=COLOR_GREY))
            fig.add_trace(go.Bar(x=df_weekly['주차'], y=df_weekly['PV'], name='PV', marker_color=COLOR_NAVY))
            fig.update_layout(barmode='group', plot_bgcolor='white', margin=dict(t=0))
            st.plotly_chart(fig, use_container_width=True)

# ----------------- 7. 메인 실행 -----------------
if 'print_mode' not in st.session_state: st.session_state['print_mode'] = False
c1, c2 = st.columns([2, 1])
with c1: st.markdown('<div class="report-title">📰 쿡앤셰프 주간 성과보고서</div>', unsafe_allow_html=True)
with c2:
    cb1, cb2 = st.columns(2)
    if st.session_state['print_mode']:
        if cb1.button("🔙 대시보드로 복귀"): st.session_state['print_mode'] = False; st.rerun()
        if cb2.button("🖨️ 인쇄 실행", type="primary"): st.components.v1.html("<script>window.parent.print();</script>", height=0)
    else:
        if cb2.button("🖨️ 인쇄 미리보기", type="primary"): st.session_state['print_mode'] = True; st.rerun()
    selected_week = st.selectbox("📅 조회 주차", list(WEEK_MAP.keys()), key="week_select", label_visibility="collapsed")

uv, pv, df_daily, df_weekly, df_t_c, df_t_l, df_t10, df_r_a, new_r, src_r, act_c = load_all_dashboard_data(selected_week)

st.markdown(f'<div class="period-info">📅 조회 기간: {WEEK_MAP[selected_week]}</div>', unsafe_allow_html=True)
st.markdown(f"<div class='update-time'>최종 집계: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)

if not st.session_state['print_mode']:
    tabs = st.tabs(["1.성과요약", "2.접근경로"])
    with tabs[0]: render_summary(df_weekly, pv, uv, new_r, src_r, df_daily, act_c)
else:
    st.markdown('<div class="print-preview-layout">', unsafe_allow_html=True)
    render_summary(df_weekly, pv, uv, new_r, src_r, df_daily, act_c)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="footer-note">※ 쿡앤셰프(Cook&Chef) 주간 데이터 자동 집계 시스템</div>', unsafe_allow_html=True)