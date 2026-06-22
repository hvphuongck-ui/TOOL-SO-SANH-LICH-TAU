import streamlit as st # Force restart 2
import os
import sys
import tempfile

# Cấu hình đường dẫn để import code từ thư mục gốc (.openclaw)
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from parser import parse_schedule_text
    import config_manager
    from game_plan_generator import generate_game_plan
except ImportError as e:
    st.error(f"Lỗi khi import thư viện cốt lõi: {e}")
    st.stop()

# --- MERGED PDF GENERATOR ---
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color, black, white
from datetime import timedelta
import math

def hex_to_color(hex_str):
    if not isinstance(hex_str, str): return Color(0,0,0,1)
    hex_str = hex_str.lstrip('#').strip()
    if len(hex_str) != 6: return Color(0,0,0,1)
    try:
        return Color(int(hex_str[0:2],16)/255.0, int(hex_str[2:4],16)/255.0, int(hex_str[4:6],16)/255.0, 1)
    except:
        return Color(0,0,0,1)

def get_contrast_color(hex_color):
    if not isinstance(hex_color, str): return "#000000"
    hex_color = hex_color.lstrip('#').strip()
    if len(hex_color) != 6: return "#000000"
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#000000" if luminance > 0.5 else "#FFFFFF"
    except:
        return "#000000"

def generate_pdf(vessels, output_path):
    if not vessels: return False
    base_date = vessels[0]["etb"].replace(hour=0, minute=0, second=0, microsecond=0)
    max_etd = max(v["etd"] for v in vessels)
    total_days = (max_etd - base_date).days + 2
    px_per_hour = 4
    row_height_px = 96
    cols_berth = 20
    col_berth_width_px = 40
    col_bouy_width_px = math.ceil(55 * (col_berth_width_px / 30))
    date_col_width_px = 85
    header_row0_px = 30
    header_row1_px = 20
    header_height_px = header_row0_px + header_row1_px
    total_width = date_col_width_px + col_bouy_width_px + (cols_berth + 1) * col_berth_width_px + 50
    total_height = header_height_px + total_days * row_height_px + 50
    c = canvas.Canvas(output_path, pagesize=(total_width, total_height))
    
    def draw_rect(x, y, w, h, bg="#FFFFFF", border="#000000"):
        c.setFillColor(hex_to_color(bg))
        c.setStrokeColor(hex_to_color(border))
        c.rect(x, total_height - y - h, w, h, fill=1, stroke=1)
        
    def draw_text(x, y, w, h, text, font_size=9, color="#000000", bold=True, is_header=False):
        c.setFillColor(hex_to_color(color))
        if bold: c.setFont("Helvetica-Bold", font_size)
        else: c.setFont("Helvetica", font_size)
        lines = text.split('\n')
        line_height = font_size + 2
        total_text_height = len(lines) * line_height
        start_y = total_height - y - (h/2) + (total_text_height/2) - font_size
        for i, line in enumerate(lines):
            text_width = c.stringWidth(line, "Helvetica-Bold" if bold else "Helvetica", font_size)
            c.saveState()
            path = c.beginPath()
            path.rect(x+2, total_height - y - h + 2, w-4, h-4)
            c.clipPath(path, stroke=0, fill=0)
            c.drawString(x + (w - text_width)/2, start_y - i*line_height, line)
            c.restoreState()

    draw_rect(0, 0, date_col_width_px, header_height_px, "#D3D3D3")
    draw_text(0, 0, date_col_width_px, header_height_px, "Date", 10)
    draw_rect(date_col_width_px, 0, col_bouy_width_px + cols_berth*col_berth_width_px, header_row0_px, "#D3D3D3")
    draw_text(date_col_width_px, 0, col_bouy_width_px + cols_berth*col_berth_width_px, header_row0_px, "SSIT GAME PLAN", 12)
    draw_rect(date_col_width_px, header_row0_px, col_bouy_width_px, header_row1_px, "#D3D3D3")
    draw_text(date_col_width_px, header_row0_px, col_bouy_width_px, header_row1_px, "Bouy (55m)", 9)
    for i in range(cols_berth):
        x = date_col_width_px + col_bouy_width_px + i * col_berth_width_px
        draw_rect(x, header_row0_px, col_berth_width_px, header_row1_px, "#D3D3D3")
        draw_text(x, header_row0_px, col_berth_width_px, header_row1_px, str((i+1)*30), 9)

    for i in range(total_days):
        y = header_height_px + i * row_height_px
        current_date = base_date + timedelta(days=i)
        date_str = current_date.strftime("%d/%m") + "\n" + current_date.strftime("%A")
        draw_rect(0, y, date_col_width_px, row_height_px, "#FFFFFF")
        draw_text(0, y, date_col_width_px, row_height_px, date_str, 9)
        draw_rect(date_col_width_px, y, col_bouy_width_px, row_height_px, "#FFFFFF", "#E0E0E0")
        for j in range(cols_berth):
            draw_rect(date_col_width_px + col_bouy_width_px + j*col_berth_width_px, y, col_berth_width_px, row_height_px, "#FFFFFF", "#E0E0E0")
        for hour in range(2, 24, 2):
            line_y = y + hour * px_per_hour
            color = '#A0A0A0' if hour == 12 else '#E0E0E0'
            c.setStrokeColor(hex_to_color(color))
            c.line(date_col_width_px, total_height - line_y, date_col_width_px + col_bouy_width_px + cols_berth*col_berth_width_px, total_height - line_y)

    placed_ships = []
    for v in vessels:
        duration_hours = (v["etd"] - v["etb"]).total_seconds() / 3600
        v["duration_hours"] = duration_hours
        v["draw_start_time"] = v["etb"]
        v["draw_end_time"] = v["etb"] + timedelta(hours=duration_hours)
        v["is_delayed"] = False
        v["position"] = "right"
        overlaps = [s for s in placed_ships if s["draw_end_time"] > v["draw_start_time"]]
        if overlaps:
            blocker = max(overlaps, key=lambda x: x["draw_end_time"])
            if len(overlaps) == 1:
                prev_v = overlaps[0]
                if v["loa"] + prev_v["loa"] <= 535:
                    if prev_v.get("locked_position"):
                        v["position"] = "right" if prev_v["position"] == "left" else "left"
                    else:
                        if v["loa"] < prev_v["loa"]:
                            v["position"] = "left"
                            prev_v["position"] = "right"
                        else:
                            v["position"] = "right"
                            prev_v["position"] = "left"
                    v["locked_position"] = True
                    prev_v["locked_position"] = True
                else:
                    v["draw_start_time"] = blocker["draw_end_time"]
                    v["draw_end_time"] = v["draw_start_time"] + timedelta(hours=duration_hours)
                    v["is_delayed"] = True
                    v["position"] = blocker["position"]
            else:
                v["draw_start_time"] = blocker["draw_end_time"]
                v["draw_end_time"] = v["draw_start_time"] + timedelta(hours=duration_hours)
                v["is_delayed"] = True
                v["position"] = blocker["position"]
        placed_ships.append(v)

    for v in placed_ships:
        hours_since_base = (v["draw_start_time"] - base_date).total_seconds() / 3600
        y_offset = header_height_px + hours_since_base * px_per_hour
        height = v["duration_hours"] * px_per_hour
        width = math.ceil(v["loa"] * (col_berth_width_px / 30))
        if v["position"] == "left":
            x_offset = date_col_width_px + col_bouy_width_px + 1 * col_berth_width_px
        else:
            x_570m = date_col_width_px + col_bouy_width_px + 19 * col_berth_width_px
            x_offset = x_570m - width
        etb_str = v["etb"].strftime("%d/%H:%M")
        etd_str = v["etd"].strftime("%d/%H:%M")
        duration_h_str = f"{(v['etd'] - v['etb']).total_seconds() / 3600:g}"
        line1 = v.get("clean_name", "")
        if v.get("parsed_voyage"): line1 += f" {v['parsed_voyage']}"
        line1 += f" ({etb_str} - {etd_str} | {duration_h_str}h) - {v['loa']}m - {v.get('parsed_service', '')}"
        disch_val = v.get("disch")
        load_val = v.get("load")
        if disch_val is None and load_val is None:
            line2 = "Disch:    , Load:    --> Total:    "
        else:
            d = int(disch_val) if disch_val else 0
            l = int(load_val) if load_val else 0
            line2 = f"Disch: {d}, Load: {l} --> Total: {d+l}"
        text = f"{line1}\n{line2}"
        bg_color = v.get("color", "#D3D3D3")
        font_color = get_contrast_color(bg_color)
        draw_rect(x_offset, y_offset, width, height, bg_color, "#000000")
        draw_text(x_offset, y_offset, width, height, text, 8, font_color, True)
        needs_tbu = v.get("is_delayed", False)
        if not needs_tbu:
            for other in placed_ships:
                if other is not v and other["etb"] == v["etb"] and other["position"] == v["position"]:
                    needs_tbu = True
                    break
        if needs_tbu:
            stamp_w, stamp_h = 47, 22
            sx = x_offset + width - stamp_w - 5
            sy = y_offset + 5
            draw_rect(sx, sy, stamp_w, stamp_h, "#FFFF00", "#FF0000")
            draw_text(sx, sy, stamp_w, stamp_h, "TBU", 10, "#FF0000", True)
    c.save()
    return True
# --- END MERGED PDF GENERATOR ---

st.set_page_config(page_title="Tạo Game Plan (Excel)", page_icon="🚢", layout="centered")

st.markdown("""
<style>
    .main-header { font-family: 'Inter', sans-serif; color: #1E3A8A; font-weight: 700; }
    .stButton>button { background-color: #2563EB; color: white; border-radius: 8px; font-weight: 600; padding: 0.5rem 1rem; transition: all 0.3s; }
    .stButton>button:hover { background-color: #1D4ED8; transform: translateY(-2px); }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-header'>🚢 Công cụ tự động vẽ Game Plan (Berth Chart)</h1>", unsafe_allow_html=True)
st.markdown("Copy và paste đoạn text chứa lịch tàu vào ô bên dưới, hệ thống sẽ tự động bóc tách và vẽ sơ đồ Game Plan thành file Excel cho bạn tải về.")

raw_text = st.text_area("📄 Nhập dữ liệu Lịch tàu (Raw Text):", height=250)

if st.button("🚀 Xử lý và Tạo File Excel", use_container_width=True):
    if not raw_text.strip():
        st.warning("⚠️ Vui lòng dán dữ liệu lịch tàu vào ô bên trên.")
    else:
        with st.spinner("Đang phân tích dữ liệu và vẽ sơ đồ..."):
            vessels_data = parse_schedule_text(raw_text)
            
            if not vessels_data:
                st.error("❌ Không nhận diện được tàu nào. Vui lòng kiểm tra lại định dạng text.")
            else:
                config = config_manager.load_config()
                
                # Tạo file tạm thời trên máy chủ
                temp_dir = tempfile.gettempdir()
                output_path = os.path.join(temp_dir, "Game_Plan.xlsx")
                
                success, msg, missing_info = generate_game_plan(vessels_data, config, output_path)
                
                if success:
                    # Tạo file PDF
                    pdf_path = os.path.join(temp_dir, "Game_Plan.pdf")
                    pdf_success = False
                    try:
                        generate_pdf(vessels_data, pdf_path)
                        pdf_success = True
                    except Exception as e:
                        print(f"PDF Error: {e}")
                    
                    if missing_info and missing_info.get("services"):
                        st.warning("⚠️ Đã tạo thành công, nhưng có một số tàu bị thiếu thông tin Service (hệ thống không tự nhận diện được):")
                        for srv in missing_info["services"]:
                            st.write(f"- {srv}")
                    else:
                        st.success("✅ Tuyệt vời! Đã vẽ xong sơ đồ Game Plan.")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        # Đọc file để tải về
                        with open(output_path, "rb") as f:
                            file_data = f.read()
                            
                        st.download_button(
                            label="📥 TẢI FILE EXCEL",
                            data=file_data,
                            file_name="Game_Plan_Berth_Chart.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    with col2:
                        try:
                            with open(pdf_path, "rb") as f:
                                pdf_data = f.read()
                            st.download_button(
                                label="📥 TẢI FILE PDF (1 Trang)",
                                data=pdf_data,
                                file_name="Game_Plan_Berth_Chart.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                        except Exception as e:
                            st.error("Lỗi xuất PDF")
                else:
                    st.error(f"❌ Lỗi khi tạo file: {msg}")
