import json
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="MCQ Answer Sheet", page_icon="📝", layout="centered")

GAS_WEBAPP_URL = st.secrets.get("gas", {}).get("webapp_url", "").strip()
TEACHER_KEY = st.secrets.get("app", {}).get("teacher_key", "").strip()
TIMEOUT = 25

def gas_get(action: str, params: dict | None = None):
    url = f"{GAS_WEBAPP_URL}?action={action}"
    if params:
        for k,v in params.items():
            url += f"&{k}={requests.utils.quote(str(v))}"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def gas_post(action: str, payload: dict):
    url = f"{GAS_WEBAPP_URL}?action={action}"
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

# Robust query param
raw_mode = st.query_params.get("mode", "exam")
if isinstance(raw_mode, list) and raw_mode:
    raw_mode = raw_mode[0]
mode = str(raw_mode).strip().lower()

def fetch_exams():
    try:
        js = gas_get("get_config")
        if js.get("ok"):
            return js["data"]["exams"]
        else:
            st.error(js.get("error","Config error"))
    except Exception as e:
        st.error(f"โหลดรายการชุดข้อสอบล้มเหลว: {e}")
    return []

def fetch_exam(exam_id: str):
    try:
        js = gas_get("get_exam", {"exam_id": exam_id})
        if js.get("ok"):
            return js["data"]
        else:
            st.error(js.get("error","Exam error"))
    except Exception as e:
        st.error(f"โหลดข้อมูลชุดข้อสอบล้มเหลว: {e}")
    return None

def page_exam():
    st.markdown("### 📝 กระดาษคำตอบ MCQ (มือถือ) — หลายชุดข้อสอบ")
    if not GAS_WEBAPP_URL:
        st.warning("⚠️ ตั้งค่า [gas.webapp_url] ใน Secrets ก่อน")
        return

    exams = fetch_exams()
    if not exams:
        st.info("ยังไม่มีชุดข้อสอบในชีท 'Exams'")
        return

    # Select exam set
    exam_titles = [f"{e['exam_id']} — {e['title']}" for e in exams]
    idx = st.selectbox("เลือกชุดข้อสอบ", options=list(range(len(exams))), format_func=lambda i: exam_titles[i], index=0, disabled=st.session_state.get("submitted", False))
    selected_exam = exams[idx]
    exam_id = selected_exam["exam_id"]

    # Load specific exam details
    exam = fetch_exam(exam_id)
    if not exam: return
    qn = int(exam.get("question_count",0))
    correct = exam.get("correct_answers",[])

    # Name & check duplicate status
    name = st.text_input("ชื่อผู้สอบ", placeholder="พิมพ์ชื่อ-สกุล", disabled=st.session_state.get("submitted", False))
    colA, colB = st.columns([1,1])
    with colA:
        if st.button("ตรวจสอบสิทธิ์ส่ง (เช็กว่าชื่อเคยส่งแล้วไหม)", disabled=st.session_state.get("submitted", False)):
            if not name.strip():
                st.warning("กรุณากรอกชื่อก่อนตรวจสอบ")
            else:
                try:
                    chk = gas_get("check_submitted", {"exam_id": exam_id, "student_name": name.strip()})
                    if chk.get("ok") and chk["data"]["submitted"]:
                        st.session_state["submitted"] = True
                        st.info("ชื่อผู้สอบนี้ได้ส่งคำตอบแล้วสำหรับชุดนี้ (ล็อคการส่งซ้ำ)")
                    else:
                        st.success("ยังไม่พบการส่งของชื่อนี้สำหรับชุดนี้ สามารถทำข้อสอบได้")
                except Exception as e:
                    st.error(f"ตรวจสอบล้มเหลว: {e}")
    with colB:
        if st.session_state.get("submitted", False):
            st.button("ส่งคำตอบ (ปิดการส่งซ้ำแล้ว)", disabled=True)

    st.info(f"ชุด: {exam_id} • {exam.get('title','')} • จำนวน {qn} ข้อ (ตัวเลือก A–E)")
    options = ["A","B","C","D","E"]

    # Init answers & lock flag
    if "answers" not in st.session_state or len(st.session_state["answers"])!=qn:
        st.session_state["answers"] = [""]*qn
    if "submitted" not in st.session_state:
        st.session_state["submitted"] = False

    # Checkbox UI per question (mutually exclusive)
    for i in range(qn):
        st.markdown(f"**ข้อ {i+1}**")
        cols = st.columns(5, vertical_alignment="center")
        current = st.session_state["answers"][i]
        for j, label in enumerate(options):
            key = f"q{i+1}_{label}"
            checked = (current == label)
            cols[j].checkbox(label, value=checked, key=key, disabled=st.session_state["submitted"])
        # Enforce single choice
        selected = None
        for label in options:
            if st.session_state.get(f"q{i+1}_{label}"):
                selected = label if selected is None else selected
        if selected is not None:
            for label in options:
                if label != selected and st.session_state.get(f"q{i+1}_{label}"):
                    st.session_state[f"q{i+1}_{label}"] = False
        st.session_state["answers"][i] = selected or ""
        st.divider()

    # Submit (server-side duplicate lock by (exam_id, name))
    submit_disabled = st.session_state.get("submitted", False)
    if st.button("ส่งคำตอบ", type="primary", use_container_width=True, disabled=submit_disabled):
        if not name.strip():
            st.warning("กรุณากรอกชื่อ")
            return
        try:
            js = gas_post("submit", {"exam_id": exam_id, "student_name": name.strip(), "answers": st.session_state["answers"]})
            if js.get("ok"):
                res = js["data"]
                st.session_state["submitted"] = True
                st.success(f"ส่งคำตอบสำเร็จ ✅ ได้คะแนน {res['score']} / {qn} ({res['percent']}%)")
                with st.expander("ดูเฉลยรายข้อ / ผลลัพธ์"):
                    df = pd.DataFrame(res["detail"])
                    df["status"] = df["is_correct"].map({True:"ถูก", False:"ผิด"})
                    df = df[["q","ans","correct","status"]]
                    df.columns = ["ข้อ","คำตอบ","เฉลย","สถานะ"]
                    st.dataframe(df, hide_index=True, use_container_width=True)
            else:
                if js.get("error")=="DUPLICATE_SUBMISSION":
                    st.session_state["submitted"] = True
                    st.info("ชื่อผู้สอบนี้ได้ส่งคำตอบแล้วสำหรับชุดนี้ (ระบบล็อคการส่งซ้ำ)")
                else:
                    st.error(f"ส่งคำตอบไม่สำเร็จ: {js.get('error')}")
        except Exception as e:
            st.error(f"ส่งคำตอบล้มเหลว: {e}")

def page_dashboard():
    st.markdown("### 👩‍🏫 Dashboard อาจารย์ (แยกตามชุดข้อสอบ)")
    if not TEACHER_KEY:
        st.error("ยังไม่ได้ตั้งค่ารหัสผ่านอาจารย์ใน Secrets (app.teacher_key)")
        return
    key_in = st.text_input("รหัสผ่านอาจารย์", type="password")
    if st.button("เข้าสู่ระบบ", use_container_width=True) or key_in:
        if key_in != TEACHER_KEY:
            st.error("รหัสผ่านไม่ถูกต้อง")
            return
        st.success("เข้าสู่ระบบแล้ว ✅")

        exams = fetch_exams()
        if not exams:
            st.info("ยังไม่มีชุดข้อสอบในชีท 'Exams'")
            return
        exam_titles = [f"{e['exam_id']} — {e['title']}" for e in exams]
        idx = st.selectbox("เลือกชุดข้อสอบที่ต้องการดูผล", options=list(range(len(exams))), format_func=lambda i: exam_titles[i], index=0)
        exam_id = exams[idx]["exam_id"]
        st.caption(f"กำลังแสดงผลของชุด: {exam_id}")

        try:
            js = gas_get("get_dashboard", {"exam_id": exam_id})
            if not js.get("ok"):
                st.error(js.get("error","Unknown error"))
                return
            records = js["data"]
            if not records:
                st.info("ยังไม่มีคำตอบของชุดนี้")
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
            plt.title(f"คะแนน (%) ต่อคน • {exam_id}")
            st.pyplot(fig, use_container_width=True)

            # Build correct answers from first record detail (they all same per exam)
            first_detail = df.iloc[0]["detail"] if "detail" in df.columns else None
            qn = len(first_detail) if first_detail else 0
            if qn>0:
                counts = [0]*qn
                total = len(df)
                for _, row in df.iterrows():
                    ans = [s.strip().upper() for s in str(row.get("answers","")).split(",")]
                    for i in range(qn):
                        if i < len(ans) and first_detail and ans[i] == first_detail[i]["correct"]:
                            counts[i] += 1
                perc = [ round((c*100)/total) if total>0 else 0 for c in counts ]
                item_df = pd.DataFrame({"ข้อ": [i+1 for i in range(qn)], "%ถูก": perc})
                st.subheader("Item Analysis")
                st.dataframe(item_df, hide_index=True, use_container_width=True)

                fig2 = plt.figure()
                plt.plot(item_df["ข้อ"], item_df["%ถูก"], marker="o")
                plt.xlabel("ข้อ")
                plt.ylabel("% ถูก")
                plt.title(f"Item Difficulty • {exam_id}")
                st.pyplot(fig2, use_container_width=True)

        except Exception as e:
            st.error(f"โหลดข้อมูลล้มเหลว: {e}")

if mode == "dashboard":
    page_dashboard()
else:
    page_exam()
