import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# ----------------------------
# Simple Login (Can be replaced by streamlit-authenticator)
# ----------------------------

def login():
    st.title("Inventory Cleanup & Visualizer")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == "admin" and password == "12345":
            st.session_state["authenticated"] = True
        else:
            st.error("Invalid credentials")

if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    login()
    st.stop()

# ----------------------------
# Upload Excel
# ----------------------------

st.sidebar.title("Upload Inventory File")
uploaded_file = st.sidebar.file_uploader("Upload Excel file with 'Sheet' sheet", type=["xlsx"])

if not uploaded_file:
    st.info("Please upload an Excel file to continue.")
    st.stop()

# ----------------------------
# Load and Clean Data
# ----------------------------

@st.cache_data
def load_data(file):
    xl = pd.ExcelFile(file)
    if "Sheet" not in xl.sheet_names:
        st.error("Sheet named 'Sheet' not found in file.")
        return None
    df = xl.parse("Sheet", skiprows=14)
    return df

df = load_data(uploaded_file)
if df is None:
    st.stop()

df.columns = [str(c).strip().lower() for c in df.columns]
required = ['item code', 'barcode', 'item description', 'qty in stock', 'cost usd']
for col in required:
    if col not in df.columns:
        st.error(f"Missing required column: {col}")
        st.stop()

df = df[df['item code'].astype(str).str.startswith(('SH', 'RL'))]
df = df[df['item description'].notnull()]

def get_base(code):
    return code[:-1] if isinstance(code, str) and len(code) > 1 else code

df['item_code_base'] = df['item code'].apply(get_base)

# Grouping
grouped = {}
for _, row in df.iterrows():
    key = row['item_code_base']
    desc = row['item description']
    bonded = 'bonded' in str(desc).lower()
    qty = row['qty in stock']
    cost = row['cost usd']
    barcode = row['barcode']

    if key not in grouped:
        grouped[key] = {
            'qty': qty,
            'cost_sum': qty * cost,
            'barcode': barcode,
            'desc': desc if not bonded else '',
            'has_non_bonded': not bonded
        }
    else:
        grouped[key]['qty'] += qty
        grouped[key]['cost_sum'] += qty * cost
        if not bonded and not grouped[key]['has_non_bonded']:
            grouped[key]['desc'] = desc
            grouped[key]['has_non_bonded'] = True

# Build final DataFrame
cleaned = pd.DataFrame([{
    'Item Code Base': k,
    'BarCode': v['barcode'],
    'Item Description': v['desc'],
    'Qty (Total)': round(v['qty'], 2),
    'Cost (Avg)': round(v['cost_sum'] / v['qty'], 2) if v['qty'] else 0
} for k, v in grouped.items()])

st.success("✅ Cleanup complete.")

# ----------------------------
# Visualize by Color Code
# ----------------------------

st.header("🎨 Visual by Color Code")
cleaned['Color Code'] = cleaned['Item Code Base'].astype(str).str[-5:]
color_groups = cleaned.groupby('Color Code')

# Use 2 wide columns with full width tables
cols = st.columns(2)
others = []
col_index = 0

for color, group in sorted(color_groups, key=lambda x: x[0]):
    if len(group) == 1:
        others.append(group)
        continue

  with cols[col_index]:
        with st.container():
            st.subheader(f"Color {color}")
            st.dataframe(
                group[['Item Description', 'Qty (Total)']].reset_index(drop=True),
                use_container_width=True
            )

            
    col_index = (col_index + 1) % 2

# Show single-item color groups
if others:
    st.markdown("---")
    st.subheader("Other Colors (1 item only)")
    others_df = pd.concat(others)
    st.dataframe(
        others_df[['Item Description', 'Qty (Total)']].reset_index(drop=True),
        use_container_width=True
    )

# ----------------------------
# Export to Excel
# ----------------------------

def to_excel_download(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output

st.markdown("---")
st.download_button(
    "📥 Download Cleaned Excel",
    data=to_excel_download(cleaned),
    file_name="cleaned_inventory.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
