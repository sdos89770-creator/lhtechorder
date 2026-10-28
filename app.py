from datetime import datetime
import os
import pandas as pd
import streamlit as st

# 초기 기본 명단
DEFAULT_WORKERS = ["김철수", "이영희", "박민수", "정지영", "오민석", "김도현"]

# 선택 가능한 식사 메뉴 리스트 (원하시는 만큼 추가하거나 빼셔도 됩니다!)
AVAILABLE_MENUS = [
    "짜장면",
    "간짜장",
    "짬뽕",
    "짬뽕밥",
    "볶음밥",
    "새우볶음밥",
    "잡채밥",
    "우동",
    "짬뽕+공기밥",
    "기타(직접입력)",
]

# 관리자 비밀번호 설정
ADMIN_PASSWORD = "0007"


def get_data_file_path(date_obj):
    """선택된 날짜에 해당하는 개별 CSV 파일 이름을 반환합니다."""
    date_str = date_obj.strftime("%Y-%m-%d")
    return f"orders_{date_str}.csv"


def load_data(date_obj):
    data_file = get_data_file_path(date_obj)
    
    data_key = f"df_data_{date_obj.strftime('%Y-%m-%d')}"
    if data_key in st.session_state:
        return st.session_state[data_key]

    if os.path.exists(data_file):
        try:
            df = pd.read_csv(data_file, encoding="utf-8-sig")
            if "메뉴 선택" not in df.columns or "이름" not in df.columns:
                os.remove(data_file)
                return load_data(date_obj)
            df["이름"] = df["이름"].astype(str)
            df["메뉴 선택"] = df["메뉴 선택"].fillna("").astype(str)
            st.session_state[data_key] = df
            return df
        except Exception:
            os.remove(data_file)
            return load_data(date_obj)
    else:
        initial_data = {
            "이름": DEFAULT_WORKERS,
            "메뉴 선택": [""] * len(DEFAULT_WORKERS),
        }
        df = pd.DataFrame(initial_data)
        df["이름"] = df["이름"].astype(str)
        df["메뉴 선택"] = df["메뉴 선택"].astype(str)
        df.to_csv(data_file, index=False, encoding="utf-8-sig")
        st.session_state[data_key] = df
        return df


st.set_page_config(page_title="잔업 식사 주문 시스템", page_icon="🍱", layout="centered")

st.title("🍱 이화테크원 잔업근무 식사 주문")
st.write("날짜를 선택하고 본인 이름과 메뉴, 곱배기 여부를 선택해 주세요!")

# --- 날짜 선택 및 요일 설정 ---
days_of_week = ["월", "화", "수", "목", "금", "토", "일"]
selected_date = st.date_input("📅 주문 날짜 선택", value=datetime.now())

weekday_str = days_of_week[selected_date.weekday()]
formatted_date_str = (
    f"{selected_date.year}년 {selected_date.month}월 {selected_date.day}일"
    f" ({weekday_str})"
)

st.info(f"📌 현재 선택된 주문 일자: **{formatted_date_str}**")

# 선택된 날짜에 해당하는 데이터 불러오기
data_key = f"df_data_{selected_date.strftime('%Y-%m-%d')}"
df = load_data(selected_date)
current_data_file = get_data_file_path(selected_date)

# 사이드바: 관리자 모드 설정
st.sidebar.header("⚙️ 관리자 설정")
admin_mode = st.sidebar.checkbox("관리자 모드 켜기")

is_authenticated = False

if admin_mode:
    password_input = st.sidebar.text_input("관리자 비밀번호를 입력하세요", type="password")
    
    if password_input == ADMIN_PASSWORD:
        is_authenticated = True
        st.sidebar.success("관리자 인증 성공!")
    elif password_input != "":
        st.sidebar.error("비밀번호가 틀렸습니다.")

if admin_mode and is_authenticated:
    st.sidebar.subheader(
        f"👥 [{selected_date.strftime('%m/%d')}] 근무자 명단 관리"
    )
    st.sidebar.write("선택한 날짜의 잔업 근무자 명단을 수정할 수 있습니다.")

    current_names = "\n".join(df["이름"].tolist())
    
    admin_text_key = f"admin_names_{selected_date}"
    if admin_text_key not in st.session_state:
        st.session_state[admin_text_key] = current_names

    edited_names_text = st.sidebar.text_area(
        "이름을 줄바꿈으로 입력하세요", 
        key=admin_text_key, 
        height=150
    )

    if st.sidebar.button("해당 날짜 명단 업데이트"):
        new_names = [n.strip() for n in edited_names_text.split("\n") if n.strip()]
        if new_names:
            old_dict = dict(zip(df["이름"], df["메뉴 선택"]))
            new_data = []
            for name in new_names:
                menu = old_dict.get(name, "")
                new_data.append(
                    {
                        "이름": str(name),
                        "메뉴 선택": str(menu) if pd.notna(menu) else "",
                    }
                )

            df = pd.DataFrame(new_data)
            df["이름"] = df["이름"].astype(str)
            df["메뉴 선택"] = df["메뉴 선택"].astype(str)
            
            st.session_state[data_key] = df
            df.to_csv(current_data_file, index=False, encoding="utf-8-sig")
            
            st.sidebar.success(
                f"[{formatted_date_str}] 명단이 업데이트되었습니다!"
            )
            st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 해당 날짜 주문 초기화 (메뉴 리셋)"):
        df["메뉴 선택"] = ""
        st.session_state[data_key] = df
        df.to_csv(current_data_file, index=False, encoding="utf-8-sig")
        st.sidebar.success(f"[{formatted_date_str}] 메뉴 데이터가 초기화되었습니다.")
        st.rerun()


# 1. 작업자 주문 입력(선택) 섹션
st.subheader("✍️ 내 메뉴 선택하기")
worker_names = df["is_worker" if "is_worker" in df.columns else "이름"].tolist() if "이름" in df.columns else []

if not worker_names:
    st.warning(
        "등록된 작업자가 없습니다. 왼쪽 사이드바 '관리자 모드'에서 명단을"
        " 추가해주세요."
    )
else:
    selected_name = st.selectbox("본인의 이름을 선택하세요", worker_names, key=f"selected_worker_{selected_date}")

    # 현재 선택된 사용자의 기존 메뉴 가져오기
    current_row = df.loc[df["이름"] == selected_name]
    current_menu_raw = (
        str(current_row["메뉴 선택"].values[0]) if not current_row.empty else ""
    )
    if current_menu_raw == "nan" or pd.isna(current_menu_raw):
        current_menu_raw = ""

    # 기존 저장된 데이터에서 메뉴 이름과 곱배기 여부 분리하기
    # 예: "짜장면 (곱배기)" -> 메뉴: "짜장면", 곱배기: True
    is_gopbaegi_default = "(곱배기)" in current_menu_raw
    pure_menu = current_menu_raw.replace(" (곱배기)", "").strip()

    # 기본 메뉴 인덱스 찾기
    default_index = 0
    if pure_menu in AVAILABLE_MENUS:
        default_index = AVAILABLE_MENUS.index(pure_menu)
    elif pure_menu != "":
        if "기타(직접입력)" in AVAILABLE_MENUS:
            default_index = AVAILABLE_MENUS.index("기타(직접입력)")

    # 화면 배치: 메뉴 선택과 곱배기 체크박스를 나란히 배치
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_menu_option = st.selectbox(
            "드실 메뉴를 선택하세요",
            options=AVAILABLE_MENUS,
            index=default_index,
            key=f"menu_select_{selected_date}_{selected_name}"
        )
        
    with col2:
        st.write("") # 간격 맞추기용
        st.write("")
        is_gopbaegi = st.checkbox("곱배기 (+)", value=is_gopbaegi_default, key=f"gopbaegi_check_{selected_date}_{selected_name}")

    # 기타 직접 입력 처리
    final_menu_name = selected_menu_option
    if selected_menu_option == "기타(직접입력)":
        custom_input = st.text_input("직접 메뉴를 입력해주세요", value="" if pure_menu in AVAILABLE_MENUS else pure_menu, key=f"custom_menu_{selected_date}_{selected_name}")
        final_menu_name = custom_input

    # 최종 저장될 문자열 조합 (곱배기가 체크되어 있으면 " (곱배기)" 붙이기)
    if final_menu_name and final_menu_name.strip() != "":
        if is_gopbaegi:
            final_menu_to_save = f"{final_menu_name} (곱배기)"
        else:
            final_menu_to_save = final_menu_name
    else:
        final_menu_to_save = ""

    if st.button("내 주문 저장하기"):
        df.loc[df["이름"] == selected_name, "메뉴 선택"] = str(final_menu_to_save)
        st.session_state[data_key] = df
        df.to_csv(current_data_file, index=False, encoding="utf-8-sig")
        st.success(
            f"[{formatted_date_str}] [{selected_name}]님의 메뉴([{final_menu_to_save}])가 저장되었습니다!"
        )
        st.rerun()

# 2. 전체 현황 및 카카오톡 공유 섹션
st.markdown("---")
st.subheader(f"📊 {formatted_date_str} 잔업 식사 현황 전체보기")

if os.path.exists(current_data_file):
    current_df = pd.read_csv(current_data_file, encoding="utf-8-sig")
else:
    current_df = df

st.dataframe(current_df, use_container_width=True)

st.markdown("---")
st.subheader("💬 카카오톡 단체방 공유용 텍스트")
st.write(
    "아래 박스의 복사 버튼을 눌러 카카오톡 단체방에 그대로 붙여넣으세요."
)

valid_orders = []
for idx, row in current_df.iterrows():
    menu = str(row["메뉴 선택"])
    if menu and menu != "nan" and menu.strip() != "":
        valid_orders.append((row["이름"], menu.strip()))

# 메뉴별 개수 카운팅 집계 (곱배기 포함된 이름 그대로 집계됨)
menu_counts = {}
for name, menu in valid_orders:
    menu_counts[menu] = menu_counts.get(menu, 0) + 1

kakao_text = f"[ {formatted_date_str} 잔업 식사 주문 현황 ]\n\n[개인별 주문]\n"

if len(valid_orders) == 0:
    kakao_text += "아직 메뉴를 입력한 인원이 없습니다."
else:
    for name, menu in valid_orders:
        kakao_text += f"• {name}: {menu}\n"

    kakao_text += f"\n[메뉴별 총 수량]\n"
    for menu_name, count in menu_counts.items():
        kakao_text += f"• {menu_name}: {count}개\n"

    kakao_text += f"\n총 주문인원: {len(valid_orders)}명"

st.code(kakao_text, language="text")
