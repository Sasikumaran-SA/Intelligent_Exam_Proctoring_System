import os
import datetime
from fpdf import FPDF
from sqlalchemy.orm import Session
import models

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 20)
        self.set_text_color(31, 41, 55) # Dark gray
        self.cell(0, 15, 'Exam Security Audit Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(107, 114, 128)
        self.cell(0, 10, f'Page {self.page_no()} | Generated on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')

def generate_session_report(db: Session, session_id: int):
    # 1. Fetch Data
    session_data = db.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
    if not session_data:
        return None, "Session not found"
    
    student = session_data.student
    violations = session_data.violations
    
    # 2. Setup PDF
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # 3. Student & Session Summary
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'I. Session Information', 0, 1)
    
    pdf.set_font('Arial', '', 11)
    pdf.set_fill_color(249, 250, 251) # Light gray background
    
    # Convert UTC to IST (+5:30) for the report
    ist_start = session_data.start_time + datetime.timedelta(hours=5, minutes=30)
    info = [
        ['Student Name:', student.name],
        ['Student ID:', student.student_id],
        ['Session Date:', ist_start.strftime("%Y-%m-%d %H:%M:%S IST")],
        ['Final Trust Score:', f'{session_data.trust_score:.2f}%'],
        ['Total Violations:', str(len(violations))]
    ]
    
    for label, value in info:
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(40, 8, label, 1, 0, 'L', True)
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 8, value, 1, 1, 'L')
    
    pdf.ln(10)

    # 4. Violation Timeline Table
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'II. Violation Timeline', 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(229, 231, 235)
    pdf.cell(15, 8, 'ID', 1, 0, 'C', True)
    pdf.cell(110, 8, 'Violation Type', 1, 0, 'C', True)
    pdf.cell(0, 8, 'Timestamp (UTC)', 1, 1, 'C', True)

    pdf.set_font('Arial', '', 10)
    for i, v in enumerate(violations):
        ist_vtime = v.timestamp + datetime.timedelta(hours=5, minutes=30)
        pdf.cell(15, 8, str(i+1), 1, 0, 'C')
        pdf.cell(110, 8, v.violation_type, 1, 0, 'L')
        pdf.cell(0, 8, ist_vtime.strftime("%H:%M:%S IST"), 1, 1, 'C')

    pdf.ln(10)

    # 5. Evidence Gallery (Top 20 Snapshots)
    if violations:
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, 'III. Evidence Gallery', 0, 1)
        
        # Filter for unique snapshots to save space
        seen_snapshots = []
        gallery_items = []
        for v in violations:
            if v.snapshot_url and v.snapshot_url not in seen_snapshots:
                gallery_items.append(v)
                seen_snapshots.append(v.snapshot_url)
            if len(gallery_items) >= 100: break

        # Draw grid
        col_width = 90
        row_height = 60
        margin_left = 10
        row_spacing = 20
        page_bottom_limit = 260 # A4 is ~297mm
        
        for i, item in enumerate(gallery_items):
            # 1. Row Management: If starting a new row (even index)
            if i % 2 == 0:
                # Check if this row fits on the current page
                current_y = pdf.get_y()
                if current_y + row_height + row_spacing > page_bottom_limit:
                    pdf.add_page()
                    # Reset cursor after add_page (header is auto-run)
                    pdf.set_y(30) # Start below header
            
            # 2. X/Y Calculation
            x = margin_left + (i % 2) * col_width
            current_y = pdf.get_y()
            
            # 3. Draw Image
            try:
                filename = os.path.basename(item.snapshot_url)
                img_path = os.path.join(os.path.dirname(__file__), '..', '..', 'public', 'snapshots', filename)
                
                if os.path.exists(img_path):
                    pdf.image(img_path, x=x, y=current_y, w=col_width - 10, h=row_height)
                else:
                    pdf.set_xy(x, current_y)
                    pdf.cell(col_width - 10, row_height, '[No Image]', 1, 0, 'C')
            except Exception as e:
                pdf.set_xy(x, current_y)
                pdf.cell(col_width - 10, row_height, '[Error]', 1, 0, 'C')

            # 4. Draw Label (Below image)
            pdf.set_font('Arial', 'I', 7)
            ist_snap = item.timestamp + datetime.timedelta(hours=5, minutes=30)
            label = f'{item.violation_type} at {ist_snap.strftime("%H:%M:%S IST")}'
            pdf.text(x, current_y + row_height + 5, label)

            # 5. Move to next row if we just finished the right column
            if i % 2 == 1:
                pdf.ln(row_height + row_spacing)
            elif i == len(gallery_items) - 1:
                # If it's the last item and it's on the left column, move cursor down anyway
                pdf.ln(row_height + row_spacing)

    # 6. Save PDF
    reports_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'reports')
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    filename = f"report_session_{session_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    file_path = os.path.join(reports_dir, filename)
    pdf.output(file_path)
    
    return file_path, None
