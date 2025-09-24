import streamlit as st
import pandas as pd
import io
import zipfile
import requests
from math import radians, sin, cos, sqrt, atan2
from concurrent.futures import ThreadPoolExecutor
import os
from fpdf import FPDF

st.set_page_config(page_title="Helper Tool- Sahil", layout="wide")
st.title("📦 Helper Tool - Sahil (Beginner Friendly, CSV Only)")

# ---------------------- Utilities ----------------------
METRO_RANGES = [
    range(110001, 110099), range(400001, 400105), range(700001, 700105),
    range(600001, 600119), range(560001, 560108), range(500001, 500099),
    range(380001, 380062), range(411001, 411063), range(122001, 122019)
]

def is_metro(pin): return any(int(pin) in r for r in METRO_RANGES)

def get_location(pin):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(f"https://api.postalpincode.in/pincode/{pin}", timeout=10, headers=headers)
        data = res.json()
        if data[0]["Status"].lower() == "success":
            po = data[0]["PostOffice"][0]
            return po.get("Name",""), po.get("District",""), po.get("State","")
    except: 
        return "Unknown", "Unknown", "Unknown"
    return "Unknown", "Unknown", "Unknown"

def get_latlon(pin):
    try:
        url = f"https://nominatim.openstreetmap.org/search?postalcode={pin}&country=India&format=json"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = res.json()
        if data: return float(data[0]['lat']), float(data[0]['lon'])
    except: pass
    return None, None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return round(R*2*atan2(sqrt(a), sqrt(1-a)),2)

def classify_zone(fpin, tpin, fd, fs, td, ts):
    special = {"himachal pradesh", "karnataka", "jammu & kashmir", "west bengal", "assam",
               "manipur", "mizoram", "nagaland", "tripura", "meghalaya", "sikkim", "arunachal pradesh"}
    if fpin == tpin: return "LOCAL"
    if fd.lower() == td.lower() and fd != "N/A": return "LOCAL"
    if is_metro(fpin) and is_metro(tpin): return "METRO"
    if fs.lower() == ts.lower(): return "REGIONAL"
    if fs.lower() in special or ts.lower() in special: return "SPECIAL"
    return "ROI"

def process(row):
    f, t = str(row['from_pincode']), str(row['to_pincode'])
    fc, fd, fs = get_location(f)
    tc, td, ts = get_location(t)
    lat1, lon1 = get_latlon(f)
    lat2, lon2 = get_latlon(t)
    dist = haversine(lat1, lon1, lat2, lon2) if None not in [lat1, lon1, lat2, lon2] else "N/A"
    zone = classify_zone(f, t, fd, fs, td, ts)
    return {"From": f, "To": t, "From City": fc, "From State": fs, "To City": tc,
            "To State": ts, "Distance (KM)": dist, "Zone": zone}

def clean_dataframe(df):
    df = df.drop_duplicates()
    df = df.dropna(how='all')
    df.columns = [str(c).strip().title() for c in df.columns]
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    return df

def summarize_dataframe(df, col=None):
    summary = {"Total Rows": len(df)}
    if col and col in df.columns:
        summary["Unique Values"] = df[col].nunique()
        top5 = df[col].value_counts().head(5).to_dict()
        summary["Top 5 Values"] = top5
    return summary

# ---------------------- Sidebar ----------------------
tool = st.sidebar.selectbox("Choose Tool", [
    "Data Compiler",
    "Files Splitter",
    "Pincode Zone + Distance",
    "Data Cleaner & Summary",
    "Create Folders from List"
])
st.sidebar.markdown("---")
st.sidebar.markdown("💡 **Tips for Beginners:**")
st.sidebar.markdown("""
- Upload Excel/CSV files in correct format.
- Use 'Data Compiler' to combine multiple files.
- Use 'Files Splitter' to split large files by a column.
- 'Pincode Zone + Distance' helps classify and calculate distances.
- 'Data Cleaner & Summary' cleans files and shows basic stats.
- 'Create Folders from List' generates folders, ZIP, or PDF download.
- All downloads are in CSV format to avoid dependency issues.
""")

# ---------------------- Data Compiler ----------------------
if tool=="Data Compiler":
    st.header("📁 Data Compiler (CSV Only)")
    files = st.file_uploader("Upload CSV/Excel", type=["csv","xlsx"], accept_multiple_files=True)
    if files:
        dfs=[]
        for f in files:
            df0 = pd.read_csv(f) if f.name.endswith(".csv") else pd.read_excel(f)
            df0["Source File"] = f.name
            dfs.append(df0)
        if dfs:
            df_all = pd.concat(dfs, ignore_index=True).fillna("")
            st.dataframe(df_all, use_container_width=True)
            st.download_button("⬇️ Download Compiled CSV", df_all.to_csv(index=False).encode(), "compiled.csv")

# ---------------------- Files Splitter ----------------------
elif tool=="Files Splitter":
    st.header("📂 Files Splitter")
    uploaded_file = st.file_uploader("Upload CSV/Excel", type=["csv","xlsx"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
        st.dataframe(df.head(), use_container_width=True)
        col_to_split = st.selectbox("Select column to split by", df.columns)
        output_mode = st.radio("Output Mode", ["Single CSV per sheet (ZIP)", "Multiple CSV Files (ZIP)"])
        if col_to_split:
            unique_vals = df[col_to_split].dropna().unique().tolist()
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                for val in unique_vals:
                    df_val = df[df[col_to_split]==val]
                    zip_file.writestr(f"{val}.csv", df_val.to_csv(index=False).encode())
            st.download_button("⬇️ Download ZIP of CSVs", zip_buffer.getvalue(), "split_files.zip")

# ---------------------- Pincode Zone + Distance ----------------------
elif tool=="Pincode Zone + Distance":
    st.header("📍 Pincode Zone + Distance")
    mode = st.radio("Mode", ["Upload File","Manual Pairs"])
    if mode=="Upload File":
        fl=st.file_uploader("Upload CSV/XLSX with columns from_pincode,to_pincode", type=["csv","xlsx"])
        if fl:
            df0=pd.read_csv(fl) if fl.name.endswith(".csv") else pd.read_excel(fl)
            if 'from_pincode' in df0.columns and 'to_pincode' in df0.columns:
                with st.spinner("Processing pincodes..."):
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        out=list(executor.map(process, df0.to_dict("records")))
                dfRes=pd.DataFrame(out)
                st.dataframe(dfRes, use_container_width=True)
                st.download_button("⬇️ Download CSV", dfRes.to_csv(index=False).encode(), "zones.csv")
    else:
        txt=st.text_area("Enter pairs as 'from,to' per line",height=200)
        if txt:
            pairs=[line.split(",") for line in txt.splitlines() if "," in line]
            df_pairs=pd.DataFrame(pairs,columns=["from_pincode","to_pincode"])
            out=[process(r) for r in df_pairs.to_dict("records")]
            st.dataframe(pd.DataFrame(out),use_container_width=True)
            st.download_button("⬇️ Download CSV", pd.DataFrame(out).to_csv(index=False).encode(), "zones_manual.csv")

# ---------------------- Data Cleaner & Summary ----------------------
elif tool=="Data Cleaner & Summary":
    st.header("🧹 Data Cleaner & Summary")
    uploaded_file = st.file_uploader("Upload CSV/Excel", type=["csv","xlsx"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
        df_clean = clean_dataframe(df)
        st.subheader("Cleaned Data")
        st.dataframe(df_clean, use_container_width=True)
        st.download_button("⬇️ Download Cleaned CSV", df_clean.to_csv(index=False).encode(), "cleaned_file.csv")
        col = st.selectbox("Select column for summary", df_clean.columns)
        if col:
            summary = summarize_dataframe(df_clean, col)
            st.subheader("Summary")
            st.json(summary)

# ---------------------- Create Folders from List (with PDF) ----------------------
elif tool=="Create Folders from List":
    st.header("📂 Create Folders from List")
    txt = st.text_area("Enter folder names, one per line", height=200)
    base_folder = "Created_Folders"
    os.makedirs(base_folder, exist_ok=True)

    if st.button("✅ Create Folders"):
        folder_names = [line.strip() for line in txt.splitlines() if line.strip()]

        # Create folders + ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for name in folder_names:
                folder_path = os.path.join(base_folder, name)
                os.makedirs(folder_path, exist_ok=True)
                zf.writestr(f"{name}/", "")
        st.success(f"{len(folder_names)} folders created in '{base_folder}'!")
        st.download_button("⬇️ Download Folders as ZIP", zip_buffer.getvalue(), "folders.zip")

        # Create PDF of folder names
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, "Folder Names", ln=True, align="C")
        pdf.ln(5)
        for idx, name in enumerate(folder_names, 1):
            pdf.cell(0, 8, f"{idx}. {name}", ln=True)
        pdf_buffer = io.BytesIO()
        pdf.output(pdf_buffer)
        st.download_button("⬇️ Download Folder Names as PDF", pdf_buffer.getvalue(), "folders.pdf")
