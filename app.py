import streamlit as st
import matplotlib
matplotlib.use('Agg') # 화면 충돌 방지
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from garminconnect import Garmin
import datetime
import gpxpy

# --------------------------------------------------------
# 1. 사이드바 설정 (영어)
# --------------------------------------------------------
st.sidebar.header("Settings")
MY_WEEKLY_GOAL = st.sidebar.number_input("Weekly Goal (km)", value=100.0, step=5.0)
MY_THRESHOLD_PACE = st.sidebar.number_input("Threshold Pace (sec)", value=270, help="4:30 = 270")
MY_MAX_HR = st.sidebar.number_input("Max Heart Rate", value=185)

st.sidebar.markdown("---")
z2_limit = st.sidebar.number_input("Zone 2 Limit", value=125)
z3_limit = st.sidebar.number_input("Zone 3 Limit", value=148)
z4_limit = st.sidebar.number_input("Zone 4 Limit", value=168)

# --------------------------------------------------------
# 2. 메인 로직
# --------------------------------------------------------
st.title("🏃‍♂️ Garmin Dashboard")

if st.button("🔄 Load Latest Activity", type="primary"):
    # 비밀번호 확인
    if "GARMIN_EMAIL" not in st.secrets:
        st.error("Please set Secrets (GARMIN_EMAIL, GARMIN_PASSWORD)!")
        st.stop()

    email = st.secrets["GARMIN_EMAIL"]
    password = st.secrets["GARMIN_PASSWORD"]

    status = st.empty()
    status.info("Connecting to Garmin...")

    try:
        # 로그인
        client = Garmin(email, password)
        client.login()
        
        # 활동 가져오기
        activities = client.get_activities(0, 1)
        if not activities:
            st.warning("No recent activities found.")
            st.stop()
            
        act = activities[0]
        status.success(f"Activity Found: {act['activityName']}")
        
        # 데이터 계산
        dist_km = act['distance'] / 1000
        duration_sec = act['duration']
        pace_sec = duration_sec / dist_km if dist_km > 0 else 0
        avg_hr = act.get('averageHR', 0)
        
        # 주간 거리 계산 (안전 장치)
        try:
            act_date = datetime.datetime.strptime(act['startTimeLocal'].split(" ")[0], "%Y-%m-%d").date()
            start_week = act_date - datetime.timedelta(days=act_date.weekday())
            end_week = start_week + datetime.timedelta(days=6)
            recent = client.get_activities_by_date(start_week.isoformat(), end_week.isoformat(), "running")
            weekly_dist = sum([r['distance'] for r in recent]) / 1000
        except:
            weekly_dist = 0.0

        # -------------------------------------------
        # 그림 그리기 (기본 폰트 사용)
        # -------------------------------------------
        fig = plt.figure(figsize=(10, 14), facecolor='#121212')
        ax = plt.gca()
        ax.set_facecolor('#121212')
        ax.axis('off')

        # 제목
        plt.text(0.5, 0.96, act['activityName'], color='white', ha='center', fontsize=20, fontweight='bold')
        plt.text(0.5, 0.93, act['startTimeLocal'][:16], color='#888', ha='center', fontsize=14)

        # 지도 (없으면 건너뜀)
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
            plt.text(0.5, 0.75, "No Map Data", color='#555', ha='center')

        # 게이지 그리기 함수
        def draw_gauge(y, title, val, sub, ratio, col):
            plt.text(0.1, y+0.04, title, color='#aaa', fontsize=12)
            plt.text(0.9, y+0.04, val, color='white', ha='right', fontsize=22, fontweight='bold')
            rect_bg = plt.Rectangle((0.1, y), 0.8, 0.02, facecolor='#333', edgecolor='none', transform=ax.transData)
            rect_val = plt.Rectangle((0.1, y), 0.8*min(max(ratio,0.02),1), 0.02, facecolor=col, edgecolor='none', transform=ax.transData)
            ax.add_patch(rect_bg)
            ax.add_patch(rect_val)
            plt.text(0.1, y-0.03, sub, color=col, fontsize=11, fontweight='bold')

        # 1. 심박수
        hr_zone = "Z1"
        hr_col = '#00d2be'
        if avg_hr > z4_limit: hr_zone="Z5"; hr_col='#ff4d4d'
        elif avg_hr > z3_limit: hr_zone="Z4"; hr_col='#ff8c00'
        elif avg_hr > z2_limit: hr_zone="Z3"; hr_col='#ffd700'
        elif avg_hr > 100: hr_zone="Z2"
        draw_gauge(0.45, "Heart Rate", f"{int(avg_hr)}", f"Zone: {hr_zone}", avg_hr/MY_MAX_HR, hr_col)

        # 2. 페이스
        p_ratio = MY_THRESHOLD_PACE / pace_sec
        p_col = '#00d2be' if p_ratio <= 1.0 else '#ff4d4d'
        draw_gauge(0.32, "Pace", f"{int(pace_sec//60)}'{int(pace_sec%60):02d}''", f"Target {int(p_ratio*100)}%", p_ratio*0.8, p_col)

        # 3. 주간 거리
        w_ratio = weekly_dist / MY_WEEKLY_GOAL
        w_col = '#ce82ff' if w_ratio >= 1.0 else '#00d2be'
        w_txt = f"Left: {max(MY_WEEKLY_GOAL-weekly_dist, 0):.1f}km"
        if w_ratio >= 1.0: w_txt = f"Goal Reached! (+{weekly_dist - MY_WEEKLY_GOAL:.1f}km)"
        draw_gauge(0.19, "Weekly Dist", f"{weekly_dist:.1f} km", w_txt, w_ratio, w_col)

        # 하단 정보
        box_bg = plt.Rectangle((0.1, 0.03), 0.8, 0.08, facecolor='#222', edgecolor='#333', transform=ax.transData)
        ax.add_patch(box_bg)
        
        plt.text(0.2, 0.06, "DIST", color='#888', ha='center', fontsize=10)
        plt.text(0.2, 0.04, f"{dist_km:.2f}", color='white', ha='center', fontsize=16, fontweight='bold')
        
        plt.text(0.5, 0.06, "TIME", color='#888', ha='center', fontsize=10)
        plt.text(0.5, 0.04, f"{int(duration_sec//3600)}:{int((duration_sec%3600)//60):02d}", color='white', ha='center', fontsize=16, fontweight='bold')
        
        plt.text(0.8, 0.06, "CAL", color='#888', ha='center', fontsize=10)
        plt.text(0.8, 0.04, f"{int(act.get('calories',0))}", color='white', ha='center', fontsize=16, fontweight='bold')

        st.pyplot(fig)
        status.empty()

    except Exception as e:
        st.error(f"Error: {e}")
