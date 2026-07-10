import io

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_ics309_pdf(comm_log):
    """Generate an ICS-309 Communications Log PDF. Returns a BytesIO buffer."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ICSTitle', parent=styles['Heading1'], fontSize=14,
        alignment=1, spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        'ICSSubtitle', parent=styles['Normal'], fontSize=8,
        alignment=1, spaceAfter=12,
    )
    label_style = ParagraphStyle(
        'ICSLabel', parent=styles['Normal'], fontSize=7, textColor=colors.grey,
    )
    value_style = ParagraphStyle(
        'ICSValue', parent=styles['Normal'], fontSize=9,
    )
    small_style = ParagraphStyle(
        'ICSSmall', parent=styles['Normal'], fontSize=8,
    )

    elements = []

    # Title
    elements.append(Paragraph('ICS 309 — COMMUNICATIONS LOG', title_style))
    elements.append(Paragraph(
        'Use this form to record radio traffic during an incident or event.',
        subtitle_style
    ))

    # Header info table
    op_start = comm_log.op_period_start.strftime('%Y-%m-%d %H:%M') if comm_log.op_period_start else ''
    op_end = comm_log.op_period_end.strftime('%Y-%m-%d %H:%M') if comm_log.op_period_end else ''

    header_data = [
        [
            Paragraph('<b>1. Incident Name / Activation #</b>', label_style),
            Paragraph('<b>2. Operational Period</b>', label_style),
        ],
        [
            Paragraph(f'{comm_log.incident_name or ""}'
                      f'{" / " + comm_log.activation_number if comm_log.activation_number else ""}',
                      value_style),
            Paragraph(f'From: {op_start}  To: {op_end}', value_style),
        ],
        [
            Paragraph('<b>3. Net Name / Position / Tactical Call</b>', label_style),
            Paragraph('<b>4. Radio Operator (Name, Call Sign)</b>', label_style),
        ],
        [
            Paragraph(comm_log.net_name_or_position or '', value_style),
            Paragraph(f'{comm_log.operator_name or ""}'
                      f'{", " + comm_log.operator_callsign if comm_log.operator_callsign else ""}',
                      value_style),
        ],
    ]

    header_table = Table(header_data, colWidths=[3.75 * inch, 3.75 * inch])
    header_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 12))

    # Communications log table
    log_header = [
        Paragraph('<b>Time</b>', small_style),
        Paragraph('<b>From Call Sign</b>', small_style),
        Paragraph('<b>From Msg #</b>', small_style),
        Paragraph('<b>To Call Sign</b>', small_style),
        Paragraph('<b>To Msg #</b>', small_style),
        Paragraph('<b>Message</b>', small_style),
    ]

    log_data = [log_header]
    for entry in comm_log.entries:
        time_str = entry.time.strftime('%H:%M') if entry.time else ''
        log_data.append([
            Paragraph(time_str, small_style),
            Paragraph(entry.from_callsign or '', small_style),
            Paragraph(entry.from_msg_num or '', small_style),
            Paragraph(entry.to_callsign or '', small_style),
            Paragraph(entry.to_msg_num or '', small_style),
            Paragraph(entry.message or '', small_style),
        ])

    # Add empty rows to fill page if few entries
    while len(log_data) < 25:
        log_data.append(['', '', '', '', '', ''])

    col_widths = [0.7 * inch, 1.0 * inch, 0.7 * inch, 1.0 * inch, 0.7 * inch, 3.4 * inch]
    log_table = Table(log_data, colWidths=col_widths, repeatRows=1)
    log_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e0e0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    elements.append(log_table)
    elements.append(Spacer(1, 12))

    # Footer
    prepared_date = comm_log.prepared_date.strftime('%Y-%m-%d') if comm_log.prepared_date else ''
    footer_data = [
        [
            Paragraph('<b>6. Prepared By</b>', label_style),
            Paragraph('<b>7. Date/Time Prepared</b>', label_style),
        ],
        [
            Paragraph(comm_log.prepared_by or comm_log.operator_name or '', value_style),
            Paragraph(prepared_date, value_style),
        ],
    ]

    footer_table = Table(footer_data, colWidths=[3.75 * inch, 3.75 * inch])
    footer_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(footer_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_skywarn_worksheet_pdf(storm):
    """Generate the St. Clair County ARPSC SkyWarn Work Sheet for a storm.

    Reproduces the paper form's five sections, filling structured data and
    padding each table with blank rows for field write-ins. Returns a BytesIO.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(letter),
        leftMargin=0.4 * inch, rightMargin=0.4 * inch,
        topMargin=0.4 * inch, bottomMargin=0.4 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('WSTitle', parent=styles['Heading1'], fontSize=14,
                                 alignment=1, spaceAfter=2)
    section_style = ParagraphStyle('WSSection', parent=styles['Heading2'], fontSize=11,
                                   spaceBefore=8, spaceAfter=4)
    label_style = ParagraphStyle('WSLabel', parent=styles['Normal'], fontSize=7,
                                 textColor=colors.grey)
    value_style = ParagraphStyle('WSValue', parent=styles['Normal'], fontSize=9)
    small_style = ParagraphStyle('WSSmall', parent=styles['Normal'], fontSize=8)
    head_style = ParagraphStyle('WSHead', parent=styles['Normal'], fontSize=8, alignment=1)

    full_width = 10.2 * inch
    grid_style = TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d9d9d9')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ])

    def check(val):
        return '<b>X</b>' if val else ''  # Helvetica has no ballot-box glyphs

    def pad(rows, target, ncols):
        while len(rows) < target:
            rows.append([''] * ncols)
        return rows

    elements = []

    # --- Header ---
    elements.append(Paragraph('St. Clair County ARPSC SkyWarn Work Sheet', title_style))
    date_str = storm.event_date.strftime('%Y-%m-%d') if storm.event_date else ''
    ncs = storm.net_control_name or ''
    if storm.net_control_callsign:
        ncs = f'{ncs} ({storm.net_control_callsign})' if ncs else storm.net_control_callsign
    header_data = [
        [Paragraph('<b>Net Control Name</b>', label_style),
         Paragraph(ncs, value_style),
         Paragraph('<b>Main Freq.</b>', label_style),
         Paragraph(storm.freq_main or '', value_style)],
        [Paragraph('<b>Date</b>', label_style),
         Paragraph(date_str, value_style),
         Paragraph('<b>North Freq.</b>', label_style),
         Paragraph(storm.freq_north or '', value_style)],
        [Paragraph('<b>Storm</b>', label_style),
         Paragraph(storm.name or '', value_style),
         Paragraph('<b>South Freq.</b>', label_style),
         Paragraph(storm.freq_south or '', value_style)],
        [Paragraph('', label_style),
         Paragraph('', value_style),
         Paragraph('<b>DTX Tx</b>', label_style),
         Paragraph(storm.freq_dtx or '', value_style)],
    ]
    header_table = Table(header_data,
                         colWidths=[1.4 * inch, 4.1 * inch, 1.1 * inch, 3.6 * inch])
    header_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_table)

    # --- NWS Watches and Warnings ---
    elements.append(Paragraph('NWS Watches and Warnings', section_style))
    ww_head = [Paragraph(f'<b>{h}</b>', head_style) for h in
               ('TSM Watch', 'TSM Warning', 'TDO Watch', 'TDO Warning', 'County', 'Start', 'End')]
    ww_rows = [ww_head]
    for w in storm.watch_warnings:
        ww_rows.append([
            Paragraph(check(w.tsm_watch), head_style),
            Paragraph(check(w.tsm_warning), head_style),
            Paragraph(check(w.tdo_watch), head_style),
            Paragraph(check(w.tdo_warning), head_style),
            Paragraph(w.county or '', small_style),
            Paragraph(w.start_time or '', small_style),
            Paragraph(w.end_time or '', small_style),
        ])
    pad(ww_rows, 9, 7)
    ww_widths = [1.15 * inch, 1.25 * inch, 1.15 * inch, 1.25 * inch,
                 2.2 * inch, 1.5 * inch, 1.7 * inch]
    ww_table = Table(ww_rows, colWidths=ww_widths, repeatRows=1)
    ww_table.setStyle(TableStyle(grid_style.getCommands() + [
        ('ALIGN', (0, 0), (3, -1), 'CENTER'),
    ]))
    elements.append(ww_table)

    # --- Net Condition ---
    elements.append(Paragraph('Net Condition', section_style))
    nc_rows = [[Paragraph('<b>Condition</b>', head_style),
                Paragraph('<b>Reason</b>', head_style),
                Paragraph('<b>Time</b>', head_style)]]
    for c in storm.net_conditions:
        nc_rows.append([
            Paragraph(c.condition or '', small_style),
            Paragraph(c.reason or '', small_style),
            Paragraph(c.time or '', small_style),
        ])
    pad(nc_rows, 9, 3)
    nc_table = Table(nc_rows, colWidths=[2.2 * inch, 6.4 * inch, 1.6 * inch], repeatRows=1)
    nc_table.setStyle(grid_style)
    elements.append(nc_table)

    # --- Participating Stations ---
    elements.append(PageBreak())
    elements.append(Paragraph('Participating Stations', section_style))
    ps_rows = [[Paragraph(f'<b>{h}</b>', head_style) for h in
                ('Role', 'Station', 'Location', 'In', 'Out')]]
    for s in storm.net_stations:
        ps_rows.append([
            Paragraph(s.role or '', small_style),
            Paragraph(s.station or '', small_style),
            Paragraph(s.location or '', small_style),
            Paragraph(s.time_in or '', small_style),
            Paragraph(s.time_out or '', small_style),
        ])
    pad(ps_rows, 24, 5)
    ps_table = Table(ps_rows,
                     colWidths=[1.8 * inch, 1.6 * inch, 4.2 * inch, 1.3 * inch, 1.3 * inch],
                     repeatRows=1)
    ps_table.setStyle(grid_style)
    elements.append(ps_table)

    # --- Weather Reports (T-E-L) ---
    elements.append(PageBreak())
    elements.append(Paragraph('Weather Reports (Time – Effect – Location)', section_style))
    wr_rows = [[Paragraph(f'<b>{h}</b>', head_style) for h in
                ('Station', 'Time', 'Effect', 'Location', 'Passed Via')]]
    # storm.reports is already chronological; guard against a missing occurred_at
    for r in sorted(storm.reports, key=lambda x: (x.occurred_at or x.created_at)):
        effect = r.damage_type or ''
        if r.description:
            effect = f'{effect} — {r.description}' if effect else r.description
        time_str = r.occurred_at.strftime('%m/%d %H:%M') if r.occurred_at else ''
        wr_rows.append([
            Paragraph(r.reporter_name or '', small_style),
            Paragraph(time_str, small_style),
            Paragraph(effect, small_style),
            Paragraph(r.location_text or '', small_style),
            Paragraph(r.passed_via or '', small_style),
        ])
    pad(wr_rows, 24, 5)
    wr_table = Table(wr_rows,
                     colWidths=[1.6 * inch, 1.2 * inch, 3.6 * inch, 2.6 * inch, 1.2 * inch],
                     repeatRows=1)
    wr_table.setStyle(grid_style)
    elements.append(wr_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer
