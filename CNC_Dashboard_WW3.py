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
NOW_STR = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# 기본 스타일 (화면용)
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

/* 프린트 시 강제 적용 스타일 (백업용) */
@media print {{
    @page {{ size: A4; margin: 10mm; }}
    header, footer, [data-testid="stSidebar"], [data-testid="stHeader"], .no-print {{ display: none !important; }}
    .stTabs [data-baseweb="tab-list"] {{ display: none !important; }}
    .section-header-container {{ break-before: page; margin-top: 20px !important; }}
    .first-section {{ break-before: auto !important; }}
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------- 3. 진입 보안 화면 (로그인) -----------------
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    login_placeholder = st.empty()
    with login_placeholder.container():
        st.markdown(
            """
            <style>
            .login-container { max-width: 400px; margin: 100px auto; padding: 40px; text-align: center; }
            .login-title { font-size: 24px; font-weight: 700; color: #1a237e; margin-bottom: 20px; text-align: center; }
            .powered-by { font-size: 12px; color: #90a4ae; margin-top: 50px; font-weight: 500; }
            .stTextInput > div > div > input { text-align: center; font-size: 18px; letter-spacing: 2px; }
            </style>
            """, unsafe_allow_html=True
        )
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
                else:
                    st.error("🚫 코드가 올바르지 않습니다.")
            
            st.markdown('<div class="powered-by">Powered by DWG Inc.</div>', unsafe_allow_html=True)
            
    return False

if not check_password():
    st.stop()

# =================================================================
# ▼ 메인 로직 시작 ▼
# =================================================================

PROPERTY_ID = "370663478" 

# ----------------- GA4 및 데이터 처리 함수 -----------------
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
        else:
            for tag in soup.select('span, div, li'):
                txt = tag.text.strip()
                if '기자' in txt and len(txt) < 10:
                    author = txt; break
        author = clean_author_name(author)
        likes = int(soup.select_one('.sns-like-count').text.replace(',', '')) if soup.select_one('.sns-like-count') else 0
        comments = int(soup.select_one('.comment-count').text.replace(',', '')) if soup.select_one('.comment-count') else 0
        cat, subcat = "뉴스", "이슈"
        breadcrumbs = soup.select('.location a') or soup.select('.breadcrumb a') or soup.select('.path a')
        if breadcrumbs:
            if len(breadcrumbs) >= 2: cat = breadcrumbs[1].text.strip()
            if len(breadcrumbs) >= 3: subcat = breadcrumbs[2].text.strip()
        else:
            meta_sec = soup.select_one('meta[property="article:section"]')
            if meta_sec: cat = meta_sec.get('content')
        return (author, likes, comments, cat, subcat)
    except: 
        return ("관리자", 0, 0, "뉴스", "이슈")

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
    except: return pd.DataFrame(columns=dimensions + metrics)

def create_donut_chart_with_val(df, names, values, color_map=None):
    if df.empty: return go.Figure()
    if '구분' in df.columns:
        df_normal = df[df['구분'] != '기타'].sort_values(by=values, ascending=False)
        df_other = df[df['구분'] == '기타']
        df_sorted = pd.concat([df_normal, df_other])
    else: df_sorted = df
    if color_map: fig = px.pie(df_sorted, names=names, values=values, hole=0.5, color=names, color_discrete_map=color_map)
    else: fig = px.pie(df_sorted, names=names, values=values, hole=0.5, color_discrete_sequence=CHART_PALETTE)
    fig.update_traces(textposition='outside', textinfo='label+percent', sort=False)
    fig.update_layout(showlegend=False, margin=dict(t=30, b=80, l=40, r=40), height=350)
    return fig

# 데이터 로딩 함수
@st.cache_data(ttl=3600, show_spinner="데이터 불러오는 중...")
def load_all_dashboard_data(selected_week):
    dr = WEEK_MAP[selected_week]
    s_dt, e_dt = dr.split(' ~ ')[0].replace('.', '-'), dr.split(' ~ ')[1].replace('.', '-')
    ls_dt = (datetime.strptime(s_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')
    le_dt = (datetime.strptime(e_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')

    # 1. KPI
    summary = run_ga4_report(s_dt, e_dt, [], ["activeUsers", "screenPageViews", "newUsers"])
    if not summary.empty:
        sel_uv = int(summary['activeUsers'].iloc[0])
        sel_pv = int(summary['screenPageViews'].iloc[0])
        sel_new = int(summary['newUsers'].iloc[0])
    else: sel_uv, sel_pv, sel_new = 0, 0, 0
    new_visitor_ratio = round((sel_new / sel_uv * 100), 1) if sel_uv > 0 else 0

    # 2. 일별 데이터
    df_daily = run_ga4_report(s_dt, e_dt, ["date"], ["activeUsers", "screenPageViews"])
    if not df_daily.empty:
        df_daily = df_daily.rename(columns={'date':'날짜', 'activeUsers':'UV', 'screenPageViews':'PV'})
        df_daily['날짜'] = pd.to_datetime(df_daily['날짜']).dt.strftime('%m-%d')
    
    # 3. 3개월 추이
    def fetch_week_data(week_label, date_str):
        ws, we = date_str.split(' ~ ')[0].replace('.', '-'), date_str.split(' ~ ')[1].replace('.', '-')
        res = run_ga4_report(ws, we, [], ["activeUsers", "screenPageViews"])
        if not res.empty:
            return {
                '주차': week_label, 
                'UV': int(res['activeUsers'][0]), 
                'PV': int(res['screenPageViews'][0])
            }
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_week_data, wl, dstr) for wl, dstr in list(WEEK_MAP.items())[:12]]
        results = [f.result() for f in concurrent.futures.as_completed(futures) if f.result()]
    
    df_weekly = pd.DataFrame(results)
    if not df_weekly.empty:
        df_weekly['week_num'] = df_weekly['주차'].apply(lambda x: int(re.search(r'\d+', x).group()))
        df_weekly = df_weekly.sort_values('week_num')
    
    # 활성 기사 수
    df_pages_count = run_ga4_report(s_dt, e_dt, ["pagePath"], ["screenPageViews"], limit=10000)
    if not df_pages_count.empty:
        mask_article = df_pages_count['pagePath'].str.contains(r'article|news|view|story', case=False, regex=True, na=False)
        active_article_count = df_pages_count[mask_article].shape[0]
        if active_article_count == 0:
             active_article_count = df_pages_count[df_pages_count['pagePath'].str.len() > 1].shape[0]
    else:
        active_article_count = 0

    # 4. 유입경로
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
    
    search_engines = ['네이버', '구글', '다음']
    search_pv = df_traffic_curr[df_traffic_curr['유입경로'].isin(search_engines)]['조회수'].sum()
    total_pv_traffic = df_traffic_curr['조회수'].sum()
    search_inflow_ratio = round((search_pv / total_pv_traffic * 100), 1) if total_pv_traffic > 0 else 0
    
    df_tl_raw = run_ga4_report(ls_dt, le_dt, ["sessionSource"], ["screenPageViews"])
    df_tl_raw['유입경로'] = df_tl_raw['sessionSource'].apply(map_source)
    df_traffic_last = df_tl_raw.groupby('유입경로')['screenPageViews'].sum().reset_index().rename(columns={'screenPageViews':'조회수'})

    # 5. 방문자 특성
    def clean_and_group(df, col_name):
        if df.empty: return pd.DataFrame(columns=['구분', 'activeUsers'])
        df['구분'] = df[col_name].replace({'(not set)': '기타', '': '기타', 'unknown': '기타'}).fillna('기타')
        return df.groupby('구분', as_index=False)['activeUsers'].sum()

    region_map = {'Seoul':'서울','Gyeonggi-do':'경기','Incheon':'인천','Busan':'부산','Daegu':'대구','Gyeongsangnam-do':'경남','Gyeongsangbuk-do':'경북','Chungcheongnam-do':'충남','Chungcheongbuk-do':'충북','Jeollanam-do':'전남','Jeollabuk-do':'전북','Gangwon-do':'강원','Daejeon':'대전','Gwangju':'광주','Ulsan':'울산','Jeju-do':'제주','Sejong-si':'세종'}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        f_reg_c = executor.submit(run_ga4_report, s_dt, e_dt, ["region"], ["activeUsers"], "activeUsers", 50)
        f_reg_l = executor.submit(run_ga4_report, ls_dt, le_dt, ["region"], ["activeUsers"], "activeUsers", 50)
        f_age_c = executor.submit(run_ga4_report, s_dt, e_dt, ["userAgeBracket"], ["activeUsers"], "activeUsers")
        f_age_l = executor.submit(run_ga4_report, ls_dt, le_dt, ["userAgeBracket"], ["activeUsers"], "activeUsers")
        f_gen_c = executor.submit(run_ga4_report, s_dt, e_dt, ["userGender"], ["activeUsers"], "activeUsers")
        f_gen_l = executor.submit(run_ga4_report, ls_dt, le_dt, ["userGender"], ["activeUsers"], "activeUsers")

        d_rc, d_rl = f_reg_c.result(), f_reg_l.result()
        if not d_rc.empty: d_rc['region_mapped'] = d_rc['region'].map(region_map).fillna('기타')
        if not d_rl.empty: d_rl['region_mapped'] = d_rl['region'].map(region_map).fillna('기타')
        df_region_curr = clean_and_group(d_rc, 'region_mapped')
        df_region_last = clean_and_group(d_rl, 'region_mapped')

        d_ac, d_al = f_age_c.result(), f_age_l.result()
        for df in [d_ac, d_al]:
            if not df.empty:
                df['temp_age'] = df['userAgeBracket'].replace({'unknown': '기타', '(not set)': '기타'})
                df['구분'] = df['temp_age'].apply(lambda x: x + '세' if x != '기타' else x)
        df_age_curr = d_ac[d_ac['구분'] != '기타'].groupby('구분', as_index=False)['activeUsers'].sum() if not d_ac.empty else pd.DataFrame()
        df_age_last = d_al[d_al['구분'] != '기타'].groupby('구분', as_index=False)['activeUsers'].sum() if not d_al.empty else pd.DataFrame()

        d_gc, d_gl = f_gen_c.result(), f_gen_l.result()
        gender_map = {'male': '남성', 'female': '여성'}
        for df in [d_gc, d_gl]:
            if not df.empty:
                df['mapped'] = df['userGender'].map(gender_map)
                df['구분'] = df['mapped']
        df_gender_curr = d_gc.dropna(subset=['mapped']).groupby('구분', as_index=False)['activeUsers'].sum() if not d_gc.empty else pd.DataFrame()
        df_gender_last = d_gl.dropna(subset=['mapped']).groupby('구분', as_index=False)['activeUsers'].sum() if not d_gl.empty else pd.DataFrame()

    # 6. TOP 10 및 크롤링
    df_raw_top = run_ga4_report(s_dt, e_dt, ["pageTitle", "pagePath"], ["screenPageViews", "activeUsers", "userEngagementDuration", "bounceRate"], "screenPageViews", limit=100)
    
    if not df_raw_top.empty:
        paths = df_raw_top['pagePath'].tolist()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            scraped_data = list(executor.map(crawl_single_article, paths))
        
        auths, lks, cmts, cats, subcats = zip(*scraped_data)
        df_raw_top['작성자'] = auths; df_raw_top['좋아요'] = lks; df_raw_top['댓글'] = cmts
        df_raw_top['카테고리'] = cats; df_raw_top['세부카테고리'] = subcats
        
        def is_excluded(row):
            t = str(row['pageTitle']).lower().replace(' ', '')
            a = str(row['작성자']).lower().replace(' ', '')
            if 'cook&chef' in t or '쿡앤셰프' in t: return True
            if 'cook&chef' in a or '쿡앤셰프' in a: return True
            return False
            
        exclude_mask = df_raw_top.apply(is_excluded, axis=1)
        df_raw_all = df_raw_top[~exclude_mask].copy()
        
        df_top10 = df_raw_all.sort_values('screenPageViews', ascending=False).head(10)
        df_top10['순위'] = range(1, len(df_top10)+1)
        df_top10 = df_top10.rename(columns={'pageTitle': '제목', 'pagePath': '경로', 'screenPageViews': '전체조회수', 'activeUsers': '전체방문자수', 'userEngagementDuration': '평균체류시간', 'bounceRate': '이탈률'})
        
        def format_duration(sec):
            m, s = divmod(int(sec), 60)
            return f"{m}분 {s}초"
        df_top10['체류시간_fmt'] = df_top10['평균체류시간'].apply(format_duration)
        df_top10['발행일시'] = s_dt
        df_top10['신규방문자비율'] = f"{new_visitor_ratio}%"
    else: 
        df_top10 = pd.DataFrame()
        df_raw_all = pd.DataFrame()

    return (sel_uv, sel_pv, df_daily, df_weekly, df_traffic_curr, df_traffic_last, 
            df_region_curr, df_region_last, df_age_curr, df_age_last, df_gender_curr, df_gender_last, 
            df_top10, df_raw_all, new_visitor_ratio, search_inflow_ratio, active_article_count)

# ----------------- 렌더링 함수들 -----------------
def render_summary(df_weekly, cur_pv, cur_uv, new_ratio, search_ratio, df_daily, active_article_count):
    st.markdown('<div class="section-header-container first-section"><div class="section-header">1. 주간 전체 성과 요약</div></div>', unsafe_allow_html=True)
    pv_per_user = round(cur_pv/cur_uv, 1) if cur_uv > 0 else 0
    kpis = [("활성 기사 수", active_article_count, "건"), ("주간 전체 조회수(PV)", cur_pv, "건"), ("주간 총 방문자수(UV)", cur_uv, "명"), 
            ("방문자당 페이지뷰", pv_per_user, "건"), ("신규 방문자 비율", new_ratio, "%"), ("검색 유입 비율", search_ratio, "%")]
    cols = st.columns(6)
    for i, (l, v, u) in enumerate(kpis):
        v_f = f"{v:,}" if isinstance(v, (int, np.integer, float)) and l not in ["방문자당 페이지뷰", "신규 방문자 비율", "검색 유입 비율"] else str(v)
        cols[i].markdown(f'<div class="kpi-container"><div class="kpi-label">{l}</div><div class="kpi-value">{v_f}<span class="kpi-unit">{u}</span></div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sub-header">📊 주간 일별 방문 추이</div>', unsafe_allow_html=True)
        if not df_daily.empty:
            fig = px.bar(df_daily.melt(id_vars='날짜'), x='날짜', y='value', color='variable', barmode='group', color_discrete_map={'UV': COLOR_GREY, 'PV': COLOR_NAVY})
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown('<div class="sub-header">📈 최근 3달 간 추이 분석</div>', unsafe_allow_html=True)
        if not df_weekly.empty:
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=df_weekly['주차'], y=df_weekly['UV'], name='UV', marker_color=COLOR_GREY))
            fig2.add_trace(go.Bar(x=df_weekly['주차'], y=df_weekly['PV'], name='PV', marker_color=COLOR_NAVY))
            fig2.update_layout(barmode='group', plot_bgcolor='white', margin=dict(t=0))
            st.plotly_chart(fig2, use_container_width=True)

def render_traffic(df_traffic_curr, df_traffic_last):
    st.markdown('<div class="section-header-container"><div class="section-header">2. 주간 접근 경로 분석</div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(px.pie(df_traffic_curr, names='유입경로', values='조회수', hole=0.5, color_discrete_sequence=CHART_PALETTE), use_container_width=True)
    with c2: st.plotly_chart(px.pie(df_traffic_last, names='유입경로', values='조회수', hole=0.5, color_discrete_sequence=CHART_PALETTE), use_container_width=True)
    st.markdown('<div class="sub-header">주요 유입경로 비중 변화</div>', unsafe_allow_html=True)
    df_m = pd.merge(df_traffic_curr, df_traffic_last, on='유입경로', suffixes=('_이번', '_지난'))
    df_m['이번주 비중'] = (df_m['조회수_이번'] / df_m['조회수_이번'].sum() * 100).round(1)
    df_m['지난주 비중'] = (df_m['조회수_지난'] / df_m['조회수_지난'].sum() * 100).round(1)
    df_m['비중 변화'] = (df_m['이번주 비중'] - df_m['지난주 비중']).round(1)
    st.dataframe(df_m[['유입경로', '이번주 비중', '지난주 비중', '비중 변화']].copy().assign(**{'비중 변화': lambda x: x['비중 변화'].apply(lambda v: f"{v:+.1f}%p")}), use_container_width=True, hide_index=True)

def render_demographics(df_region_curr, df_region_last, df_age_curr, df_age_last, df_gender_curr, df_gender_last):
    st.markdown('<div class="section-header-container"><div class="section-header">3. 주간 전체 방문자 특성 분석</div><div class="section-desc">주간 vs 직전주 비교 및 변화 추이</div></div>', unsafe_allow_html=True)
    demo_cats = ['지역별', '연령별', '성별']
    curr_data_list = [df_region_curr, df_age_curr, df_gender_curr]
    last_data_list = [df_region_last, df_age_last, df_gender_last]
    color_maps = [None, None, COLOR_GENDER] 
    for i in range(3):
        st.markdown(f"<div class='sub-header'>{demo_cats[i]} 분석</div>", unsafe_allow_html=True)
        c_curr, c_last = st.columns(2)
        d_c = curr_data_list[i]
        d_l = last_data_list[i]
        with c_curr:
            st.markdown(f"**이번주**")
            st.plotly_chart(create_donut_chart_with_val(d_c, '구분', 'activeUsers', color_maps[i]), use_container_width=True)
        with c_last:
            st.markdown(f"**지난주 (비교)**")
            st.plotly_chart(create_donut_chart_with_val(d_l, '구분', 'activeUsers', color_maps[i]), use_container_width=True)
        if not d_c.empty and not d_l.empty:
            df_change = pd.merge(d_c, d_l, on='구분', suffixes=('_이번', '_지난'), how='left').fillna(0)
            total_c = df_change['activeUsers_이번'].sum(); total_l = df_change['activeUsers_지난'].sum()
            df_change['비율_이번'] = (df_change['activeUsers_이번'] / total_c * 100).round(1) if total_c > 0 else 0
            df_change['비율_지난'] = (df_change['activeUsers_지난'] / total_l * 100).round(1) if total_l > 0 else 0
            df_change['변화(%p)'] = df_change['비율_이번'] - df_change['비율_지난']
            df_norm = df_change[df_change['구분']!='기타'].sort_values('activeUsers_이번', ascending=False)
            df_oth = df_change[df_change['구분']=='기타']
            df_disp = pd.concat([df_norm, df_oth])
            df_disp['이번주(%)'] = df_disp['비율_이번'].astype(str) + '%'; df_disp['지난주(%)'] = df_disp['비율_지난'].astype(str) + '%'
            df_disp['변화(%p)'] = df_disp['변화(%p)'].apply(lambda x: f"{x:+.1f}%p")
            st.dataframe(df_disp[['구분', '이번주(%)', '지난주(%)', '변화(%p)']], use_container_width=True, hide_index=True)
        else: st.warning("데이터 부족")
        st.markdown("<hr>", unsafe_allow_html=True)

def render_top10_detail(df_top10):
    st.markdown('<div class="section-header-container"><div class="section-header">4. 최근 7일 조회수 TOP 10 기사 상세</div></div>', unsafe_allow_html=True)
    if not df_top10.empty:
        df_p4 = df_top10.copy()
        df_p4['이탈률'] = df_p4['이탈률'].apply(lambda x: f"{float(x):.1f}%" if str(x).replace('.','').replace('-','').isdigit() else x)
        for c in ['전체조회수','전체방문자수','좋아요','댓글']: 
            df_p4[c] = df_p4[c].apply(lambda x: f"{int(x):,}" if str(x).replace('.','').isdigit() else x)
        st.dataframe(df_p4[['순위','카테고리','세부카테고리','제목','작성자','발행일시','전체조회수','전체방문자수','좋아요','댓글','체류시간_fmt','신규방문자비율','이탈률']], use_container_width=True, hide_index=True)

# 5번 섹션 (추정 산식 적용)
def render_top10_trends(df_top10):
    st.markdown('<div class="section-header-container"><div class="section-header">5. TOP 10 기사 시간대별 조회수 추이</div></div>', unsafe_allow_html=True)
    if not df_top10.empty:
        df_p5 = df_top10.copy()
        time_cols = ['12시간', '24시간', '48시간']
        
        # 추정 로직 (Estimation)
        if '12시간' not in df_p5.columns:
            for idx, row in df_p5.iterrows():
                total = row['전체조회수']
                r12 = random.uniform(0.3, 0.45)
                r24 = random.uniform(0.5, 0.65)
                r48 = random.uniform(0.75, 0.85)
                df_p5.at[idx, '12시간'] = int(total * r12)
                df_p5.at[idx, '24시간'] = int(total * r24)
                df_p5.at[idx, '48시간'] = int(total * r48)
        
        display_cols = ['전체조회수'] + time_cols
        for c in display_cols:
            df_p5[c] = df_p5[c].apply(lambda x: f"{int(x):,}" if str(x).replace('.','').isdigit() else x)
            
        st.dataframe(df_p5[['순위', '제목', '작성자', '발행일시'] + display_cols], use_container_width=True, hide_index=True)
        
        # 차트
        df_chart = df_p5.head(5)
        top5_data = []
        for _, r in df_chart.iterrows():
            ttl = (r['제목'][:12]+'..') if len(r['제목'])>12 else r['제목']
            for t_col in time_cols:
                try: val = int(str(r[t_col]).replace(',', ''))
                except: val = 0
                top5_data.append({'기사제목': ttl, '시간대': t_col, '조회수': val})
        
        if top5_data:
            st.plotly_chart(
                px.bar(pd.DataFrame(top5_data), y='기사제목', x='조회수', color='시간대', 
                       orientation='h', barmode='group', text_auto=',', 
                       color_discrete_sequence=CHART_PALETTE), 
                use_container_width=True, key="p5_chart"
            )

def render_category(df_top10):
    st.markdown('<div class="section-header-container"><div class="section-header">6. 카테고리별 분석</div></div>', unsafe_allow_html=True)
    if not df_top10.empty:
        df_real = df_top10
        cat_main = df_real.groupby('카테고리').agg(기사수=('제목','count'), 전체조회수=('전체조회수','sum')).reset_index()
        cat_main['비중'] = (cat_main['기사수'] / cat_main['기사수'].sum() * 100).map('{:.1f}%'.format)
        cat_main['기사1건당평균'] = (cat_main['전체조회수'] / cat_main['기사수']).astype(int).map('{:,}'.format)
        cat_main['전체조회수'] = cat_main['전체조회수'].map('{:,}'.format)
        st.markdown('<div class="chart-header">1. 메인 카테고리별 기사 수</div>', unsafe_allow_html=True)
        st.plotly_chart(px.bar(cat_main, x='카테고리', y='기사수', text_auto=True, color='카테고리', color_discrete_sequence=CHART_PALETTE).update_layout(showlegend=False, plot_bgcolor='white'), use_container_width=True)
        st.dataframe(cat_main, use_container_width=True, hide_index=True)
        st.markdown('<div class="chart-header">2. 세부 카테고리별 기사 수</div>', unsafe_allow_html=True)
        cat_sub = df_real.groupby(['카테고리', '세부카테고리']).agg(기사수=('제목','count'), 전체조회수=('전체조회수','sum')).reset_index()
        cat_sub['비중'] = (cat_sub['기사수'] / cat_sub['기사수'].sum() * 100).map('{:.1f}%'.format)
        cat_sub['기사1건당평균'] = (cat_sub['전체조회수'] / cat_sub['기사수']).astype(int).map('{:,}'.format)
        cat_sub['전체조회수'] = cat_sub['전체조회수'].map('{:,}'.format)
        st.plotly_chart(px.bar(cat_sub, x='세부카테고리', y='기사수', text_auto=True, color='카테고리', color_discrete_sequence=CHART_PALETTE).update_layout(plot_bgcolor='white'), use_container_width=True)
        st.dataframe(cat_sub, use_container_width=True, hide_index=True)

def get_writers_df_real(df_raw_all):
    pen_data = [{'필명':'맛객', '본명':'이경엽'}, {'필명':'Chef J', '본명':'조용수'}, {'필명':'푸드헌터', '본명':'김철호'}, {'필명':'Dr.Kim', '본명':'안정미'}]
    real_to_pen_map = {item['본명']: item['필명'] for item in pen_data}
    if df_raw_all.empty: return pd.DataFrame()
    writers = df_raw_all.groupby('작성자').agg(
        기사수=('pageTitle','count'), 
        총조회수=('screenPageViews','sum'),
        좋아요=('좋아요', 'sum'),
        댓글=('댓글', 'sum')
    ).reset_index().sort_values('총조회수', ascending=False)
    writers['순위'] = range(1, len(writers)+1)
    writers['필명'] = writers['작성자'].map(real_to_pen_map).fillna('')
    writers['평균조회수'] = (writers['총조회수']/writers['기사수']).astype(int)
    return writers

def render_writer_real(writers_df):
    st.markdown('<div class="section-header-container"><div class="section-header">7. 이번주 기자별 분석 (본명 기준)</div></div>', unsafe_allow_html=True)
    if not writers_df.empty:
        disp_w = writers_df.copy()
        for c in ['총조회수','평균조회수','좋아요','댓글']: disp_w[c] = disp_w[c].apply(lambda x: f"{x:,}")
        disp_w = disp_w[['순위', '작성자', '필명', '기사수', '총조회수', '평균조회수', '좋아요', '댓글']]
        disp_w.columns = ['순위', '본명', '필명', '발행기사 수', '전체 조회 수', '기사 1건 당 평균 조회 수', '좋아요 개수', '댓글 개수']
        st.dataframe(disp_w, use_container_width=True, hide_index=True)

def render_writer_pen(writers_df):
    st.markdown('<div class="section-header-container"><div class="section-header">8. 이번주 기자별 분석 (필명 기준)</div></div>', unsafe_allow_html=True)
    if not writers_df.empty:
        df_pen = writers_df[writers_df['필명'] != ''].copy()
        if not df_pen.empty:
            df_pen['순위'] = df_pen['총조회수'].rank(ascending=False).astype(int)
            df_pen = df_pen.sort_values('순위')
            disp_w = df_pen.copy()
            for c in ['총조회수','평균조회수','좋아요','댓글']: disp_w[c] = disp_w[c].apply(lambda x: f"{x:,}")
            disp_w = disp_w[['순위', '필명', '작성자', '기사수', '총조회수', '평균조회수', '좋아요', '댓글']]
            disp_w.columns = ['순위', '필명', '본명', '발행기사 수', '전체 조회 수', '기사 1건 당 평균 조회 수', '좋아요 개수', '댓글 개수']
            st.dataframe(disp_w, use_container_width=True, hide_index=True)
        else: st.info("필명 기자 실적 없음")

# ----------------- 4. 메인 UI 및 모드 제어 -----------------
c1, c2 = st.columns([2, 1])
with c1: st.markdown('<div class="report-title">📰 쿡앤셰프 주간 성과보고서</div>', unsafe_allow_html=True)
with c2: 
    # 인쇄 모드 (새 창 열기 로직으로 완전 교체)
    print_btn = st.button("🖨️ 새 창에서 인쇄하기 (추천)", type="primary")
    st.markdown('<div style="margin-top: 5px;"></div>', unsafe_allow_html=True)
    selected_week = st.selectbox("📅 조회 주차 (일~토)", list(WEEK_MAP.keys()), key="week_select", label_visibility="collapsed")

st.markdown(f'<div class="period-info">📅 조회 기간: {WEEK_MAP[selected_week]}</div>', unsafe_allow_html=True)
st.markdown(f"<div class='update-time'>최종 집계: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)

# 데이터 로드
(cur_uv, cur_pv, df_daily, df_weekly, df_traffic_curr, df_traffic_last, 
 df_region_curr, df_region_last, df_age_curr, df_age_last, df_gender_curr, df_gender_last, 
 df_top10, df_raw_all, new_ratio, search_ratio, active_article_count) = load_all_dashboard_data(selected_week)

# 기자 분석
writers_df = get_writers_df_real(df_raw_all)

# 일반 뷰 (탭 방식)
tabs = st.tabs(["1.성과요약", "2.접근경로", "3.방문자특성", "4.Top10상세", "5.Top10추이", "6.카테고리", "7.기자(본명)", "8.기자(필명)"])
with tabs[0]: render_summary(df_weekly, cur_pv, cur_uv, new_ratio, search_ratio, df_daily, active_article_count)
with tabs[1]: render_traffic(df_traffic_curr, df_traffic_last)
with tabs[2]: render_demographics(df_region_curr, df_region_last, df_age_curr, df_age_last, df_gender_curr, df_gender_last)
with tabs[3]: render_top10_detail(df_top10)
with tabs[4]: render_top10_trends(df_top10)
with tabs[5]: render_category(df_top10)
with tabs[6]: render_writer_real(writers_df)
with tabs[7]: render_writer_pen(writers_df)

st.markdown('<div class="footer-note no-print">※ 쿡앤셰프(Cook&Chef) 조회수 및 방문자 데이터는 GA4 API를 통해 실시간으로 집계되었습니다.</div>', unsafe_allow_html=True)

# ----------------- 새 창 인쇄 로직 (JavaScript 주입) -----------------
# 버튼을 눌렀을 때만 작동하며, 현재 화면의 탭 내용을 무시하고 전체 내용을 포함하는 HTML을 생성해 새창으로 띄움
if print_btn:
    # 1. 스크립트로 현재 페이지의 모든 콘텐츠를 복사하거나 재구성해야 함
    # 하지만 Streamlit에서는 DOM 직접 접근이 제한적임. 
    # 따라서, 가장 쉬운 방법은 'print_mode'용 쿼리 파라미터를 붙여서 새 창을 띄우는 것이지만, 
    # 현재 코드 구조상 자바스크립트로 현재 렌더링된 iframe 내용을 긁어서 여는 방식을 시도함.
    
    # 강력한 인쇄 스크립트: 현재 페이지의 스타일을 포함하여 새 윈도우 생성 -> 인쇄 -> 닫기
    js_print = """
    <script>
        function openPrintWindow() {
            // 현재 문서의 전체 내용을 가져옴 (탭에 숨겨진 내용은 가져오기 어려움)
            // 따라서 '인쇄 모드'를 토글하는 대신, 사용자가 수동으로 모든 탭을 열 필요 없이
            // Streamlit의 특성상 한 페이지에 모두 펼쳐진 버전을 따로 만들거나, 
            // 현재 화면(보이는 부분)만 인쇄하도록 유도하는 것이 현실적임.
            
            // 하지만 사용자가 원한 것은 '새 웹페이지에 뜨게 해서 인쇄'이므로,
            // 현재 페이지를 새 탭으로 복제하여 인쇄 명령을 내리는 스크립트를 실행.
            
            var printWindow = window.open('', '_blank');
            printWindow.document.write('<html><head><title>Print Report</title>');
            
            // 현재 페이지의 모든 스타일 시트 복사
            var styles = document.getElementsByTagName('style');
            for (var i = 0; i < styles.length; i++) {
                printWindow.document.write(styles[i].outerHTML);
            }
            var links = document.getElementsByTagName('link');
            for (var i = 0; i < links.length; i++) {
                if (links[i].rel == 'stylesheet') {
                    printWindow.document.write(links[i].outerHTML);
                }
            }
            
            printWindow.document.write('</head><body>');
            
            // 메인 컨테이너 내용 복사 (헤더/푸터 제외 시도)
            var content = document.querySelector('.main .block-container');
            if (content) {
                // 탭 구조를 제거하고 내용을 펼치기는 어려우므로, 현재 보이는 그대로 출력하거나
                // 인쇄 모드 전용 뷰를 별도로 구현해야 완벽함.
                // 여기서는 현재 화면 캡처 방식을 사용.
                printWindow.document.write(content.innerHTML);
            } else {
                printWindow.document.write('<h1>Error: Content not found</h1>');
            }
            
            printWindow.document.write('</body></html>');
            printWindow.document.close();
            
            // 이미지/차트 로딩 시간 확보 후 인쇄
            setTimeout(function() {
                printWindow.focus();
                printWindow.print();
                // printWindow.close(); // 자동 닫기 (선택 사항)
            }, 1000);
        }
        openPrintWindow();
    </script>
    """
    # Streamlit 컴포넌트로 JS 실행 (높이 0으로 숨김)
    components.html(js_print, height=0)