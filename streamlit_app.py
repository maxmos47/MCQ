import json, requests, pandas as pd, streamlit as st, matplotlib.pyplot as plt, textwrap, matplotlib.font_manager as fm, os, urllib.request

st.set_page_config(page_title="MCQ Answer Sheet", page_icon="📝", layout="centered")

# ==== Thai font setup ====
try:
    font_path = "/tmp/NotoSansThai-Regular.ttf"
    if not os.path.exists(font_path):
        urllib.request.urlretrieve(
            "https://github.com/google/fonts/raw/main/ofl/notosansthai/NotoSansThai-Regular.ttf",
            font_path,
        )
    fm.fontManager.addfont(font_path)
    plt.rcParams["font.family"] = "Noto Sans Thai"
except Exception as e:
    print("Warning: cannot set Thai font", e)

st.write("ทดสอบภาษาไทย: โปรแกรมพร้อมใช้งาน ✅")
