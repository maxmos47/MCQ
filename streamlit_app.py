import json, requests, pandas as pd, streamlit as st, matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os, urllib.request, textwrap

st.set_page_config(page_title="MCQ Dashboard (TH)", page_icon="📝", layout="centered")

# ========== Ensure Thai Font ==========
def ensure_thai_font():
    local_font = os.path.join(os.path.dirname(__file__), "fonts", "NotoSansThai-Regular.ttf")
    tmp_font   = "/tmp/NotoSansThai-Regular.ttf"
    font_path = None
    if os.path.exists(local_font):
        font_path = local_font
    else:
        try:
            if not os.path.exists(tmp_font):
                urllib.request.urlretrieve(
                    "https://github.com/google/fonts/raw/main/ofl/notosansthai/NotoSansThai-Regular.ttf",
                    tmp_font,
                )
            font_path = tmp_font
        except Exception as e:
            print("WARN: download Thai font failed:", e)
    if font_path and os.path.exists(font_path):
        try:
            fm.fontManager.addfont(font_path)
            plt.rcParams["font.family"] = ["Noto Sans Thai", "Tahoma", "DejaVu Sans", "sans-serif"]
            plt.rcParams["axes.unicode_minus"] = False
        except Exception as e:
            print("WARN: cannot register Thai font:", e)
    else:
        plt.rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]
        plt.rcParams["axes.unicode_minus"] = False

ensure_thai_font()

st.markdown("## 🧭 ทดสอบฟอนต์ไทยบนกราฟ")
import matplotlib.pyplot as plt

students = ["สมชาย", "สมหญิง", "อนันต์", "รัตนา"]
scores = [85, 70, 95, 60]

fig, ax = plt.subplots(figsize=(6,4))
ax.barh(students, scores, color="skyblue")
ax.set_xlabel("คะแนน (%)", fontsize=12)
ax.set_title("ผลการทดสอบ", fontsize=14)
for i,v in enumerate(scores):
    ax.text(v+1, i, f"{v}%", va="center", fontsize=12)
st.pyplot(fig, use_container_width=True)
st.success("✅ ฟอนต์ไทยพร้อมใช้งาน หากตัวหนังสือแสดงถูก แปลว่าพร้อมแล้ว!")
