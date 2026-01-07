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

# ----------------- 2. CSS 스타일 정의 (폰트 확대 및 가로 인쇄 최적화) -----------------
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

.report-title {{ font-size: 3.5rem; font-weight: 900; color: {COLOR_NAVY}; border-bottom: 5px solid {COLOR_RED}; padding-bottom: 20px; }}
.period-info {{ font-size: 1.6rem; font-weight: 700; color: #455a64; margin-top: 15px; }}
.update-time {{ color: {COLOR_NAVY}; font-weight: 700; font-size: 1.3rem; text-align: right; margin-top: -15px; margin-bottom: 30px; font-family: monospace; }}
.kpi-container {{ background-color: #fff; border: 1px solid #eceff1; border-top: 6px solid {COLOR_RED}; border-radius: 8px; padding: 25px 15px; text-align: center; margin-bottom: 15px; height: 200px; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
.kpi-label {{ font-size: 1.5rem; font-weight: 700; color: #455a64; margin-bottom: 12px; }}
.kpi-value {{ font-size: 3.2rem; font-weight: 900; color: {COLOR_NAVY}; line-height: 1.1; }}
.section-header {{ font-size: 2.5rem; font-weight: 800; color: {COLOR_NAVY}; margin: 0; }}
.sub-header {{ font-size: 1.8rem; font-weight: 700; color: {COLOR_NAVY}; margin-top: 35px; border-left: 5px solid {COLOR_RED}; padding-left: 15px; }}
.stTabs [data-baseweb="tab"] {{ height: 80px; font-size: 1.5rem; font-weight: 700; }}
[data-testid="stDataFrame"] thead th {{ background-color: {COLOR_NAVY} !important; color: white !important; font-size: 1.3rem !important; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

PRINT_CSS = """
<style>
@media print {
    @page { size: A4 landscape; margin: 8mm; }
    body { transform: scale(0.85) !important; transform-origin: top left !important; width: 118% !important; }
    .no-print { display: none !important; }
    .page-break { page-break-before: always !important; display: block; height: 1px; }
    .kpi-container { height: 160px !important; }
    [data-testid="stDataFrame"] { font-size: 14px !important; width: 100% !important; }
}
</style>
"""
st.markdown(PRINT_CSS, unsafe_allow_html=True)

# ----------------- 3. 보안 및 데이터 유틸리티 -----------------
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

PROPERTY_ID = "370663478"

@st.cache_resource
def get_ga4_client():
    try:
        kd = st.secrets["ga4_credentials"]
        return BetaAnalyticsDataClient(credentials=service_account.Credentials.from_service_account_info(kd))
    except: return None

def map_source(s):
    s = s.lower()
    if 'naver' in s: return '네이버'
    if 'daum' in s: return '다음'
    if 'google' in s: return '구글'
    if '(direct)' in s: return '직접'
    return '기타'

def crawl_article_meta(url_path):
    full_url = f"http://www.cooknchefnews.com{url_path}"
    try:
        res = requests.get(full_url, timeout=2)
        soup = BeautifulSoup(res.text, 'html.parser')
        author = "관리자"
        a_tag = soup.select_one('.user-name') or soup.select_one('.writer')
        if a_tag: author = a_tag.text.strip().replace('기자', '')
        
        date_str = ""
        d_tag = soup.select_one('.date') or soup.select_one('.regdate')
        if d_tag: date_str = re.sub(r'[^0-9\-]', '', d_tag.text.strip())[:10]
        
        cat = "뉴스"
        bread = soup.select('.location a')
        if len(bread) >= 2: cat = bread[1].text.strip()
        
        return {"작성자": author, "카테고리": cat, "발행일": date_str}
    except: return {"작성자": "관리자", "카테고리": "뉴스", "발행일": ""}

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
        row_dict = {dims[i]: row.dimension_values[i].value for i in range(len(dims))}
        for i, m in enumerate(mets): row_dict[m] = float(row.metric_values[i].value) if '.' in row.metric_values[i].value else int(row.metric_values[i].value)
        data.append(row_dict)
    return pd.DataFrame(data)

# ----------------- 4. 데이터 엔진 (이원화 분석) -----------------
@st.cache_data(ttl=3600)
def load_full_data(selected_week):
    dr = WEEK_MAP[selected_week]
    s_dt, e_dt = dr.split(' ~ ')[0].replace('.', '-'), dr.split(' ~ ')[1].replace('.', '-')
    ls_dt = (datetime.strptime(s_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')
    le_dt = (datetime.strptime(e_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')

    # KPI
    k_res = run_ga4(s_dt, e_dt, [], ["activeUsers", "screenPageViews", "newUsers"])
    uv = int(k_res['activeUsers'][0]) if not k_res.empty else 0
    pv = int(k_res['screenPageViews'][0]) if not k_res.empty else 0
    nu = int(k_res['newUsers'][0]) if not k_res.empty else 0

    # 기사별 매체 유입 상세 데이터
    df_raw = run_ga4(s_dt, e_dt, ["pageTitle", "pagePath", "sessionSource"], ["screenPageViews", "activeUsers", "userEngagementDuration", "bounceRate"])
    unique_paths = df_raw[df_raw['pagePath'].str.contains(r'article|news', na=False)]['pagePath'].unique()[:50]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        meta_map = {p: ex.submit(crawl_article_meta, p) for p in unique_paths}
    
    art_list = []
    for p in unique_paths:
        m = meta_map[p].result()
        p_data = df_raw[df_raw['pagePath'] == p].copy()
        p_data['매체'] = p_data['sessionSource'].apply(map_source)
        
        source_dist = p_data.groupby('매체')['screenPageViews'].sum().to_dict()
        total_p_pv = sum(source_dist.values())
        total_p_uv = p_data['activeUsers'].sum()
        
        # 툴팁용 매체 비중 문자열
        dist_str = " | ".join([f"{k}: {int(v/total_p_pv*100)}%" for k, v in source_dist.items()])
        
        art_list.append({
            "제목": p_data['pageTitle'].iloc[0], "경로": p, "작성자": m["작성자"], 
            "카테고리": m["카테고리"], "발행일": m["발행일"], "조회수": total_p_pv, 
            "방문자수": total_p_uv, "매체비중": dist_str
        })
    
    df_art = pd.DataFrame(art_list)
    df_pub = df_art[df_art['발행일'].between(s_dt, e_dt)].sort_values('조회수', ascending=False).head(10)
    df_act = df_art.sort_values('조회수', ascending=False).head(10)

    # 데모 및 지역 (원형 그래프 크기 조정용)
    df_reg_c = run_ga4(s_dt, e_dt, ["region"], ["activeUsers"])
    df_reg_l = run_ga4(ls_dt, le_dt, ["region"], ["activeUsers"])
    df_cat = df_art.groupby('카테고리')['조회수'].sum().reset_index()

    return (uv, pv, nu, df_pub, df_act, df_cat, df_reg_c, df_reg_l)

# ----------------- 5. 렌더링 섹션 -----------------
def render_kpis(pv, uv, nu, act_cnt):
    st.markdown('<div class="section-header-container"><div class="section-header">1. 주간 전체 성과 요약</div></div>', unsafe_allow_html=True)
    k_list = [("(지난 7일 간) 조회수", pv, "건"), ("(지난 7일 간) 방문자수", uv, "명"), ("신규 방문자", nu, "명"), ("활성 기사수", act_cnt, "건")]
    cols = st.columns(4)
    for i, (l, v, u) in enumerate(k_list):
        cols[i].markdown(f'<div class="kpi-container"><div class="kpi-label">{l}</div><div class="kpi-value">{v:,}<span style="font-size:1.5rem; color:#999; margin-left:5px;">{u}</span></div></div>', unsafe_allow_html=True)

def render_top10(df_pub, df_act):
    st.markdown('<div class="section-header-container"><div class="section-header">2. TOP 10 기사 상세 분석 (이원화)</div></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔥 활성 기사 기준 (누적)", "🆕 발행 기사 기준 (이번주)"])
    
    for tab, df, label in [(t1, df_act, "활성"), (t2, df_pub, "발행")]:
        with tab:
            if not df.empty:
                df['순위'] = range(1, len(df)+1)
                st.dataframe(df[['순위', '카테고리', '제목', '작성자', '발행일', '조회수', '방문자수', '매체비중']], hide_index=True, use_container_width=True)
                fig = px.bar(df, x="조회수", y="제목", orientation='h', color="작성자", text="매체비중", title=f"{label} 기사 매체 유입 비중")
                fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=500)
                st.plotly_chart(fig, use_container_width=True)

def render_cats_demos(df_cat, df_reg_c, df_reg_l):
    st.markdown('<div class="section-header-container"><div class="section-header">3. 카테고리 및 지역별 분석</div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sub-header">카테고리별 분석 (원형)</div>', unsafe_allow_html=True)
        st.plotly_chart(px.pie(df_cat, names='카테고리', values='조회수', hole=0.4, color_discrete_sequence=CHART_PALETTE), use_container_width=True)
    with c2:
        st.markdown('<div class="sub-header">지역별 유입 비중 (지난주 크기 축소)</div>', unsafe_allow_html=True)
        cc1, cc2 = st.columns([1.5, 1])
        with cc1: st.plotly_chart(px.pie(df_reg_c.head(7), names='region', values='activeUsers', title="이번주"), use_container_width=True)
        with cc2: st.plotly_chart(px.pie(df_reg_l.head(7), names='region', values='activeUsers', title="지난주").update_layout(showlegend=False, height=300), use_container_width=True)

# ----------------- 6. 메인 컨트롤러 -----------------
if 'print_mode' not in st.session_state: st.session_state['print_mode'] = False

c1, c2 = st.columns([2, 1])
with c1: st.markdown('<div class="report-title">📰 쿡앤셰프 주간 성과보고서</div>', unsafe_allow_html=True)
with c2:
    btn_c1, btn_c2 = st.columns(2)
    if st.session_state['print_mode']:
        if btn_c1.button("🔙 대시보드 복귀"): st.session_state['print_mode'] = False; st.rerun()
        if btn_c2.button("🖨️ 인쇄 실행", type="primary"): components.html("<script>window.parent.print();</script>", height=0)
    else:
        if btn_c2.button("🖨️ 인쇄 미리보기", type="primary"): st.session_state['print_mode'] = True; st.rerun()
    sel_w = st.selectbox("📅 주차", list(WEEK_MAP.keys()), key="ws", label_visibility="collapsed")

(uv, pv, nu, df_pub, df_act, df_cat, rc, rl) = load_full_data(sel_w)

if st.session_state['print_mode']:
    st.markdown('<div class="print-preview-layout">', unsafe_allow_html=True)
    render_kpis(pv, uv, nu, len(df_act))
    render_top10(df_pub, df_act)
    st.markdown('<div class="page-break"></div>', unsafe_allow_html=True)
    render_cats_demos(df_cat, rc, rl)
    st.markdown('<div class="print-footer">Cook&Chef Weekly 성과보고서 - 해당 주차 데이터 기준</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    render_kpis(pv, uv, nu, len(df_act))
    render_top10(df_pub, df_act)
    render_cats_demos(df_cat, rc, rl)

st.markdown('<div class="footer-note no-print">※ 쿡앤셰프(Cook&Chef) GA4 데이터 자동 집계 시스템</div>', unsafe_allow_html=True)
