import streamlit as st
import pandas as pd
import io
import zipfile
import requests
from math import radians, sin, cos, sqrt, atan2
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Helper Tool- Sahil", layout="wide")
st.title("📦 Helper Tool - Sahil (Beginner Friendly)")

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
    "File Format Converter",
    "Data Cleaner & Summary",
    "Merge Two Files"
])
st.sidebar.markdown("---")
st.sidebar.markdown("💡 **Tips for Beginners:**")
st.sidebar.markdown("""
- Upload Excel/CSV files in correct format.
- Use 'Data Compiler' to combine multiple files.
- Use 'Files Splitter' to split large files by a column.
- 'Pincode Zone + Distance' helps classify and calculate distances.
- 'File Format Converter' easily converts CSV ↔ Excel.
- 'Data Cleaner & Summary' cleans files and shows basic stats.
- 'Merge Two Files' merges files on a selected column.
""")

# ---------------------- Data Compiler ----------------------
if tool=="Data Compiler":
    st.header("📁 Data Compiler (Excel/CSV Only)")
    files = st.file_uploader("Upload Excel/CSV", type=["xlsx","csv"], accept_multiple_files=True)
    if files:
        dfs=[]
        for f in files:
            df0 = pd.read_csv(f) if f.name.endswith(".csv") else pd.read_excel(f)
            df0["Source File"] = f.name
            dfs.append(df0)
        if dfs:
            df_all = pd.concat(dfs, ignore_index=True).fillna("")
            st.dataframe(df_all, use_container_width=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as w:  # ✅ Changed engine
                df_all.to_excel(w, index=False)
            st.download_button("⬇️ Download Excel", buf.getvalue(), "compiled.xlsx")

# ---------------------- Files Splitter ----------------------
elif tool=="Files Splitter":
    st.header("📂 Files Splitter")
    uploaded_file = st.file_uploader("Upload Excel/CSV", type=["xlsx","csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
        st.dataframe(df.head(), use_container_width=True)
        col_to_split = st.selectbox("Select column to split by", df.columns)
        output_mode = st.radio("Output Format", ["Single Excel (Multiple Sheets)","Multiple Excel Files (ZIP)"])
        if col_to_split:
            unique_vals = df[col_to_split].dropna().unique().tolist()
            if output_mode=="Single Excel (Multiple Sheets)":
                buffer=io.BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    for val in unique_vals:
                        df_val = df[df[col_to_split]==val]
                        df_val.to_excel(writer, sheet_name=str(val)[:31], index=False)
                st.download_button("⬇️ Download Split Excel", buffer.getvalue(), "split_output.xlsx")
            else:
                zip_buffer=io.BytesIO()
                with zipfile.ZipFile(zip_buffer,"w") as zip_file:
                    for val in unique_vals:
                        df_val=df[df[col_to_split]==val]
                        excel_bytes=io.BytesIO()
                        with pd.ExcelWriter(excel_bytes, engine="xlsxwriter") as writer:
                            df_val.to_excel(writer, index=False)
                        zip_file.writestr(f"{val}.xlsx", excel_bytes.getvalue())
                st.download_button("⬇️ Download ZIP of Files", zip_buffer.getvalue(), "split_files.zip")

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
                # Highlight unknown pincodes
                dfRes_styled = dfRes.style.applymap(lambda x: 'background-color: #ffcccc' if x=="Unknown" else '')
                st.dataframe(dfRes_styled,use_container_width=True)
                st.download_button("⬇️ Download CSV", dfRes.to_csv(index=False).encode(), "zones.csv")
    else:
        txt=st.text_area("Enter pairs as 'from,to' per line",height=200)
        if txt:
            pairs=[line.split(",") for line in txt.splitlines() if "," in line]
            df_pairs=pd.DataFrame(pairs,columns=["from_pincode","to_pincode"])
            out=[process(r) for r in df_pairs.to_dict("records")]
            st.dataframe(pd.DataFrame(out),use_container_width=True)

# ---------------------- File Format Converter ----------------------
elif tool=="File Format Converter":
    st.header("🔄 File Format Converter")
    uploaded_file = st.file_uploader("Upload Excel/CSV", type=["xlsx","csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
        if uploaded_file.name.endswith(".csv"):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as w: 
                df.to_excel(w, index=False)
            st.download_button("⬇️ Download as Excel", buf.getvalue(), uploaded_file.name.replace(".csv",".xlsx"))
        else:
            st.download_button("⬇️ Download as CSV", df.to_csv(index=False).encode(), uploaded_file.name.replace(".xlsx",".csv"))

# ---------------------- Data Cleaner & Summary ----------------------
elif tool=="Data Cleaner & Summary":
    st.header("🧹 Data Cleaner & Summary")
    uploaded_file = st.file_uploader("Upload Excel/CSV", type=["xlsx","csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
        df_clean = clean_dataframe(df)
        st.subheader("Cleaned Data")
        st.dataframe(df_clean, use_container_width=True)
        st.download_button("⬇️ Download Cleaned File", df_clean.to_csv(index=False).encode(), "cleaned_file.csv")
        col = st.selectbox("Select column for summary", df_clean.columns)
        if col:
            summary = summarize_dataframe(df_clean, col)
            st.subheader("Summary")
            st.json(summary)

# ---------------------- Merge Two Files ----------------------
elif tool=="Merge Two Files":
    st.header("🔗 Merge Two Files")
    uploaded_files = st.file_uploader("Upload 2 Excel/CSV files", type=["xlsx","csv"], accept_multiple_files=True)
    if uploaded_files and len(uploaded_files)==2:
        df1 = pd.read_csv(uploaded_files[0]) if uploaded_files[0].name.endswith(".csv") else pd.read_excel(uploaded_files[0])
        df2 = pd.read_csv(uploaded_files[1]) if uploaded_files[1].name.endswith(".csv") else pd.read_excel(uploaded_files[1])
        merge_col = st.selectbox("Select column to merge on", df1.columns.intersection(df2.columns))
        if merge_col:
            df_merged = pd.merge(df1, df2, on=merge_col, how='outer')
            st.dataframe(df_merged, use_container_width=True)
            st.download_button("⬇️ Download Merged File", df_merged.to_csv(index=False).encode(), "merged_file.csv")
