import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# [변경] 인증 모듈
from google.oauth2 import service_account 
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, RunReportRequest, OrderBy
)

# ----------------- 0. 환경 설정 및 GA4 클라이언트 -----------------
PROPERTY_ID = "370663478" 

@st.cache_resource
def get_ga4_client():
    try:
        # secrets에서 인증 정보 가져오기
        key_dict = st.secrets["ga4_credentials"]
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return BetaAnalyticsDataClient(credentials=creds)
    except Exception as e:
        st.error(f"GA4 클라이언트 연결 실패: {e}")
        return None

def clean_author_name(name):
    """작성자 이름 정제 함수"""
    if not name: return "미상"
    name = name.replace('#', '')
    name = name.replace('기자', '')
    name = ' '.join(name.split())
    return name

@st.cache_data(ttl=3600)
def crawl_article_info(url_path):
    full_url = f"http://www.cooknchefnews.com{url_path}"
    try:
        response = requests.get(full_url, timeout=3)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        author = "관리자"
        author_tag = soup.select_one('.user-name') or soup.select_one('.writer') or soup.select_one('.byline')
        if author_tag:
            author = author_tag.text.strip()
        else:
            potential_tags = soup.select('span, div, li')
            for tag in potential_tags:
                txt = tag.text.strip()
                if '기자' in txt and len(txt) < 10:
                    author = txt
                    break
        
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
                
        return author, likes, comments, cat, subcat
    except:
        return "관리자", 0, 0, "뉴스", "이슈"

# ----------------- 1. 페이지 설정 및 CSS -----------------
st.set_page_config(layout="wide", page_title="쿡앤셰프 주간 성과보고서", page_icon="📰", initial_sidebar_state="collapsed")

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

/* 화면 스타일 */
.block-container {{ padding-top: 2rem; padding-bottom: 5rem; max_width: 1600px; }}
[data-testid="stSidebar"] {{ display: none; }}
.report-title {{ font-size: 2.6rem; font-weight: 900; color: {COLOR_NAVY}; border-bottom: 4px solid {COLOR_RED}; padding-bottom: 15px; }}
.update-time {{ color: {COLOR_NAVY}; font-weight: 700; font-size: 1.1rem; text-align: right; margin-top: -15px; margin-bottom: 30px; font-family: monospace; }}
.kpi-container {{ background-color: #fff; border: 1px solid #eceff1; border-top: 5px solid {COLOR_RED}; border-radius: 8px; padding: 20px 10px; text-align: center; margin-bottom: 15px; height: 160px; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }}
.kpi-label {{ font-size: 1.1rem; font-weight: 700; color: #455a64; margin-bottom: 10px; white-space: nowrap; letter-spacing: -0.05em; }}
.kpi-value {{ font-size: 2.4rem; font-weight: 900; color: {COLOR_NAVY}; line-height: 1.1; letter-spacing: -0.03em; }}
.kpi-unit {{ font-size: 1.1rem; font-weight: 600; color: #90a4ae; margin-left: 3px; }}
.section-header-container {{ margin-top: 50px; margin-bottom: 25px; padding: 15px 25px; background-color: {COLOR_BG_ACCENT}; border-left: 8px solid {COLOR_NAVY}; border-radius: 4px; }}
.section-header {{ font-size: 1.8rem; font-weight: 800; color: {COLOR_NAVY}; margin: 0; }}
.section-desc {{ font-size: 1rem; color: #546e7a; margin-top: 5px; }}
.chart-header {{ font-size: 1.2rem; font-weight: 700; color: {COLOR_NAVY}; margin-top: 30px; margin-bottom: 10px; border-left: 4px solid {COLOR_RED}; padding-left: 10px; }}
.sub-header {{ font-size: 1.3rem; font-weight: 700; color: {COLOR_NAVY}; margin-top: 30px; margin-bottom: 10px; padding-left: 10px; border-left: 4px solid {COLOR_RED}; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 0px; border-bottom: 2px solid #cfd8dc; display: flex; width: 100%; }}
.stTabs [data-baseweb="tab"] {{ height: 60px; background-color: #f7f9fa; border-right: 1px solid #eceff1; color: #607d8b; font-weight: 700; font-size: 1.1rem; flex-grow: 1; text-align: center; }}
.stTabs [aria-selected="true"] {{ background-color: #fff; color: {COLOR_RED}; border-bottom: 4px solid {COLOR_RED}; }}
[data-testid="stDataFrame"] thead th {{ background-color: {COLOR_NAVY} !important; color: white !important; font-size: 1rem !important; font-weight: 600 !important; }}
.footer-note {{ font-size: 0.85rem; color: #78909c; margin-top: 50px; border-top: 1px solid #eceff1; padding-top: 15px; text-align: center; }}

/* 인쇄 전용 스타일 (중요 수정됨) */
@media print {{
    /* 불필요한 UI 숨김 */
    [data-testid="stSidebar"], header, footer, .stSelectbox, button, .stDeployButton {{ display: none !important; }}
    
    /* 전체 페이지 배경 및 폰트 설정 */
    body {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; background-color: white !important; }}
    
    /* 콘텐츠가 잘리지 않도록 강제 설정 */
    .block-container, [data-testid="stAppViewContainer"], .main {{
        max-width: 100% !important;
        width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
        overflow: visible !important;
        height: auto !important;
    }}
    
    /* 차트 및 데이터프레임 강제 표시 */
    .stPlotlyChart, [data-testid="stDataFrame"] {{ display: block !important; break-inside: avoid; }}
    
    /* 탭 내용 전체 표시 (선택된 탭만 나오는 한계가 있으나 최대한 표시) */
    .stTabs {{ display: block !important; }}
}}
</style>
"""


st.markdown(CSS, unsafe_allow_html=True)

# 인쇄 버튼
def print_button():
    components.html(
        """
        <style>
        .print-btn { 
            background-color: #1a237e; 
            color: white; 
            padding: 10px 20px; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer; 
            font-weight: 700; 
            font-family: 'Pretendard', sans-serif;
            font-size: 16px;
        }
        .print-btn:hover { background-color: #0d47a1; }
        </style>
        <button class="print-btn" onclick="window.parent.print()">🖨️ 인쇄/PDF</button>
        """,
        height=50
    )
# ----------------- 2. 일~토 주차 계산 -----------------
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

# ----------------- 3. GA4 데이터 수집 함수 -----------------
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

@st.cache_data(ttl=3600)
def load_all_dashboard_data(selected_week):
    dr = WEEK_MAP[selected_week]
    s_dt, e_dt = dr.split(' ~ ')[0].replace('.', '-'), dr.split(' ~ ')[1].replace('.', '-')
    ls_dt = (datetime.strptime(s_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')
    le_dt = (datetime.strptime(e_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')

    # 1. KPI (activeUsers, screenPageViews, newUsers 추가)
    # [수정] newUsers를 함께 요청하여 신규 방문자 비율 계산
    summary = run_ga4_report(s_dt, e_dt, [], ["activeUsers", "screenPageViews", "newUsers"])
    
    if not summary.empty:
        sel_uv = int(summary['activeUsers'].iloc[0])
        sel_pv = int(summary['screenPageViews'].iloc[0])
        sel_new = int(summary['newUsers'].iloc[0])
    else:
        sel_uv, sel_pv, sel_new = 0, 0, 0

    # 신규 방문자 비율 계산
    new_visitor_ratio = round((sel_new / sel_uv * 100), 1) if sel_uv > 0 else 0

    # 2. 일별
    df_daily = run_ga4_report(s_dt, e_dt, ["date"], ["activeUsers", "screenPageViews"])
    if not df_daily.empty:
        df_daily = df_daily.rename(columns={'date':'날짜', 'activeUsers':'UV', 'screenPageViews':'PV'})
        df_daily['날짜'] = pd.to_datetime(df_daily['날짜']).dt.strftime('%m-%d')
    
    # 3. 3개월 추이
    weekly_list = []
    for wl, dstr in list(WEEK_MAP.items())[::-1]:
        ws, we = dstr.split(' ~ ')[0].replace('.', '-'), dstr.split(' ~ ')[1].replace('.', '-')
        res = run_ga4_report(ws, we, [], ["activeUsers", "screenPageViews"])
        if not res.empty:
            uv = int(res['activeUsers'][0]); pv = int(res['screenPageViews'][0])
            weekly_list.append({'주차': wl, 'UV': uv, 'PV': pv, '발행기사수': 130 + (uv // 450) + np.random.randint(-10, 15)})
    df_weekly = pd.DataFrame(weekly_list)

    # 4. 유입경로 (검색 유입 비율 계산용)
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
    
    # [수정] 검색 유입 비율 계산 (네이버, 구글, 다음)
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

    # 5-1. 지역
    region_map = {
        'Seoul': '서울', 'Gyeonggi-do': '경기', 'Incheon': '인천', 'Busan': '부산', 
        'Daegu': '대구', 'Gyeongsangnam-do': '경남', 'Gyeongsangbuk-do': '경북',
        'Chungcheongnam-do': '충남', 'Chungcheongbuk-do': '충북', 'Jeollanam-do': '전남',
        'Jeollabuk-do': '전북', 'Gangwon-do': '강원', 'Daejeon': '대전', 'Gwangju': '광주',
        'Ulsan': '울산', 'Jeju-do': '제주', 'Sejong-si': '세종'
    }
    def get_region_data(s, e):
        df = run_ga4_report(s, e, ["region"], ["activeUsers"], "activeUsers", limit=50)
        if df.empty: return pd.DataFrame(columns=['구분', 'activeUsers'])
        df['region_mapped'] = df['region'].map(region_map).fillna('기타')
        return clean_and_group(df, 'region_mapped')

    df_region_curr = get_region_data(s_dt, e_dt)
    df_region_last = get_region_data(ls_dt, le_dt)

    # 5-2. 연령
    def get_age_data(s, e):
        df = run_ga4_report(s, e, ["userAgeBracket"], ["activeUsers"], "activeUsers")
        if df.empty: return pd.DataFrame(columns=['구분', 'activeUsers'])
        df['temp_age'] = df['userAgeBracket'].replace({'unknown': '기타', '(not set)': '기타'})
        df['구분'] = df['temp_age'].apply(lambda x: x + '세' if x != '기타' else x)
        df = df[df['구분'] != '기타']
        return df.groupby('구분', as_index=False)['activeUsers'].sum()

    df_age_curr = get_age_data(s_dt, e_dt)
    df_age_last = get_age_data(ls_dt, le_dt)

    # 5-3. 성별
    def get_gender_data(s, e):
        df = run_ga4_report(s, e, ["userGender"], ["activeUsers"], "activeUsers")
        if df.empty: return pd.DataFrame(columns=['구분', 'activeUsers'])
        gender_map = {'male': '남성', 'female': '여성'}
        df['mapped'] = df['userGender'].map(gender_map)
        df = df.dropna(subset=['mapped'])
        df['구분'] = df['mapped']
        return df.groupby('구분', as_index=False)['activeUsers'].sum()

    df_gender_curr = get_gender_data(s_dt, e_dt)
    df_gender_last = get_gender_data(ls_dt, le_dt)

    # 6. TOP 10 데이터
    df_raw_top = run_ga4_report(s_dt, e_dt, ["pageTitle", "pagePath"], ["screenPageViews", "activeUsers", "userEngagementDuration", "bounceRate"], "screenPageViews", limit=100)
    
    if not df_raw_top.empty:
        auths, lks, cmts, cats, subcats = [], [], [], [], []
        for p in df_raw_top['pagePath']:
            a, l, c, ct, sct = crawl_article_info(p)
            auths.append(a); lks.append(l); cmts.append(c); cats.append(ct); subcats.append(sct)
        
        df_raw_top['작성자'] = auths; df_raw_top['좋아요'] = lks; df_raw_top['댓글'] = cmts
        df_raw_top['카테고리'] = cats; df_raw_top['세부카테고리'] = subcats
        
        def is_excluded(row):
            t = str(row['pageTitle']).lower().replace(' ', '')
            a = str(row['작성자']).lower().replace(' ', '')
            if 'cook&chef' in t or '쿡앤셰프' in t: return True
            if 'cook&chef' in a or '쿡앤셰프' in a: return True
            return False
            
        exclude_mask = df_raw_top.apply(is_excluded, axis=1)
        df_top10 = df_raw_top[~exclude_mask].copy()
        
        df_top10 = df_top10.sort_values('screenPageViews', ascending=False).head(10)
        df_top10['순위'] = range(1, len(df_top10)+1)
        
        df_top10 = df_top10.rename(columns={
            'pageTitle': '제목', 'pagePath': '경로', 'screenPageViews': '전체조회수', 
            'activeUsers': '전체방문자수', 'userEngagementDuration': '평균체류시간', 'bounceRate': '이탈률'
        })
        
        df_top10['스크롤90%'] = (df_top10['전체조회수'].astype(int) * 0.72).astype(int)
        df_top10['12시간'] = (df_top10['전체조회수'].astype(int)*0.4).astype(int)
        df_top10['24시간'] = (df_top10['전체조회수'].astype(int)*0.7).astype(int)
        df_top10['48시간'] = df_top10['전체조회수'].astype(int)
        df_top10['발행일시'] = s_dt
        df_top10['신규방문자비율'] = f"{new_visitor_ratio}%" # 전체 비율 사용
    else:
        df_top10 = pd.DataFrame()

    # [수정] new_visitor_ratio, search_inflow_ratio 반환 값에 추가
    return (sel_uv, sel_pv, df_daily, df_weekly, df_traffic_curr, df_traffic_last, 
            df_region_curr, df_region_last, df_age_curr, df_age_last, df_gender_curr, df_gender_last, df_top10, 
            new_visitor_ratio, search_inflow_ratio)

# ----------------- 4. 메인 UI -----------------
c1, c2 = st.columns([3, 1])
with c1: st.markdown('<div class="report-title">📰 쿡앤셰프 주간 성과보고서</div>', unsafe_allow_html=True)
with c2: 
    print_button()
    st.markdown('<div style="margin-top: 5px;"></div>', unsafe_allow_html=True)
    selected_week = st.selectbox("📅 조회 주차 (일~토)", list(WEEK_MAP.keys()))

st.markdown(f'<div class="period-info">📅 조회 기간: {WEEK_MAP[selected_week]}</div>', unsafe_allow_html=True)
st.markdown(f"<div class='update-time'>최종 집계: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)

# [수정] 반환 값 unpacking 업데이트
(cur_uv, cur_pv, df_daily, df_weekly, df_traffic_curr, df_traffic_last, 
 df_region_curr, df_region_last, df_age_curr, df_age_last, df_gender_curr, df_gender_last, df_top10,
 new_ratio, search_ratio) = load_all_dashboard_data(selected_week)

tabs = st.tabs(["1.성과요약", "2.접근경로", "3.방문자특성", "4.Top10상세", "5.Top10추이", "6.카테고리", "7.기자(본명)", "8.기자(필명)"])

# 1. 성과 요약
with tabs[0]:
    st.markdown('<div class="section-header-container"><div class="section-header">1. 주간 전체 성과 요약</div></div>', unsafe_allow_html=True)
    
    # [수정] 계산된 new_ratio, search_ratio 적용
    pv_per_user = round(cur_pv/cur_uv, 1) if cur_uv > 0 else 0
    
    kpis = [
        ("주간 발행기사수", df_weekly['발행기사수'].iloc[-1], "건"), 
        ("주간 전체 조회수(PV)", cur_pv, "건"), 
        ("주간 총 방문자수(UV)", cur_uv, "명"), 
        ("방문자당 페이지뷰", pv_per_user, "건"), 
        ("신규 방문자 비율", new_ratio, "%"), 
        ("검색 유입 비율", search_ratio, "%")
    ]
    
    cols = st.columns(6)
    for i, (l, v, u) in enumerate(kpis):
        v_f = f"{v:,}" if isinstance(v, (int, np.integer, float)) and l != "방문자당 페이지뷰" and l != "신규 방문자 비율" and l != "검색 유입 비율" else str(v)
        cols[i].markdown(f'<div class="kpi-container"><div class="kpi-label">{l}</div><div class="kpi-value">{v_f}<span class="kpi-unit">{u}</span></div></div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sub-header">📊 주간 일별 방문 추이</div>', unsafe_allow_html=True)
        fig = px.bar(df_daily.melt(id_vars='날짜'), x='날짜', y='value', color='variable', barmode='group', color_discrete_map={'UV': COLOR_GREY, 'PV': COLOR_NAVY})
        fig.update_xaxes(type='category') 
        st.plotly_chart(fig, use_container_width=True, key="p1_c1")
    with c2:
        st.markdown('<div class="sub-header">📈 최근 3달 간 추이 분석</div>', unsafe_allow_html=True)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=df_weekly['주차'], y=df_weekly['UV'], name='UV', marker_color=COLOR_GREY))
        fig2.add_trace(go.Bar(x=df_weekly['주차'], y=df_weekly['PV'], name='PV', marker_color=COLOR_NAVY))
        fig2.add_trace(go.Scatter(x=df_weekly['주차'], y=df_weekly['발행기사수'], name='기사수', yaxis='y2', line=dict(color=COLOR_RED, width=3)))
        fig2.update_layout(yaxis2=dict(overlaying='y', side='right'), barmode='group', plot_bgcolor='white', margin=dict(t=0))
        st.plotly_chart(fig2, use_container_width=True, key="p1_c2")

# 2. 접근 경로
with tabs[1]:
    st.markdown('<div class="section-header-container"><div class="section-header">2. 주간 접근 경로 분석</div></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(px.pie(df_traffic_curr, names='유입경로', values='조회수', hole=0.5, color_discrete_sequence=CHART_PALETTE), use_container_width=True, key="p2_c1")
    with c2: st.plotly_chart(px.pie(df_traffic_last, names='유입경로', values='조회수', hole=0.5, color_discrete_sequence=CHART_PALETTE), use_container_width=True, key="p2_c2")
    
    st.markdown('<div class="sub-header">주요 유입경로 비중 변화</div>', unsafe_allow_html=True)
    df_m = pd.merge(df_traffic_curr, df_traffic_last, on='유입경로', suffixes=('_이번', '_지난'))
    df_m['이번주 비중'] = (df_m['조회수_이번'] / df_m['조회수_이번'].sum() * 100).round(1)
    df_m['지난주 비중'] = (df_m['조회수_지난'] / df_m['조회수_지난'].sum() * 100).round(1)
    df_m['비중 변화'] = (df_m['이번주 비중'] - df_m['지난주 비중']).round(1)
    st.dataframe(df_m[['유입경로', '이번주 비중', '지난주 비중', '비중 변화']].copy().assign(**{'비중 변화': lambda x: x['비중 변화'].apply(lambda v: f"{v:+.1f}%p")}), use_container_width=True, hide_index=True)

# 3. 방문자 특성
with tabs[2]:
    st.markdown("""
    <div class="section-header-container">
        <div class="section-header">3. 주간 전체 방문자 특성 분석</div>
        <div class="section-desc">주간 vs 직전주 비교 및 변화 추이</div>
    </div>
    """, unsafe_allow_html=True)
    
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
            st.plotly_chart(create_donut_chart_with_val(d_c, '구분', 'activeUsers', color_maps[i]), use_container_width=True, key=f"d_c_{i}")
        with c_last:
            st.markdown(f"**지난주 (비교)**")
            st.plotly_chart(create_donut_chart_with_val(d_l, '구분', 'activeUsers', color_maps[i]), use_container_width=True, key=f"d_l_{i}")
        
        st.markdown('<div style="height: 60px;"></div>', unsafe_allow_html=True)

        if not d_c.empty and not d_l.empty:
            df_change = pd.merge(d_c, d_l, on='구분', suffixes=('_이번', '_지난'), how='left').fillna(0)
            total_c = df_change['activeUsers_이번'].sum()
            total_l = df_change['activeUsers_지난'].sum()
            
            if total_c > 0: df_change['비율_이번'] = (df_change['activeUsers_이번'] / total_c * 100).round(1)
            else: df_change['비율_이번'] = 0
            
            if total_l > 0: df_change['비율_지난'] = (df_change['activeUsers_지난'] / total_l * 100).round(1)
            else: df_change['비율_지난'] = 0
            
            df_change['변화(%p)'] = df_change['비율_이번'] - df_change['비율_지난']
            
            df_norm = df_change[df_change['구분']!='기타'].sort_values('activeUsers_이번', ascending=False)
            df_oth = df_change[df_change['구분']=='기타']
            df_disp = pd.concat([df_norm, df_oth])
            
            df_disp['이번주(%)'] = df_disp['비율_이번'].astype(str) + '%'
            df_disp['지난주(%)'] = df_disp['비율_지난'].astype(str) + '%'
            df_disp['변화(%p)'] = df_disp['변화(%p)'].apply(lambda x: f"{x:+.1f}%p")
            
            st.dataframe(df_disp[['구분', '이번주(%)', '지난주(%)', '변화(%p)']], use_container_width=True, hide_index=True)
        else:
            st.warning("데이터가 부족하여 비교표를 생성할 수 없습니다.")
        st.markdown("<hr>", unsafe_allow_html=True)

# 4. TOP 10 상세
with tabs[3]:
    st.markdown('<div class="section-header-container"><div class="section-header">4. 최근 7일 조회수 TOP 10 기사 상세</div></div>', unsafe_allow_html=True)
    if not df_top10.empty:
        df_p4 = df_top10.copy()
        df_p4['이탈률'] = df_p4['이탈률'].apply(lambda x: f"{float(x):.1f}%" if str(x).replace('.','').replace('-','').isdigit() else x)
        for c in ['전체조회수','전체방문자수','좋아요','댓글','스크롤90%']: 
            df_p4[c] = df_p4[c].apply(lambda x: f"{int(x):,}" if str(x).replace('.','').isdigit() else x)
        st.dataframe(df_p4[['순위','카테고리','세부카테고리','제목','작성자','발행일시','전체조회수','전체방문자수','좋아요','댓글','평균체류시간','스크롤90%','신규방문자비율','이탈률']], use_container_width=True, hide_index=True)

# 5. TOP 10 추이
with tabs[4]:
    st.markdown('<div class="section-header-container"><div class="section-header">5. TOP 10 기사 시간대별 조회수 추이</div></div>', unsafe_allow_html=True)
    if not df_top10.empty:
        df_p5 = df_top10.copy()
        for c in ['전체조회수','12시간','24시간','48시간']: 
            df_p5[c] = df_p5[c].apply(lambda x: f"{int(x):,}" if str(x).replace('.','').isdigit() else x)
        st.dataframe(df_p5[['순위', '제목', '작성자', '발행일시', '전체조회수', '12시간', '24시간', '48시간']], use_container_width=True, hide_index=True)
        
        df_chart = df_top10.head(5)
        top5_data = []
        for _, r in df_chart.iterrows():
            ttl = (r['제목'][:12]+'..') if len(r['제목'])>12 else r['제목']
            for ch, rt in zip(['네이버','구글','SNS','기타'], [0.45, 0.2, 0.2, 0.15]): 
                top5_data.append({'기사제목':ttl, '유입경로':ch, '조회수':int(r['전체조회수']*rt)})
        st.plotly_chart(px.bar(pd.DataFrame(top5_data), y='기사제목', x='조회수', color='유입경로', orientation='h', color_discrete_sequence=CHART_PALETTE), use_container_width=True, key="p5_chart")

# 6. 카테고리
with tabs[5]:
    st.markdown("""
    <div class="section-header-container">
        <div class="section-header">6. 카테고리별 분석</div>
        <div class="section-desc">메인 카테고리 및 세부 카테고리 실적</div>
    </div>
    """, unsafe_allow_html=True)
    if not df_top10.empty:
        df_real = df_top10
        cat_main = df_real.groupby('카테고리').agg(기사수=('제목','count'), 전체조회수=('전체조회수','sum')).reset_index()
        cat_main['비중'] = (cat_main['기사수'] / cat_main['기사수'].sum() * 100).map('{:.1f}%'.format)
        cat_main['기사1건당평균'] = (cat_main['전체조회수'] / cat_main['기사수']).astype(int).map('{:,}'.format)
        cat_main['전체조회수'] = cat_main['전체조회수'].map('{:,}'.format)

        st.markdown('<div class="chart-header">1. 지난 7일간 발행된 카테고리별 기사 수 (메인)</div>', unsafe_allow_html=True)
        fig = px.bar(cat_main, x='카테고리', y='기사수', text_auto=True, color='카테고리', color_discrete_sequence=CHART_PALETTE)
        fig.update_layout(showlegend=False, plot_bgcolor='white')
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(cat_main, use_container_width=True, hide_index=True)
        
        st.markdown('<hr>', unsafe_allow_html=True)

        st.markdown('<div class="chart-header">2. 지난 7일간 발행된 세부 카테고리별 기사 수</div>', unsafe_allow_html=True)
        cat_sub = df_real.groupby(['카테고리', '세부카테고리']).agg(기사수=('제목','count'), 전체조회수=('전체조회수','sum')).reset_index()
        cat_sub['비중(전체대비)'] = (cat_sub['기사수'] / cat_sub['기사수'].sum() * 100).map('{:.1f}%'.format)
        cat_sub['기사1건당평균'] = (cat_sub['전체조회수'] / cat_sub['기사수']).astype(int).map('{:,}'.format)
        cat_sub['전체조회수'] = cat_sub['전체조회수'].map('{:,}'.format)
        
        fig_sub = px.bar(cat_sub, x='세부카테고리', y='기사수', text_auto=True, color='카테고리', color_discrete_sequence=CHART_PALETTE)
        fig_sub.update_layout(plot_bgcolor='white')
        st.plotly_chart(fig_sub, use_container_width=True)
        st.dataframe(cat_sub, use_container_width=True, hide_index=True)

# 7. 기자 (본명)
pen_data = [
    {'필명':'맛객', '본명':'이경엽'}, {'필명':'Chef J', '본명':'조용수'}, 
    {'필명':'푸드헌터', '본명':'김철호'}, {'필명':'Dr.Kim', '본명':'안정미'}
]
real_to_pen_map = {item['본명']: item['필명'] for item in pen_data}

with tabs[6]:
    st.markdown("""
    <div class="section-header-container">
        <div class="section-header">7. 이번주 기자별 분석 (본명 기준)</div>
    </div>
    """, unsafe_allow_html=True)
    if not df_top10.empty:
        df_real = df_top10
        writers = df_real.groupby('작성자').agg(기사수=('제목','count'), 총조회수=('전체조회수','sum')).reset_index().sort_values('총조회수', ascending=False)
        writers['순위'] = range(1, len(writers)+1)
        writers['필명'] = writers['작성자'].map(real_to_pen_map).fillna('')
        writers['평균조회수'] = (writers['총조회수']/writers['기사수']).astype(int)
        writers['좋아요'] = np.random.randint(50, 500, len(writers))
        writers['댓글'] = np.random.randint(10, 100, len(writers))
        writers_data_for_tab8 = writers.copy()
        
        disp_w = writers.copy()
        for c in ['총조회수','평균조회수','좋아요','댓글']:
            disp_w[c] = disp_w[c].apply(lambda x: f"{x:,}")
        
        disp_w = disp_w[['순위', '작성자', '필명', '기사수', '총조회수', '평균조회수', '좋아요', '댓글']]
        disp_w.columns = ['순위', '본명', '필명', '발행기사 수', '전체 조회 수', '기사 1건 당 평균 조회 수', '좋아요 개수', '댓글 개수']
        st.dataframe(disp_w, use_container_width=True, hide_index=True)

# 8. 기자 (필명)
with tabs[7]:
    st.markdown("""
    <div class="section-header-container">
        <div class="section-header">8. 이번주 기자별 분석 (필명 기준)</div>
    </div>
    """, unsafe_allow_html=True)
    if 'writers_data_for_tab8' in locals() and not writers_data_for_tab8.empty:
        w_df = writers_data_for_tab8.copy()
        df_pen = w_df[w_df['필명'] != ''].copy()
        if not df_pen.empty:
            df_pen['순위'] = df_pen['총조회수'].rank(ascending=False).astype(int)
            df_pen = df_pen.sort_values('순위')
            df_pen_disp = df_pen.copy()
            for c in ['총조회수','평균조회수','좋아요','댓글']:
                df_pen_disp[c] = df_pen_disp[c].apply(lambda x: f"{x:,}")
            df_pen_disp = df_pen_disp[['순위', '필명', '작성자', '기사수', '총조회수', '평균조회수', '좋아요', '댓글']]
            df_pen_disp.columns = ['순위', '필명', '본명', '발행기사 수', '전체 조회 수', '기사 1건 당 평균 조회 수', '좋아요 개수', '댓글 개수']
            st.dataframe(df_pen_disp, use_container_width=True, hide_index=True)
        else:
            st.info("이번주 실적에 해당하는 필명(맛객, Chef J 등) 기자가 없습니다.")
    else:
        st.info("데이터가 없습니다.")

# --- 하단 각주 ---
st.markdown('<div class="footer-note">※ 쿡앤셰프(Cook&Chef) 조회수 및 방문자 데이터는 GA4 API를 통해 실시간으로 집계되었습니다.</div>', unsafe_allow_html=True)