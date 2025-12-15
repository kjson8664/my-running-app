import streamlit as st
# 서버에서 그림 그릴 때 충돌 방지
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import rc
from garminconnect import Garmin
import datetime
import os
import gpxpy

# ==========================================
# 폰트 설정 (이모지 사용 금지)
# ==========================================
rc('font', family='NanumGothic')
plt.rcParams['axes.unicode_minus'] = False

# ==========================================
# 사이드바
# ==========================================
st.sidebar.header("설정")
MY_WEEKLY_GOAL = st.sidebar.number_input("주간 목표 (km)", value=100.0, step=5.0)
MY_THRESHOLD_PACE = st.sidebar.number_input("역치 페이스 (초)", value=270, help="4분30초=270")
MY_MAX_HR = st.sidebar.number_input("최대 심박수", value=185)

st.sidebar.markdown("---")
z2_limit = st.sidebar.number_input("Zone 2 상한", value=125)
z3_limit = st.sidebar.number_input("Zone 3 상한", value=148)
z4_limit = st.sidebar.number_input("Zone 4 상한", value=168)

# ==========================================
# 메인 로직
# ==========================================
st.title("Garmin Workout Analyst")

if st.button("기록 가져오기", type="primary"):
    if "GARMIN_EMAIL" not in st.secrets:
        st.error("비밀번호 설정(Secrets)을 확인해주세요!")
        st.stop()

    email = st.secrets["GARMIN_EMAIL"]
    password = st.secrets["GARMIN_PASSWORD"]

    status = st.empty()
    status.info("가민 서버 접속 중...")

    try:
        # 로그인
        client = Garmin(email, password)
        client.login()
        
        # 데이터 가져오기
        activities = client.get_activities(0, 1)
        if not activities:
            st.warning("최근 활동이 없습니다.")
            st.stop()
            
        act = activities[0]
        status.success(f"활동 발견: {act['activityName']}")
        
        # 수치 계산
        dist_km = act['distance'] / 1000
        duration_sec = act['duration']
        pace_sec = duration_sec / dist_km if dist_km > 0 else 0
        avg_hr = act.get('averageHR', 0)
        
        # 주간 거리 계산
        act_date = datetime.datetime.strptime(act['startTimeLocal'].split(" ")[0], "%Y-%m-%d").date()
        start_week = act_date - datetime.timedelta(days=act_date.weekday())
        end_week = start_week + datetime.timedelta(days=6)
        recent = client.get_activities_by_date(start_week.isoformat(), end_week.isoformat(), "running")
        weekly_dist = sum([r['distance'] for r in recent]) / 1000

        # -------------------------------------------
        # 그림 그리기 (이모지 절대 금지!)
        # -------------------------------------------
        fig = plt.figure(figsize=(10, 14), facecolor='#121212')
        ax = plt.gca()
        ax.set_facecolor('#121212')
        ax.axis('off')

        # 헤더
        plt.text(0.5, 0.96, act['activityName'], color='white', ha='center', fontsize=22, fontweight='bold')
        plt.text(0.5, 0.93, act['startTimeLocal'][:16], color='#888', ha='center', fontsize=14)

        # 지도
        try:
            gpx_data = client.download_activity(act['activityId'], dl_fmt=client.ActivityDownloadFormat.GPX)
            gpx = gpxpy.parse(gpx_data)
            points = []
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        points.append((point.longitude, point.latitude))
            if points:
                lons, lats = zip(*points)
                map_ax = fig.add_axes([0.1, 0.60, 0.8, 0.30])
                map_ax.set_facecolor('#1e1e1e')
                map_ax.plot(lons, lats, color='#00d2be', linewidth=4)
                map_ax.axis('off')
                map_ax.set_aspect('equal', 'box')
        except:
            plt.text(0.5, 0.75, "NO GPS DATA", color='#555', ha='center')

        # 게이지 함수
        def draw_gauge(y, title, val, sub, ratio, col):
            plt.text(0.1, y+0.04, title, color='#aaa', fontsize=12)
            plt.text(0.9, y+0.04, val, color='white', ha='right', fontsize=22, fontweight='bold')
            ax.add_patch(patches.FancyBboxPatch((0.1, y), 0.8, 0.02, boxstyle="round,pad=0", fc='#333', ec='none'))
            ax.add_patch(patches.FancyBboxPatch((0.1, y), 0.8*min(max(ratio,0.02),1), 0.02, boxstyle="round,pad=0", fc=col, ec='none'))
            plt.text(0.1, y-0.03, sub, color=col, fontsize=11, fontweight='bold')

        # 1. 심박 (이모지 제거됨)
        hr_zone = "Z1"
        hr_col = '#00d2be'
        if avg_hr > z4_limit: hr_zone="Z5"; hr_col='#ff4d4d'
        elif avg_hr > z3_limit: hr_zone="Z4"; hr_col='#ff8c00'
        elif avg_hr > z2_limit: hr_zone="Z3"; hr_col='#ffd700'
        elif avg_hr > 100: hr_zone="Z2"
        draw_gauge(0.45, "HEART RATE", f"{int(avg_hr)}", f"Zone: {hr_zone}", avg_hr/MY_MAX_HR, hr_col)

        # 2. 페이스
        p_ratio = MY_THRESHOLD_PACE / pace_sec
        p_col = '#00d2be' if p_ratio <= 1.0 else '#ff4d4d'
        draw_gauge(0.32, "PACE", f"{int(pace_sec//60)}'{int(pace_sec%60):02d}''", f"Target {int(p_ratio*100)}%", p_ratio*0.8, p_col)

        # 3. 주간 거리
        w_ratio = weekly_dist / MY_WEEKLY_GOAL
        w_col = '#ce82ff' if w_ratio >= 1.0 else '#00d2be'
        w_txt = f"Remain {max(MY_WEEKLY_GOAL-weekly_dist, 0):.1f}km"
        if w_ratio >= 1.0: w_txt = f"GOAL! (+{weekly_dist - MY_WEEKLY_GOAL:.1f}km)"
        draw_gauge(0.19, "WEEKLY DIST", f"{weekly_dist:.1f} km", w_txt, w_ratio, w_col)

        # 하단 박스
        ax.add_patch(patches.FancyBboxPatch((0.1, 0.03), 0.8, 0.08, boxstyle="round,pad=0.02", fc='#222', ec='#333'))
        plt.text(0.2, 0.06, "DIST", color='#888', ha='center', fontsize=10)
        plt.text(0.2, 0.04, f"{dist_km:.2f}", color='white', ha='center', fontsize=16, fontweight='bold')
        plt.text(0.5, 0.06, "TIME", color='#888', ha='center', fontsize=10)
        plt.text(0.5, 0.04, f"{int(duration_sec//3600)}:{int((duration_sec%3600)//60):02d}", color='white', ha='center', fontsize=16, fontweight='bold')
        plt.text(0.8, 0.06, "CAL", color='#888', ha='center', fontsize=10)
        plt.text(0.8, 0.04, f"{int(act.get('calories',0))}", color='white', ha='center', fontsize=16, fontweight='bold')

        st.pyplot(fig)
        status.empty() # 로딩 문구 삭제

    except Exception as e:
        st.error(f"오류가 났어요: {e}")
