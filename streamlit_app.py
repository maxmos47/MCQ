import json
import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import textwrap
import os, urllib.request

st.set_page_config(page_title="MCQ Answer Sheet", page_icon="📝", layout="centered")

GAS_WEBAPP_URL = st.secrets.get("gas", {}).get("webapp_url", "").strip()
TEACHER_KEY = st.secrets.get("app", {}).get("teacher_key", "").strip()
TIMEOUT = 25

def gas_get(action: str, params: dict | None = None):
    url = f"{GAS_WEBAPP_URL}?action={action}"
    if params:
        for k, v in params.items():
            url += f"&{k}={requests.utils.quote(str(v))}"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def gas_post(action: str, payload: dict):
    url = f"{GAS_WEBAPP_URL}?action={action}"
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

# Routing
raw_mode = st.query_params.get("mode", "exam")
if isinstance(raw_mode, list) and raw_mode:
    raw_mode = raw_mode[0]
mode = str(raw_mode).strip().lower()

# ====================== Student Page ======================
def page_exam():
    st.markdown("### 📝 กระดาษคำตอบ MCQ (มือถือ) — ชุดข้อสอบที่อาจารย์กำหนด")
    if not GAS_WEBAPP_URL:
        st.warning("⚠️ ตั้งค่า [gas.webapp_url] ใน Secrets ก่อน")
        return

    # โหลดชุดข้อสอบที่กำลังใช้งาน
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

    qn = int(exam.get("question_count", 0))
    exam_id = exam.get("exam_id", "")
    st.info(f"ชุด: {exam_id} • {exam.get('title','')} • จำนวน {qn} ข้อ (ตัวเลือก A–E)")

    ss = st.session_state
    ss.setdefault("submitted", False)
    ss.setdefault("pending_submit_payload", None)
    ss.setdefault("submit_result", None)
    ss.setdefault("submit_error", None)
    ss.setdefault("answers", [""] * qn)

    # ถ้ามีผลลัพธ์แล้ว ให้ล็อคทันที
    if ss["submit_result"] is not None:
        ss["submitted"] = True

    is_pending = ss["pending_submit_payload"] is not None
    disabled_all = ss["submitted"] or is_pending

    name = st.text_input("ชื่อผู้สอบ", placeholder="พิมพ์ชื่อ-สกุล", disabled=disabled_all)

    options = ["A", "B", "C", "D", "E"]
    if len(ss["answers"]) != qn:
        ss["answers"] = [""] * qn

    for i in range(qn):
        ss["answers"][i] = st.radio(
            f"ข้อ {i+1}",
            options=[""] + options,
            index=([""] + options).index(ss["answers"][i]) if ss["answers"][i] in ([""] + options) else 0,
            horizontal=True,
            disabled=disabled_all,
            key=f"q_{i+1}_radio",
        )
        st.divider()

    def _arm_submit():
        if not name.strip():
            ss["submit_error"] = "กรุณากรอกชื่อ"
            return
        ss["submit_error"] = None
        ss["pending_submit_payload"] = {
            "exam_id": exam_id,
            "student_name": name.strip(),
            "answers": ss["answers"],
        }

    if not ss["submitted"]:
        st.button(
            "ส่งคำตอบ",
            type="primary",
            use_container_width=True,
            disabled=disabled_all,
            on_click=_arm_submit,
        )
    else:
        st.button("ส่งคำตอบ (ล็อคแล้ว)", use_container_width=True, disabled=True)

    # ส่งจริงเมื่อ pending
    if ss["pending_submit_payload"] is not None:
        with st.spinner("กำลังส่งคำตอบ..."):
            try:
                js2 = gas_post("submit", ss["pending_submit_payload"])
                if js2.get("ok"):
                    ss["submit_result"] = js2["data"]
                    ss["submitted"] = True
                    ss["submit_error"] = None
                else:
                    err = js2.get("error") or "ส่งคำตอบไม่สำเร็จ"
                    ss["submit_error"] = err
                    if err == "DUPLICATE_SUBMISSION":
                        ss["submitted"] = True
                    else:
                        ss["submitted"] = False
            except Exception as e:
                ss["submit_error"] = f"ส่งคำตอบล้มเหลว: {e}"
                ss["submitted"] = False
            finally:
                ss["pending_submit_payload"] = None
        st.rerun()

    if ss["submit_error"]:
        st.error(ss["submit_error"])

    if ss["submit_result"]:
        res = ss["submit_result"]
        st.success(f"ส่งคำตอบสำเร็จ ✅ ได้คะแนน {res['score']} / {qn} ({res['percent']}%)")
        with st.expander("ดูเฉลยรายข้อ / ผลลัพธ์"):
            df = pd.DataFrame(res["detail"])
            df["status"] = df["is_correct"].map({True: "ถูก", False: "ผิด"})
            df = df[["q", "ans", "correct", "status"]]
            df.columns = ["ข้อ", "คำตอบ", "เฉลย", "สถานะ"]
            st.dataframe(df, hide_index=True, use_container_width=True)

# ====================== Teacher Dashboard ======================
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
                st.error(cfg.get("error", "Config error"))
                return
            exams = cfg["data"]["exams"]
            active_id = cfg["data"].get("active_exam_id", "")
        except Exception as e:
            st.error(f"โหลดข้อมูลล้มเหลว: {e}")
            return
        if not exams:
            st.info("ยังไม่มีชุดข้อสอบในชีท 'Exams'")
            return

        id_to_title = {e["exam_id"]: e["title"] for e in exams}
        options = [e["exam_id"] for e in exams]
        current_idx = options.index(active_id) if active_id in options else 0
        new_idx = st.selectbox(
            "เลือกชุดข้อสอบที่จะใช้งาน (Active)",
            options=list(range(len(options))),
            index=current_idx,
            format_func=lambda i: f"{options[i]} — {id_to_title[options[i]]}",
        )
        chosen_id = options[new_idx]

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("บันทึกให้เป็น Active Exam", type="primary", use_container_width=True):
                try:
                    js = gas_post("set_active_exam", {"exam_id": chosen_id, "teacher_key": TEACHER_KEY})
                    if js.get("ok"):
                        st.success(f"ตั้งค่า Active Exam เป็น {chosen_id} เรียบร้อย")
                    elif js.get("error") == "UNAUTHORIZED":
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
                st.error(jsr.get("error", "Unknown error"))
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
            show = df[["timestamp", "student_name", "score", "percent", "answers"]].copy()
            show.columns = ["เวลา", "ชื่อ", "คะแนน", "เปอร์เซ็นต์", "คำตอบ"]
            st.dataframe(show, hide_index=True, use_container_width=True)

            st.subheader("สถิติคะแนนรวม")
            avg = float(df["percent"].astype(float).mean())
            best = int(df["percent"].astype(float).max())
            worst = int(df["percent"].astype(float).min())
            st.write(f"ค่าเฉลี่ย: {avg:.1f}% | สูงสุด: {best}% | ต่ำสุด: {worst}%")

            # === กราฟคะแนนอ่านง่าย (แนวนอน) ===
            plot_df = df[["student_name", "percent"]].copy()
            plot_df["student_name"] = plot_df["student_name"].astype(str).str.strip()
            def wrap_label(s, width=10):
                return "\n".join(textwrap.wrap(s, width=width))
            plot_df["label"] = plot_df["student_name"].apply(lambda s: wrap_label(s, width=10))
            plot_df = plot_df.sort_values("percent", ascending=True)

            fig, ax = plt.subplots(figsize=(10, max(3, 0.6 * len(plot_df))))
            ax.barh(plot_df["label"], plot_df["percent"])
            ax.set_xlim(0, 100)
            ax.set_xlabel("Percent", fontsize=12)
            ax.set_ylabel("นักเรียน", fontsize=12)
            ax.set_title(f"คะแนน (%) ต่อคน • {chosen_id}", fontsize=14, pad=12)
            ax.tick_params(axis="both", labelsize=12)
            for i, v in enumerate(plot_df["percent"].to_list()):
                ax.text(v + 1, i, f"{int(v)}%", va="center", fontsize=11)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)

            # === Item Analysis ===
            first_detail = df.iloc[0]["detail"] if "detail" in df.columns else None
            qn = len(first_detail) if first_detail else 0
            if qn > 0:
                counts = [0] * qn
                total = len(df)
                for _, row in df.iterrows():
                    ans = [s.strip().upper() for s in str(row.get("answers", "")).split(",")]
                    for i in range(qn):
                        if i < len(ans) and first_detail and ans[i] == first_detail[i]["correct"]:
                            counts[i] += 1
                perc = [round((c * 100) / total) if total > 0 else 0 for c in counts]
                item_df = pd.DataFrame({"ข้อ": [i + 1 for i in range(qn)], "%ถูก": perc})
                st.subheader("Item Analysis")
                st.dataframe(item_df, hide_index=True, use_container_width=True)

                fig2, ax2 = plt.subplots(figsize=(10, 4.5))
                ax2.plot(item_df["ข้อ"], item_df["%ถูก"], marker="o")
                ax2.set_xlabel("ข้อ", fontsize=12)
                ax2.set_ylabel("% ถูก", fontsize=12)
                ax2.set_title(f"Item Difficulty • {chosen_id}", fontsize=14, pad=12)
                ax2.set_ylim(0, 100)
                ax2.tick_params(axis="both", labelsize=12)
                for x, y in zip(item_df["ข้อ"], item_df["%ถูก"]):
                    ax2.text(x, y + 2, f"{y}%", ha="center", fontsize=10)
                plt.tight_layout()
                st.pyplot(fig2, use_container_width=True)

        except Exception as e:
            st.error(f"โหลดข้อมูลล้มเหลว: {e}")

# Routing
if mode == "dashboard":
    page_dashboard()
else:
    page_exam()
