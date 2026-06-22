import streamlit as st
import pandas as pd
import re
from datetime import datetime

st.set_page_config(page_title="Vessel Schedule Comparator", page_icon="🚢", layout="wide")

st.markdown("""
<style>
    .main-header { font-family: 'Inter', sans-serif; color: #1E3A8A; font-weight: 700; }
    .stButton>button { background-color: #2563EB; color: white; border-radius: 8px; font-weight: 600; padding: 0.5rem 1rem; transition: all 0.3s; }
    .stButton>button:hover { background-color: #1D4ED8; transform: translateY(-2px); }
    table { width: 100%; border-collapse: collapse; font-family: 'Arial', sans-serif; }
    th { background-color: #f3f4f6; color: #374151; font-weight: bold; text-align: left; padding: 12px; border-bottom: 2px solid #e5e7eb; }
    td { padding: 12px; border-bottom: 1px solid #e5e7eb; color: #1f2937; }
</style>
""", unsafe_allow_html=True)

def clean_vessel_name(name):
    if not isinstance(name, str): return ""
    return " ".join(name.upper().split())

def normalize_time(time_str):
    if not time_str: return ""
    return "".join(time_str.split()).upper()

def parse_datetime(time_str):
    if not time_str: return None
    import re
    # Format 1: 21/06/2026 19:00 or 21/06 19:00
    m_tsv = re.search(r'(\d{1,2})/(\d{1,2})(?:/\d{2,4})?\s+(\d{1,2}):(\d{2})', time_str)
    if m_tsv:
        try:
            return datetime(2000, int(m_tsv.group(2)), int(m_tsv.group(1)), int(m_tsv.group(3)), int(m_tsv.group(4)))
        except ValueError:
            pass
            
    # Format 2: 24th Jun/2100LT
    m_old = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s*([a-zA-Z]{3,})[^\d]*(\d{2})(\d{2})', time_str)
    if m_old:
        try:
            day = int(m_old.group(1))
            month_str = m_old.group(2)[:3].capitalize()
            hour = int(m_old.group(3))
            minute = int(m_old.group(4))
            month = datetime.strptime(month_str, '%b').month
            return datetime(2000, month, day, hour, minute)
        except ValueError:
            pass
            
    return None

def calc_time_diff_hours(old_time_str, new_time_str):
    dt_old = parse_datetime(old_time_str)
    dt_new = parse_datetime(new_time_str)
    if not dt_old or not dt_new:
        return None
    diff = (dt_new - dt_old).total_seconds() / 3600.0
    if diff < -4000:
        dt_new = datetime(2001, dt_new.month, dt_new.day, dt_new.hour, dt_new.minute)
        diff = (dt_new - dt_old).total_seconds() / 3600.0
    elif diff > 4000:
        dt_old = datetime(2001, dt_old.month, dt_old.day, dt_old.hour, dt_old.minute)
        diff = (dt_new - dt_old).total_seconds() / 3600.0
    return diff

def calc_time_diff_html(old_time_str, new_time_str):
    diff = calc_time_diff_hours(old_time_str, new_time_str)
    if diff is None or abs(diff) < 0.01:
        return ""
    if diff > 0:
        return f" <span style='color:#dc2626; font-weight:bold;'>(Trễ {diff:g}h)</span>"
    else:
        return f" <span style='color:#dc2626; font-weight:bold;'>(Sớm {-diff:g}h)</span>"

def parse_schedule(text):
    lines = text.strip().split('\n')
    schedule = []
    if not lines: return schedule
    
    current_vessel = None
    time_pattern = re.compile(r'^(ETA|ETB|ETD)\s*[:\-]?\s*(.+)$', re.IGNORECASE)
    ignore_pattern = re.compile(r'^(Disch|Load|Discharge|POB)\b', re.IGNORECASE)
    
    # Mẫu regex để tìm ra ngày tháng, hỗ trợ cả định dạng mới (Sun 21/06/2026 19:00) và cũ (24th Jun/2100LT)
    datetime_pattern = re.compile(
        r'('
        r'(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+)?\d{1,2}/\d{1,2}(?:/\d{2,4})?\s+\d{1,2}:\d{2}'
        r'|'
        r'\d{1,2}(?:st|nd|rd|th)?\s*[a-zA-Z]{3,}[^\d]*\d{4}(?:LT|lt|Lt)?'
        r')', re.IGNORECASE
    )
    
    for line in lines:
        line = line.strip()
        if not line or 'Vessel Name' in line:
            continue
            
        # Kiểm tra nếu là dòng bắt đầu bằng ETA, ETB, ETD (Cấu trúc cũ)
        time_match = time_pattern.match(line)
        if time_match:
            key, val = time_match.groups()
            key = key.upper()
            if current_vessel:
                current_vessel[key] = val.strip()
        elif ignore_pattern.match(line):
            continue
        else:
            # Tìm tất cả các cụm ngày giờ trong dòng
            dates = list(datetime_pattern.finditer(line))
            if len(dates) >= 1:
                # Nếu có ngày giờ -> Đây là một dòng dữ liệu tàu (Bảng)
                # Tên tàu là tất cả những chữ nằm trước cụm ngày giờ đầu tiên
                v_name = line[:dates[0].start()].strip()
                v_name = " ".join(v_name.split())
                if v_name.upper().startswith("VESSEL:"):
                    v_name = v_name[7:].strip()
                    
                if v_name:
                    schedule.append({
                        'VesselName': v_name,
                        'ETA': '',
                        'ETB': dates[0].group().strip(),
                        'ETD': dates[1].group().strip() if len(dates) > 1 else ''
                    })
            else:
                # Nếu không có ngày giờ nào -> Đây có thể là tên tàu đứng một mình (Cấu trúc cũ)
                if current_vessel:
                    schedule.append(current_vessel)
                
                v_name = line
                if v_name.upper().startswith("VESSEL:"):
                    v_name = v_name[7:].strip()
                    
                current_vessel = {'VesselName': v_name, 'ETA': '', 'ETB': '', 'ETD': ''}
                
    if current_vessel:
        schedule.append(current_vessel)
        
    return schedule

def compare_schedules(sched_old, sched_new):
    dict_old = {clean_vessel_name(v['VesselName']): v for v in sched_old}
    dict_new = {clean_vessel_name(v['VesselName']): v for v in sched_new}
    
    matched_pairs = []
    old_keys = list(dict_old.keys())
    new_keys = list(dict_new.keys())
    
    # 1. Khớp chính xác hoàn toàn (Exact match)
    for k in list(old_keys):
        if k in new_keys:
            matched_pairs.append((k, k))
            old_keys.remove(k)
            new_keys.remove(k)
            
    # 2. Khớp chuỗi bắt đầu (Prefix match) - giải quyết lỗi khác biệt số chuyến (Voyage)
    for old_k in list(old_keys):
        for new_k in list(new_keys):
            if new_k.startswith(old_k) or old_k.startswith(new_k):
                matched_pairs.append((old_k, new_k))
                old_keys.remove(old_k)
                new_keys.remove(new_k)
                break
                
    results = []
    
    # Hàm con để xử lý từng dòng
    def process_row(old_v, new_v, vessel_name):
        status = "Không đổi"
        
        old_etb_display = old_v['ETB'] if old_v and old_v['ETB'] else (old_v['ETA'] if old_v else '')
        new_etb_display = new_v['ETB'] if new_v and new_v['ETB'] else (new_v['ETA'] if new_v else '')
        old_etd_display = old_v['ETD'] if old_v else ''
        new_etd_display = new_v['ETD'] if new_v else ''
        
        if not old_v:
            status = "Thêm mới"
        elif not new_v:
            status = "Đã hủy/Bỏ qua"
        else:
            diff_etb_h = calc_time_diff_hours(old_etb_display, new_etb_display)
            diff_etd_h = calc_time_diff_hours(old_etd_display, new_etd_display)
            
            is_changed = False
            
            if diff_etb_h is not None:
                if abs(diff_etb_h) > 0.01: is_changed = True
            else:
                if normalize_time(old_etb_display) != normalize_time(new_etb_display): is_changed = True
                
            if diff_etd_h is not None:
                if abs(diff_etd_h) > 0.01: is_changed = True
            else:
                if normalize_time(old_etd_display) != normalize_time(new_etd_display): is_changed = True
                
            if is_changed:
                status = "Thay đổi thời gian"
                diff_etb = calc_time_diff_html(old_etb_display, new_etb_display)
                if diff_etb: new_etb_display += diff_etb
                diff_etd = calc_time_diff_html(old_etd_display, new_etd_display)
                if diff_etd: new_etd_display += diff_etd
                
        results.append({
            'Tên Tàu': vessel_name,
            'Trạng thái': status,
            'ETB (Mới)': new_etb_display,
            'ETB (Cũ)': old_etb_display,
            'ETD (Mới)': new_etd_display,
            'ETD (Cũ)': old_etd_display
        })

    # Duyệt qua các cặp đã match
    for old_k, new_k in matched_pairs:
        # Lấy tên dài hơn để hiển thị (thường là tên có chứa số chuyến)
        display_name = dict_new[new_k]['VesselName'] if len(dict_new[new_k]['VesselName']) > len(dict_old[old_k]['VesselName']) else dict_old[old_k]['VesselName']
        process_row(dict_old[old_k], dict_new[new_k], display_name)
        
    # Các tàu chỉ có ở Lịch Cũ (Bị hủy)
    for old_k in old_keys:
        process_row(dict_old[old_k], None, dict_old[old_k]['VesselName'])
        
    # Các tàu chỉ có ở Lịch Mới (Thêm mới)
    for new_k in new_keys:
        process_row(None, dict_new[new_k], dict_new[new_k]['VesselName'])
        
    status_order = {'Thay đổi thời gian': 0, 'Thêm mới': 1, 'Đã hủy/Bỏ qua': 2, 'Không đổi': 3}
    results.sort(key=lambda x: (status_order.get(x['Trạng thái'], 99), x['Tên Tàu']))
    return pd.DataFrame(results)

st.markdown("<h1 class='main-header'>🚢 Công cụ So sánh Lịch Tàu (Bản Đẹp)</h1>", unsafe_allow_html=True)
st.markdown("Copy và paste lịch tàu (dạng text) vào 2 ô bên dưới. Bảng kết quả sẽ in đậm và tô đỏ tự động sự thay đổi về giờ giấc.")

col1, col2 = st.columns(2)
with col1:
    text_new = st.text_area("📄 Lịch Mới", height=250)
with col2:
    text_old = st.text_area("📄 Lịch Cũ", height=250)

if st.button("🚀 Phân tích và So sánh", use_container_width=True):
    if not text_old.strip() or not text_new.strip():
        st.warning("⚠️ Vui lòng dán cả văn bản Lịch cũ và Lịch mới.")
    else:
        with st.spinner("Đang phân tích..."):
            sched1 = parse_schedule(text_old)
            sched2 = parse_schedule(text_new)
            df_results = compare_schedules(sched1, sched2)
            
            st.subheader("📊 Bảng Kết quả So sánh")
            
            def highlight_rows(row):
                status = row['Trạng thái']
                if status == 'Thêm mới':
                    return ['background-color: rgba(34, 197, 94, 0.15)'] * len(row)
                elif status == 'Đã hủy/Bỏ qua':
                    return ['background-color: rgba(239, 68, 68, 0.15)'] * len(row)
                elif status == 'Thay đổi thời gian':
                    return ['background-color: rgba(245, 158, 11, 0.15)'] * len(row)
                else:
                    return [''] * len(row)
                    
            styled_df = df_results.style.apply(highlight_rows, axis=1).hide(axis="index")
            
            # Render HTML to allow spans to work
            html = styled_df.to_html(escape=False)
            st.markdown(html, unsafe_allow_html=True)
