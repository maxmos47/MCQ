# streamlit_app.py
import json
import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib as mpl
import textwrap
import os
import urllib.request
import json as _json
from collections import Counter, defaultdict
from datetime import datetime, timezone

# ---------------- Fonts (Thai) ----------------
# พยายามใช้ TH Sarabun New ถ้ามีไฟล์ในโปรเจกต์ (เช่น thsarabunnew-webfont.ttf)
try:
    if os.path.exists("thsarabunnew-webfont.ttf"):
        mpl.font_manager.fontManager.addfont("thsarabunnew-webfont.ttf")
        mpl.rc("font", family="TH Sarabun New", size=20)
    else:
        # fallback ที่อ่านไทยได้ดีพอควรบนหลายระบบ
        plt.rcParams["font.family"] = "Tahoma"
        mpl.rc("font", family="DejaVu Sans", size=12)
except Exception:
    plt.rcParams["font.family"] = "DejaVu Sans"

plt.rcParams["axes.unicode_minus"] = False

# ---------------- Page Config (ปรับเป็น Wide Mode) ----------------
st.set_page_config(page_title="MCQ Answer Sheet", page_icon="📝", layout="wide")

# ---------------- Custom CSS for Mobile UI/Card Style ----------------
def load_css():
    st.markdown("""
        <style>
        /* 1. Mobile-friendly: Reduce padding around main content */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            padding-left: 1rem !important; /* Force minimal padding on sides */
            padding-right: 1rem !important; /* Force minimal padding on sides */
        }
        
        /* 2. Style for Question Card */
        .stQuestionCard {
            border: 1px solid #e0e0e0;
            border-radius: 12px; /* Soften the corners */
            padding: 15px;
            margin-bottom: 12px; /* Space between cards */
            box-shadow: 1px 1px 5px rgba(0, 0, 0, 0.05); /* Soft shadow */
            background-color: #ffffff; /* White background */
        }

        /* 3. Reduce vertical space (st.divider) in form */
        div[data-testid="stDivider"] {
            margin-top: 5px;
            margin-bottom: 10px;
        }
        
        /* 4. Make radio buttons more visually distinct */
        div[data-testid*="stRadio"] label {
            padding: 5px 10px;
            border-radius: 8px;
            margin: 2px;
            transition: background-color 0.1s;
        }
        /* Highlight selected option */
        div[data-testid*="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
            background-color: #e6f7ff; /* Light blue background for selected */
            border-left: 3px solid var(--primary-color); /* Primary color stripe */
        }
        </style>
        """, unsafe_allow_html=True)

# ---------------- Secrets / Config ----------------
GAS_WEBAPP_URL = st.secrets.get("gas", {}).get("webapp_url", "").strip()
TEACHER_KEY    = st.secrets.get("app", {}).get("teacher_key", "").strip()
TIMEOUT        = 25

# ---------------- GAS Helpers ----------------
def gas_get(action: str, params: dict):
    # ... (ส่วนนี้ใช้โค้ดเดิม) ...
    url = f"{GAS_WEBAPP_URL}?action={action}&{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            return _json.loads(response.read().decode())
    except Exception as e:
        return {"success": False, "error": str(e)}

def gas_post(action: str, payload: dict):
    # ... (ส่วนนี้ใช้โค้ดเดิม) ...
    url = f"{GAS_WEBAPP_URL}?action={action}"
    try:
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return _json.loads(response.read().decode())
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_active_exam():
    # ... (ส่วนนี้ใช้โค้ดเดิม) ...
    return gas_get("get_active_exam", {})

def get_exam_data(exam_id: str):
    # ... (ส่วนนี้ใช้โค้ดเดิม) ...
    return gas_get("get_exam_data", {"exam_id": exam_id})

# ---------------- Session State Helpers ----------------
ss = st.session_state

def init_session_state():
    # ... (ส่วนนี้ใช้โค้ดเดิม) ...
    if "answers" not in ss:
        ss["answers"] = []
    if "submitted" not in ss:
        ss["submitted"] = False
    if "payload" not in ss:
        ss["payload"] = None
    if "pending_submit_payload" not in ss:
        ss["pending_submit_payload"] = None

def get_mode_from_url():
    # ... (ส่วนนี้ใช้โค้ดเดิม) ...
    if "key" in st.query_params and st.query_params["key"] == TEACHER_KEY:
        return "teacher"
    return "student"

# ---------------- Pages ----------------
def page_exam():
    # โหลด CSS
    load_css() 
    
    st.title("📝 กระดาษคำตอบ MCQ")
    
    init_session_state()
    
    st.info("กำลังโหลดชุดข้อสอบ...", icon="⏳")
    
    exam_data = get_active_exam()
    st.empty() # Clear loading message
    
    if not exam_data.get("success", False):
        st.error(f"ไม่พบชุดข้อสอบที่เปิดใช้งานอยู่: {exam_data.get('error', 'โปรดตรวจสอบการตั้งค่า GAS')}")
        return

    exam_id = exam_data.get("exam_id")
    qn = exam_data.get("qn", 0)
    
    if qn == 0:
        st.warning("ชุดข้อสอบนี้มี 0 ข้อ")
        return

    # ตรวจสอบเวลา (ถ้ามี)
    time_limit_minutes = exam_data.get("time_limit", 0)
    end_time_iso = exam_data.get("end_time")

    now_utc = datetime.now(timezone.utc)
    
    # Check if a time limit exists and if the exam has ended
    if end_time_iso:
        end_time = datetime.fromisoformat(end_time_iso.replace('Z', '+00:00'))
        if now_utc > end_time:
            if not ss["submitted"]:
                st.error("หมดเวลาการทำข้อสอบแล้ว")
            else:
                st.success("คุณส่งคำตอบไปแล้ว")
            
            # Show exam info but disable controls
            st.info(f"ชุดข้อสอบ: {exam_id}, จำนวน {qn} ข้อ")
            
            # Try to show score if available
            if ss["payload"] and ss["payload"].get("score") is not None:
                 st.metric(label="คะแนน", value=f"{ss['payload']['score']} / {qn}")

            return
        
        # Display remaining time if not submitted
        if not ss["submitted"]:
            time_remaining = end_time - now_utc
            minutes_remaining = int(time_remaining.total_seconds() // 60)
            seconds_remaining = int(time_remaining.total_seconds() % 60)
            
            # Display countdown in a fixed sidebar/header element (simplified here)
            st.sidebar.markdown(f"**เหลือเวลา:** **{minutes_remaining}** นาที **{seconds_remaining}** วินาที")
            
            # Auto-refresh to update countdown
            if time_remaining.total_seconds() > 0:
                from time import sleep
                sleep(1)
                st.rerun()

    is_pending = ss["pending_submit_payload"] is not None
    disabled_all = ss["submitted"] or is_pending

    with st.form("exam_form", clear_on_submit=False):
        # หุ้ม ชื่อผู้สอบ ด้วย Container
        with st.container(border=True):
             st.subheader("ข้อมูลผู้สอบ")
             name = st.text_input("ชื่อผู้สอบ", placeholder="พิมพ์ชื่อ-สกุล", disabled=disabled_all)
        
        st.markdown("### คำตอบ")
        options = ["A", "B", "C", "D", "E"]
        if len(ss["answers"]) != qn:
            ss["answers"] = [""] * qn

        # ลูปคำถาม: หุ้มแต่ละข้อด้วย Card
        for i in range(qn):
            current = ss["answers"][i]
            
            # แทรก HTML สำหรับ Card Style
            st.markdown('<div class="stQuestionCard">', unsafe_allow_html=True) 
            
            st.markdown(f"**ข้อ {i+1}**") # เน้นเลขข้อ
            
            choice = st.radio(
                f" ", # ใช้ช่องว่างเป็น Label เพื่อซ่อนข้อความซ้ำ
                options=[""] + options,
                index=([""] + options).index(current) if current in ([""] + options) else 0,
                horizontal=True,
                disabled=disabled_all,
                key=f"q_{i+1}_radio_form",
            )
            ss["answers"][i] = choice
            
            st.divider() 
            
            st.markdown('</div>', unsafe_allow_html=True) # ปิด Card
        
        # --- Submit Button Logic ---
        submitted = st.form_submit_button("ส่งคำตอบ", disabled=disabled_all or not name.strip())

        if submitted:
            if not name.strip():
                st.error("กรุณากรอกชื่อผู้สอบ")
            else:
                payload = {
                    "exam_id": exam_id,
                    "student_name": name.strip(),
                    "answers": ss["answers"],
                }
                ss["pending_submit_payload"] = payload
                st.rerun() # Trigger rerun to submit outside of form

    if is_pending:
        st.info("กำลังส่งคำตอบ...", icon="📧")
        
        # Check time again before submission
        if end_time_iso:
            end_time = datetime.fromisoformat(end_time_iso.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > end_time:
                st.error("การส่งล้มเหลว: หมดเวลาการทำข้อสอบแล้ว")
                ss["pending_submit_payload"] = None
                return

        response = gas_post("submit_answer", ss["pending_submit_payload"])
        st.empty() # Clear submitting message

        if response.get("success", False):
            ss["submitted"] = True
            ss["payload"] = response.get("payload")
            st.success("ส่งคำตอบสำเร็จ! ✨")
            
            # Show score
            if ss["payload"] and ss["payload"].get("score") is not None:
                st.metric(label="คะแนน", value=f"{ss['payload']['score']} / {qn}")
            else:
                st.info("ไม่แสดงคะแนน เนื่องจากชุดข้อสอบไม่ได้เปิดเฉลยทันที")
            
            st.balloons()
        else:
            st.error(f"การส่งล้มเหลว: {response.get('error', 'Unknown Error')}")
        
        ss["pending_submit_payload"] = None
        st.rerun()

def page_dashboard():
    # โหลด CSS
    load_css()
    
    st.title("👨‍🏫 Dashboard")
    
    init_session_state()
    
    teacher_key_input = st.text_input("รหัสอาจารย์", type="password", 
                                      value=st.query_params.get("key", "") or TEACHER_KEY)
    
    if teacher_key_input != TEACHER_KEY:
        st.error("รหัสอาจารย์ไม่ถูกต้อง")
        return
    
    # ดึงข้อมูลชุดข้อสอบทั้งหมด
    exams_res = gas_get("get_exam_ids", {})
    if not exams_res.get("success", False):
        st.error(f"ไม่สามารถดึงข้อมูลชุดข้อสอบ: {exams_res.get('error', 'Unknown Error')}")
        return

    exam_ids = exams_res.get("exam_ids", [])
    if not exam_ids:
        st.info("ไม่พบชุดข้อสอบในฐานข้อมูล")
        return

    # เลือกชุดข้อสอบ
    selected_id = st.selectbox("เลือกชุดข้อสอบ", exam_ids)

    if selected_id:
        st.info(f"กำลังโหลดข้อมูลของชุด **{selected_id}**...", icon="⏳")
        exam_data = get_exam_data(selected_id)
        st.empty() # Clear loading message

        if not exam_data.get("success", False):
            st.error(f"โหลดข้อมูลล้มเหลว: {exam_data.get('error', 'Unknown Error')}")
            return

        qn = exam_data.get("qn", 0)
        df_raw = exam_data.get("df", [])
        answer_key = exam_data.get("answer_key", [])
        total = len(df_raw)
        
        # แปลงเป็น DataFrame
        df = pd.DataFrame(df_raw)

        # ---------------- ส่วนแสดงผล ----------------
        
        # แก้ไข Indentation Error: ย้าย st.subheader ให้ถูกที่
        st.subheader("ผลการสอบของชุดนี้")
        try:
            if total == 0:
                st.info("ยังไม่มีนักเรียนส่งคำตอบสำหรับชุดนี้")
                return

            st.metric(label="จำนวนผู้ส่งคำตอบ", value=total)
            
            # คำนวณสถิติ
            scores = df["score"].tolist()
            
            st.metric("คะแนนเฉลี่ย", f"{pd.Series(scores).mean():.2f} / {qn}")
            st.markdown(f"**คะแนนสูงสุด:** {max(scores)} / {qn} | **คะแนนต่ำสุด:** {min(scores)} / {qn}")
            
            # ใช้ expander สำหรับตารางรายคนขนาดใหญ่
            with st.expander("📊 สรุปผลรายคน (คลิกเพื่อดูรายละเอียด)"):
                show = df[["timestamp", "student_name", "score", "percent", "answers"]].copy()
                show.columns = ["เวลา", "ชื่อ", "คะแนน", "เปอร์เซ็นต์", "คำตอบ"]
                st.dataframe(show, hide_index=True, use_container_width=True) # use_container_width=True

            st.subheader("สถิติคะแนนรวม")
            
            # กราฟคะแนน
            with st.container(border=True):
                st.markdown("##### กราฟแจกแจงคะแนน")
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.hist(scores, bins=range(0, qn + 2), align='left', rwidth=0.8, color='skyblue', edgecolor='black')
                ax.set_xticks(range(0, qn + 1))
                ax.set_xlabel("คะแนน")
                ax.set_ylabel("จำนวนนักเรียน")
                ax.set_title("แจกแจงคะแนนสอบ", fontsize=14, pad=12)
                plt.tight_layout()
                st.pyplot(fig, use_container_width=True)
            
            # Item Analysis
            if qn > 0 and total > 0:
                all_opts = ["A", "B", "C", "D", "E", ""]
                
                # Distribution Count
                dist_counts = Counter()
                for ans_list in df["answers"].tolist():
                    for i, ans in enumerate(ans_list):
                        dist_counts[(i + 1, ans)] += 1

                dist_data = defaultdict(lambda: {'ข้อ': 0, **{o: 0 for o in all_opts}})
                for (q_num, choice), count in dist_counts.items():
                    dist_data[q_num]['ข้อ'] = q_num
                    dist_data[q_num][choice] = count

                dist_df = pd.DataFrame(list(dist_data.values())).sort_values(by='ข้อ')
                
                # Check if answer key is valid
                if isinstance(answer_key, list) and len(answer_key) == qn and any(answer_key):
                    # Item Analysis (มีเฉลย)
                    correct_counts = Counter()
                    for ans_list in df["answers"].tolist():
                        for i, ans in enumerate(ans_list):
                            if i < qn and ans == answer_key[i]:
                                correct_counts[i + 1] += 1
                    
                    # Create Item Analysis DataFrame
                    item_df_data = []
                    hardest = {'ข้อ': 0, '%ถูก': 101}
                    for i in range(qn):
                        q_num = i + 1
                        correct = correct_counts[q_num]
                        percent_correct = (correct / total) * 100
                        item_df_data.append({
                            "ข้อ": q_num,
                            "เฉลย": answer_key[i],
                            "จำนวนถูก": correct,
                            "%ถูก": f"{percent_correct:.2f}%",
                        })
                        if percent_correct < hardest['%ถูก']:
                            hardest = {'ข้อ': q_num, '%ถูก': f"{percent_correct:.2f}"}

                    item_df = pd.DataFrame(item_df_data)

                    # ใช้ expander สำหรับตาราง Item Analysis และกราฟ
                    with st.expander("✅ Item Analysis — สรุปการตอบถูกรายข้อ"):
                        st.dataframe(item_df, hide_index=True, use_container_width=True)
                        
                        # กราฟ % ถูก
                        fig1, ax1 = plt.subplots(figsize=(10, max(3.5, 0.4 * qn)))
                        y = item_df["ข้อ"].astype(str)
                        width = [float(p.strip('%')) for p in item_df["%ถูก"].tolist()]
                        ax1.barh(y, width, color='lightgreen', edgecolor='black')
                        ax1.set_xlim(0, 100)
                        ax1.set_xlabel("ร้อยละการตอบถูก")
                        ax1.set_ylabel("ข้อ")
                        ax1.set_title("ร้อยละการตอบถูกรายข้อ", fontsize=14, pad=12)
                        plt.tight_layout()
                        st.pyplot(fig1, use_container_width=True)
                        
                        st.caption(f"🔎 ข้อที่นักเรียนผิดเยอะที่สุด: **ข้อ {hardest['ข้อ']}** (ถูก {hardest['%ถูก']}%)")
                else:
                    # Distribution (ไม่มีเฉลย)
                    # ใช้ expander สำหรับตาราง Distribution และกราฟ
                    with st.expander("📊 Item Analysis — แจกแจงตัวเลือกต่อข้อ"):
                        st.dataframe(dist_df, hide_index=True, use_container_width=True)
                        
                        # กราฟ stacked distribution
                        figd, axd = plt.subplots(figsize=(10, max(3.5, 0.55 * len(dist_df))))
                        y = dist_df["ข้อ"].astype(str)
                        left = [0] * len(dist_df)
                        for o in all_opts:
                            vals = dist_df[o].tolist()
                            axd.barh(y, vals, left=left, label=o)
                            left = [l + v for l, v in zip(left, vals)]
                        axd.set_xlabel("จำนวนนักเรียน", fontsize=12)
                        axd.set_ylabel("ข้อ", fontsize=12)
                        axd.set_title("Distribution ตัวเลือกต่อข้อ (A–E/เว้นว่าง)", fontsize=14, pad=12)
                        axd.legend(loc="lower right", ncol=3)
                        plt.tight_layout()
                        st.pyplot(figd, use_container_width=True)
                        
                        st.info("ℹ️ ต้องมีเฉลย (answer_key) จึงจะคำนวณถูก/ผิดต่อข้อได้ — "
                                "ทำได้โดยตั้งชุดนี้ให้เป็น Active (เพื่อดึงจาก get_active_exam) "
                                "หรือเพิ่ม endpoint ฝั่ง GAS ที่คืน answer_key ของชุดที่เลือก")
        except Exception as e:
            st.error(f"โหลดข้อมูลล้มเหลว: {e}")

# ----------------------------------------------------------------------
# ====================== Run Main App ======================\n
# ----------------------------------------------------------------------

init_session_state()
mode = get_mode_from_url()

if mode == 'teacher':
    page_dashboard()
else:
    page_exam()
