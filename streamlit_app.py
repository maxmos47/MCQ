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

raw_mode = st.query_params.get("mode", "exam")
if isinstance(raw_mode, list) and raw_mode:
    raw_mode = raw_mode[0]
mode = str(raw_mode).strip().lower()

def page_exam():
    st.markdown("### 📝 กระดาษคำตอบ MCQ (มือถือ) — ชุดข้อสอบที่อาจารย์กำหนด")
    if not GAS_WEBAPP_URL:
        st.warning("⚠️ ตั้งค่า [gas.webapp_url] ใน Secrets ก่อน")
        return
    try:
        js = gas_get("get_active_exam")
        if not js.get("ok"):
            st.error("ยังไม่ได้กำหนดชุดข้อสอบที่ใช้อยู่ (Active Exam)")
            st.info("ให้อาจารย์ไปตั้งค่าที่หน้า Dashboard")
            return
        exam = js["data"]
    except Exception as e:
        st.error(f"โหลดชุดข้อสอบล้มเหลว: {e}")
        return

    qn = int(exam.get("question_count",0))
    exam_id = exam.get("exam_id","")
    st.info(f"ชุด: {exam_id} • {exam.get('title','')} • จำนวน {qn} ข้อ (ตัวเลือก A–E)")

    if "submitted" not in st.session_state: st.session_state["submitted"] = False
    name = st.text_input("ชื่อผู้สอบ", placeholder="พิมพ์ชื่อ-สกุล", disabled=st.session_state["submitted"])

    options = ["A","B","C","D","E"]
    if "answers" not in st.session_state or len(st.session_state["answers"])!=qn:
        st.session_state["answers"] = [""]*qn

    for i in range(qn):
        st.session_state["answers"][i] = st.radio(
            f"ข้อ {i+1}",
            options=[""]+options,
            index=([""]+options).index(st.session_state["answers"][i]) if st.session_state["answers"][i] in ([""]+options) else 0,
            horizontal=True,
            disabled=st.session_state["submitted"],
            key=f"q_{i+1}_radio"
        )
        st.divider()

    if st.button("ส่งคำตอบ", type="primary", use_container_width=True, disabled=st.session_state["submitted"]):
        if not name.strip():
            st.warning("กรุณากรอกชื่อ")
            return
        try:
            js2 = gas_post("submit", {"exam_id": exam_id, "student_name": name.strip(), "answers": st.session_state["answers"]})
            if js2.get("ok"):
                st.session_state["submitted"] = True
                res = js2["data"]
                st.success(f"ส่งคำตอบสำเร็จ ✅ ได้คะแนน {res['score']} / {qn} ({res['percent']}%)")
                with st.expander("ดูเฉลยรายข้อ / ผลลัพธ์"):
                    df = pd.DataFrame(res["detail"])
                    df["status"] = df["is_correct"].map({True:"ถูก", False:"ผิด"})
                    df = df[["q","ans","correct","status"]]
                    df.columns = ["ข้อ","คำตอบ","เฉลย","สถานะ"]
                    st.dataframe(df, hide_index=True, use_container_width=True)
            else:
                if js2.get("error")=="DUPLICATE_SUBMISSION":
                    st.session_state["submitted"] = True
                    st.info("ชื่อผู้สอบนี้ได้ส่งคำตอบแล้วสำหรับชุดนี้ (ระบบล็อคการส่งซ้ำ)")
                else:
                    st.error(f"ส่งคำตอบไม่สำเร็จ: {js2.get('error')}")
        except Exception as e:
            st.error(f"ส่งคำตอบล้มเหลว: {e}")

def page_dashboard():
    st.markdown("### 👩‍🏫 Dashboard อาจารย์ — ตั้งค่า Active Exam และดูผล")
    if not TEACHER_KEY:
        st.error("ยังไม่ได้ตั้งค่ารหัสผ่านอาจารย์ใน Secrets (app.teacher_key)")
        return
    key_in = st.text_input("รหัสผ่านอาจารย์", type="password")
    if st.button("เข้าสู่ระบบ", use_container_width=True) or key_in:
        if key_in != TEACHER_KEY:
            st.error("รหัสผ่านไม่ถูกต้อง")
            return
        st.success("เข้าสู่ระบบแล้ว ✅")
        try:
            cfg = gas_get("get_config")
            if not cfg.get("ok"):
                st.error(cfg.get("error","Config error"))
                return
            exams = cfg["data"]["exams"]
            active_id = cfg["data"].get("active_exam_id","")
        except Exception as e:
            st.error(f"โหลดข้อมูลล้มเหลว: {e}")
            return
        if not exams:
            st.info("ยังไม่มีชุดข้อสอบในชีท 'Exams'")
            return

        id_to_title = {e["exam_id"]: e["title"] for e in exams}
        options = [e["exam_id"] for e in exams]
        current_idx = options.index(active_id) if active_id in options else 0
        new_idx = st.selectbox("เลือกชุดข้อสอบที่จะใช้งาน (Active)", options=list(range(len(options))), index=current_idx, format_func=lambda i: f"{options[i]} — {id_to_title[options[i]]}" )
        chosen_id = options[new_idx]

        col1, col2 = st.columns([1,1])
        with col1:
            if st.button("บันทึกให้เป็น Active Exam", type="primary", use_container_width=True):
                try:
                    js = gas_post("set_active_exam", {"exam_id": chosen_id, "teacher_key": TEACHER_KEY})
                    if js.get("ok"):
                        st.success(f"ตั้งค่า Active Exam เป็น {chosen_id} เรียบร้อย")
                    elif js.get("error")=="UNAUTHORIZED":
                        st.error("ไม่ได้รับอนุญาต (ตรวจ TEACHER_KEY ในชีท Config ของ GAS)")
                    else:
                        st.error(f"บันทึกไม่สำเร็จ: {js.get('error')}")
                except Exception as e:
                    st.error(f"บันทึกล้มเหลว: {e}")
        with col2:
            st.caption(f"ชุดที่ใช้อยู่ตอนนี้: **{active_id or 'ยังไม่ได้ตั้ง'}**")

        st.subheader("ผลการสอบของชุดนี้")
        try:
            jsr = gas_get("get_dashboard", {"exam_id": chosen_id})
            if not jsr.get("ok"):
                st.error(jsr.get("error","Unknown error"))
                return
            records = jsr["data"]
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
            plt.title(f"คะแนน (%) ต่อคน • {chosen_id}")
            st.pyplot(fig, use_container_width=True)

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
                plt.title(f"Item Difficulty • {chosen_id}")
                st.pyplot(fig2, use_container_width=True)

        except Exception as e:
            st.error(f"โหลดข้อมูลล้มเหลว: {e}")

if mode == "dashboard":
    page_dashboard()
else:
    page_exam()
