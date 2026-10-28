
from datetime import date, datetime
import os

import pandas as pd
import streamlit as st
from supabase import create_client


# =========================================================
# 1. 기본 설정
# =========================================================

st.set_page_config(
    page_title="잔업 식사 주문 시스템",
    page_icon="🍱",
    layout="centered",
)

DEFAULT_WORKERS = [
    "김철수", "이영희", "박민수",
    "정지영", "오민석", "김도현",
]

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

# 비밀번호와 DB 키는 Streamlit Secrets에서 읽습니다.
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]


# =========================================================
# 2. 데이터베이스 연결
# =========================================================

@st.cache_resource
def get_supabase():
    """Supabase 연결 객체를 생성하고 재사용합니다."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


db = get_supabase()


# =========================================================
# 3. 공통 데이터 처리 함수
# =========================================================

def get_active_workers():
    """현재 근무 중인 직원 명단을 가져옵니다."""
    response = (
        db.table("workers")
        .select("name")
        .eq("active", True)
        .order("name")
        .execute()
    )

    names = [row["name"] for row in response.data]

    # 최초 실행 시 기본 명단을 등록합니다.
    if not names:
        db.table("workers").upsert(
            [{"name": name, "active": True}
             for name in DEFAULT_WORKERS],
            on_conflict="name",
        ).execute()

        response = (
            db.table("workers")
            .select("name")
            .eq("active", True)
            .order("name")
            .execute()
        )
        names = [row["name"] for row in response.data]

    return names


def get_orders(order_date):
    """선택한 날짜의 주문을 직원 이름별로 가져옵니다."""
    response = (
        db.table("orders")
        .select("worker_name, menu")
        .eq("order_date", order_date.isoformat())
        .execute()
    )

    return {
        row["worker_name"]: row["menu"]
        for row in response.data
    }


def save_order(order_date, worker_name, menu):
    """
    날짜와 직원 이름이 같은 주문은 갱신합니다.
    DB의 복합 기본 키가 중복 행 생성을 방지합니다.
    """
    db.table("orders").upsert(
        {
            "order_date": order_date.isoformat(),
            "worker_name": worker_name,
            "menu": menu,
            "updated_at": datetime.now().astimezone().isoformat(),
        },
        on_conflict="order_date,worker_name",
    ).execute()


def reset_orders(order_date):
    """선택한 날짜의 주문만 초기화합니다."""
    db.table("orders").delete().eq(
        "order_date", order_date.isoformat()
    ).execute()


def update_workers(new_names):
    """
    현재 근무자 명단을 갱신합니다.
    비활성화한 직원의 과거 주문은 삭제하지 않습니다.
    """
    current_response = (
        db.table("workers")
        .select("name")
        .eq("active", True)
        .execute()
    )

    current_names = {
        row["name"] for row in current_response.data
    }
    new_name_set = set(new_names)

    removed_names = current_names - new_name_set
    added_names = new_name_set

    # 기존 직원은 비활성화합니다.
    # 과거 주문 기록은 유지합니다.
    if removed_names:
        for name in removed_names:
            db.table("workers").update(
                {"active": False}
            ).eq("name", name).execute()

    # 신규 직원 또는 기존 직원은 활성화합니다.
    if added_names:
        db.table("workers").upsert(
            [
                {"name": name, "active": True}
                for name in added_names
            ],
            on_conflict="name",
        ).execute()


def make_current_dataframe(workers, orders):
    """근무자 명단과 주문을 결합해 화면용 표를 만듭니다."""
    return pd.DataFrame(
        [
            {
                "이름": name,
                "메뉴 선택": orders.get(name, "") or "",
            }
            for name in workers
        ],
        columns=["이름", "메뉴 선택"],
    )


# =========================================================
# 4. 날짜 선택
# =========================================================

st.title("🍱 이화테크원 잔업근무 식사 주문")
st.write("날짜를 선택하고 본인 이름과 메뉴, 곱배기 여부를 선택해 주세요!")

selected_date = st.date_input(
    "📅 주문 날짜 선택",
    value=date.today(),
)

days_of_week = ["월", "화", "수", "목", "금", "토", "일"]

formatted_date_str = (
    f"{selected_date.year}년 "
    f"{selected_date.month}월 "
    f"{selected_date.day}일 "
    f"({days_of_week[selected_date.weekday()]})"
)

st.info(f"📌 현재 선택된 주문 일자: **{formatted_date_str}**")


# =========================================================
# 5. 데이터 불러오기
# =========================================================

try:
    worker_names = get_active_workers()
    order_map = get_orders(selected_date)
except Exception as e:
    st.error(
        "데이터베이스에서 정보를 불러오지 못했습니다. "
        "Supabase 연결과 테이블 설정을 확인해 주세요."
    )
    st.exception(e)
    st.stop()

df = make_current_dataframe(worker_names, order_map)


# =========================================================
# 6. 관리자 모드
# =========================================================

st.sidebar.header("⚙️ 관리자 설정")

admin_mode = st.sidebar.checkbox("관리자 모드 켜기")

is_authenticated = False

if admin_mode:
    password_input = st.sidebar.text_input(
        "관리자 비밀번호를 입력하세요",
        type="password",
        key="admin_password_input",
    )

    is_authenticated = (
        bool(password_input)
        and password_input == ADMIN_PASSWORD
    )

    if is_authenticated:
        st.sidebar.success("관리자 인증 성공!")
    elif password_input:
        st.sidebar.error("비밀번호가 틀렸습니다.")

if admin_mode and is_authenticated:
    st.sidebar.subheader(
        f"👥 [{selected_date.strftime('%m/%d')}] 근무자 명단 관리"
    )
    st.sidebar.write(
        "선택한 날짜에 적용할 근무자 명단을 수정합니다."
    )

    admin_text_key = f"admin_names_{selected_date.isoformat()}"

    if admin_text_key not in st.session_state:
        st.session_state[admin_text_key] = "\n".join(worker_names)

    edited_names_text = st.sidebar.text_area(
        "이름을 줄바꿈으로 입력하세요",
        key=admin_text_key,
        height=150,
    )

    if st.sidebar.button("해당 날짜 명단 업데이트"):
        new_names = list(dict.fromkeys(
            name.strip()
            for name in edited_names_text.splitlines()
            if name.strip()
        ))

        if not new_names:
            st.sidebar.error("근무자 이름을 한 명 이상 입력해 주세요.")

        else:
            try:
                update_workers(new_names)

                st.session_state[admin_text_key] = "\n".join(
                    new_names
                )

                st.sidebar.success("근무자 명단이 업데이트되었습니다.")
                st.rerun()

            except Exception as e:
                st.sidebar.error("명단 업데이트에 실패했습니다.")
                st.sidebar.exception(e)

    st.sidebar.markdown("---")

    if st.sidebar.button("🔄 해당 날짜 주문 초기화"):
        try:
            reset_orders(selected_date)
            st.sidebar.success("선택한 날짜의 주문을 초기화했습니다.")
            st.rerun()

        except Exception as e:
            st.sidebar.error("주문 초기화에 실패했습니다.")
            st.sidebar.exception(e)


# =========================================================
# 7. 직원 주문 입력
# =========================================================

st.subheader("✍️ 내 메뉴 선택하기")

# 관리자가 명단을 바꾼 직후에도 최신 명단을 사용합니다.
try:
    worker_names = get_active_workers()
    order_map = get_orders(selected_date)
    df = make_current_dataframe(worker_names, order_map)
except Exception as e:
    st.error("최신 주문 정보를 불러오지 못했습니다.")
    st.exception(e)
    st.stop()

if not worker_names:
    st.warning("등록된 근무자가 없습니다.")

else:
    selected_name = st.selectbox(
        "본인의 이름을 선택하세요",
        worker_names,
        key=f"selected_worker_{selected_date.isoformat()}",
    )

    current_menu_raw = order_map.get(selected_name, "") or ""

    is_gopbaegi_default = "(곱배기)" in current_menu_raw
    pure_menu = current_menu_raw.replace(
        " (곱배기)", ""
    ).strip()

    if pure_menu in AVAILABLE_MENUS:
        default_index = AVAILABLE_MENUS.index(pure_menu)
    elif pure_menu:
        default_index = AVAILABLE_MENUS.index("기타(직접입력)")
    else:
        default_index = 0

    col1, col2 = st.columns([3, 1])

    with col1:
        selected_menu_option = st.selectbox(
            "드실 메뉴를 선택하세요",
            options=AVAILABLE_MENUS,
            index=default_index,
            key=f"menu_select_{selected_date}_{selected_name}",
        )

    with col2:
        st.write("")
        st.write("")
        is_gopbaegi = st.checkbox(
            "곱배기 (+)",
            value=is_gopbaegi_default,
            key=f"gopbaegi_check_{selected_date}_{selected_name}",
        )

    final_menu_name = selected_menu_option

    if selected_menu_option == "기타(직접입력)":
        custom_default = (
            pure_menu if pure_menu not in AVAILABLE_MENUS else ""
        )

        final_menu_name = st.text_input(
            "직접 메뉴를 입력해주세요",
            value=custom_default,
            key=f"custom_menu_{selected_date}_{selected_name}",
        )

    if final_menu_name and final_menu_name.strip():
        final_menu_to_save = final_menu_name.strip()

        if is_gopbaegi:
            final_menu_to_save += " (곱배기)"
    else:
        final_menu_to_save = ""

    if st.button("내 주문 저장하기", type="primary"):
        try:
            # 화면에서 전달된 이름이 현재 근무자 명단에
            # 포함되어 있는지 다시 확인합니다.
            latest_workers = get_active_workers()

            if selected_name not in latest_workers:
                st.error("현재 근무자 명단에 없는 이름입니다.")
                st.stop()

            # Supabase의 복합 기본 키를 이용해 주문을 갱신합니다.
            save_order(
                selected_date,
                selected_name,
                final_menu_to_save,
            )

            st.success(
                f"[{formatted_date_str}] "
                f"[{selected_name}]님의 주문을 저장했습니다."
            )
            st.rerun()

        except Exception as e:
            st.error("주문 저장에 실패했습니다. 다시 시도해 주세요.")
            st.exception(e)


# =========================================================
# 8. 전체 주문 현황
# =========================================================

st.markdown("---")
st.subheader(f"📊 {formatted_date_str} 잔업 식사 현황 전체보기")

try:
    worker_names = get_active_workers()
    order_map = get_orders(selected_date)
    current_df = make_current_dataframe(worker_names, order_map)

    st.dataframe(
        current_df,
        use_container_width=True,
        hide_index=True,
    )

except Exception as e:
    st.error("전체 주문 현황을 불러오지 못했습니다.")
    st.exception(e)
    st.stop()


# =========================================================
# 9. 카카오톡 공유 텍스트
# =========================================================

st.markdown("---")
st.subheader("💬 카카오톡 단체방 공유용 텍스트")
st.write(
    "아래 텍스트를 복사해 카카오톡 단체방에 붙여넣으세요."
)

valid_orders = []

for _, row in current_df.iterrows():
    name = str(row["이름"])
    menu = str(row["메뉴 선택"]).strip()

    if menu and menu.lower() != "nan":
        valid_orders.append((name, menu))

menu_counts = {}

for name, menu in valid_orders:
    menu_counts[menu] = menu_counts.get(menu, 0) + 1

kakao_text = (
    f"[ {formatted_date_str} 잔업 식사 주문 현황 ]\n\n"
    "[개인별 주문]\n"
)

if not valid_orders:
    kakao_text += "아직 메뉴를 입력한 인원이 없습니다."

else:
    for name, menu in valid_orders:
        kakao_text += f"• {name}: {menu}\n"

    kakao_text += "\n[메뉴별 총 수량]\n"

    for menu_name, count in menu_counts.items():
        kakao_text += f"• {menu_name}: {count}개\n"

    kakao_text += f"\n총 주문인원: {len(valid_orders)}명"

st.code(kakao_text, language="text")
