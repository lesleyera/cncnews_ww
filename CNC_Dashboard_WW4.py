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

CSS = f"""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css');
body {{ background-color: #ffffff; font-family: 'Pretendard', sans-serif; color: #263238; }}
header[data-testid="stHeader"] {{ visibility: hidden !important; }}
[data-testid="stToolbar"] {{ visibility: hidden !important; }}
.block-container {{ padding-top: 2rem !important; padding-bottom: 5rem; max_width: 1600px; }}
[data-testid="stSidebar"] {{ display: none; }}

.report-title {{ font-size: 2.6rem; font-weight: 900; color: {COLOR_NAVY}; border-bottom: 4px solid {COLOR_RED}; padding-bottom: 15px; margin-top: 10px; }}
.period-info {{ font-size: 1.2rem; font-weight: 700; color: #455a64; margin-top: 10px; }}
.update-time {{ color: {COLOR_NAVY}; font-weight: 700; font-size: 1.1rem; text-align: right; margin-top: -15px; margin-bottom: 30px; font-family: monospace; }}

/* KPI 가독성 증대 및 용어 변경 반영 */
.kpi-container {{ background-color: #fff; border: 1px solid #eceff1; border-top: 5px solid {COLOR_RED}; border-radius: 8px; padding: 20px 10px; text-align: center; margin-bottom: 15px; height: 160px; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }}
.kpi-label {{ font-size: 1.2rem; font-weight: 700; color: #455a64; margin-bottom: 10px; white-space: nowrap; letter-spacing: -0.05em; }}
.kpi-value {{ font-size: 2.6rem; font-weight: 900; color: {COLOR_NAVY}; line-height: 1.1; letter-spacing: -0.03em; }}
.kpi-unit {{ font-size: 1.2rem; font-weight: 600; color: #90a4ae; margin-left: 3px; }}

.section-header-container {{ margin-top: 30px; margin-bottom: 25px; padding: 15px 25px; background-color: {COLOR_BG_ACCENT}; border-left: 8px solid {COLOR_NAVY}; border-radius: 4px; }}
.section-header {{ font-size: 1.8rem; font-weight: 800; color: {COLOR_NAVY}; margin: 0; }}
.sub-header {{ font-size: 1.4rem; font-weight: 700; color: {COLOR_NAVY}; margin-top: 30px; margin-bottom: 10px; padding-left: 10px; border-left: 4px solid {COLOR_RED}; }}

/* 표 폰트 크기 증대 */
[data-testid="stDataFrame"] {{ font-size: 1.1rem !important; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------- 인쇄 모드 스타일 (가로 인쇄 최적화) -----------------
PRINT_CSS = """
<style>
.print-preview-layout { transform: scale(0.85); transform-origin: top center; width: 117%; }
@media print {
    @page { 
        size: A4 landscape; /* 가로 인쇄 */
        margin: 10mm; 
    }
    body { transform: scale(0.75) !important; transform-origin: top left !important; width: 133% !important; }
    .no-print, .stButton, header, footer, [data-testid="stSidebar"] { display: none !important; }
    .page-break { page-break-before: always !important; display: block; height: 1px; }
    .kpi-container { height: 140px !important; }
    .kpi-label { font-size: 1.3rem !important; }
    .kpi-value { font-size: 2.8rem !important; }
}
</style>
"""
st.markdown(PRINT_CSS, unsafe_allow_html=True)

# ----------------- 3. 진입 보안 화면 (로그인) -----------------
def check_password():
    if st.session_state.get("password_correct", False): return True
    login_placeholder = st.empty()
    with login_placeholder.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown('<div style="margin-top: 100px; text-align: center; font-size: 24px; font-weight: 700; color: #1a237e;">🔒 쿡앤셰프 주간 성과보고서</div>', unsafe_allow_html=True)
            password = st.text_input("Access Code", type="password", key="password_input", label_visibility="collapsed")
            if password:
                if password == "cncnews2026":
                    st.session_state["password_correct"] = True
                    login_placeholder.empty()
                    st.rerun()
                else: st.error("🚫 코드가 올바르지 않습니다.")
    return False

if not check_password(): st.stop()

# =================================================================
# ▼ 메인 로직 시작 ▼
# =================================================================
PROPERTY_ID = "370663478" 

@st.cache_resource
def get_ga4_client():
    try:
        key_dict = st.secrets["ga4_credentials"]
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return BetaAnalyticsDataClient(credentials=creds)
    except: return None

def clean_author_name(name):
    if not name: return "미상"
    return ' '.join(name.replace('#', '').replace('기자', '').split())

def crawl_single_article(url_path):
    full_url = f"http://www.cooknchefnews.com{url_path}"
    try:
        response = requests.get(full_url, timeout=2)
        soup = BeautifulSoup(response.text, 'html.parser')
        author = "관리자"
        author_tag = soup.select_one('.user-name') or soup.select_one('.writer')
        if author_tag: author = author_tag.text.strip()
        author = clean_author_name(author)
        cat, subcat = "뉴스", "이슈"
        breadcrumbs = soup.select('.location a') or soup.select('.breadcrumb a')
        if breadcrumbs and len(breadcrumbs) >= 2: cat = breadcrumbs[1].text.strip()
        if breadcrumbs and len(breadcrumbs) >= 3: subcat = breadcrumbs[2].text.strip()
        return (author, cat, subcat)
    except: return ("관리자", "뉴스", "이슈")

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

@st.cache_data(ttl=3600)
def load_all_dashboard_data(selected_week):
    dr = WEEK_MAP[selected_week]
    s_dt, e_dt = dr.split(' ~ ')[0].replace('.', '-'), dr.split(' ~ ')[1].replace('.', '-')
    ls_dt = (datetime.strptime(s_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')
    le_dt = (datetime.strptime(e_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')

    # KPI 데이터
    summary = run_ga4_report(s_dt, e_dt, [], ["activeUsers", "screenPageViews", "newUsers"])
    sel_uv, sel_pv = (int(summary['activeUsers'][0]), int(summary['screenPageViews'][0])) if not summary.empty else (0, 0)

    # 일별 데이터 (X축 오류 수정)
    df_daily = run_ga4_report(s_dt, e_dt, ["date"], ["activeUsers", "screenPageViews"])
    if not df_daily.empty:
        df_daily['날짜'] = pd.to_datetime(df_daily['date'], format='%Y%m%d').dt.strftime('%m-%d')
        df_daily = df_daily.sort_values('date')

    # 3개월 추이 (정렬 및 연도 구분)
    def fetch_week_data(wl, ds):
        ws, we = ds.split(' ~ ')[0].replace('.', '-'), ds.split(' ~ ')[1].replace('.', '-')
        res = run_ga4_report(ws, we, [], ["activeUsers", "screenPageViews"])
        if not res.empty:
            y = ws[:4]
            wn = int(re.search(r'\d+', wl).group())
            return {'주차': f"{y}년 {wl}", 'UV': int(res['activeUsers'][0]), 'PV': int(res['screenPageViews'][0]), 'sort': f"{y}{wn:02d}"}
        return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        results = [f.result() for f in concurrent.futures.as_completed([ex.submit(fetch_week_data, wl, dstr) for wl, dstr in list(WEEK_MAP.items())[:12]]) if f.result()]
    df_weekly = pd.DataFrame(results).sort_values('sort') if results else pd.DataFrame()

    # 유입경로 (매체별 구분 + KeyError 방지)
    df_t_raw = run_ga4_report(s_dt, e_dt, ["sessionSource", "sessionMedium"], ["screenPageViews"])
    if not df_t_raw.empty and 'sessionSource' in df_t_raw.columns:
        def map_media(row):
            s, m = str(row['sessionSource']).lower(), str(row['sessionMedium']).lower()
            if 'naver' in s: return '네이버'
            if 'daum' in s: return '다음'
            if 'google' in s: return '구글'
            if m == 'organic': return '검색엔진(기타)'
            if 'facebook' in s or 'instagram' in s: return 'SNS'
            return '직접/기타'
        df_t_raw['매체'] = df_t_raw.apply(map_media, axis=1)
        df_traffic = df_t_raw.groupby('매체')['screenPageViews'].sum().reset_index().rename(columns={'screenPageViews':'조회수'})
    else: df_traffic = pd.DataFrame(columns=['매체', '조회수'])

    # 기사 TOP10 (활성/발행 이원화)
    # 활성기사: 누적 데이터 중 기간 내 조회수 상위
    df_top_raw = run_ga4_report(s_dt, e_dt, ["pageTitle", "pagePath"], ["screenPageViews", "activeUsers", "userEngagementDuration"], order_by_metric="screenPageViews", limit=15)
    df_top_raw = df_top_raw[~df_top_raw['pageTitle'].str.contains('쿡앤셰프|Cook&Chef', na=False)].head(10)
    
    # 크롤링으로 카테고리/작성자 보완
    if not df_top_raw.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            scraped = list(ex.map(crawl_single_article, df_top_raw['pagePath']))
        df_top_raw['작성자'], df_top_raw['카테고리'], df_top_raw['세부카테고리'] = zip(*scraped)
        df_top_raw['순위'] = range(1, len(df_top_raw)+1)
    
    # 카테고리 분석 데이터
    df_cat = df_top_raw.groupby('카테고리')['screenPageViews'].sum().reset_index().rename(columns={'screenPageViews':'조회수'}) if not df_top_raw.empty else pd.DataFrame()

    return (sel_uv, sel_pv, df_daily, df_weekly, df_traffic, df_top_raw, df_cat)

# ----------------- 렌더링 함수들 -----------------
def render_summary(df_w, pv, uv, df_d, active_cnt):
    st.markdown('<div class="section-header-container"><div class="section-header">1. 주간 전체 성과 요약</div></div>', unsafe_allow_html=True)
    kpis = [("지난 7일 간 조회수(PV)", pv, "건"), ("지난 7일 간 방문자수(UV)", uv, "명"), ("활성 기사 수", active_cnt, "건")]
    cols = st.columns(3)
    for i, (l, v, u) in enumerate(kpis):
        cols[i].markdown(f'<div class="kpi-container"><div class="kpi-label">{l}</div><div class="kpi-value">{v:,}<span class="kpi-unit">{u}</span></div></div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sub-header">📊 주간 일별 방문 추이</div>', unsafe_allow_html=True)
        if not df_d.empty:
            fig = px.bar(df_d, x='날짜', y=['activeUsers', 'screenPageViews'], barmode='group', color_discrete_map={'activeUsers':COLOR_GREY, 'screenPageViews':COLOR_NAVY})
            fig.update_layout(xaxis_type='category', legend=dict(orientation="h", y=1.1, x=1))
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown('<div class="sub-header">📈 최근 3개월 추이</div>', unsafe_allow_html=True)
        if not df_w.empty:
            fig2 = go.Figure([go.Bar(x=df_w['주차'], y=df_w['UV'], name='UV', marker_color=COLOR_GREY), go.Bar(x=df_w['주차'], y=df_w['PV'], name='PV', marker_color=COLOR_NAVY)])
            fig2.update_layout(barmode='group', xaxis_type='category', margin=dict(t=0))
            st.plotly_chart(fig2, use_container_width=True)

# ----------------- 메인 실행 -----------------
if 'print_mode' not in st.session_state: st.session_state['print_mode'] = False

# 인쇄 미리보기 시 유연한 주차 적용 (현재 선택값 유지)
sel_week = st.selectbox("📅 조회 주차 선택", list(WEEK_MAP.keys()), index=0, key="week_box")
(uv, pv, df_d, df_w, df_tr, df_at, df_cat) = load_all_dashboard_data(sel_week)

# 헤더 및 제어 버튼
c_h1, c_h2 = st.columns([4, 1])
with c_h1: st.markdown(f'<div class="report-title">📰 주간 성과보고서 ({sel_week})</div>', unsafe_allow_html=True)
with c_h2:
    if st.session_state['print_mode']:
        if st.button("🔙 돌아가기"): st.session_state['print_mode'] = False; st.rerun()
        if st.button("🖨️ 인쇄 실행"): components.v1.html("<script>window.parent.print();</script>", height=0)
    else:
        if st.button("🖨️ 인쇄 미리보기"): st.session_state['print_mode'] = True; st.rerun()

if st.session_state['print_mode']:
    st.markdown('<div class="print-preview-layout">', unsafe_allow_html=True)
    render_summary(df_w, pv, uv, df_d, len(df_at))
    st.markdown('<div class="page-break"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">🔥 활성 기사 TOP 10 (지난 7일 간 조회수)</div>', unsafe_allow_html=True)
    st.dataframe(df_at, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    t = st.tabs(["📊 성과 요약", "🔝 기사/카테고리 분석", "🌐 유입 경로"])
    with t[0]: render_summary(df_w, pv, uv, df_d, len(df_at))
    with t[1]:
        st.markdown('<div class="sub-header">🔥 활성 기사 TOP 10 (지난 7일 간 조회수)</div>', unsafe_allow_html=True)
        st.dataframe(df_at[['순위', '카테고리', 'pageTitle', '작성자', 'screenPageViews']], use_container_width=True, hide_index=True)
        st.markdown("---")
        st.markdown('<div class="sub-header">📂 카테고리별 비중 (지난 7일 간 조회수)</div>', unsafe_allow_html=True)
        if not df_cat.empty:
            # 원그래프 크기 조절을 위해 컨테이너 사용
            cc1, cc2 = st.columns([1, 1])
            with cc1:
                fig_c = px.pie(df_cat, values='조회수', names='카테고리', hole=0.4, color_discrete_sequence=CHART_PALETTE)
                fig_c.update_layout(width=400, height=400, margin=dict(t=0, b=0))
                st.plotly_chart(fig_c, use_container_width=True)
    with t[2]:
        st.markdown('<div class="sub-header">🌐 매체별 유입 분석 (지난 7일 간 조회수)</div>', unsafe_allow_html=True)
        if not df_tr.empty:
            st.plotly_chart(px.pie(df_tr, values='조회수', names='매체', hole=0.4, color_discrete_sequence=CHART_PALETTE), use_container_width=True)

st.markdown('<div class="footer-note no-print">※ 쿡앤셰프(Cook&Chef) GA4 데이터 자동 집계 시스템</div>', unsafe_allow_html=True)
