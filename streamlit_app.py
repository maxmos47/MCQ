import json
import requests
import pandas as pd
import streamlit as st
import math

st.set_page_config(page_title="MCQ Answer Sheet", page_icon="📝", layout="centered")

# ===============
# SETTINGS (via secrets.toml)
# ===============
GAS_WEBAPP_URL = st.secrets.get("gas", {}).get("webapp_url", "").strip()
TEACHER_KEY = st.secrets.get("app", {}).get("teacher_key", "").strip()

if not GAS_WEBAPP_URL:
    st.warning("⚠️ Please set [gas] webapp_url in .streamlit/secrets.toml")
    
# Helper: call GAS
def gas_get(action: str):
    url = f"{GAS_WEBAPP_URL}?action={action}"
    r = requests.get(url, timeout=30)
    return r.json()

def gas_post(action: str, payload: dict):
    url = f"{GAS_WEBAPP_URL}?action={action}"
    r = requests.post(url, json=payload, timeout=30)
    return r.json()

# 🔧 robust query-param handling
raw_mode = st.query_params.get("mode", "exam")
# Streamlit >=1.30 returns str, older versions may return list; handle both
if isinstance(raw_mode, list) and raw_mode:
    raw_mode = raw_mode[0]
mode = str(raw_mode).strip().lower()

# Common: fetch config
def fetch_config():
    try:
        js = gas_get("get_config")
        if js.get("ok"):
            return js["data"]
        else:
            st.error(f"Config error: {js.get('error')}")
    except Exception as e:
        st.error(f"Failed to get config: {e}")
    return None

# ----------------------
# STUDENT EXAM PAGE
# ----------------------
def page_exam():
    st.markdown("### 📝 กระดาษคำตอบ MCQ (มือถือ)")
    cfg = fetch_config()
    if not cfg:
        return
    qn = int(cfg.get("question_count", 0))
    correct = cfg.get("correct_answers", [])
    if qn <= 0 or not correct or len(correct) != qn:
        st.error("การตั้งค่าใน Google Sheet ยังไม่ถูกต้อง (Question_Count / Correct_Answers)")
        return
    
    st.info(f"ชุดข้อสอบ: {qn} ข้อ (ตัวเลือก A–E)")
    name = st.text_input("ชื่อผู้สอบ", placeholder="พิมพ์ชื่อ-สกุล")
    options = ["A", "B", "C", "D", "E"]

    # Persist answers in session (handy on mobile)
    if "answers" not in st.session_state:
        st.session_state["answers"] = [""]*qn

    cols = st.columns(1)
    with cols[0]:
        for i in range(qn):
            st.session_state["answers"][i] = st.selectbox(
                f"ข้อ {i+1}",
                options=[""] + options,
                index=([""] + options).index(st.session_state["answers"][i]) if st.session_state["answers"][i] in ([""]+options) else 0,
                key=f"q_{i+1}",
            )
    if st.button("ส่งคำตอบ", type="primary", use_container_width=True):
        if not name.strip():
            st.warning("กรุณากรอกชื่อ")
            return
        filled = [a for a in st.session_state["answers"] if a]
        if len(filled) == 0:
            st.warning("กรุณาเลือกคำตอบอย่างน้อย 1 ข้อ")
            return
        try:
            js = gas_post("submit", {"student_name": name.strip(), "answers": st.session_state["answers"]})
            if js.get("ok"):
                res = js["data"]
                st.success(f"ส่งคำตอบสำเร็จ ✅ ได้คะแนน {res['score']} / {qn} ({res['percent']}%)")
                # Show detail
                with st.expander("ดูเฉลยรายข้อ / ผลลัพธ์"):
                    df = pd.DataFrame(res["detail"])
                    df["status"] = df["is_correct"].map({True:"ถูก", False:"ผิด"})
                    df = df[["q","ans","correct","status"]]
                    df.columns = ["ข้อ","คำตอบ","เฉลย","สถานะ"]
                    st.dataframe(df, hide_index=True, use_container_width=True)
            else:
                st.error(f"ส่งคำตอบไม่สำเร็จ: {js.get('error')}")
        except Exception as e:
            st.error(f"ส่งคำตอบล้มเหลว: {e}")

# ----------------------
# TEACHER DASHBOARD
# ----------------------
def page_dashboard():
    st.markdown("### 👩‍🏫 Dashboard อาจารย์")
    key_in = st.text_input("รหัสผ่านอาจารย์", type="password")
    if st.button("เข้าสู่ระบบ", use_container_width=True) or key_in:
        if not TEACHER_KEY:
            st.error("ยังไม่ได้ตั้งค่ารหัสผ่านอาจารย์ใน secrets.toml (app.teacher_key)")
            return
        if key_in != TEACHER_KEY:
            st.error("รหัสผ่านไม่ถูกต้อง")
            return

        st.success("เข้าสู่ระบบแล้ว ✅")
        cfg = fetch_config()
        if not cfg:
            return
        qn = int(cfg.get("question_count", 0))
        correct = cfg.get("correct_answers", [])

        try:
            js = gas_get("get_dashboard")
            if not js.get("ok"):
                st.error(js.get("error", "Unknown error"))
                return
            records = js["data"]
            if not records:
                st.info("ยังไม่มีคำตอบจากนักเรียน")
                return
            # Table
            df = pd.DataFrame(records)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp", ascending=True)

            st.subheader("สรุปผลรายคน")
            show = df[["timestamp","student_name","score","percent","answers"]].copy()
            show.columns = ["เวลา","ชื่อ","คะแนน","เปอร์เซ็นต์","คำตอบ"]
            st.dataframe(show, hide_index=True, use_container_width=True)

            # Stats
            st.subheader("สถิติคะแนนรวม")
            avg = float(df["percent"].mean())
            best = int(df["percent"].max())
            worst = int(df["percent"].min())
            st.write(f"ค่าเฉลี่ย: {avg:.1f}% | สูงสุด: {best}% | ต่ำสุด: {worst}%")

            # Bar chart (matplotlib default style/colors)
            import matplotlib.pyplot as plt
            fig = plt.figure()
            plt.bar(df["student_name"], df["percent"])
            plt.xticks(rotation=45, ha="right")
            plt.ylabel("Percent")
            plt.title("คะแนน (%) ต่อคน")
            st.pyplot(fig, use_container_width=True)

            # Item Analysis
            st.subheader("Item Analysis (เปอร์เซ็นต์คนตอบถูกต่อข้อ)")
            # Recompute from answers + correct
            counts = [0]*qn
            total = len(df)
            for _, row in df.iterrows():
                ans = [s.strip().upper() for s in str(row["answers"]).split(",")]
                for i in range(qn):
                    if i < len(ans) and ans[i] == correct[i]:
                        counts[i] += 1
            perc = [ round((c*100)/total) if total>0 else 0 for c in counts ]
            item_df = pd.DataFrame({"ข้อ": [i+1 for i in range(qn)], "%ถูก": perc})
            st.dataframe(item_df, hide_index=True, use_container_width=True)

            fig2 = plt.figure()
            plt.plot(item_df["ข้อ"], item_df["%ถูก"], marker="o")
            plt.xlabel("ข้อ")
            plt.ylabel("% ถูก")
            plt.title("Item Difficulty")
            st.pyplot(fig2, use_container_width=True)

        except Exception as e:
            st.error(f"โหลดข้อมูลล้มเหลว: {e}")

# Router
if mode == "dashboard":
    page_dashboard()
else:
    page_exam()
