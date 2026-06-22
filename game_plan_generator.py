import xlsxwriter
from datetime import datetime, timedelta
import math
import os
import urllib.request
import re

def get_contrast_color(hex_color):
    hex_color = hex_color.lstrip('#')
    if not hex_color or len(hex_color) != 6:
        return "#000000"
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#000000" if luminance > 0.5 else "#FFFFFF"
    except ValueError:
        return "#000000"

def fetch_loa_from_vesselfinder(vessel_name):
    try:
        name = vessel_name.replace(' ', '+')
        url = f'https://www.vesselfinder.com/vessels?name={name}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=5)
        html = res.read().decode('utf-8', errors='ignore')

        match = re.search(r'href="(/vessels/details/\d+)"', html)
        if match:
            detail_url = 'https://www.vesselfinder.com' + match.group(1)
            req2 = urllib.request.Request(detail_url, headers={'User-Agent': 'Mozilla/5.0'})
            res2 = urllib.request.urlopen(req2, timeout=5)
            html2 = res2.read().decode('utf-8', errors='ignore')
            
            loa_match = re.search(r'Length / Beam.*?v3.*?(\d+)\s*/', html2, re.IGNORECASE | re.DOTALL)
            if loa_match:
                return int(loa_match.group(1))
            loa_match2 = re.search(r'Length Overall \(m\).*?v3.*?(\d+(?:\.\d+)?)', html2, re.IGNORECASE | re.DOTALL)
            if loa_match2:
                return int(float(loa_match2.group(1)))
    except Exception as e:
        print(f"Error fetching LOA for {vessel_name}: {e}")
    return None

def generate_game_plan(vessels, config, output_path='game_plan.xlsx'):
    try:
        missing_info = {"services": []}
        # Load config rules
        SERVICE_RULES = config.get("service_rules", {})
        SERVICE_COLORS = config.get("service_colors", {})
        VESSELS_LOA = config.get("vessels_loa", {})
        DEFAULT_COLOR = config.get("default_color", "#D3D3D3")
        DEFAULT_LOA = config.get("default_loa", 300)

        if not vessels:
            return False, "No vessels data provided."

        # Preprocess vessels to extract service, clean vessel name, and voyage
        for v in vessels:
            full_name = v.get("name", "")
            service_name = v.get("service", "")
            if service_name:
                service_name = service_name.upper().replace("SERVICE", "").strip()
                
                # If parsed service is not in colors, try substring match (e.g., "AMERICA/ Z7S" -> "AMERICA")
                if service_name not in SERVICE_COLORS:
                    matched_srv = ""
                    for srv in SERVICE_COLORS:
                        if srv in service_name:
                            matched_srv = srv
                            break
                    service_name = matched_srv # Will be empty if no match, triggering fallback logic

            # 1. Check for manual service prefixes
            if not service_name:
                for srv in SERVICE_RULES.values():
                    if full_name.upper().startswith(srv.upper() + " ") or full_name.upper().startswith(srv.upper() + "-"):
                        service_name = srv
                        full_name = full_name[len(srv):].strip(" -")
                        break
                        
            # 2. Check for unknown service separated by " - "
            if not service_name and " - " in full_name:
                parts_dash = full_name.split(" - ")
                if "SERVICE" in parts_dash[-1].upper():
                    service_name = parts_dash[-1].upper().replace("SERVICE", "").strip()
                    full_name = " - ".join(parts_dash[:-1]).strip()
                elif "SERVICE" in parts_dash[0].upper():
                    service_name = parts_dash[0].upper().replace("SERVICE", "").strip()
                    full_name = " - ".join(parts_dash[1:]).strip()
                else:
                    service_name = parts_dash[0].strip()
                    full_name = parts_dash[1].strip()

            # Extract voyage
            v["clean_name"] = full_name
            parts = full_name.split()
            chuyen = ""
            for i, part in enumerate(parts):
                if any(char.isdigit() for char in part):
                    chuyen = " ".join(parts[i:])
                    v["clean_name"] = " ".join(parts[:i])
                    break
                    
            if chuyen.upper().startswith("V."):
                chuyen = chuyen[2:].strip()
                
            # 4. Infer service from voyage rule if still missing
            if not service_name and chuyen:
                for voy_part in chuyen.split():
                    clean_voy = voy_part.replace("/", "").strip()
                    if len(clean_voy) >= 3:
                        prefix_suffix = clean_voy[:2].upper() + clean_voy[-1].upper()
                        if prefix_suffix in SERVICE_RULES:
                            service_name = SERVICE_RULES[prefix_suffix]
                            break
                            
            # 5. Check direct vessel service mapping
            if not service_name:
                clean_name_upper = v["clean_name"].upper()
                if clean_name_upper in config.get("vessels_service", {}):
                    service_name = config["vessels_service"][clean_name_upper]
                    
            if not service_name and v["clean_name"] not in missing_info["services"]:
                missing_info["services"].append(v["clean_name"])
                    
            v["parsed_voyage"] = chuyen
            v["parsed_service"] = service_name

            # Lookup LOA and Color if not provided
            if "loa" not in v:
                clean_name_upper = v["clean_name"].upper()
                if clean_name_upper in VESSELS_LOA:
                    v["loa"] = VESSELS_LOA[clean_name_upper]
                else:
                    fetched_loa = fetch_loa_from_vesselfinder(v["clean_name"])
                    if fetched_loa:
                        v["loa"] = fetched_loa
                        # Save to config memory so it doesn't fetch repeatedly
                        VESSELS_LOA[clean_name_upper] = fetched_loa
                        try:
                            import config_manager
                            config["vessels_loa"][clean_name_upper] = fetched_loa
                            config_manager.save_config(config)
                        except Exception:
                            pass
                    else:
                        v["loa"] = DEFAULT_LOA
            
            if "color" not in v:
                # Assign color based on service
                v["color"] = SERVICE_COLORS.get(service_name, DEFAULT_COLOR)

        # Sort by ETB (asc), then Duration (desc)
        vessels.sort(key=lambda x: (x["etb"], -(x["etd"] - x["etb"]).total_seconds()))
        
        # Base date is the first vessel's ETB at 00:00
        if vessels:
            base_date = vessels[0]["etb"].replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
        # Calculate total days based on the latest ETD
        if vessels:
            max_etd = max(v["etd"] for v in vessels)
            total_days = (max_etd - base_date).days + 2 # Add some margin
        else:
            total_days = 9

        px_per_hour = 4
        row_height_px = 96
        cols_berth = 20 # 600m / 30m
        col_berth_width_px = 40 # Increased slightly from 35 to reduce white space
        col_bouy_width_px = math.ceil(55 * (col_berth_width_px / 30)) # 74px
        date_col_width_px = 85 # Keep at 85 to fit "Wednesday" tightly

        header_row0_px = 30
        header_row1_px = 20
        header_height_px = header_row0_px + header_row1_px

        # Create directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        wb = xlsxwriter.Workbook(output_path)
        ws = wb.add_worksheet('Berth Chart')
        
        # Setup Print Layout
        ws.set_landscape()
        ws.set_paper(9) # A4
        ws.set_margins(left=0.3, right=0.3, top=0.5, bottom=0.5)
        ws.fit_to_pages(1, 0) # Fit to 1 page wide, infinite pages tall

        ws.set_column_pixels(0, 0, date_col_width_px)
        ws.set_column_pixels(1, 1, col_bouy_width_px)
        ws.set_column_pixels(2, cols_berth + 1, col_berth_width_px)

        header_format = wb.add_format({
            'bold': True,
            'valign': 'vcenter',
            'align': 'center',
            'border': 1,
            'bottom': 2,
            'bg_color': '#D3D3D3'
        })

        date_format = wb.add_format({
            'bold': True,
            'valign': 'vcenter',
            'align': 'center',
            'border': 1,
            'bottom': 2,
            'text_wrap': True
        })

        berth_day_format = wb.add_format({
            'bottom': 2,
            'bottom_color': 'black',
            'right': 1,
            'right_color': '#E0E0E0'
        })

        # Headers
        ws.set_row_pixels(0, header_row0_px)
        ws.set_row_pixels(1, header_row1_px)

        ws.merge_range(0, 0, 1, 0, "Date", header_format)
        ws.merge_range(0, 1, 0, cols_berth + 1, "SSIT GAME PLAN", header_format)

        ws.write(1, 1, "Bouy (55m)", header_format)
        for i in range(cols_berth):
            mark = (i + 1) * 30
            ws.write(1, i + 2, str(mark), header_format)

        # Y-axis setup
        for i in range(total_days):
            row_idx = i + 2
            ws.set_row_pixels(row_idx, row_height_px)
            current_date = base_date + timedelta(days=i)
            date_str = current_date.strftime("%d/%m") + "\n" + current_date.strftime("%A")
            ws.write(row_idx, 0, date_str, date_format)
            # Apply bottom border to berth cells to create 0h line and right border for 30m columns
            ws.write(row_idx, 1, "", berth_day_format)
            for j in range(cols_berth):
                ws.write(row_idx, j + 2, "", berth_day_format)

        # Draw horizontal grid lines for even hours in the Berth area only
        for day in range(total_days):
            for hour in range(2, 24, 2):
                y_offset = header_height_px + day * row_height_px + hour * px_per_hour
                color = '#A0A0A0' if hour == 12 else '#E0E0E0'
                ws.insert_textbox(0, 0, "", {
                    'width': col_bouy_width_px + cols_berth * col_berth_width_px,
                    'height': 1,
                    'x_offset': date_col_width_px,
                    'y_offset': y_offset,
                    'border': {'color': color, 'width': 0.5},
                    'fill': {'color': color}
                })

        # Phase 1: Calculate placements and handle overlaps
        placed_ships = []
        for v in vessels:
            duration_hours = (v["etd"] - v["etb"]).total_seconds() / 3600
            v["duration_hours"] = duration_hours
            
            v["draw_start_time"] = v["etb"]
            v["draw_end_time"] = v["etb"] + timedelta(hours=duration_hours)
            v["is_delayed"] = False
            v["position"] = "right" # default
            
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

        etb_counts = {}
        for v in vessels:
            etb = v["etb"]
            etb_counts[etb] = etb_counts.get(etb, 0) + 1

        # Phase 2: Draw vessels
        for v in placed_ships:
            is_delayed = v["is_delayed"]
            duration_hours = v["duration_hours"]
            draw_start_time = v["draw_start_time"]
            
            hours_since_base = (draw_start_time - base_date).total_seconds() / 3600
            y_offset = header_height_px + hours_since_base * px_per_hour
            height = duration_hours * px_per_hour
            
            # 1 column = 44px = 30m => 1m = 44/30 px
            width = math.ceil(v["loa"] * (col_berth_width_px / 30))
            
            if v["position"] == "left":
                # left align 30m
                x_offset = date_col_width_px + col_bouy_width_px + 1 * col_berth_width_px
            else:
                # 570m mark is at the end of the 19th berth column
                x_570m = date_col_width_px + col_bouy_width_px + 19 * col_berth_width_px
                x_offset = x_570m - width
            
            # Text
            etb_str = v["etb"].strftime("%d/%H:%M")
            etd_str = v["etd"].strftime("%d/%H:%M")
            
            # Calculate duration
            duration = v["etd"] - v["etb"]
            duration_h = duration.total_seconds() / 3600
            duration_h_str = f"{duration_h:g}"
            
            # Use preprocessed data
            service_name = v["parsed_service"]
            full_name = v["clean_name"]
            chuyen = v["parsed_voyage"]
            
            line1 = full_name
            if chuyen:
                line1 += f" {chuyen}"
            line1 += f" ({etb_str} - {etd_str} | {duration_h_str}h) - {v['loa']}m - {service_name}"
            
            disch_val = v.get("disch")
            load_val = v.get("load")
            
            if disch_val is None and load_val is None:
                disch_text = "   "
                load_text = "   "
                total_text = "   "
            else:
                disch_text = str(disch_val) if disch_val is not None else "0"
                load_text = str(load_val) if load_val is not None else "0"
                d = int(disch_val) if disch_val is not None else 0
                l = int(load_val) if load_val is not None else 0
                total_text = str(d + l)
                
            line2 = f"Disch: {disch_text}, Load: {load_text} --> Total: {total_text}"
            
            text = f"{line1}\n{line2}"
            
            font_color = get_contrast_color(v["color"])
            
            ws.insert_textbox(0, 0, text, {
                'width': width,
                'height': height,
                'x_offset': x_offset,
                'y_offset': y_offset,
                'align': {'vertical': 'middle', 'horizontal': 'center'},
                'font': {'size': 9, 'bold': True, 'color': font_color},
                'fill': {'color': v["color"]},
                'border': {'color': '#000000', 'width': 1}
            })

            needs_tbu = is_delayed
            if not needs_tbu:
                for other in placed_ships:
                    if other is not v and other["etb"] == v["etb"] and other["position"] == v["position"]:
                        needs_tbu = True
                        break
                        
            if needs_tbu:
                stamp_w = 47
                stamp_h = 22
                ws.insert_textbox(0, 0, "TBU", {
                    'width': stamp_w,
                    'height': stamp_h,
                    'x_offset': x_offset + width - stamp_w - 5,
                    'y_offset': y_offset + 5,
                    'align': {'vertical': 'middle', 'horizontal': 'center'},
                    'font': {'size': 10, 'color': '#FF0000', 'bold': True},
                    'fill': {'color': '#FFFF00'},
                    'border': {'color': '#FF0000', 'width': 1.5}
                })

        # --- Add Schedule Sheet ---
        ws2 = wb.add_worksheet('Schedule List')

        header_fmt = wb.add_format({
            'bold': True, 
            'font_color': 'white', 
            'bg_color': '#1F4E78', 
            'border': 1, 
            'align': 'center', 
            'valign': 'vcenter'
        })
        left_fmt = wb.add_format({
            'border': 1, 
            'align': 'left', 
            'valign': 'vcenter', 
            'bold': True
        })
        center_fmt = wb.add_format({
            'border': 1, 
            'align': 'center', 
            'valign': 'vcenter'
        })
        center_wrap_fmt = wb.add_format({
            'border': 1, 
            'align': 'center', 
            'valign': 'vcenter', 
            'text_wrap': True
        })

        ws2.set_column('A:A', 25)
        ws2.set_column('B:B', 15)
        ws2.set_column('C:D', 18)
        ws2.set_row(0, 25)

        headers = ["Ten Tau", "Chuyen", "ETB", "ETD"]
        ws2.write_row(0, 0, headers, header_fmt)

        for idx, v in enumerate(vessels):
            row = idx + 1
            ws2.set_row(row, 35)
            
            ten_tau = v["clean_name"]
            chuyen = v["parsed_voyage"]
                
            etb_str = v["etb"].strftime("%d/%H:%M\n%A")
            etd_str = v["etd"].strftime("%d/%H:%M\n%A")
            
            ws2.write(row, 0, ten_tau, left_fmt)
            ws2.write(row, 1, chuyen, center_fmt)
            ws2.write(row, 2, etb_str, center_wrap_fmt)
            ws2.write(row, 3, etd_str, center_wrap_fmt)

        try:
            wb.close()
            return True, f"Successfully generated {output_path}", missing_info
        except Exception as e:
            return False, f"Error saving file. Please close Excel if it is open.\nDetails: {e}", missing_info
    except Exception as e:
        import traceback
        return False, f"Exception occurred during generation:\n{traceback.format_exc()}", None
