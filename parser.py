import re
from datetime import datetime

def parse_date(date_str, default_year=2026):
    s = date_str.upper().strip()
    # Remove day of week at start (e.g. SUN, MON)
    s = re.sub(r'^[A-Z]{3}\s+', '', s)
    s = re.sub(r'(\d+)(ST|ND|RD|TH)', r'\1', s)
    s = re.sub(r'\s+', ' ', s)
    s = s.replace(" /", "/").replace("/ ", "/")
    
    # Clean up trailing texts
    s = re.sub(r'[a-zA-Z]+$', '', s).strip()
    
    formats = [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H%M",
        "%d %b/%H%M",
        "%d %b/%H:%M",
        "%d/%H%M",
        "%d/%H:%M"
    ]
    
    now = datetime.now()
    default_month = now.month
    
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            if "%b" not in fmt and "%m" not in fmt:
                dt = dt.replace(month=default_month)
            if "%Y" not in fmt:
                dt = dt.replace(year=default_year)
            return dt
        except ValueError:
            continue
    return None

def extract_sum(text):
    if not text:
        return None
    numbers = map(int, re.findall(r'\d+', text))
    total = sum(numbers)
    return total if total > 0 else None

import csv
import io

def parse_tabular_data(raw_text, default_year=2026):
    vessels_data = []
    
    # Use csv to properly handle newlines inside quotes
    f = io.StringIO(raw_text.strip())
    # Try tab delimiter first (Excel default copy-paste)
    reader = csv.reader(f, delimiter='\t')
    
    for parts in reader:
        if not parts: continue
        
        # If no tabs were found, fallback to space splitting (though this might break names with spaces)
        if len(parts) == 1 and ' ' in parts[0]:
            import shlex
            try:
                parts = shlex.split(parts[0])
            except ValueError:
                parts = parts[0].split()

        if len(parts) >= 3:
            # Clean up quotes and newlines in parts
            parts = [p.replace('\n', ' ').strip() for p in parts]
            
            # Check if this is header line
            header_str = ' '.join(parts).lower()
            if "arrival at berth" in header_str or "vessel name" in header_str or "name of vessel" in header_str:
                continue
            
            etb_date = None
            etd_date = None
            etb_idx = -1
            etd_idx = -1
            
            # Try to dynamically find ETB and ETD from the end of the line
            for i in range(len(parts)-1, 0, -1):
                d = parse_date(parts[i], default_year)
                if d:
                    if etd_date is None:
                        etd_date = d
                        etd_idx = i
                    elif etb_date is None:
                        etb_date = d
                        etb_idx = i
                        break
                        
            if etb_date and etd_date:
                start_idx = 0
                if parts[0].strip().isdigit() and len(parts[0].strip()) <= 2:
                    start_idx = 1
                    
                name = parts[start_idx].strip()
                voyage = parts[start_idx + 1].strip() if etb_idx > start_idx + 1 else ""
                full_name = f"{name} {voyage}".strip()
                
                service_str = None
                if etb_idx > start_idx + 2:
                    service_str = parts[start_idx + 2].strip()
                elif len(parts) > etd_idx + 1:
                    service_str = parts[-1].strip()
                    
                vessels_data.append({
                    "name": full_name,
                    "etb": etb_date,
                    "etd": etd_date,
                    "disch": None,
                    "load": None,
                    "service": service_str
                })
    return vessels_data

def parse_single_block(block, default_year=2026):
    dt_pattern = r'(\d{1,2}(?:st|nd|rd|th)?\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s*/\s*\d{2}:?\d{2})'
    
    lines = [line.strip() for line in block.split('\n') if line.strip()]
    if not lines:
        return None
        
    name_line = lines[0]
    
    eta_line = next((l for l in lines if "ETA" in l.upper() or "E.T.A" in l.upper()), None)
    etb_line = next((l for l in lines if "ETB" in l.upper() or "E.T.B" in l.upper()), None)
    etd_line = next((l for l in lines if "ETD" in l.upper() or "E.T.D" in l.upper()), None)
    
    eta_date = None
    etb_date = None
    etd_date = None
    
    if eta_line:
        m = re.search(dt_pattern, eta_line, re.IGNORECASE)
        if m:
            eta_date = parse_date(m.group(1), default_year)

    if etb_line:
        m = re.search(dt_pattern, etb_line, re.IGNORECASE)
        if m:
            etb_date = parse_date(m.group(1), default_year)
            
    if etd_line:
        m = re.search(dt_pattern, etd_line, re.IGNORECASE)
        if m:
            etd_date = parse_date(m.group(1), default_year)
            
    def _extract_sum(text):
        if not text: return None
        numbers = map(int, re.findall(r'\d+', text))
        total = sum(numbers)
        return total if total > 0 else None

    disch_val = None
    load_val = None
    
    disch_match = re.search(r'Disch(.*?)(?:,|$|Load)', block, re.IGNORECASE)
    if disch_match:
        disch_val = _extract_sum(disch_match.group(1))
        
    load_match = re.search(r'Load(.*)', block, re.IGNORECASE)
    if load_match:
        load_val = _extract_sum(load_match.group(1))
        
    final_etb = etb_date if etb_date else eta_date
    is_eta = True if (not etb_date and eta_date) else False

    if final_etb and etd_date:
        return {
            "name": name_line,
            "etb": final_etb,
            "etd": etd_date,
            "disch": disch_val,
            "load": load_val,
            "is_eta": is_eta,
            "service": None
        }
    return None

def parse_schedule_text(raw_text, default_year=2026):
    vessels_data = []
    blocks = re.split(r'\n\s*\n', raw_text.strip())
    
    for block in blocks:
        if not block.strip():
            continue
            
        lower_block = block.lower()
        if 'etb:' in lower_block or 'eta:' in lower_block or 'e.t.b' in lower_block or 'e.t.d' in lower_block or 'disch' in lower_block:
            parsed = parse_single_block(block, default_year)
            if parsed:
                vessels_data.append(parsed)
            else:
                # Fallback to tabular if block parsing failed for some reason
                vessels_data.extend(parse_tabular_data(block, default_year))
        else:
            vessels_data.extend(parse_tabular_data(block, default_year))
            
    return vessels_data
