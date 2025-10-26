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

# ---------------- Page Config ----------------
st.set_page_config(page_title="MCQ Answer Sheet", page_icon="📝", layout="centered")

# ---------------- Secrets / Config ----------------
GAS_WEBAPP_URL = st.secrets.get("gas", {}).get("webapp_url", "").strip()
TEACHER_KEY    = st.secrets.get("app", {}).get("teacher_key", "").strip()
TIMEOUT        = 25

# ---------------- GAS Helpers ----------------
def gas_get(action: str, params: dict | None = None):
    if not GAS_WEBAPP_URL:
        raise RuntimeError("GAS_WEBAPP_URL is not set.")
    url = f"{GAS_WEBAPP_URL}?action={action}"
    if params:
        for k, v in params.items():
            url += f"&{k}={requests.utils.quote(str(v))}"
    r = requests.get(url, timeout=TIMEOUT)
    ct = r.headers.get("Content-Type", "")
    body_preview = (r.text or "")[:800]
    if r.status_code != 200:
        raise RuntimeError(f"GAS HTTP {r.status_code} ({ct}) — {body_preview}")
    try:
        return r.json()
    except Exception:
        raise RuntimeError(f"GAS ตอบกลับไม่ใช่ JSON ({ct}) — ตัวอย่าง: {body_preview}")

def gas_post(action: str, payload: dict):
    if not GAS_WEBAPP_URL:
        raise RuntimeError("GAS_WEBAPP_URL is not set.")
    url = f"{GAS_WEBAPP_URL}?action={action}"
    r = requests.post(url, json=payload, timeout=30)
    ct = r.headers.get("Content-Type", "")
    body_preview = (r.text or "")[:800]
    if r.status_code != 200:
        raise RuntimeError(f"GAS HTTP {r.status_code} ({ct}) — {body_preview}")
    try:
        return r.json()
    except Exception:
        raise RuntimeError(f"GAS ตอบกลับไม่ใช่ JSON ({ct}) — ตัวอย่าง: {body_preview}")

# ---------------- Routing (via ?mode=...) ----------------
raw_mode = st.query_params.get("mode", "exam")
if isinstance(raw_mode, list) and raw_mode:
    raw_mode = raw_mode[0]
mode = str(raw_mode).strip().lower()

# ----------------------------------------------------------------------
# ====================== Student Page ======================
# ----------------------------------------------------------------------

def is_within_window(start_utc: str, end_utc: str) -> tuple[bool, str]:
    try:
        if not start_utc or not end_utc:
            # ถ้าขาดอย่างใดอย่างหนึ่ง = ถือว่าไม่ได้ล็อกเวลา
            return True, "ไม่จำกัดเวลา"
        now = datetime.now(timezone.utc)
        start = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
        end   = datetime.fromisoformat(end_utc.replace("Z", "+00:00"))
        if now < start:
            return False, f"ยังไม่ถึงเวลาสอบ (เริ่ม {start_utc})"
        if now > end:
            return False, f"หมดเวลาทำข้อสอบแล้ว (สิ้นสุด {end_utc})"
        return True, ""
    except Exception as e:
        # ถ้าพาร์สเวลาไม่ได้ ให้ปล่อยผ่าน (ไม่ล็อก) เพื่อไม่บล็อคผู้ใช้โดยผิดพลาด
        return True, f"ไม่สามารถตรวจสอบเวลาได้ ({e})"

def page_exam():
    st.markdown("### 📝 กระดาษคำตอบ MCQ (มือถือ) — ชุดข้อสอบที่อาจารย์กำหนด")
    if not GAS_WEBAPP_URL:
        st.warning("⚠️ ตั้งค่า [gas.webapp_url] ใน Secrets ก่อน")
        return

    # 1) โหลดชุดข้อสอบ
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

    # 2) ตรวจช่วงเวลา (บังคับปิดฟอร์มถ้าอยู่นอกช่วง)
    time_mode_raw = (exam.get("time_mode", "") or "").strip().lower()
    window_start  = exam.get("window_start_utc", "") or ""
    window_end    = exam.get("window_end_utc", "") or ""

    # ถ้ามี start และ end ให้ถือว่า "ล็อกเวลา" ไม่ว่าค่า time_mode จะเป็นอะไร
    has_window = bool(window_start and window_end)
    ok_time, msg_time = is_within_window(window_start, window_end)

    if has_window and not ok_time:
        st.error(f"⏰ {msg_time}")
        st.info(f"ช่วงเวลาสอบ (UTC): {window_start} → {window_end}")
        # 🔒 ปิดฟอร์มทันที: ไม่ render ฟอร์มด้านล่าง
        return
    elif has_window:
        st.caption(f"🕒 ช่วงเวลาสอบ (UTC): {window_start} → {window_end}")

    # 3) เหมือน baseline เดิมต่อไป (ฟอร์ม + ส่งคำตอบ)
    ss = st.session_state
    ss.setdefault("submitted", False)
    ss.setdefault("pending_submit_payload", None)
    ss.setdefault("submit_result", None)
    ss.setdefault("submit_error", None)
    ss.setdefault("answers", [""] * qn)

    if ss["submit_result"] is not None:
        ss["submitted"] = True

    is_pending = ss["pending_submit_payload"] is not None
    disabled_all = ss["submitted"] or is_pending

    with st.form("exam_form", clear_on_submit=False):
        name = st.text_input("ชื่อผู้สอบ", placeholder="พิมพ์ชื่อ-สกุล", disabled=disabled_all)

        options = ["A", "B", "C", "D", "E"]
        if len(ss["answers"]) != qn:
            ss["answers"] = [""] * qn

        for i in range(qn):
            current = ss["answers"][i]
            choice = st.radio(
                f"ข้อ {i+1}",
                options=[""] + options,
                index=([""] + options).index(current) if current in ([""] + options) else 0,
                horizontal=True,
                disabled=disabled_all,
                key=f"q_{i+1}_radio_form",
            )
            ss["answers"][i] = choice
            st.divider()

        submitted_form = st.form_submit_button(
            "ส่งคำตอบ",
            type="primary",
            use_container_width=True,
            disabled=disabled_all,
        )

    if submitted_form and not ss["submitted"]:
        if not name.strip():
            ss["submit_error"] = "กรุณากรอกชื่อ"
        else:
            ss["submit_error"] = None
            ss["pending_submit_payload"] = {
                "exam_id": exam_id,
                "student_name": name.strip(),
                "answers": ss["answers"],
            }

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
                    ss["submitted"] = (err == "DUPLICATE_SUBMISSION")
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

# ----------------------------------------------------------------------
# ====================== Teacher Dashboard ======================
# ----------------------------------------------------------------------

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
            st.stop()
            return
        st.success("เข้าสู่ระบบแล้ว ✅")

        # โหลด Config/Exams
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

        # เลือกชุดข้อสอบ Active
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

            # ======================= Item Analysis (รวมเข้ากับโค้ดเดิม) =======================
            from collections import Counter
            import json as _json

            # --- 1) แปลงคำตอบนักเรียนเป็น list[list[str]] ---
            answers_lists = []
            if "answers" in df.columns:
                for s in df["answers"].astype(str).fillna(""):
                    # split + ทำความสะอาด + ตัดค่าว่าง
                    arr = [a.strip().upper() for a in s.split(",")]
                    arr = [a for a in arr if a]  # ตัดค่าว่าง
                    answers_lists.append(arr)
            else:
                answers_lists = []

            total = len(answers_lists)

            # --- 2) ลองดึง detail เพื่อดูจำนวนข้อจากเฉลยรายข้อ ---
            first_detail = None
            if "detail" in df.columns:
                for v in df["detail"]:
                    try:
                        d = v if isinstance(v, list) else _json.loads(v) if isinstance(v, str) else None
                        if isinstance(d, list) and len(d) > 0:
                            first_detail = d
                            break
                    except Exception:
                        pass
            qn_detail = len(first_detail) if isinstance(first_detail, list) else 0

            # --- 3) ลองดึง answer_key ของชุดนี้ (ถ้ามี) ---
            answer_key = None
            # ถ้ามี detail → ดึงเฉลยจาก detail
            if isinstance(first_detail, list):
                answer_key = [str(x.get("correct","")).strip().upper() if isinstance(x, dict) else "" for x in first_detail]

            # ถ้ายังไม่มี → ลอง get_active_exam (ใช้เฉพาะเมื่อ exam_id ตรง)
            if answer_key is None:
                try:
                    ex = gas_get("get_active_exam")
                    if ex.get("ok") and str(ex["data"].get("exam_id","")) == str(chosen_id):
                        k = str(ex["data"].get("answer_key","") or "")
                        answer_key = [c.strip().upper() for c in list(k)]
                except Exception:
                    pass
            key_len = len(answer_key) if isinstance(answer_key, list) else 0

            # --- 4) เอาจำนวนข้อจาก "คำตอบจริง" ของนักเรียนแบบเสียงข้างมาก ---
            lens = [len(a) for a in answers_lists]
            maj_len = Counter(lens).most_common(1)[0][0] if lens else 0

            # --- 5) สรุปจำนวนข้อที่เชื่อถือได้ที่สุด ---
            candidates = [x for x in [maj_len, qn_detail, key_len] if x and x > 0]
            qn = min(candidates) if candidates else 0

            if qn == 0 or total == 0:
                st.info("ยังไม่มีคำตอบ/จำนวนข้อเพียงพอสำหรับการวิเคราะห์รายข้อ")
            else:
                # --- 6) บังคับให้ทุกอย่างยาวเท่า qn (truncate) ---
                answers_lists = [arr[:qn] for arr in answers_lists]
                if isinstance(answer_key, list):
                    answer_key = answer_key[:qn]

                # 7) แจกแจงการเลือกตัวเลือกต่อข้อ (fallback ทำงานได้เสมอ)
                option_counts = [Counter() for _ in range(qn)]
                valid_opts = ["A", "B", "C", "D", "E"]
                for arr in answers_lists:
                    for i in range(qn):
                        opt = arr[i].upper() if i < len(arr) else ""
                        opt = opt if opt in valid_opts else "(blank)"
                        option_counts[i][opt] += 1

                # 8) ถ้ามีเฉลย → คำนวณถูก/ผิดต่อข้อ
                if isinstance(answer_key, list) and any(answer_key):
                    correct_counts = [0] * qn
                    for arr in answers_lists:
                        for i in range(qn):
                            stu = arr[i].upper() if i < len(arr) else ""
                            key = answer_key[i] if i < len(answer_key) else ""
                            if stu and key and (stu == key):
                                correct_counts[i] += 1
                    wrong_counts = [total - c for c in correct_counts]
                    perc_correct = [round((c * 100) / total) if total > 0 else 0 for c in correct_counts]

                    item_df = pd.DataFrame({
                        "ข้อ": [i + 1 for i in range(qn)],
                        "ถูก(คน)": correct_counts,
                        "ผิด(คน)": wrong_counts,
                        "%ถูก": perc_correct,
                    })

                    st.subheader("📌 Item Analysis — สรุปการตอบถูกรายข้อ")
                    st.dataframe(item_df, hide_index=True, use_container_width=True)

                    # กราฟ % ถูก (เรียงจากยาก→ง่าย)
                    plot1 = item_df.sort_values("%ถูก", ascending=True)
                    fig1, ax1 = plt.subplots(figsize=(10, max(3.5, 0.55 * len(plot1))))
                    ax1.barh(plot1["ข้อ"].astype(str), plot1["%ถูก"])
                    ax1.set_xlabel("% ถูก", fontsize=12)
                    ax1.set_ylabel("ข้อ", fontsize=12)
                    ax1.set_xlim(0, 100)
                    ax1.set_title("เปอร์เซ็นต์ตอบถูกต่อข้อ (เรียงจากยาก→ง่าย)", fontsize=14, pad=12)
                    for i, v in enumerate(plot1["%ถูก"].tolist()):
                        ax1.text(v + 1, i, f"{v}%", va="center", fontsize=11)
                    plt.tight_layout()
                    st.pyplot(fig1, use_container_width=True)

                    # กราฟซ้อน ถูก/ผิด ต่อข้อ
                    plot2 = item_df.copy()
                    fig2, ax2 = plt.subplots(figsize=(10, max(3.5, 0.55 * len(plot2))))
                    y = plot2["ข้อ"].astype(str)
                    ax2.barh(y, plot2["ผิด(คน)"], label="Wrong")
                    ax2.barh(y, plot2["ถูก(คน)"], left=plot2["ผิด(คน)"], label="Correct")
                    ax2.set_xlabel("จำนวนนักเรียน", fontsize=12)
                    ax2.set_ylabel("ข้อ", fontsize=12)
                    ax2.set_title("จำนวนถูก/ผิด ต่อข้อ (Stacked)", fontsize=14, pad=12)
                    ax2.legend(loc="lower right")
                    plt.tight_layout()
                    st.pyplot(fig2, use_container_width=True)

                    # สรุปข้อยากที่สุด
                    hardest = plot1.iloc[0]
                    st.caption(f"🔎 ข้อที่นักเรียนผิดเยอะที่สุด: ข้อ {hardest['ข้อ']} (ถูก {hardest['%ถูก']}%)")
                else:
                    # 9) ไม่มีเฉลย → แสดงกราฟ distribution ต่อข้อ (A–E/เว้นว่าง)
                    st.subheader("📌 Item Analysis — แจกแจงตัวเลือกต่อข้อ (ยังไม่ทราบเฉลย)")
                    dist_df = []
                    all_opts = ["A", "B", "C", "D", "E", "(blank)"]
                    for i, cnt in enumerate(option_counts, start=1):
                        row = {"ข้อ": i}
                        for o in all_opts:
                            row[o] = cnt.get(o, 0)
                        dist_df.append(row)
                    dist_df = pd.DataFrame(dist_df)
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
# ====================== Run Main App ======================
# ----------------------------------------------------------------------

if mode == "dashboard":
    page_dashboard()
else:
    page_exam()
