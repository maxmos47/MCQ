import json
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="MCQ Answer Sheet", page_icon="📝", layout="centered")

GAS_WEBAPP_URL = st.secrets.get("gas", {}).get("webapp_url", "").strip()
TEACHER_KEY = st.secrets.get("app", {}).get("teacher_key", "").strip()
TIMEOUT = 25

def gas_get(action: str):
    url = f"{GAS_WEBAPP_URL}?action={action}"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def gas_post(action: str, payload: dict):
    url = f"{GAS_WEBAPP_URL}?action={action}"
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

# Robust query-param handling
raw_mode = st.query_params.get("mode", "exam")
if isinstance(raw_mode, list) and raw_mode:
    raw_mode = raw_mode[0]
mode = str(raw_mode).strip().lower()

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

def page_health():
    st.markdown("### 🩺 Health Check")
    if not GAS_WEBAPP_URL:
        st.error("ยังไม่ได้ตั้งค่า [gas.webapp_url] ใน secrets")
        return
    st.write("ทดสอบ:", GAS_WEBAPP_URL)

    try:
        js = gas_get("get_config")
        st.success("get_config OK")
        st.code(json.dumps(js, ensure_ascii=False, indent=2))
    except Exception as e:
        st.error(f"get_config ล้มเหลว: {e}")
        return

    try:
        dummy = {"student_name": "HEALTHCHECK", "answers": ["A"]*int(js.get("data",{}).get("question_count",1))}
        res = gas_post("submit", dummy)
        if res.get("ok"):
            st.success("submit OK")
            st.code(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            st.warning(f"submit error: {res.get('error')}")
    except Exception as e:
        st.error(f"submit ล้มเหลว: {e}")
        return

    try:
        dash = gas_get("get_dashboard")
        if dash.get("ok"):
            st.success("get_dashboard OK")
            st.code(json.dumps(dash, ensure_ascii=False, indent=2))
        else:
            st.warning(f"get_dashboard error: {dash.get('error')}")
    except Exception as e:
        st.error(f"get_dashboard ล้มเหลว: {e}")

def page_exam():
    st.markdown("### 📝 กระดาษคำตอบ MCQ (มือถือ)")
    if not GAS_WEBAPP_URL:
        st.warning("⚠️ ตั้งค่า [gas.webapp_url] ใน Secrets ก่อน")
        return
    cfg = fetch_config()
    if not cfg:
        st.info("เปิด Health Check: ?mode=health เพื่อตรวจสอบ")
        return
    qn = int(cfg.get("question_count", 0))
    correct = cfg.get("correct_answers", [])
    if qn <= 0 or not correct or len(correct) != qn:
        st.error("การตั้งค่าใน Google Sheet ยังไม่ถูกต้อง (Question_Count / Correct_Answers)")
        return
    
    st.info(f"ชุดข้อสอบ: {qn} ข้อ (ตัวเลือก A–E)")
    name = st.text_input("ชื่อผู้สอบ", placeholder="พิมพ์ชื่อ-สกุล", disabled=st.session_state.get("submitted", False))
    options = ["A", "B", "C", "D", "E"]

    # Init session states
    if "answers" not in st.session_state or len(st.session_state["answers"]) != qn:
        st.session_state["answers"] = [""]*qn
    if "submitted" not in st.session_state:
        st.session_state["submitted"] = False

    # Checkbox UI per question (mutually exclusive)
    for i in range(qn):
        st.markdown(f"**ข้อ {i+1}**")
        cols = st.columns(5, vertical_alignment="center")
        # Determine current selected
        current = st.session_state["answers"][i]
        keys = []
        for j, label in enumerate(options):
            key = f"q{i+1}_{label}"
            keys.append(key)
            checked = (current == label)
            # Disable checkboxes after submit
            val = cols[j].checkbox(label, value=checked, key=key, disabled=st.session_state["submitted"])
            # We will process after loop to keep exclusivity

        # Enforce single selection
        selected = None
        for label in options:
            if st.session_state.get(f"q{i+1}_{label}"):
                selected = label if selected is None else selected  # keep first True (shouldn't have multiple)
        # If more than one got checked (rare), keep the last interaction effect:
        # Reset others to False
        if selected is not None:
            for label in options:
                if label != selected and st.session_state.get(f"q{i+1}_{label}"):
                    st.session_state[f"q{i+1}_{label}"] = False
        st.session_state["answers"][i] = selected or ""

        st.divider()

    # Submit button (locked after first submit)
    submit_disabled = st.session_state.get("submitted", False)
    if st.button("ส่งคำตอบ", type="primary", use_container_width=True, disabled=submit_disabled):
        if not name.strip():
            st.warning("กรุณากรอกชื่อ")
            return
        try:
            js = gas_post("submit", {"student_name": name.strip(), "answers": st.session_state["answers"]})
            if js.get("ok"):
                res = js["data"]
                st.session_state["submitted"] = True  # lock further submissions
                st.success(f"ส่งคำตอบสำเร็จ ✅ ได้คะแนน {res['score']} / {qn} ({res['percent']}%)")
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
            st.info("ลองเปิด Health Check: ?mode=health เพื่อตรวจสอบรายละเอียด")

def page_dashboard():
    st.markdown("### 👩‍🏫 Dashboard อาจารย์")
    if not TEACHER_KEY:
        st.error("ยังไม่ได้ตั้งค่ารหัสผ่านอาจารย์ใน Secrets (app.teacher_key)")
        return
    key_in = st.text_input("รหัสผ่านอาจารย์", type="password")
    if st.button("เข้าสู่ระบบ", use_container_width=True) or key_in:
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

            df = pd.DataFrame(records)
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                df = df.sort_values("timestamp", ascending=True)

            st.subheader("สรุปผลรายคน")
            show = df[["timestamp","student_name","score","percent","answers"]].copy()
            show.columns = ["เวลา","ชื่อ","คะแนน","เปอร์เซ็นต์","คำตอบ"]
            st.dataframe(show, hide_index=True, use_container_width=True)

            st.subheader("สถิติคะแนนรวม")
            avg = float(df["percent"].astype(float).mean())
            best = int(df["percent"].astype(float).max())
            worst = int(df["percent"].astype(float).min())
            st.write(f"ค่าเฉลี่ย: {avg:.1f}% | สูงสุด: {best}% | ต่ำสุด: {worst}%")

            import matplotlib.pyplot as plt
            fig = plt.figure()
            plt.bar(df["student_name"], df["percent"])
            plt.xticks(rotation=45, ha="right")
            plt.ylabel("Percent")
            plt.title("คะแนน (%) ต่อคน")
            st.pyplot(fig, use_container_width=True)

            st.subheader("Item Analysis (เปอร์เซ็นต์คนตอบถูกต่อข้อ)")
            counts = [0]*qn
            total = len(df)
            for _, row in df.iterrows():
                ans = [s.strip().upper() for s in str(row.get("answers","")).split(",")]
                for i in range(qn):
                    if i < len(ans) and i < len(correct) and ans[i] == correct[i]:
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
            st.info("ลองเปิด Health Check: ?mode=health เพื่อตรวจสอบรายละเอียด")

if mode == "dashboard":
    page_dashboard()
elif mode == "health":
    page_health()
else:
    page_exam()
