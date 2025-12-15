import streamlit as st
from garminconnect import Garmin
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import font_manager, rc
import datetime
import os
import gpxpy
import requests

# ---------------------------------------------------------
# 1. 폰트 설정 (서버에 한글 폰트 설치)
# ---------------------------------------------------------
@st.cache_resource
def set_korean_font():
    # 나눔고딕 폰트 다운로드
    font_url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
    font_name = "NanumGothic-Bold.ttf"
    if not os.path.exists(font_name):
        with open(font_name, "wb") as f:
            f.write(requests.get(font_url).content)
    
    font_manager.fontManager.addfont(font_name)
    rc('font', family=font_manager.FontProperties(fname=font_name).get_name())

set_korean_font()

# ---------------------------------------------------------
# 2. 사이드바 (설정 입력창)
# ---------------------------------------------------------
st.sidebar.header("⚙️ 내 설정")
st.sidebar.info("비밀번호는 코드에 없습니다! 안전해요.")

# 목표 설정 (화살표로 조절 가능)
MY_WEEKLY_GOAL = st.sidebar.number_input("이번주 목표 거리 (km)", value=100.0, step=5.0)
MY_THRESHOLD_PACE = st.sidebar.number_input("내 역치 페이스 (초)", value=270, help="4분27초=270, 5분=300")
MY_MAX_HR = st.sidebar.number_input("최대 심박수", value=178)

st.sidebar.markdown("---")
st.sidebar.subheader("심박존 설정 (상한선)")
z2_limit = st.sidebar.number_input("Zone 2 (Easy) 끝", value=123)
z3_limit = st.sidebar.number_input("Zone 3 (Aerobic) 끝", value=142)
z4_limit = st.sidebar.number_input("Zone 4 (Threshold) 끝", value=158)

# ---------------------------------------------------------
# 3. 메인 화면 로직
# ---------------------------------------------------------
st.title("🏃‍♂️ 나만의 러닝 분석기")
st.markdown("핸드폰에서 **[기록 가져오기]** 버튼만 누르세요!")

if st.button("🔄 최신 가민 기록 가져오기", type="primary"):
    # 비밀번호 가져오기 (보안)
    try:
        email = st.secrets["GARMIN_EMAIL"]
        password = st.secrets["GARMIN_PASSWORD"]
    except:
        st.error("설정(Secrets)에 이메일과 비밀번호가 없습니다!")
        st.stop()

    status_text = st.empty() # 진행상황 표시용
    status_text.text("⏳ 가민 서버에 접속 중...")

    try:
        # 가민 로그인
        client = Garmin(email, password)
        client.login()
        
        status_text.text("✅ 로그인 성공! 데이터 찾는 중...")

        # 최신 활동 1개 가져오기
        activities = client.get_activities(0, 1)
        if not activities:
            st.error("최근 기록된 운동이 없습니다.")
            st.stop()
        
        act = activities[0]
        status_text.text(f"🏃 활동 발견: {act['activityName']}")

        # -----------------------------------------------------
        # 데이터 가공 (주간 거리 등)
        # -----------------------------------------------------
        # 주간 거리 계산 (월요일~일요일)
        act_time = datetime.datetime.strptime(act['startTimeLocal'], "%Y-%m-%d %H:%M:%S")
        act_date = act_time.date()
        start_of_week = act_date - datetime.timedelta(days=act_date.weekday()) # 월요일
        end_of_week = start_of_week + datetime.timedelta(days=6) # 일요일
        
        # 넉넉히 데이터 가져와서 필터링
        recent_acts = client.get_activities_by_date(start_of_week.isoformat(), end_of_week.isoformat(), "running")
        
        weekly_dist = 0.0
        for r in recent_acts:
            r_date_str = r['startTimeLocal'].split(" ")[0]
            r_date = datetime.datetime.strptime(r_date_str, "%Y-%m-%d").date()
            if start_of_week <= r_date <= end_of_week:
                weekly_dist += r['distance']
        
        weekly_dist_km = weekly_dist / 1000

        # 기본 수치들
        dist_km = act['distance'] / 1000
        duration_sec = act['duration']
        pace_sec = duration_sec / dist_km if dist_km > 0 else 0
        avg_hr = act.get('averageHR', 0)
        
        # -----------------------------------------------------
        # 인포그래픽 그리기 (Matplotlib)
        # -----------------------------------------------------
        status_text.text("🎨 인포그래픽 그리는 중...")
        
        fig = plt.figure(figsize=(10, 14), facecolor='#121212')
        ax = plt.gca()
        ax.set_facecolor('#121212')
        ax.axis('off')

        # [헤더]
        plt.text(0.5, 0.96, act['activityName'], color='white', ha='center', fontsize=22, fontweight='bold')
        plt.text(0.5, 0.93, act_time.strftime("%Y.%m.%d %H:%M"), color='#888', ha='center', fontsize=14)

        # [지도]
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
                map_ax.plot(lons[0], lats[0], 'wo', markersize=8) # 시작점
                map_ax.plot(lons[-1], lats[-1], 's', color='#ff4d4d', markersize=8) # 끝점
        except:
            plt.text(0.5, 0.75, "GPS 데이터 없음", color='#555', ha='center')

        # [게이지 그리기 함수]
        def draw_gauge(y, title, val, sub, ratio, col):
            plt.text(0.1, y+0.04, title, color='#aaa', fontsize=12)
            plt.text(0.9, y+0.04, val, color='white', ha='right', fontsize=22, fontweight='bold')
            ax.add_patch(patches.FancyBboxPatch((0.1, y), 0.8, 0.02, boxstyle="round,pad=0", fc='#333', ec='none'))
            ax.add_patch(patches.FancyBboxPatch((0.1, y), 0.8*min(max(ratio,0.02),1), 0.02, boxstyle="round,pad=0", fc=col, ec='none'))
            plt.text(0.1, y-0.03, sub, color=col, fontsize=11, fontweight='bold')

        # 1. 심박수
        hr_zone = "Z1 (Recovery)"
        hr_col = '#00d2be'
        if avg_hr > z4_limit: hr_zone="Z5 (VO2 Max)"; hr_col='#ff4d4d'
        elif avg_hr > z3_limit: hr_zone="Z4 (Threshold)"; hr_col='#ff8c00'
        elif avg_hr > z2_limit: hr_zone="Z3 (Tempo)"; hr_col='#ffd700'
        elif avg_hr > 100: hr_zone="Z2 (Base)"
        
        draw_gauge(0.45, "HEART RATE", f"{int(avg_hr)} bpm", f"Zone: {hr_zone}", avg_hr/MY_MAX_HR, hr_col)
        
        # 2. 페이스
        p_ratio = MY_THRESHOLD_PACE / pace_sec
        p_col = '#00d2be' 
        p_txt = "Easy Run"
        if p_ratio > 1.05: p_col='#ff4d4d'; p_txt="Interval"
        elif p_ratio >= 0.98: p_col='#ff8c00'; p_txt="Threshold"
        elif p_ratio > 0.85: p_col='#ffd700'; p_txt="Tempo"
        
        draw_gauge(0.32, "PACE", f"{int(pace_sec//60)}'{int(pace_sec%60):02d}''", f"{p_txt} (Target {int(p_ratio*100)}%)", p_ratio*0.8, p_col)
        
        # 3. 주간 거리
        w_ratio = weekly_dist_km / MY_WEEKLY_GOAL
        w_col = '#00d2be' if w_ratio < 1.0 else '#ce82ff'
        w_txt = f"남은 거리 {max(MY_WEEKLY_GOAL-weekly_dist_km, 0):.1f}km"
        if w_ratio >= 1.0: w_txt = f"🎉 목표 달성! (+{weekly_dist_km - MY_WEEKLY_GOAL:.1f}km)"
        
        draw_gauge(0.19, "WEEKLY DIST", f"{weekly_dist_km:.1f} km", w_txt, w_ratio, w_col)
        
        # [하단 요약 박스]
        ax.add_patch(patches.FancyBboxPatch((0.1, 0.03), 0.8, 0.08, boxstyle="round,pad=0.02", fc='#222', ec='#333'))
        plt.text(0.2, 0.045, f"{dist_km:.2f}", color='white', ha='center', fontsize=18, fontweight='bold')
        plt.text(0.5, 0.045, f"{int(duration_sec//3600)}:{int((duration_sec%3600)//60):02d}", color='white', ha='center', fontsize=18, fontweight='bold')
        plt.text(0.8, 0.045, f"{int(act.get('calories',0))}", color='white', ha='center', fontsize=18, fontweight='bold')
        plt.text(0.2, 0.08, "DIST", color='#888', ha='center', fontsize=10)
        plt.text(0.5, 0.08, "TIME", color='#888', ha='center', fontsize=10)
        plt.text(0.8, 0.08, "CAL", color='#888', ha='center', fontsize=10)

        # 화면에 출력
        st.pyplot(fig)
        status_text.empty() # 진행중 텍스트 지우기
        st.success("분석 완료! 이미지를 꾹 눌러 저장하세요.")
        
    except Exception as e:
        st.error(f"오류가 났어요: {e}")