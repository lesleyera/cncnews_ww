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
body {{ background-color: #ffffff; font-family: 'Pretendard', sans-serif; color: #263238; font-size: 18px; }}

header[data-testid="stHeader"] {{ visibility: hidden !important; }}
[data-testid="stToolbar"] {{ visibility: hidden !important; }}
.block-container {{ padding-top: 2rem !important; padding-bottom: 5rem; max_width: 100% !important; }}
[data-testid="stSidebar"] {{ display: none; }}

.report-title {{ font-size: 3.5rem; font-weight: 900; color: {COLOR_NAVY}; border-bottom: 5px solid {COLOR_RED}; padding-bottom: 20px; margin-top: 10px; }}
.period-info {{ font-size: 1.6rem; font-weight: 700; color: #455a64; margin-top: 15px; }}
.update-time {{ color: {COLOR_NAVY}; font-weight: 700; font-size: 1.3rem; text-align: right; margin-top: -15px; margin-bottom: 30px; font-family: monospace; }}
.kpi-container {{ background-color: #fff; border: 1px solid #eceff1; border-top: 6px solid {COLOR_RED}; border-radius: 8px; padding: 25px 15px; text-align: center; margin-bottom: 15px; height: 200px; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
.kpi-label {{ font-size: 1.5rem; font-weight: 700; color: #455a64; margin-bottom: 12px; white-space: nowrap; }}
.kpi-value {{ font-size: 3.2rem; font-weight: 900; color: {COLOR_NAVY}; line-height: 1.1; }}
.kpi-unit {{ font-size: 1.4rem; font-weight: 600; color: #90a4ae; margin-left: 3px; }}
.section-header-container {{ margin-top: 30px; margin-bottom: 25px; padding: 20px 30px; background-color: {COLOR_BG_ACCENT}; border-left: 10px solid {COLOR_NAVY}; border-radius: 4px; }}
.section-header {{ font-size: 2.5rem; font-weight: 800; color: {COLOR_NAVY}; margin: 0; }}
.sub-header {{ font-size: 1.8rem; font-weight: 700; color: {COLOR_NAVY}; margin-top: 30px; margin-bottom: 15px; border-left: 5px solid {COLOR_RED}; padding-left: 15px; }}
.stTabs [data-baseweb="tab"] {{ height: 80px; font-size: 1.5rem; font-weight: 700; }}
[data-testid="stDataFrame"] thead th {{ background-color: {COLOR_NAVY} !important; color: white !important; font-size: 1.3rem !important; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# 가로 인쇄 및 확대 설정
PRINT_CSS = """
<style>
@media print {
    @page { size: A4 landscape; margin: 8mm; }
    body { transform: scale(0.85) !important; transform-origin: top left !important; width: 118% !important; font-size: 18px !important; }
    .no-print, header, footer, [data-testid="stSidebar"] { display: none !important; }
    .page-break { page-break-before: always !important; display: block; height: 1px; }
    .kpi-container { height: 160px !important; }
}
</style>
"""
st.markdown(PRINT_CSS, unsafe_allow_html=True)

# ----------------- 3. 진입 보안 -----------------
def check_password():
    if st.session_state.get("password_correct", False): return True
    lp = st.empty()
    with lp.container():
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown('<div style="margin-top:100px; text-align:center; font-size:28px; font-weight:700;">🔒 Access Code</div>', unsafe_allow_html=True)
            pw = st.text_input("PW", type="password", label_visibility="collapsed")
            if pw == "cncnews2026":
                st.session_state["password_correct"] = True
                st.rerun()
            elif pw: st.error("🚫 Incorrect code")
    return False

if not check_password(): st.stop()

# ----------------- 4. 데이터 로직 -----------------
PROPERTY_ID = "370663478"

@st.cache_resource
def get_ga4_client():
    try:
        key_dict = st.secrets["ga4_credentials"]
        return BetaAnalyticsDataClient(credentials=service_account.Credentials.from_service_account_info(key_dict))
    except: return None

def map_source(source):
    s = source.lower()
    if 'naver' in s: return '네이버'
    if 'daum' in s: return '다음'
    if 'google' in s: return '구글'
    if '(direct)' in s: return '직접 접근'
    return '기타'

def crawl_meta(url_path):
    full_url = f"http://www.cooknchefnews.com{url_path}"
    try:
        res = requests.get(full_url, timeout=2)
        soup = BeautifulSoup(res.text, 'html.parser')
        author = "관리자"
        a_tag = soup.select_one('.user-name') or soup.select_one('.writer')
        if a_tag: author = a_tag.text.strip().replace('기자', '')
        
        d_tag = soup.select_one('.date') or soup.select_one('.publish-date') or soup.select_one('time')
        p_date = ""
        if d_tag: p_date = re.sub(r'[^0-9\-]', '', d_tag.text.strip())[:10]
        
        cat = "뉴스"
        bread = soup.select('.location a')
        if len(bread) >= 2: cat = bread[1].text.strip()
        return author, cat, p_date
    except: return "관리자", "뉴스", ""

def get_weeks():
    w = {}
    today = datetime.now()
    ls = today - timedelta(days=(today.weekday() + 1) % 7)
    for i in range(12):
        s = ls - timedelta(weeks=i)
        e = s + timedelta(days=6)
        label = f"{s.isocalendar()[1]}주차"
        w[label] = f"{s.strftime('%Y.%m.%d')} ~ {e.strftime('%Y.%m.%d')}"
    return w
WEEK_MAP = get_weeks()

def run_ga4(sd, ed, dims, mets, limit=10000):
    client = get_ga4_client()
    if not client: return pd.DataFrame()
    req = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in dims],
        metrics=[Metric(name=m) for m in mets],
        date_ranges=[DateRange(start_date=sd, end_date=ed)],
        limit=limit
    )
    res = client.run_report(req)
    data = []
    for row in res.rows:
        rd = {dims[i]: row.dimension_values[i].value for i in range(len(dims))}
        for i, m in enumerate(mets): rd[m] = float(row.metric_values[i].value) if '.' in row.metric_values[i].value else int(row.metric_values[i].value)
        data.append(rd)
    return pd.DataFrame(data)

@st.cache_data(ttl=3600)
def load_full_data(selected_week):
    dr = WEEK_MAP[selected_week]
    s_dt, e_dt = dr.split(' ~ ')[0].replace('.', '-'), dr.split(' ~ ')[1].replace('.', '-')
    ls_dt = (datetime.strptime(s_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')
    le_dt = (datetime.strptime(e_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')

    sum_res = run_ga4(s_dt, e_dt, [], ["activeUsers", "screenPageViews", "newUsers"])
    uv = int(sum_res['activeUsers'][0]) if not sum_res.empty else 0
    pv = int(sum_res['screenPageViews'][0]) if not sum_res.empty else 0
    nu = int(sum_res['newUsers'][0]) if not sum_res.empty else 0

    df_daily = run_ga4(s_dt, e_dt, ["date"], ["activeUsers", "screenPageViews"])
    if not df_daily.empty:
        df_daily['날짜'] = pd.to_datetime(df_daily['date'], format='%Y%m%d').dt.strftime('%m-%d')
        df_daily = df_daily.sort_values('날짜')

    # 기사별 상세 데이터 및 유입경로 (이원화 분석)
    df_raw = run_ga4(s_dt, e_dt, ["pageTitle", "pagePath", "sessionSource"], ["screenPageViews", "activeUsers"])
    unique_paths = df_raw[df_raw['pagePath'].str.contains(r'article|news|view', na=False)]['pagePath'].unique()[:50]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        meta_results = list(ex.map(crawl_meta, unique_paths))
    
    art_data = []
    for path, meta in zip(unique_paths, meta_results):
        p_data = df_raw[df_raw['pagePath'] == path].copy()
        total_p_pv = p_data['screenPageViews'].sum()
        total_p_uv = p_data['activeUsers'].sum()
        
        sources = p_data.groupby('sessionSource')['screenPageViews'].sum().reset_index()
        sources['매체'] = sources['sessionSource'].apply(map_traffic_source)
        source_summary = sources.groupby('매체')['screenPageViews'].sum().to_dict()
        source_str = " | ".join([f"{k}: {int(v/total_p_pv*100)}%" for k,v in source_summary.items()])

        art_data.append({
            "제목": p_data['pageTitle'].iloc[0], "경로": path, "작성자": meta[0],
            "카테고리": meta[1], "발행일": meta[2], "조회수": total_p_pv, 
            "방문자수": total_p_uv, "매체비중": source_str, "유입매체_상세": source_summary
        })
    
    df_art = pd.DataFrame(art_data)
    df_top_active = df_art.sort_values('조회수', ascending=False).head(10) # 활성기사 TOP10
    df_top_pub = df_art[df_art['발행일'].between(s_dt, e_dt)].sort_values('조회수', ascending=False).head(10) # 발행기사 TOP10

    df_cat = df_art.groupby('카테고리')['조회수'].sum().reset_index()
    df_reg_c = run_ga4(s_dt, e_dt, ["region"], ["activeUsers"])
    df_reg_l = run_ga4(ls_dt, le_dt, ["region"], ["activeUsers"])

    return uv, pv, nu, df_daily, df_top_active, df_top_pub, df_cat, df_reg_c, df_reg_l

# ----------------- 5. 렌더링 -----------------
def render_summary(pv, uv, nu, act_cnt, df_daily):
    st.markdown('<div class="section-header-container"><div class="section-header">1. 주간 전체 성과 요약</div></div>', unsafe_allow_html=True)
    cols = st.columns(4)
    titles = ["(지난 7일 간) 조회수", "(지난 7일 간) 방문자수", "신규 방문자 수", "활성 기사 수"]
    vals = [pv, uv, nu, act_cnt]
    units = ["건", "명", "명", "건"]
    for i in range(4):
        cols[i].markdown(f'<div class="kpi-container"><div class="kpi-label">{titles[i]}</div><div class="kpi-value">{vals[i]:,}<span class="kpi-unit">{units[i]}</span></div></div>', unsafe_allow_html=True)
    
    if not df_daily.empty:
        st.markdown('<div class="sub-header">📊 주간 일별 방문 추이</div>', unsafe_allow_html=True)
        st.plotly_chart(px.bar(df_daily.melt(id_vars='날짜', value_vars=['UV', 'PV']), x='날짜', y='value', color='variable', barmode='group', color_discrete_map={'UV': COLOR_GREY, 'PV': COLOR_NAVY}, key="daily_chart"), use_container_width=True)

def render_top10(df_active, df_pub):
    st.markdown('<div class="section-header-container"><div class="section-header">2. TOP 10 기사 상세 분석 (이원화)</div></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔥 활성 기사 기준 (누적)", "🆕 발행 기사 기준 (신규)"])
    
    for tab, df, key_suffix in [(t1, df_active, "act"), (t2, df_pub, "pub")]:
        with tab:
            if not df.empty:
                df_disp = df[['카테고리', '제목', '작성자', '발행일', '조회수', '방문자수', '매체비중']].copy()
                st.dataframe(df_disp, use_container_width=True, hide_index=True)
                
                # 매체별 유입 비중 차트 (마우스 오버 상세 확인용)
                chart_data = []
                for _, row in df.iterrows():
                    for m, v in row['유입매체_상세'].items():
                        chart_data.append({"제목": row['제목'][:15]+"..", "매체": m, "조회수": v})
                fig = px.bar(pd.DataFrame(chart_data), x="제목", y="조회수", color="매체", title="기사별 유입 매체 분포", color_discrete_sequence=CHART_PALETTE)
                st.plotly_chart(fig, use_container_width=True, key=f"top10_chart_{key_suffix}")

def render_category_demo(df_cat, rc, rl):
    st.markdown('<div class="section-header-container"><div class="section-header">3. 카테고리 및 지역별 분석</div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sub-header">카테고리별 조회 비중 (원형)</div>', unsafe_allow_html=True)
        st.plotly_chart(px.pie(df_cat, names='카테고리', values='조회수', hole=0.4, color_discrete_sequence=CHART_PALETTE, key="cat_pie"), use_container_width=True)
    with c2:
        st.markdown('<div class="sub-header">지역별 유입 (지난주 크기 축소)</div>', unsafe_allow_html=True)
        cc1, cc2 = st.columns([1.5, 1])
        with cc1: st.plotly_chart(px.pie(rc.head(8), names='region', values='activeUsers', title="이번주", key="reg_pie_c"), use_container_width=True)
        with cc2: st.plotly_chart(px.pie(rl.head(8), names='region', values='activeUsers', title="지난주").update_layout(showlegend=False, height=280), use_container_width=True, key="reg_pie_l")

def render_freelancer(df_active):
    st.markdown('<div class="section-header-container"><div class="section-header">4. 프리랜서 기자 성과 평가</div></div>', unsafe_allow_html=True)
    fl_names = ['맛객', 'Chef J', '푸드헌터', 'Dr.Kim']
    df_fl = df_active[df_active['작성자'].isin(fl_names)].copy()
    if not df_fl.empty:
        st.dataframe(df_fl[['작성자', '제목', '조회수', '방문자수', '발행일', '매체비중']], hide_index=True, use_container_width=True)
    else: st.info("이번주 TOP 10 내 프리랜서 기자 기사가 없습니다.")

# ----------------- 6. 메인 -----------------
if 'print_mode' not in st.session_state: st.session_state['print_mode'] = False

c1, c2 = st.columns([2, 1])
with c1: st.markdown('<div class="report-title">📰 쿡앤셰프 주간 성과보고서</div>', unsafe_allow_html=True)
with c2:
    col_btn1, col_btn2 = st.columns(2)
    if st.session_state['print_mode']:
        if col_btn1.button("🔙 대시보드 복귀"): st.session_state['print_mode'] = False; st.rerun()
        if col_btn2.button("🖨️ 인쇄 실행", type="primary"): components.html("<script>window.parent.print();</script>", height=0)
    else:
        if col_btn2.button("🖨️ 인쇄 미리보기", type="primary"): st.session_state['print_mode'] = True; st.rerun()
    sel_w = st.selectbox("주차 선택", list(WEEK_MAP.keys()), key="ws_select", label_visibility="collapsed")

# 데이터 로드
uv, pv, nu, df_daily, df_act, df_pub, df_cat, rc, rl = load_full_data(sel_w)

if st.session_state['print_mode']:
    st.markdown('<div class="print-preview-layout">', unsafe_allow_html=True)
    render_summary(pv, uv, nu, len(df_act), df_daily)
    render_top10(df_act, df_pub)
    st.markdown('<div class="page-break"></div>', unsafe_allow_html=True)
    render_category_demo(df_cat, rc, rl)
    render_freelancer(df_act)
    st.markdown('<div class="print-footer">Cook&Chef Weekly 성과보고서 - 해당 주차 데이터 기준</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    render_summary(pv, uv, nu, len(df_act), df_daily)
    render_top10(df_act, df_pub)
    render_category_demo(df_cat, rc, rl)
    render_freelancer(df_act)

st.markdown('<div class="footer-note no-print">※ 데이터 출처: Google Analytics 4 (Property: 370663478)</div>', unsafe_allow_html=True)
