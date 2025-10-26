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
# ... (ส่วนนี้ใช้โค้ดเดิม) ...
# (เช่น def gas_get, def gas_post, def get_active_exam, def get_exam_data)
# ...

# ---------------- Session State Helpers ----------------
# ... (ส่วนนี้ใช้โค้ดเดิม) ...
# (เช่น def init_session_state, def get_mode_from_url)
# ...

# ---------------- Pages ----------------
def page_exam():
    # โหลด CSS
    load_css() 
    
    st.title("📝 กระดาษคำตอบ MCQ")
    
    # ... โค้ดโหลดชุดข้อสอบ ...
    
    # ... โค้ดตรวจช่วงเวลา ...
    
    # ... โค้ด session_state ...

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
        
        # ... ปุ่มส่งคำตอบ ...
        # ... (โค้ดเดิมสำหรับปุ่ม submit) ...

def page_dashboard():
    # โหลด CSS (เพื่อให้การแสดงผลของ Container และ Divider สอดคล้องกัน)
    load_css()
    
    # ... โค้ดโหลดข้อมูล ...

    # ... โค้ดแสดงชุดที่เลือก ...

        st.subheader("ผลการสอบของชุดนี้")
        try:
            # ... โค้ดคำนวณสถิติ ...
            
            # ใช้ expander สำหรับตารางรายคนขนาดใหญ่
            with st.expander("📊 สรุปผลรายคน (คลิกเพื่อดูรายละเอียด)"):
                show = df[["timestamp", "student_name", "score", "percent", "answers"]].copy()
                show.columns = ["เวลา", "ชื่อ", "คะแนน", "เปอร์เซ็นต์", "คำตอบ"]
                st.dataframe(show, hide_index=True, use_container_width=True) # use_container_width=True

            st.subheader("สถิติคะแนนรวม")
            # ... (โค้ดแสดงค่าเฉลี่ย/สูงสุด/ต่ำสุดเหมือนเดิม) ...

            # กราฟคะแนน
            with st.container(border=True):
                st.markdown("##### กราฟแจกแจงคะแนน")
                # ... (โค้ดสร้าง fig) ...
                st.pyplot(fig, use_container_width=True)
            
            # Item Analysis
            if qn > 0 and total > 0:
                # ... (โค้ดคำนวณ item analysis) ...
                
                if isinstance(answer_key, list) and any(answer_key):
                    # Item Analysis (มีเฉลย)
                    # ใช้ expander สำหรับตาราง Item Analysis และกราฟ
                    with st.expander("✅ Item Analysis — สรุปการตอบถูกรายข้อ"):
                        st.dataframe(item_df, hide_index=True, use_container_width=True)
                        
                        # ... กราฟ % ถูก
                        st.pyplot(fig1, use_container_width=True)
                        
                        st.caption(f"🔎 ข้อที่นักเรียนผิดเยอะที่สุด: ข้อ {hardest['ข้อ']} (ถูก {hardest['%ถูก']}%)")
                else:
                    # Distribution (ไม่มีเฉลย)
                    # ใช้ expander สำหรับตาราง Distribution และกราฟ
                    with st.expander("📊 Item Analysis — แจกแจงตัวเลือกต่อข้อ"):
                        st.dataframe(dist_df, hide_index=True, use_container_width=True)
                        
                        # ... กราฟ stacked distribution
                        st.pyplot(figd, use_container_width=True)
                        
                        st.info("ℹ️ ต้องมีเฉลย (answer_key) จึงจะคำนวณถูก/ผิดต่อข้อได้ — "
                                "ทำได้โดยตั้งชุดนี้ให้เป็น Active (เพื่อดึงจาก get_active_exam) "
                                "หรือเพิ่ม endpoint ฝั่ง GAS ที่คืน answer_key ของชุดที่เลือก")
        except Exception as e:
            st.error(f"โหลดข้อมูลล้มเหลว: {e}")

# ----------------------------------------------------------------------
# ====================== Run Main App ======================\n
# ----------------------------------------------------------------------

# ... (โค้ดเดิมสำหรับรัน Main App) ...
# (เช่น if mode == 'teacher': page_dashboard() else: page_exam())
# ...
