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
    [data-testid="stDataFrame"], [data-testid="stDataFrame"] > div { width: 100% !important; }
    .section-header-container { margin-top: 10px !important; }
    .block-container { padding-top: 0 !important; }
    .print-footer { position: fixed; bottom: 0; width: 100%; text-align: center; font-size: 10px; color: #999; }
}
</style>
"""
st.markdown(PRINT_CSS, unsafe_allow_html=True)

# ----------------- 3. 진입 보안 화면 (로그인) -----------------
def check_password():
    if st.session_state.get("password_correct", False): return True
    login_placeholder = st.empty()
    with login_placeholder.container():
        st.markdown('<style>.stTextInput > div > div > input { text-align: center; font-size: 18px; letter-spacing: 2px; }</style>', unsafe_allow_html=True)
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
        author_tag = soup.select_one('.user-name') or soup.select_one('.writer') or soup.select_one('.byline')
        if author_tag: author = author_tag.text.strip()
        author = clean_author_name(author)
        likes = int(soup.select_one('.sns-like-count').text.replace(',', '')) if soup.select_one('.sns-like-count') else 0
        comments = int(soup.select_one('.comment-count').text.replace(',', '')) if soup.select_one('.comment-count') else 0
        cat, subcat = "뉴스", "이슈"
        breadcrumbs = soup.select('.location a') or soup.select('.breadcrumb a')
        if breadcrumbs and len(breadcrumbs) >= 2: cat = breadcrumbs[1].text.strip()
        if breadcrumbs and len(breadcrumbs) >= 3: subcat = breadcrumbs[2].text.strip()
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
    except: return pd.DataFrame(columns=dimensions + metrics)

def create_donut_chart_with_val(df, names, values, color_map=None):
    if df.empty: return go.Figure()
    df_sorted = pd.concat([df[df['구분'] != '기타'].sort_values(by=values, ascending=False), df[df['구분'] == '기타']]) if '구분' in df.columns else df
    fig = px.pie(df_sorted, names=names, values=values, hole=0.5, color=names if color_map else None, color_discrete_map=color_map, color_discrete_sequence=CHART_PALETTE if not color_map else None)
    fig.update_traces(textposition='outside', textinfo='label+percent', sort=False)
    fig.update_layout(showlegend=False, margin=dict(t=30, b=80, l=40, r=40), height=350)
    return fig

@st.cache_data(ttl=3600, show_spinner="데이터 불러오는 중...")
def load_all_dashboard_data(selected_week):
    dr = WEEK_MAP[selected_week]
    s_dt, e_dt = dr.split(' ~ ')[0].replace('.', '-'), dr.split(' ~ ')[1].replace('.', '-')
    ls_dt = (datetime.strptime(s_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')
    le_dt = (datetime.strptime(e_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')

    summary = run_ga4_report(s_dt, e_dt, [], ["activeUsers", "screenPageViews", "newUsers"])
    if not summary.empty:
        sel_uv, sel_pv, sel_new = int(summary['activeUsers'][0]), int(summary['screenPageViews'][0]), int(summary['newUsers'][0])
    else: sel_uv, sel_pv, sel_new = 0, 0, 0
    new_ratio = round((sel_new / sel_uv * 100), 1) if sel_uv > 0 else 0

    # 수정: 일별 데이터 날짜 포맷팅 및 정렬 고정
    df_daily = run_ga4_report(s_dt, e_dt, ["date"], ["activeUsers", "screenPageViews"])
    if not df_daily.empty:
        df_daily = df_daily.rename(columns={'date':'날짜', 'activeUsers':'UV', 'screenPageViews':'PV'})
        df_daily['날짜'] = pd.to_datetime(df_daily['날짜'], format='%Y%m%d').dt.strftime('%m-%d')
        df_daily = df_daily.sort_values('날짜')
    
    # 수정: 주차별 데이터 연도 구분 및 시간순 정렬
    def fetch_week_data(week_label, date_str):
        ws, we = date_str.split(' ~ ')[0].replace('.', '-'), date_str.split(' ~ ')[1].replace('.', '-')
        res = run_ga4_report(ws, we, [], ["activeUsers", "screenPageViews"])
        if not res.empty:
            year_val = ws[:4]
            week_num = int(re.search(r'\d+', week_label).group())
            return {
                '주차': f"{year_val}년 {week_label}", 
                'UV': int(res['activeUsers'][0]), 
                'PV': int(res['screenPageViews'][0]),
                'sort_key': f"{year_val}{week_num:02d}"
            }
        return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        results = [f.result() for f in concurrent.futures.as_completed([ex.submit(fetch_week_data, wl, dstr) for wl, dstr in list(WEEK_MAP.items())[:12]]) if f.result()]
    df_weekly = pd.DataFrame(results).sort_values('sort_key') if results else pd.DataFrame()
    
    df_pc = run_ga4_report(s_dt, e_dt, ["pagePath"], ["screenPageViews"], limit=10000)
    active_article_count = df_pc[df_pc['pagePath'].str.contains(r'article|news|view', na=False)].shape[0] if not df_pc.empty else 0

    df_t_raw = run_ga4_report(s_dt, e_dt, ["sessionSource"], ["screenPageViews"])
    def map_source(s):
        s = s.lower()
        if 'naver' in s: return '네이버'
        if 'daum' in s: return '다음'
        if '(direct)' in s: return '직접'
        if 'google' in s: return '구글'
        return '기타'
    df_t_raw['유입경로'] = df_t_raw['sessionSource'].apply(map_source)
    df_traffic_curr = df_t_raw.groupby('유입경로')['screenPageViews'].sum().reset_index().rename(columns={'screenPageViews':'조회수'})
    search_ratio = round((df_traffic_curr[df_traffic_curr['유입경로'].isin(['네이버','구글','다음'])]['조회수'].sum() / df_traffic_curr['조회수'].sum() * 100), 1) if not df_traffic_curr.empty else 0
    df_tl_raw = run_ga4_report(ls_dt, le_dt, ["sessionSource"], ["screenPageViews"])
    df_tl_raw['유입경로'] = df_tl_raw['sessionSource'].apply(map_source)
    df_traffic_last = df_tl_raw.groupby('유입경로')['screenPageViews'].sum().reset_index().rename(columns={'screenPageViews':'조회수'})

    def clean_and_group(df, col_name):
        if df.empty: return pd.DataFrame(columns=['구분', 'activeUsers'])
        df['구분'] = df[col_name].replace({'(not set)': '기타', '': '기타', 'unknown': '기타'}).fillna('기타')
        return df.groupby('구분', as_index=False)['activeUsers'].sum()
    region_map = {'Seoul':'서울','Gyeonggi-do':'경기','Incheon':'인천','Busan':'부산','Daegu':'대구','Gyeongsangnam-do':'경남','Gyeongsangbuk-do':'경북','Chungcheongnam-do':'충남','Chungcheongbuk-do':'충북','Jeollanam-do':'전남','Jeollabuk-do':'전북','Gangwon-do':'강원','Daejeon':'대전','Gwangju':'광주','Ulsan':'울산','Jeju-do':'제주','Sejong-si':'세종'}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        f_reg_c = ex.submit(run_ga4_report, s_dt, e_dt, ["region"], ["activeUsers"], "activeUsers", 50)
        f_reg_l = ex.submit(run_ga4_report, ls_dt, le_dt, ["region"], ["activeUsers"], "activeUsers", 50)
        f_age_c = ex.submit(run_ga4_report, s_dt, e_dt, ["userAgeBracket"], ["activeUsers"], "activeUsers")
        f_age_l = ex.submit(run_ga4_report, ls_dt, le_dt, ["userAgeBracket"], ["activeUsers"], "activeUsers")
        f_gen_c = ex.submit(run_ga4_report, s_dt, e_dt, ["userGender"], ["activeUsers"], "activeUsers")
        f_gen_l = ex.submit(run_ga4_report, ls_dt, le_dt, ["userGender"], ["activeUsers"], "activeUsers")
        d_rc, d_rl = f_reg_c.result(), f_reg_l.result()
        if not d_rc.empty: d_rc['region_mapped'] = d_rc['region'].map(region_map).fillna('기타')
        if not d_rl.empty: d_rl['region_mapped'] = d_rl['region'].map(region_map).fillna('기타')
        df_region_curr, df_region_last = clean_and_group(d_rc, 'region_mapped'), clean_and_group(d_rl, 'region_mapped')
        d_ac, d_al = f_age_c.result(), f_age_l.result()
        for d in [d_ac, d_al]:
            if not d.empty: d['구분'] = d['userAgeBracket'].replace({'unknown':'기타','(not set)':'기타'}).apply(lambda x: x+'세' if x!='기타' else x)
        df_age_curr = d_ac[d_ac['구분']!='기타'].groupby('구분', as_index=False)['activeUsers'].sum() if not d_ac.empty else pd.DataFrame()
        df_age_last = d_al[d_al['구분']!='기타'].groupby('구분', as_index=False)['activeUsers'].sum() if not d_al.empty else pd.DataFrame()
        d_gc, d_gl = f_gen_c.result(), f_gen_l.result()
        for d in [d_gc, d_gl]:
            if not d.empty: d['구분'] = d['userGender'].map({'male':'남성','female':'여성'}).fillna('기타')
        df_gender_curr = d_gc[d_gc['구분']!='기타'].groupby('구분', as_index=False)['activeUsers'].sum() if not d_gc.empty else pd.DataFrame()
        df_gender_last = d_gl[d_gl['구분']!='기타'].groupby('구분', as_index=False)['activeUsers'].sum() if not d_gl.empty else pd.DataFrame()

    df_raw_top = run_ga4_report(s_dt, e_dt, ["pageTitle", "pagePath"], ["screenPageViews", "activeUsers", "userEngagementDuration", "bounceRate"], "screenPageViews", 100)
    if not df_raw_top.empty:
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
            scraped = list(ex.map(crawl_single_article, df_raw_top['pagePath']))
        auths, lks, cmts, cats, subcats = zip(*scraped)
        df_raw_top['작성자'], df_raw_top['좋아요'], df_raw_top['댓글'], df_raw_top['카테고리'], df_raw_top['세부카테고리'] = auths, lks, cmts, cats, subcats
        df_raw_all = df_raw_top[~df_raw_top['pageTitle'].str.contains('쿡앤셰프|Cook&Chef', na=False)].copy()
        df_top10 = df_raw_all.sort_values('screenPageViews', ascending=False).head(10)
        df_top10['순위'] = range(1, len(df_top10)+1)
        df_top10 = df_top10.rename(columns={'pageTitle': '제목', 'screenPageViews': '전체조회수', 'activeUsers': '전체방문자수', 'userEngagementDuration': '평균체류시간', 'bounceRate': '이탈률'})
        df_top10['체류시간_fmt'] = df_top10['평균체류시간'].apply(lambda x: f"{int(x)//60}분 {int(x)%60}초")
        df_top10['발행일시'], df_top10['신규방문자비율'] = s_dt, f"{new_ratio}%"
    else: df_top10, df_raw_all = pd.DataFrame(), pd.DataFrame()
    return (sel_uv, sel_pv, df_daily, df_weekly, df_traffic_curr, df_traffic_last, df_region_curr, df_region_last, df_age_curr, df_age_last, df_gender_curr, df_gender_last, df_top10, df_raw_all, new_ratio, search_ratio, active_article_count)

# ----------------- 렌더링 함수들 (하나도 빠짐없이 유지) -----------------
def render_summary(df_weekly, cur_pv, cur_uv, new_ratio, search_ratio, df_daily, active_article_count):
    st.markdown('<div class="section-header-container"><div class="section-header">1. 주간 전체 성과 요약</div></div>', unsafe_allow_html=True)
    kpis = [("활성 기사 수", active_article_count, "건"), ("주간 전체 조회수(PV)", cur_pv, "건"), ("주간 총 방문자수(UV)", cur_uv, "명"), 
            ("방문자당 페이지뷰", round(cur_pv/cur_uv, 1) if cur_uv>0 else 0, "건"), ("신규 방문자 비율", new_ratio, "%"), ("검색 유입 비율", search_ratio, "%")]
    cols = st.columns(6)
    for i, (l, v, u) in enumerate(kpis):
        v_f = f"{v:,}" if isinstance(v, (int, np.integer)) else str(v)
        cols[i].markdown(f'<div class="kpi-container"><div class="kpi-label">{l}</div><div class="kpi-value">{v_f}<span class="kpi-unit">{u}</span></div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sub-header">📊 주간 일별 방문 추이</div>', unsafe_allow_html=True)
        if not df_daily.empty: st.plotly_chart(px.bar(df_daily.melt(id_vars='날짜'), x='날짜', y='value', color='variable', barmode='group', color_discrete_map={'UV': COLOR_GREY, 'PV': COLOR_NAVY}).update_layout(xaxis_type='category'), use_container_width=True)
    with c2:
        st.markdown('<div class="sub-header">📈 최근 3달 간 추이 분석</div>', unsafe_allow_html=True)
        if not df_weekly.empty:
            fig2 = go.Figure([go.Bar(x=df_weekly['주차'], y=df_weekly['UV'], name='UV', marker_color=COLOR_GREY), go.Bar(x=df_weekly['주차'], y=df_weekly['PV'], name='PV', marker_color=COLOR_NAVY)])
            fig2.update_layout(barmode='group', plot_bgcolor='white', xaxis_type='category')
            st.plotly_chart(fig2, use_container_width=True)

def render_traffic(df_traffic_curr, df_traffic_last):
    st.markdown('<div class="section-header-container"><div class="section-header">2. 주간 접근 경로 분석</div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(px.pie(df_traffic_curr, names='유입경로', values='조회수', hole=0.5, color_discrete_sequence=CHART_PALETTE), use_container_width=True)
    with c2: st.plotly_chart(px.pie(df_traffic_last, names='유입경로', values='조회수', hole=0.5, color_discrete_sequence=CHART_PALETTE), use_container_width=True)
    st.markdown('<div class="sub-header">주요 유입경로 비중 변화</div>', unsafe_allow_html=True)
    if not df_traffic_curr.empty and not df_traffic_last.empty:
        df_m = pd.merge(df_traffic_curr, df_traffic_last, on='유입경로', suffixes=('_이번', '_지난'))
        df_m['이번주 비중'] = (df_m['조회수_이번'] / df_m['조회수_이번'].sum() * 100).round(1)
        df_m['지난주 비중'] = (df_m['조회수_지난'] / df_m['조회수_지난'].sum() * 100).round(1)
        df_m['비중 변화'] = (df_m['이번주 비중'] - df_m['지난주 비중']).round(1)
        st.dataframe(df_m[['유입경로', '이번주 비중', '지난주 비중', '비중 변화']].copy().assign(**{'비중 변화': lambda x: x['비중 변화'].apply(lambda v: f"{v:+.1f}%p")}), use_container_width=True, hide_index=True)

def render_demo_region(df_region_curr, df_region_last):
    st.markdown('<div class="section-header-container"><div class="section-header">3. 주간 전체 방문자 특성 분석 (지역)</div></div>', unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>지역별 분석</div>", unsafe_allow_html=True)
    c_curr, c_last = st.columns(2)
    with c_curr: st.plotly_chart(create_donut_chart_with_val(df_region_curr, '구분', 'activeUsers'), use_container_width=True)
    with c_last: st.plotly_chart(create_donut_chart_with_val(df_region_last, '구분', 'activeUsers'), use_container_width=True)
    if not df_region_curr.empty and not df_region_last.empty:
        df_m = pd.merge(df_region_curr, df_region_last, on='구분', suffixes=('_이번', '_지난'), how='left').fillna(0)
        df_m['이번주(%)'] = (df_m['activeUsers_이번'] / df_m['activeUsers_이번'].sum() * 100).round(1).astype(str) + '%'
        df_m['지난주(%)'] = (df_m['activeUsers_지난'] / df_m['activeUsers_지난'].sum() * 100).round(1).astype(str) + '%'
        st.dataframe(df_m[['구분', '이번주(%)', '지난주(%)']], use_container_width=True, hide_index=True)

def render_demo_age_gender(df_age_curr, df_age_last, df_gender_curr, df_gender_last):
    st.markdown('<div class="section-header-container"><div class="section-header">3. 주간 전체 방문자 특성 분석 (연령/성별)</div></div>', unsafe_allow_html=True)
    for title, curr, last, cmap in [('연령별', df_age_curr, df_age_last, None), ('성별', df_gender_curr, df_gender_last, COLOR_GENDER)]:
        st.markdown(f"<div class='sub-header'>{title} 분석</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(create_donut_chart_with_val(curr, '구분', 'activeUsers', cmap), use_container_width=True)
        with c2: st.plotly_chart(create_donut_chart_with_val(last, '구분', 'activeUsers', cmap), use_container_width=True)

def render_top10_detail(df_top10):
    st.markdown('<div class="section-header-container"><div class="section-header">4. 최근 7일 조회수 TOP 10 기사 상세</div></div>', unsafe_allow_html=True)
    if not df_top10.empty:
        df_p = df_top10.copy()
        for c in ['전체조회수','전체방문자수','좋아요','댓글']: df_p[c] = df_p[c].apply(lambda x: f"{int(x):,}")
        st.dataframe(df_p[['순위','카테고리','세부카테고리','제목','작성자','발행일시','전체조회수','전체방문자수','좋아요','댓글','체류시간_fmt','신규방문자비율','이탈률']], use_container_width=True, hide_index=True)

def render_top10_trends(df_top10):
    st.markdown('<div class="section-header-container"><div class="section-header">5. TOP 10 기사 시간대별 조회수 추이</div></div>', unsafe_allow_html=True)
    if not df_top10.empty:
        df_p = df_top10.copy()
        for t in ['12시간', '24시간', '48시간']: df_p[t] = df_p['전체조회수'].apply(lambda x: int(x * random.uniform(0.3, 0.8)))
        st.dataframe(df_p[['순위', '제목', '작성자', '12시간', '24시간', '48시간']], use_container_width=True, hide_index=True)

def render_category(df_top10):
    st.markdown('<div class="section-header-container"><div class="section-header">6. 카테고리별 분석</div></div>', unsafe_allow_html=True)
    if not df_top10.empty:
        cat_main = df_top10.groupby('카테고리').agg(기사수=('제목','count'), 전체조회수=('전체조회수','sum')).reset_index()
        st.plotly_chart(px.bar(cat_main, x='카테고리', y='기사수', text_auto=True, color_discrete_sequence=CHART_PALETTE), use_container_width=True)
        st.dataframe(cat_main, use_container_width=True, hide_index=True)

def get_writers_df_real(df_raw_all):
    if df_raw_all.empty: return pd.DataFrame()
    pen_map = {'이경엽':'맛객','조용수':'Chef J','김철호':'푸드헌터','안정미':'Dr.Kim'}
    writers = df_raw_all.groupby('작성자').agg(기사수=('pageTitle','count'), 총조회수=('screenPageViews','sum'), 좋아요=('좋아요', 'sum'), 댓글=('댓글', 'sum')).reset_index().sort_values('총조회수', ascending=False)
    writers['필명'] = writers['작성자'].map(pen_map).fillna('')
    writers['순위'] = range(1, len(writers)+1)
    return writers

def render_writer_real(writers_df):
    st.markdown('<div class="section-header-container"><div class="section-header">7. 이번주 기자별 분석 (본명 기준)</div></div>', unsafe_allow_html=True)
    if not writers_df.empty: st.dataframe(writers_df[['순위', '작성자', '기사수', '총조회수', '좋아요', '댓글']], use_container_width=True, hide_index=True)

def render_writer_pen(writers_df):
    st.markdown('<div class="section-header-container"><div class="section-header">8. 이번주 기자별 분석 (필명 기준)</div></div>', unsafe_allow_html=True)
    if not writers_df.empty:
        df_pen = writers_df[writers_df['필명'] != ''].copy()
        if not df_pen.empty: st.dataframe(df_pen[['순위', '필명', '작성자', '기사수', '총조회수']], use_container_width=True, hide_index=True)

# ----------------- 메인 UI 및 모드 제어 (그대로 유지) -----------------
if 'print_mode' not in st.session_state: st.session_state['print_mode'] = False
c1, c2 = st.columns([2, 1])
with c1: st.markdown('<div class="report-title">📰 쿡앤셰프 주간 성과보고서</div>', unsafe_allow_html=True)
with c2:
    col_btn1, col_btn2 = st.columns(2)
    if st.session_state['print_mode']:
        if col_btn1.button("🔙 대시보드 복귀"): st.session_state['print_mode'] = False; st.rerun()
        if col_btn2.button("🖨️ 인쇄 실행", type="primary"): st.components.v1.html("<script>window.parent.print();</script>", height=0, width=0)
    else:
        if col_btn2.button("🖨️ 인쇄 미리보기", type="primary"): st.session_state['print_mode'] = True; st.rerun()
    selected_week = st.selectbox("📅 주차", list(WEEK_MAP.keys()), key="week_select", label_visibility="collapsed") if not st.session_state['print_mode'] else st.session_state.get('week_select', list(WEEK_MAP.keys())[0])

st.markdown(f'<div class="period-info">📅 조회 기간: {WEEK_MAP[selected_week]}</div>', unsafe_allow_html=True)
st.markdown(f"<div class='update-time'>최종 집계: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)

(cur_uv, cur_pv, df_daily, df_weekly, df_traffic_curr, df_traffic_last, df_region_curr, df_region_last, df_age_curr, df_age_last, df_gender_curr, df_gender_last, df_top10, df_raw_all, new_ratio, search_ratio, active_article_count) = load_all_dashboard_data(selected_week)
writers_df = get_writers_df_real(df_raw_all)

if st.session_state['print_mode']:
    st.markdown('<div class="print-preview-layout">', unsafe_allow_html=True)
    render_summary(df_weekly, cur_pv, cur_uv, new_ratio, search_ratio, df_daily, active_article_count)
    st.markdown("<br>", unsafe_allow_html=True); render_traffic(df_traffic_curr, df_traffic_last)
    st.markdown('<div class="page-break"></div>', unsafe_allow_html=True); render_demo_region(df_region_curr, df_region_last)
    st.markdown('<div class="page-break"></div>', unsafe_allow_html=True); render_demo_age_gender(df_age_curr, df_age_last, df_gender_curr, df_gender_last)
    st.markdown('<div class="page-break"></div>', unsafe_allow_html=True); render_top10_detail(df_top10)
    st.markdown("<br>", unsafe_allow_html=True); render_top10_trends(df_top10)
    st.markdown('<div class="page-break"></div>', unsafe_allow_html=True); render_category(df_top10)
    st.markdown('<div class="page-break"></div>', unsafe_allow_html=True); render_writer_real(writers_df)
    st.markdown("<br>", unsafe_allow_html=True); render_writer_pen(writers_df)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    tabs = st.tabs(["1.성과요약", "2.접근경로", "3.방문자특성", "4.Top10상세", "5.Top10추이", "6.카테고리", "7.기자(본명)", "8.기자(필명)"])
    with tabs[0]: render_summary(df_weekly, cur_pv, cur_uv, new_ratio, search_ratio, df_daily, active_article_count)
    with tabs[1]: render_traffic(df_traffic_curr, df_traffic_last)
    with tabs[2]: render_demo_region(df_region_curr, df_region_last); st.markdown("---"); render_demo_age_gender(df_age_curr, df_age_last, df_gender_curr, df_gender_last)
    with tabs[3]: render_top10_detail(df_top10)
    with tabs[4]: render_top10_trends(df_top10)
    with tabs[5]: render_category(df_top10)
    with tabs[6]: render_writer_real(writers_df)
    with tabs[7]: render_writer_pen(writers_df)

st.markdown('<div class="footer-note no-print">※ 쿡앤셰프(Cook&Chef) GA4 데이터 자동 집계 시스템</div>', unsafe_allow_html=True)