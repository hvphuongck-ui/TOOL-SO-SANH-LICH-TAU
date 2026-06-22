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
    from pdf_generator import generate_pdf
except ImportError as e:
    st.error(f"Lỗi khi import thư viện cốt lõi: {e}")
    st.stop()

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
