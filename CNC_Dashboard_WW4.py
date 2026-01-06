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

st.set_page_config(
    layout="wide", 
    page_title="쿡앤셰프 주간 성과보고서", 
    page_icon="📰", 
    initial_sidebar_state="collapsed"
)

COLOR_NAVY = "#1a237e"
COLOR_RED = "#d32f2f"
COLOR_GREY = "#78909c"
COLOR_BG_ACCENT = "#fffcf7"
CHART_PALETTE = [COLOR_NAVY, COLOR_RED, "#5c6bc0", "#ef5350", "#8d6e63", COLOR_GREY]
COLOR_GENDER = {'여성': '#d32f2f', '남성': '#1a237e'} 

CSS = f"""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css');
body {{ background-color: #ffffff; font-family: 'Pretendard', sans-serif; color: #263238; font-size: 16px; }}

header[data-testid="stHeader"] {{ visibility: hidden !important; }}
[data-testid="stToolbar"] {{ visibility: hidden !important; }}
.block-container {{ padding-top: 2rem !important; padding-bottom: 5rem; max_width: 1800px; }}
[data-testid="stSidebar"] {{ display: none; }}

.report-title {{ font-size: 3.2rem; font-weight: 900; color: {COLOR_NAVY}; border-bottom: 4px solid {COLOR_RED}; padding-bottom: 15px; margin-top: 10px; }}
.period-info {{ font-size: 1.4rem; font-weight: 700; color: #455a64; margin-top: 10px; }}
.update-time {{ color: {COLOR_NAVY}; font-weight: 700; font-size: 1.2rem; text-align: right; margin-top: -15px; margin-bottom: 30px; font-family: monospace; }}
.kpi-container {{ background-color: #fff; border: 1px solid #eceff1; border-top: 5px solid {COLOR_RED}; border-radius: 8px; padding: 25px 15px; text-align: center; margin-bottom: 15px; height: 180px; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }}
.kpi-label {{ font-size: 1.3rem; font-weight: 700; color: #455a64; margin-bottom: 10px; white-space: nowrap; letter-spacing: -0.05em; }}
.kpi-value {{ font-size: 2.8rem; font-weight: 900; color: {COLOR_NAVY}; line-height: 1.1; letter-spacing: -0.03em; }}
.kpi-unit {{ font-size: 1.3rem; font-weight: 600; color: #90a4ae; margin-left: 3px; }}
.section-header-container {{ margin-top: 30px; margin-bottom: 25px; padding: 20px 30px; background-color: {COLOR_BG_ACCENT}; border-left: 8px solid {COLOR_NAVY}; border-radius: 4px; }}
.section-header {{ font-size: 2.2rem; font-weight: 800; color: {COLOR_NAVY}; margin: 0; }}
.section-desc {{ font-size: 1.2rem; color: #546e7a; margin-top: 5px; }}
.sub-header {{ font-size: 1.6rem; font-weight: 700; color: {COLOR_NAVY}; margin-top: 30px; margin-bottom: 10px; padding-left: 10px; border-left: 4px solid {COLOR_RED}; }}
.chart-header {{ font-size: 1.4rem; font-weight: 700; color: {COLOR_NAVY}; margin-top: 30px; margin-bottom: 10px; border-left: 4px solid {COLOR_RED}; padding-left: 10px; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 0px; border-bottom: 2px solid #cfd8dc; display: flex; width: 100%; }}
.stTabs [data-baseweb="tab"] {{ height: 70px; background-color: #f7f9fa; border-right: 1px solid #eceff1; color: #607d8b; font-weight: 700; font-size: 1.3rem; flex-grow: 1; text-align: center; }}
.stTabs [aria-selected="true"] {{ background-color: #fff; color: {COLOR_RED}; border-bottom: 4px solid {COLOR_RED}; }}
[data-testid="stDataFrame"] thead th {{ background-color: {COLOR_NAVY} !important; color: white !important; font-size: 1.2rem !important; font-weight: 600 !important; }}
[data-testid="stDataFrame"] tbody td {{ font-size: 1.1rem !important; }}
.footer-note {{ font-size: 1rem; color: #78909c; margin-top: 50px; border-top: 1px solid #eceff1; padding-top: 15px; text-align: center; }}

.traffic-tooltip {{ background-color: rgba(26, 35, 126, 0.95); color: white; padding: 8px 12px; border-radius: 4px; font-size: 0.9rem; }}
.tooltip-container {{ position: relative; display: inline-block; }}
.tooltip-container:hover .traffic-tooltip {{ visibility: visible; opacity: 1; }}
.traffic-tooltip {{ visibility: hidden; opacity: 0; position: absolute; z-index: 1; bottom: 125%; left: 50%; margin-left: -60px; transition: opacity 0.3s; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

PRINT_CSS = """
<style>
.print-preview-layout {
    transform: scale(0.9); 
    transform-origin: top center; 
    width: 111%;
}

@media print {
    @page { 
        size: A4 landscape; 
        margin: 8mm; 
    }
    
    body { 
        transform: scale(0.85) !important; 
        transform-origin: top left !important; 
        width: 118% !important;
        font-size: 18px !important;
    }
    
    .no-print, .stButton, header, footer, [data-testid="stSidebar"] { display: none !important; }
    
    .page-break { 
        page-break-before: always !important; 
        break-before: page !important;
        display: block;
        height: 1px;
        margin-top: 20px;
    }
    
    [data-testid="stDataFrame"] {
        width: 100% !important;
        font-size: 14px !important;
    }
    [data-testid="stDataFrame"] > div {
        width: 100% !important;
    }
    
    .section-header-container { margin-top: 8px !important; }
    .block-container { padding-top: 0 !important; }
    
    .print-footer {
        position: fixed;
        bottom: 0;
        width: 100%;
        text-align: center;
        font-size: 12px;
        color: #999;
    }
    
    .kpi-container { height: 140px !important; }
    .section-header { font-size: 1.8rem !important; }
    .sub-header { font-size: 1.4rem !important; }
}
</style>
"""
st.markdown(PRINT_CSS, unsafe_allow_html=True)

def check_password():
    if st.session_state.get("password_correct", False):
        return True

    login_placeholder = st.empty()
    with login_placeholder.container():
        st.markdown(
            """
            <style>
            .login-container { max-width: 400px; margin: 100px auto; padding: 40px; text-align: center; }
            .login-title { font-size: 28px; font-weight: 700; color: #1a237e; margin-bottom: 20px; text-align: center; }
            .powered-by { font-size: 14px; color: #90a4ae; margin-top: 50px; font-weight: 500; }
            .stTextInput > div > div > input { text-align: center; font-size: 20px; letter-spacing: 2px; }
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

def get_publish_date_from_path(url_path):
    try:
        date_match = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url_path)
        if date_match:
            year, month, day = date_match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        return (datetime.now() - timedelta(days=random.randint(1, 7))).strftime('%Y-%m-%d')
    except:
        return datetime.now().strftime('%Y-%m-%d')

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
        
        publish_date = get_publish_date_from_path(url_path)
        date_tag = soup.select_one('.date') or soup.select_one('.publish-date') or soup.select_one('time')
        if date_tag:
            date_text = date_tag.text.strip()
            try:
                parsed_date = pd.to_datetime(date_text)
                publish_date = parsed_date.strftime('%Y-%m-%d')
            except:
                pass
        
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
        
        return (author, likes, comments, cat, subcat, publish_date)
    except: 
        return ("관리자", 0, 0, "뉴스", "이슈", datetime.now().strftime('%Y-%m-%d'))

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
    except: 
        return pd.DataFrame(columns=dimensions + metrics)

def get_article_traffic_sources(start_date, end_date, page_paths):
    client = get_ga4_client()
    if not client or not page_paths: return pd.DataFrame()
    
    article_traffic = []
    
    for path in page_paths[:20]: 
        traffic_data = run_ga4_report(start_date, end_date, 
                                    ["pagePath", "sessionSource"], 
                                    ["screenPageViews"], 
                                    limit=1000)
        
        if not traffic_data.empty:
            path_data = traffic_data[traffic_data['pagePath'] == path]
            if not path_data.empty:
                for _, row in path_data.iterrows():
                    source_mapped = map_traffic_source(row['sessionSource'])
                    article_traffic.append({
                        'pagePath': path,
                        '유입경로': source_mapped,
                        '조회수': row['screenPageViews']
                    })
    
    return pd.DataFrame(article_traffic)

def map_traffic_source(source):
    source = source.lower()
    if 'naver' in source: return '네이버'
    if 'daum' in source: return '다음'
    if 'facebook' in source: return '페이스북'
    if '(direct)' in source: return '직접 접근'
    if 'google' in source: return '구글'
    if 'youtube' in source: return '유튜브'
    if 'instagram' in source: return '인스타그램'
    if 'twitter' in source: return '트위터'
    if 'kakao' in source: return '카카오'
    return '기타'

def create_donut_chart_with_val(df, names, values, color_map=None, size='normal'):
    if df.empty: return go.Figure()
    
    if size == 'small':
        height, margin_dict = 250, dict(t=15, b=50, l=25, r=25)
    else:
        height, margin_dict = 350, dict(t=30, b=80, l=40, r=40)
    
    if '구분' in df.columns:
        df_normal = df[df['구분'] != '기타'].sort_values(by=values, ascending=False)
        df_other = df[df['구분'] == '기타']
        df_sorted = pd.concat([df_normal, df_other])
    else: df_sorted = df
    
    if color_map: 
        fig = px.pie(df_sorted, names=names, values=values, hole=0.5, color=names, color_discrete_map=color_map)
    else: 
        fig = px.pie(df_sorted, names=names, values=values, hole=0.5, color_discrete_sequence=CHART_PALETTE)
    
    fig.update_traces(textposition='outside', textinfo='label+percent', sort=False)
    fig.update_layout(showlegend=False, margin=margin_dict, height=height)
    
    return fig

def evaluate_freelancer_performance(writers_df, df_all_articles):
    if writers_df.empty: return pd.DataFrame()
    
    freelancers = ['맛객', '이경엽', 'Chef J', '조용수', '푸드헌터', '김철호', 'Dr.Kim', '안정미']
    
    freelancer_data = []
    for _, writer in writers_df.iterrows():
        if any(fl in writer['작성자'] for fl in freelancers):
            avg_views = writer['평균조회수']
            total_articles = writer['기사수']
            engagement_score = (writer['좋아요'] + writer['댓글'] * 2) / total_articles if total_articles > 0 else 0
            
            if avg_views >= 1000: grade = 'S'
            elif avg_views >= 700: grade = 'A'
            elif avg_views >= 500: grade = 'B'
            elif avg_views >= 300: grade = 'C'
            else: grade = 'D'
            
            freelancer_data.append({
                '기자명': writer['작성자'],
                '발행기사수': total_articles,
                '평균조회수': avg_views,
                '참여도점수': round(engagement_score, 1),
                '성과등급': grade,
                '총조회수': writer['총조회수']
            })
    
    return pd.DataFrame(freelancer_data).sort_values('평균조회수', ascending=False)

@st.cache_data(ttl=3600, show_spinner="데이터 불러오는 중...")
def load_all_dashboard_data(selected_week):
    dr = WEEK_MAP[selected_week]
    s_dt, e_dt = dr.split(' ~ ')[0].replace('.', '-'), dr.split(' ~ ')[1].replace('.', '-')
    ls_dt = (datetime.strptime(s_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')
    le_dt = (datetime.strptime(e_dt, '%Y-%m-%d')-timedelta(days=7)).strftime('%Y-%m-%d')

    # KPI
    summary = run_ga4_report(s_dt, e_dt, [], ["activeUsers", "screenPageViews", "newUsers"])
    if not summary.empty:
        sel_uv = int(summary['activeUsers'].iloc[0])
        sel_pv = int(summary['screenPageViews'].iloc[0])
        sel_new = int(summary['newUsers'].iloc[0])
    else: sel_uv, sel_pv, sel_new = 0, 0, 0
    new_visitor_ratio = round((sel_new / sel_uv * 100), 1) if sel_uv > 0 else 0

    # 일별 데이터
    df_daily = run_ga4_report(s_dt, e_dt, ["date"], ["activeUsers", "screenPageViews"])
    if not df_daily.empty:
        df_daily = df_daily.rename(columns={'date':'날짜', 'activeUsers':'UV', 'screenPageViews':'PV'})
        df_daily['날짜'] = pd.to_datetime(df_daily['날짜']).dt.strftime('%m-%d')
    
    # 3개월 추이
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

    # 유입경로
    df_t_raw = run_ga4_report(s_dt, e_dt, ["sessionSource"], ["screenPageViews"])
    df_t_raw['유입경로'] = df_t_raw['sessionSource'].apply(map_traffic_source)
    df_traffic_curr = df_t_raw.groupby('유입경로')['screenPageViews'].sum().reset_index().rename(columns={'screenPageViews':'조회수'})
    
    search_engines = ['네이버', '구글', '다음']
    search_pv = df_traffic_curr[df_traffic_curr['유입경로'].isin(search_engines)]['조회수'].sum()
    total_pv_traffic = df_traffic_curr['조회수'].sum()
    search_inflow_ratio = round((search_pv / total_pv_traffic * 100), 1) if total_pv_traffic > 0 else 0
    
    df_tl_raw = run_ga4_report(ls_dt, le_dt, ["sessionSource"], ["screenPageViews"])
    df_tl_raw['유입경로'] = df_tl_raw['sessionSource'].apply(map_traffic_source)
    df_traffic_last = df_tl_raw.groupby('유입경로')['screenPageViews'].sum().reset_index().rename(columns={'screenPageViews':'조회수'})

    # 방문자 특성
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

    # TOP 10 크롤링
    df_raw_top = run_ga4_report(s

