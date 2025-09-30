# app.py
import streamlit as st
import requests
from datetime import datetime
from math import sqrt
import json
from pathlib import Path

# =========================
# 🔧 CONFIG (edit as needed)
# =========================
V_SUPPLY = 120.0  # volts for the "at 120 V" questions

# Tolerances (percentage of expected)
TOL_R_PCT    = 5.0   # measured R within ±5% of instructor-measured reference (kΩ basis)
TOL_VMAX_PCT = 5.0
TOL_I120_PCT = 5.0
TOL_P120_PCT = 5.0

# "Almost" = within 2× tolerance but not within main tolerance
ALMOST_MULT = 2.0

# Apps Script endpoint is stored in Streamlit Secrets
# .streamlit/secrets.toml:
# [apps_script]
# resistor_url = "https://script.google.com/macros/s/XXXX/exec"
APPS_SCRIPT_URL = st.secrets["apps_script"]["resistor_url"]

# =========================
# 📦 Load resistor catalog
# Expect R_nom, R_meas in kΩ and P_rating_W in W.
# =========================
with open(Path("data/resistors.json"), "r") as f:
    RESISTORS = json.load(f)  # keys are "1"..."40"

# =========================
# 🧮 Helpers
# =========================
def pct_close(student_val: float, target_val: float, tol_pct: float) -> bool:
    if target_val == 0:
        return abs(student_val) < 1e-12
    return abs(student_val - target_val) <= (tol_pct / 100.0) * abs(target_val)

def almost_within(student_val: float, target_val: float, tol_pct: float) -> bool:
    if target_val == 0:
        return False
    return (not pct_close(student_val, target_val, tol_pct)) and pct_close(student_val, target_val, tol_pct * ALMOST_MULT)

def verdict_icon(ok: bool, almost: bool = False) -> str:
    if ok:
        return "✅"
    if almost:
        return "⚠️"
    return "❌"

def expected_from_measured(R_meas_ohm: float, P_rating_W: float):
    Vmax = sqrt(P_rating_W * R_meas_ohm)        # sqrt(P * R)
    I120 = V_SUPPLY / R_meas_ohm                # V / R
    P120 = (V_SUPPLY * V_SUPPLY) / R_meas_ohm   # V^2 / R
    return Vmax, I120, P120

def log_submission(payload: dict):
    try:
        r = requests.post(APPS_SCRIPT_URL, json=payload, timeout=8)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)

# =========================
# 🖥️ UI
# =========================
st.set_page_config(page_title="PHY 132 – Resistor Checker", page_icon="🧪")
st.title("PHY 132 – Resistor Power & Ohm’s Law Checker")
st.write("Enter your values based on the resistor you were assigned. You’ll get instant feedback; correct submissions are recorded for credit.")

with st.expander("📘 What does the power rating mean?"):
    st.markdown(
        "The **power rating** (e.g., **1 W** or **0.5 W**) is the **maximum safe power** the resistor can dissipate. "
        "Actual power depends on the applied voltage and current: "
        r"$P = VI = I^2R = \dfrac{V^2}{R}$. "
        "For each resistor below, we use its specific rating from the catalog to compute the safe maximum voltage."
    )

colA, colB = st.columns(2)
with colA:
    student_name    = st.text_input("Name (for credit)")
with colB:
    student_comment = st.text_input("Comment (optional)")

res_num = st.number_input("Enter your resistor number (1–40)", min_value=1, max_value=40, step=1)
rinfo = RESISTORS.get(str(int(res_num)))
if not rinfo:
    st.stop()
    
# Reference (in kΩ from JSON)
R_ref_kohm = float(rinfo["R_meas"])
R_ref_ohm  = R_ref_kohm * 1e3
P_rating_W   = float(rinfo.get("P_rating_W", 1.0))  # default to 1 W if missing

st.info(f"Resistor #{res_num} — **Rating:** {P_rating_W:g} W")

st.subheader("Enter your measured/calculated values")
c1, c2 = st.columns(2)
with c1:
    R_student_kohm = st.number_input("Measured resistance R (kΩ)", min_value=0.0, step=0.01, format="%.2f")
    Vmax      = st.number_input("Maximum safe voltage V_max (V)", min_value=0.0, step=0.01, format="%.2f")
with c2:
    I_120_mA     = st.number_input("Current at 120 V (mA)", min_value=0.0, step=0.001, format="%.3f")
    P_120_mW     = st.number_input("Power at 120 V (mW)",  min_value=0.0, step=0.01, format="%.2f")

I_120  = I_120_mA * 1e-3
P_120  = P_120_mW * 1e-3

# Expected values from the INSTRUCTOR-MEASURED resistance (convert to Ω for physics)
Vmax_exp, I120_exp, P120_exp = expected_from_measured(R_ref_ohm)

if st.button("Check my answers"):
    # Part checks vs expected derived from instructor-measured R
    r_ok     = pct_close(R_student_kohm, R_ref_kohm,     TOL_R_PCT)
    vmax_ok  = pct_close(Vmax,      Vmax_exp,  TOL_VMAX_PCT)
    i120_ok  = pct_close(I_120,     I120_exp,  TOL_I120_PCT)
    p120_ok  = pct_close(P_120,     P120_exp,  TOL_P120_PCT)

    r_almost     = almost_within(R_student_kohm, R_ref_kohm,     TOL_R_PCT)
    vmax_almost  = almost_within(Vmax,      Vmax_exp,  TOL_VMAX_PCT)
    i120_almost  = almost_within(I_120,     I120_exp,  TOL_I120_PCT)
    p120_almost  = almost_within(P_120,     P120_exp,  TOL_P120_PCT)

    all_correct = r_ok and vmax_ok and i120_ok and p120_ok
    any_almost  = r_almost or vmax_almost or i120_almost or p120_almost

    st.markdown("### Results")
    st.write(f"{verdict_icon(r_ok, r_almost)} **Measured R**")
            #  f" - yours: {R_student_kohm:.6g} kΩ | expected: {R_ref_kohm:.6g} Ω (±{TOL_R_PCT:.0f}%)")
    st.write(f"{verdict_icon(vmax_ok, vmax_almost)} **V_max**")
            #  f" - yours: {Vmax:.6g} V | expected: {Vmax_exp:.6g} V (±{TOL_VMAX_PCT:.0f}%)")
    st.write(f"{verdict_icon(i120_ok, i120_almost)} **I at 120 V**")
            #  f" - yours: {I_120:.6g} A | expected: {I120_exp:.6g} A (±{TOL_I120_PCT:.0f}%)")
    st.write(f"{verdict_icon(p120_ok, p120_almost)} **P at 120 V**")
            #  f" - yours: {P_120:.6g} W | expected: {P120_exp:.6g} W (±{TOL_P120_PCT:.0f}%)")

    if all_correct:
        st.success("✅ All correct! Your submission has been recorded for full credit.")
        result_label = "Correct"
    elif any_almost:
        st.warning("⚠️ Close. Some answers are within 2× tolerance but not within the main tolerance.")
        result_label = "Almost"
    else:
        st.error("❌ Not quite. Re-check your calculations and try again.")
        result_label = "Incorrect"

    # Log to Google Sheets via Apps Script
    payload = {
        "Time Stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # "sheet": "2.2-Resistors",   # handle this sheet name in your Apps Script
        # "secret": st.secrets["apps_script"].get("shared_secret", ""),
        "Name": student_name,
        "Comment": student_comment,
        "Resistor #": str(int(res_num)),
        "R_ref (kΩ)": R_ref_kohm,
        "R_student (kΩ)": R_student_kohm,
        "Vmax (V)": Vmax,
        "Vmax_exp (V)": Vmax_exp,
        "I_120V (mA)": I_120_mA,
		"I120_exp (mA)": I120_exp * 1e3,
        "P_120V (mW)": P_120_mW,
        "P120_exp (mW)": P120_exp * 1e3,
        # "tolerances_pct": {
        #     "R": TOL_R_PCT,
        #     "Vmax": TOL_VMAX_PCT,
        #     "I120": TOL_I120_PCT,
        #     "P120": TOL_P120_PCT
        # },
        "result": result_label
    }
    
    status, resp = log_submission(payload)
    if status != 200:
        st.info("Note: logging issue encountered. Your local check ran fine—please try again soon or notify your instructor.")
        st.caption(f"(Logging status {status}: {resp})")

# Footer
st.markdown("""
---
<div style="display:flex;justify-content:space-between;align-items:center;">
  <div>
    Built for <b>PHY 132 – College Physics II</b> at Eastern Kentucky University.<br>
    Contact: <b>Professor Zakeri</b> (m.zakeri@eku.edu)
  </div>
  <div>
    <img src="https://raw.githubusercontent.com/ZAKI1905/phy132-kirchhoff-checker/main/img/PrimaryLogo_Maroon.png" width="150">
  </div>
</div>
""", unsafe_allow_html=True)