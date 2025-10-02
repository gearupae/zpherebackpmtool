"""
PDF Generation Service for Proposals and Invoices
"""
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
import os
import urllib.request


def _fmt_currency(value_cents: int) -> str:
    try:
        return f"{(value_cents or 0)/100:,.2f}"
    except Exception:
        return "0.00"


class PDFService:
    """Service for generating PDF documents with organization branding."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Company header style
        self.styles.add(ParagraphStyle(
            name='CompanyHeader',
            parent=self.styles['Normal'],
            fontSize=16,
            textColor=colors.black,
            spaceAfter=6,
            fontName='Helvetica-Bold'
        ))
        
        # Document title style (right-aligned)
        self.styles.add(ParagraphStyle(
            name='DocumentTitle',
            parent=self.styles['Normal'],
            fontSize=24,
            textColor=colors.black,
            spaceAfter=12,
            fontName='Helvetica-Bold',
            alignment=TA_RIGHT
        ))
        # Document title style (centered)
        self.styles.add(ParagraphStyle(
            name='DocumentTitleCenter',
            parent=self.styles['Normal'],
            fontSize=26,
            textColor=colors.black,
            spaceAfter=12,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER
        ))
        
        # Document number style
        self.styles.add(ParagraphStyle(
            name='DocumentNumber',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=6,
            alignment=TA_RIGHT
        ))
        
        # Status style
        self.styles.add(ParagraphStyle(
            name='Status',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=12,
            fontName='Helvetica-Bold',
            alignment=TA_RIGHT
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=6,
            fontName='Helvetica-Bold'
        ))
    
    def generate_proposal_pdf(self, proposal_data: Dict[str, Any], org: Optional[Dict[str, Any]] = None) -> io.BytesIO:
        """Generate PDF for proposal"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch)
        
        # Build the document content
        story = []
        
        # Header section
        story.extend(self._build_proposal_header(proposal_data, org))
        story.append(Spacer(1, 0.3*inch))
        
        # Client information
        story.extend(self._build_client_section(proposal_data.get('customer', {})))
        story.append(Spacer(1, 0.3*inch))
        
        # Items table
        story.extend(self._build_proposal_items_table(proposal_data.get('content', {}).get('items', [])))
        story.append(Spacer(1, 0.3*inch))
        
        # Totals section
        story.extend(self._build_proposal_totals(proposal_data))
        story.append(Spacer(1, 0.3*inch))
        
        # Terms and conditions
        if proposal_data.get('custom_fields', {}).get('terms_and_conditions'):
            story.extend(self._build_terms_section(proposal_data['custom_fields']['terms_and_conditions']))
        
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def generate_invoice_pdf(self, invoice_data: Dict[str, Any], org: Optional[Dict[str, Any]] = None) -> io.BytesIO:
        """Generate PDF for invoice"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
        
        # Build the document content
        story = []
        
        # Header section (logo/company left, big centered INVOICE title, meta right)
        story.extend(self._build_invoice_header(invoice_data, org))
        story.append(Spacer(1, 0.2*inch))
        
        # Two-column context section similar to the sample (To on left, Project/Document info on right)
        story.extend(self._build_invoice_context_section(invoice_data))
        story.append(Spacer(1, 0.2*inch))
        
        # Items table styled like the sample (#, Description, Qty, Rate, Total Amount, Guarantee Rate)
        story.extend(self._build_invoice_items_table(invoice_data.get('items', [])))
        story.append(Spacer(1, 0.2*inch))
        
        # Totals section
        story.extend(self._build_invoice_totals(invoice_data))
        story.append(Spacer(1, 0.2*inch))
        
        # Client acceptance/signature block (bottom)
        story.extend(self._build_client_acceptance_section())
        
        # Optional terms
        if invoice_data.get('terms_and_conditions'):
            story.append(Spacer(1, 0.15*inch))
            story.extend(self._build_terms_section(invoice_data['terms_and_conditions']))
        
        # Build with page numbers
        def _on_page(canv: canvas.Canvas, _doc):
            # Page number
            self._add_page_number(canv, _doc)
            # Watermark for drafts
            status = str(invoice_data.get('status') or '').upper()
            if status == 'DRAFT':
                self._draw_watermark(canv, 'DRAFT')
        
        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        buffer.seek(0)
        return buffer
    
    def _build_proposal_header(self, proposal_data: Dict[str, Any], org: Optional[Dict[str, Any]]) -> List:
        """Build proposal header section"""
        story = []
        header_table = self._build_branded_header(
            org,
            title="PROPOSAL",
            number=f"# {proposal_data.get('proposal_number', 'PROP-000001')}",
            status=str(proposal_data.get('status', 'DRAFT')).upper(),
            right_lines=[
                proposal_data.get('customer', {}).get('display_name', 'Client Name'),
                f"Proposal Date: {self._format_date(proposal_data.get('created_at'))}",
                f"Expiry Date: {self._format_date(proposal_data.get('valid_until'))}",
            ],
        )
        story.append(header_table)
        return story
    
    def _build_invoice_header(self, invoice_data: Dict[str, Any], org: Optional[Dict[str, Any]]) -> List:
        """Build invoice header section with centered title and company branding"""
        story = []
        header_table = self._build_branded_header(
            org,
            title="INVOICE",
            number=f"# {invoice_data.get('invoice_number', 'INV-000001')}",
            status=str(invoice_data.get('status', 'DRAFT')).upper(),
            right_lines=[],  # avoid duplicating client/date info already shown in context block
            center_title=True,
        )
        story.append(header_table)
        return story
    
    def _build_client_section(self, customer_data: Dict[str, Any]) -> List:
        """Build simple client information section (legacy)"""
        story = []
        client_info = [Paragraph(customer_data.get('display_name', 'Client Name'), self.styles['SectionHeader'])]
        if customer_data.get('company_name'):
            client_info.append(Paragraph(customer_data['company_name'], self.styles['Normal']))
        if customer_data.get('email'):
            client_info.append(Paragraph(f"Email: {customer_data['email']}", self.styles['Normal']))
        for item in client_info:
            story.append(item)
        return story
    
    def _build_proposal_items_table(self, items: List[Dict[str, Any]]) -> List:
        """Build proposal items table"""
        story = []
        
        # Table headers
        headers = ['#', 'Item', 'Qty', 'Rate', 'Tax', 'Amount']
        
        # Prepare table data
        table_data = [headers]
        
        for i, item in enumerate(items, 1):
            row = [
                str(i),
                f"{item.get('name', '')}\n{item.get('description', '')}",
                f"{item.get('quantity', 1)} {item.get('unit', 'Qty')}",
                f"{item.get('unit_price', 0):.2f}",
                f"Standard\nRated {item.get('tax_rate', 5)}%",
                f"{item.get('total', 0):.2f}"
            ]
            table_data.append(row)
        
        # Create table
        items_table = Table(table_data, colWidths=[0.5*inch, 2.5*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1*inch])
        
        # Style the table (no colored accents)
        items_table.setStyle(TableStyle([
            # Header styling (bold, no background color)
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            
            # Data styling
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'),  # Qty, Rate, Tax, Amount
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),     # Item description
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),   # Item number
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(items_table)
        return story
    
    def _build_invoice_items_table(self, items: List[Dict[str, Any]]) -> List:
        """Build invoice items table mimicking the provided sample style."""
        story = []
        headers = ['#', 'Description', 'Qty', 'Rate', 'Total Amount', 'Guarantee Rate']
        table_data = [headers]
        
        for i, item in enumerate(items or [], 1):
            qty = item.get('quantity', 1)
            rate = _fmt_currency(item.get('unit_price', 0))
            # amount field in our stored JSON is total per line inclusive of tax-discount
            total_amount = _fmt_currency(item.get('amount', qty * item.get('unit_price', 0)))
            guarantee_rate = item.get('guarantee_rate')
            if isinstance(guarantee_rate, (int, float)):
                # If in cents
                guarantee = _fmt_currency(int(guarantee_rate))
            else:
                guarantee = '0.00'
            desc_lines = []
            if item.get('description'):
                desc_lines.append(item['description'])
            # Optionally include item_type
            if item.get('item_type'):
                pass
            row = [
                str(i),
                "\n".join(desc_lines),
                f"{qty:.2f}",
                rate,
                total_amount,
                guarantee,
            ]
            table_data.append(row)
        
        # Narrower table with centered alignment to create side breathing space
        col_widths = [0.4*inch, 2.6*inch, 0.8*inch, 0.9*inch, 0.95*inch, 0.85*inch]
        items_table = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign='CENTER')
        items_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8.5),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Qty, Rate, Total, Guarantee
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(items_table)
        return story
    
    def _build_proposal_totals(self, proposal_data: Dict[str, Any]) -> List:
        """Build proposal totals section"""
        story = []
        
        total_amount = proposal_data.get('total_amount', 0)
        if isinstance(total_amount, int):
            total_amount = total_amount / 100  # Convert from cents
        
        currency = proposal_data.get('currency', 'AED').upper()
        
        # Calculate subtotal and tax (assuming 5% VAT)
        tax_rate = 0.05
        subtotal = total_amount / (1 + tax_rate)
        tax_amount = total_amount - subtotal
        
        totals_data = [
            ['', '', '', 'Sub Total', f'{subtotal:.2f}{currency}'],
            ['', '', '', f'Standard Rated ({tax_rate*100}%)', f'{tax_amount:.2f}{currency}'],
            ['', '', '', 'Total', f'{total_amount:.2f}{currency}'],
        ]
        
        totals_table = Table(totals_data, colWidths=[0.5*inch, 2.5*inch, 0.8*inch, 1.5*inch, 1.2*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (3, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (3, 0), (-1, -1), 10),
            ('LINEABOVE', (3, -1), (-1, -1), 1, colors.black),
        ]))
        
        story.append(totals_table)
        
        # Add amount in words
        amount_words = self._number_to_words(int(total_amount))
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(f"With words: {amount_words}", self.styles['Normal']))
        
        return story
    
    def _build_invoice_totals(self, invoice_data: Dict[str, Any]) -> List:
        """Build invoice totals section matching sample formatting."""
        story = []
        subtotal = (invoice_data.get('subtotal') or 0)
        tax_amount = (invoice_data.get('tax_amount') or 0)
        total_amount = (invoice_data.get('total_amount') or 0)
        amount_paid = (invoice_data.get('amount_paid') or 0)
        balance_due = (invoice_data.get('balance_due') or 0)
        
        totals_data = [
            ['', '', '', 'Sub Total', _fmt_currency(subtotal)],
            ['', '', '', 'Standard Rated (5.00%)', _fmt_currency(tax_amount)],
            ['', '', '', 'Total', _fmt_currency(total_amount)],
        ]
        if amount_paid > 0:
            totals_data.append(['', '', '', 'Amount Paid', _fmt_currency(amount_paid)])
            totals_data.append(['', '', '', 'Balance Due', _fmt_currency(balance_due)])
        
        totals_table = Table(totals_data, colWidths=[0.5*inch, 2.5*inch, 0.8*inch, 1.5*inch, 1.2*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (3, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (3, 0), (-1, -1), 10),
            ('LINEABOVE', (3, -1), (-1, -1), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(totals_table)
        
        # Amount in words for total or balance due
        display_amount = balance_due if balance_due > 0 else total_amount
        amount_words = self._number_to_words(int(display_amount/100))
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(f"With words: {amount_words}", self.styles['Normal']))
        return story
    
    def _build_branded_header(self, org: Optional[Dict[str, Any]], title: str, number: str, status: str, right_lines: List[str], center_title: bool = False, include_company_on_left: bool = False) -> Table:
        """Reusable header with company logo/info (left), optional centered title, and doc/company/meta info (right)."""
        left_flow = []
        # Try to render logo if available (logo only on left)
        try:
            if org and org.get('branding', {}).get('logo_url'):
                logo_obj = self._load_logo(org['branding']['logo_url'])
                if logo_obj is not None:
                    left_flow.append(logo_obj)
        except Exception:
            pass
        
        # Organization details
        company_name = org.get('name') if org else None
        settings = (org.get('settings') if org else {}) or {}
        
        # Optionally show company name/address on left (off by default)
        if include_company_on_left and company_name:
            left_flow.append(Paragraph(str(company_name), self.styles['CompanyHeader']))
            for key in ['address_line1', 'address_line2']:
                if settings.get(key):
                    left_flow.append(Paragraph(settings[key], self.styles['Normal']))
            city_line = " ".join([x for x in [settings.get('city'), settings.get('state'), settings.get('postal_code')] if x])
            if city_line:
                left_flow.append(Paragraph(city_line, self.styles['Normal']))
            if settings.get('country'):
                left_flow.append(Paragraph(settings.get('country'), self.styles['Normal']))
        
        # Center column (optional large title)
        center_flow = []
        if center_title:
            center_flow.append(Paragraph(title, self.styles['DocumentTitleCenter']))
        
        # Right column: company info (if not shown on left) + document meta + extra lines
        right_flow = []
        if not include_company_on_left:
            if company_name:
                right_flow.append(Paragraph(str(company_name), self.styles['CompanyHeader']))
            # Tax identifiers
            if settings.get('trn'):
                right_flow.append(Paragraph(f"TRN: {settings['trn']}", self.styles['Normal']))
            elif settings.get('gst_number'):
                right_flow.append(Paragraph(f"GST: {settings['gst_number']}", self.styles['Normal']))
            elif settings.get('tax_number'):
                right_flow.append(Paragraph(f"Tax Number: {settings['tax_number']}", self.styles['Normal']))
            # Contacts
            if settings.get('website'):
                right_flow.append(Paragraph(f"Website: {settings['website']}", self.styles['Normal']))
            if settings.get('contact_email'):
                right_flow.append(Paragraph(f"Email: {settings['contact_email']}", self.styles['Normal']))
            if settings.get('contact_phone'):
                right_flow.append(Paragraph(f"Phone: {settings['contact_phone']}", self.styles['Normal']))
        
        # Document meta
        right_flow.append(Paragraph(number, self.styles['DocumentNumber']))
        right_flow.append(Paragraph(status, self.styles['Status']))
        for line in right_lines:
            if line:
                right_flow.append(Paragraph(line, self.styles['Normal']))
        
        if center_title:
            header_data = [[left_flow, center_flow, right_flow]]
            header_table = Table(header_data, colWidths=[3*inch, 2.2*inch, 1.8*inch])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ]))
        else:
            header_data = [[left_flow, right_flow]]
            header_table = Table(header_data, colWidths=[3*inch, 4*inch])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ]))
        return header_table

    def _build_invoice_context_section(self, invoice_data: Dict[str, Any]) -> List:
        """Two-column section matching sample: 'To' on the left and 'Project/Document' details on the right."""
        story = []
        cust = invoice_data.get('customer') or {}
        proj = invoice_data.get('project') or {}
        # Left column (To)
        left = []
        left.append(Paragraph('To', self.styles['SectionHeader']))
        if cust.get('display_name'):
            left.append(Paragraph(cust['display_name'], self.styles['Normal']))
        if cust.get('company_name'):
            left.append(Paragraph(cust['company_name'], self.styles['Normal']))
        if cust.get('email'):
            left.append(Paragraph(f"Email: {cust['email']}", self.styles['Normal']))
        # Right column (Project/Doc details)
        right = []
        right_fields = [
            ('Project Name', proj.get('name')),
            ('Invoice Number', invoice_data.get('invoice_number')),
            ('Invoice Date', self._format_date(invoice_data.get('invoice_date'))),
            ('Due Date', self._format_date(invoice_data.get('due_date'))),
            ('Payment Terms', invoice_data.get('payment_terms')),
        ]
        for label, value in right_fields:
            if value:
                right.append(Paragraph(f"{label} : {value}", self.styles['Normal']))
        
        context_table = Table([[left, right]], colWidths=[3.5*inch, 3.5*inch])
        context_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(context_table)
        return story

    def _build_client_acceptance_section(self) -> List:
        """Bottom signature section similar to sample."""
        story = []
        story.append(Paragraph('Client Acceptance', self.styles['SectionHeader']))
        data = [
            ['Authorized Person Name', 'Signature', 'Date', 'Stamp'],
            ['\n\n', '\n\n', '\n\n', '\n\n'],
        ]
        table = Table(data, colWidths=[2.5*inch, 2.0*inch, 1.2*inch, 1.8*inch])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 1), (-1, 1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        return story

    def _add_page_number(self, canv: canvas.Canvas, doc):
        """Add page number at the bottom center."""
        page_num_text = f"Page {canv.getPageNumber()}"
        canv.setFont('Helvetica', 9)
        width, height = A4
        canv.drawCentredString(width / 2.0, 0.4 * inch, page_num_text)

    def _draw_watermark(self, canv: canvas.Canvas, text: str):
        """Draw a light diagonal watermark across the page."""
        width, height = A4
        canv.saveState()
        canv.setFont('Helvetica-Bold', 60)
        canv.setFillGray(0.85)
        canv.translate(width/2, height/2)
        canv.rotate(45)
        canv.drawCentredString(0, 0, text)
        canv.restoreState()

    def _resolve_logo_path(self, logo_url: str) -> Optional[str]:
        """Convert a public /uploads/... URL to a filesystem path."""
        try:
            from ..core.config import settings
            # If absolute file path
            if isinstance(logo_url, str) and os.path.isabs(logo_url) and os.path.exists(logo_url):
                return logo_url
            # Map /uploads path to filesystem
            if isinstance(logo_url, str) and logo_url.startswith('/uploads/'):
                relative = logo_url[len('/uploads/'):]
                return os.path.join(settings.UPLOAD_DIR, relative)
        except Exception:
            return None
        return None

    def _load_logo(self, logo_url: str):
        """Return a ReportLab Image for the given logo URL or path."""
        try:
            # http/https: fetch bytes
            if isinstance(logo_url, str) and (logo_url.startswith('http://') or logo_url.startswith('https://')):
                with urllib.request.urlopen(logo_url, timeout=5) as resp:
                    data = resp.read()
                bio = io.BytesIO(data)
                bio.seek(0)
                return Image(bio, width=1.8*inch, height=0.7*inch, kind='proportional')
            # local path or mapped uploads path
            local_path = self._resolve_logo_path(logo_url)
            if local_path and os.path.exists(local_path):
                return Image(local_path, width=1.8*inch, height=0.7*inch, kind='proportional')
        except Exception:
            return None
        return None

    def _build_payment_section(self, invoice_data: Dict[str, Any]) -> List:
        """Build payment information section"""
        story = []
        payment_terms = invoice_data.get('payment_terms', 'Net 30')
        story.append(Paragraph("Payment Information", self.styles['SectionHeader']))
        story.append(Paragraph(f"Payment Terms: {payment_terms}", self.styles['Normal']))
        
        if invoice_data.get('payment_history'):
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph("Payment History:", self.styles['SectionHeader']))
            
            for payment in invoice_data['payment_history']:
                payment_text = f"• {payment.get('payment_date')}: {payment.get('amount')} via {payment.get('payment_method')}"
                if payment.get('reference'):
                    payment_text += f" (Ref: {payment['reference']})"
                story.append(Paragraph(payment_text, self.styles['Normal']))
        
        return story

    # --- Purchase Order PDF ---
    def generate_purchase_order_pdf(self, po_data: Dict[str, Any], org: Optional[Dict[str, Any]] = None) -> io.BytesIO:
        """Legacy PO PDF (kept for compatibility)."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch)
        story: List[Any] = []
        # Header
        story.append(self._build_branded_header(
            org,
            title="PURCHASE ORDER",
            number=f"# {po_data.get('po_number','PO-000001')}",
            status=str(po_data.get('status','draft')).upper(),
            right_lines=[
                po_data.get('vendor_name','Vendor'),
                f"Order Date: {self._format_date(po_data.get('order_date'))}",
                f"Expected: {self._format_date(po_data.get('expected_delivery_date'))}",
            ],
        ))
        story.append(Spacer(1, 0.3*inch))
        # Items table
        items = po_data.get('items', [])
        table_data = [['#','Description','Qty','Unit','Rate','Amount']]
        for i, it in enumerate(items, 1):
            table_data.append([
                str(i),
                f"{it.get('item_name') or ''}\n{it.get('description') or ''}",
                f"{it.get('quantity',0):.2f}",
                it.get('unit','each'),
                f"{it.get('unit_price',0):.2f}",
                f"{it.get('total_price',0):.2f}",
            ])
        tbl = Table(table_data, colWidths=[0.5*inch, 3.3*inch, 0.7*inch, 0.7*inch, 0.9*inch, 1.0*inch])
        tbl.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.3*inch))
        # Totals
        subtotal = po_data.get('subtotal',0)
        tax_amount = po_data.get('tax_amount',0)
        total_amount = po_data.get('total_amount',0)
        totals = [
            ['', '', '', 'Sub Total', f"{subtotal:.2f}"],
            ['', '', '', 'Tax', f"{tax_amount:.2f}"],
            ['', '', '', 'Total', f"{total_amount:.2f}"],
        ]
        t2 = Table(totals, colWidths=[0.5*inch, 3.3*inch, 0.7*inch, 1.2*inch, 1.0*inch])
        t2.setStyle(TableStyle([
            ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
            ('FONTNAME', (3,-1), (-1,-1), 'Helvetica-Bold'),
        ]))
        story.append(t2)
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Client Acceptance", self.styles['SectionHeader']))
        story.append(Paragraph("Name: ____________________    Signature: ____________________    Date: _____________", self.styles['Normal']))
        if po_data.get('terms_and_conditions'):
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph("Terms & Conditions", self.styles['SectionHeader']))
            story.append(Paragraph(str(po_data['terms_and_conditions']), self.styles['Normal']))
        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_quantity_rental_quotation_pdf(self, data: Dict[str, Any], org: Optional[Dict[str, Any]] = None) -> io.BytesIO:
        """Generate a PDF that matches the provided 'Quantity Rental Quotation' design.
        Expected keys in data: items (list of {item_name, description, quantity, unit_price, total_price, guarantee_rate?}),
        vendor_name, project_name, plot_number, structural_element, height, floor_level, slab_thickness,
        concrete_area, formwork_area, system_type, quotation_number, quotation_date, rental_period.
        Falls back to PO fields when not provided.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.4*inch, leftMargin=0.4*inch, rightMargin=0.4*inch, bottomMargin=0.5*inch)
        story: List[Any] = []

        # Top header: logo left, org details right
        header_table_data: List[Any] = []
        left_flow: List[Any] = []
        try:
            if org and org.get('branding', {}).get('logo_url'):
                logo_path = self._resolve_logo_path(org['branding']['logo_url'])
                if logo_path and os.path.exists(logo_path):
                    left_flow.append(Image(logo_path, width=2.2*inch, height=0.8*inch, kind='proportional'))
        except Exception:
            pass
        # Optional subtitle under logo
        left_flow.append(Paragraph((org.get('branding', {}).get('tagline') if org else '') or '', self.styles['Normal']))

        right_lines = []
        org_name = (org or {}).get('name') or ''
        right_lines.append(Paragraph(org_name, ParagraphStyle(name='OrgName', parent=self.styles['Normal'], fontName='Helvetica-Bold', fontSize=12, alignment=TA_RIGHT)))
        settings = (org or {}).get('settings') or {}
        trn = settings.get('tax_number') or settings.get('trn')
        qno = data.get('quotation_number') or data.get('po_number') or 'QOUT-000001'
        qdate = self._format_date(data.get('quotation_date') or data.get('order_date'))
        rperiod = data.get('rental_period') or '4-week'
        small_right_style = ParagraphStyle(name='RightSmall', parent=self.styles['Normal'], fontSize=9, alignment=TA_RIGHT)
        for line in [
            f"TRN: {trn or '-'}",
            f"Quotation No: {qno}",
            f"Quotation Date: {qdate}",
            f"Rental Period: {rperiod}",
        ]:
            right_lines.append(Paragraph(line, small_right_style))
        header = Table([[left_flow, right_lines]], colWidths=[3.6*inch, 3.6*inch])
        header.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ]))
        story.append(header)
        story.append(Spacer(1, 0.1*inch))

        # Center title
        title_style = ParagraphStyle(name='CenteredTitle', parent=self.styles['DocumentTitle'], alignment=TA_CENTER)
        story.append(Paragraph('Quantity Rental Quotation', title_style))
        story.append(Spacer(1, 0.12*inch))

        # Two info boxes: left 'To' and right project details
        left_box: List[Any] = []
        left_box.append(Paragraph('<b>To</b>', self.styles['SectionHeader']))
        left_box.append(Paragraph(data.get('vendor_name') or data.get('to_name') or '-', self.styles['Normal']))
        # Label-value lines
        def label_value(label: str, value: Any) -> Paragraph:
            return Paragraph(f"{label} : {value if (value is not None and value != '') else '-'}", self.styles['Normal'])
        left_box.append(label_value('System Type', data.get('system_type') or 'Cup-lock + Aluminum'))
        left_box.append(label_value('Floor Level', data.get('floor_level') or 'Floor Level'))
        left_box.append(label_value('Concrete Area', f"{data.get('concrete_area', '500.00') :}"))
        left_box.append(label_value('Formwork Area', f"{data.get('formwork_area', '500.00') :}"))

        right_pairs = [
            ('Project Name', data.get('project_name') or data.get('project') or ''),
            ('Plot Number', data.get('plot_number') or ''),
            ('Structural Element', data.get('structural_element') or ''),
            ('Height', data.get('height') or ''),
            ('Floor Level', data.get('floor_level') or ''),
            ('Slab Thickness/Meter', data.get('slab_thickness') or ''),
        ]
        right_table = Table([[Paragraph(f"{k} :", self.styles['Normal']), Paragraph(str(v or '-') , self.styles['Normal'])] for k,v in right_pairs], colWidths=[1.8*inch, 1.8*inch])
        right_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        info = Table([[left_box, right_table]], colWidths=[3.6*inch, 3.6*inch])
        info.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(info)
        story.append(Spacer(1, 0.12*inch))

        # Items table styled like the sample
        items = data.get('items', [])
        table_headers = ['#', 'Description', 'Qty', 'Rate', 'Total Amount', 'Guarantee Rate']
        table_data: List[List[Any]] = [table_headers]
        for idx, it in enumerate(items, start=1):
            desc = f"{(it.get('item_name') or '')} {('L:' + str(it.get('length')) if it.get('length') else '')}"
            if it.get('description'):
                desc = f"{desc}\n{it.get('description')}".strip()
            qty = f"{float(it.get('quantity', 0)):.2f}"
            rate = f"{float(it.get('unit_price', 0)):.2f}"
            amount = f"{float(it.get('total_price', 0)):.2f}"
            guarantee = f"{float(it.get('guarantee_rate', 0)):.2f}"
            table_data.append([str(idx), desc, qty, rate, amount, guarantee])
        col_widths = [0.4*inch, 3.7*inch, 0.8*inch, 0.9*inch, 1.1*inch, 1.1*inch]
        items_tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        items_tbl.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('ALIGN', (2,1), (-1,-1), 'RIGHT'),  # Numbers right aligned
            ('ALIGN', (1,1), (1,-1), 'LEFT'),
        ]))
        story.append(items_tbl)

        # Totals row at end if provided
        totals_amount = data.get('total_amount')
        if totals_amount is None:
            try:
                totals_amount = sum(float(it.get('total_price', 0) or 0) for it in items)
            except Exception:
                totals_amount = 0
        totals_row = Table([
            ['', '', Paragraph('<b>Total</b>', self.styles['Normal']), Paragraph(f"{float(totals_amount):.2f}", self.styles['Normal']), '', '']
        ], colWidths=col_widths)
        totals_row.setStyle(TableStyle([
            ('SPAN', (0,0), (2,0)),
            ('SPAN', (4,0), (5,0)),
            ('ALIGN', (3,0), (3,0), 'RIGHT'),
            ('LINEABOVE', (0,0), (-1,0), 0.8, colors.black),
        ]))
        story.append(totals_row)

        story.append(Spacer(1, 0.15*inch))

        # Client Acceptance area
        story.append(Paragraph('Client Acceptance', ParagraphStyle(name='CA', parent=self.styles['SectionHeader'], alignment=TA_CENTER)))
        sig_table = Table([
            [Paragraph('Authorized Person Name', self.styles['Normal']), Paragraph('Signature', self.styles['Normal']), Paragraph('Date', self.styles['Normal']), Paragraph('Stamp', self.styles['Normal'])],
            ['','', '', ''],
        ], colWidths=[2.6*inch, 2.3*inch, 1.0*inch, 1.3*inch])
        sig_table.setStyle(TableStyle([
            ('LINEABOVE', (0,1), (-1,1), 0.8, colors.black),
            ('TOPPADDING', (0,1), (-1,1), 18),
        ]))
        story.append(sig_table)

        # Footer: page number center
        def _footer(canvas: canvas.Canvas, doc_):
            page_num = canvas.getPageNumber()
            footer_text = f"Page {page_num}"
            canvas.setFont('Helvetica', 8)
            canvas.drawCentredString((A4[0])/2.0, 0.35*inch, footer_text)
        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
        buffer.seek(0)
        return buffer

    # --- Project Report PDF (summary) ---
    def generate_project_report_pdf(self, report: Dict[str, Any], org: Optional[Dict[str, Any]] = None) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch)
        story: List[Any] = []
        story.append(self._build_branded_header(
            org,
            title="PROJECT REPORT",
            number=f"Project: {report.get('project',{}).get('name','')}",
            status=str(report.get('project',{}).get('status','')).upper(),
            right_lines=[
                f"Created: {self._format_date(report.get('generated_at'))}",
                f"Owner: {report.get('project',{}).get('owner','')}",
            ],
        ))
        story.append(Spacer(1, 0.3*inch))
        # Basic metrics tables (tasks and invoices)
        if report.get('tasks'):
            story.append(Paragraph("Task Summary", self.styles['SectionHeader']))
            td = [['Status','Count']]
            for k,v in report['tasks'].items():
                td.append([k, v])
            t = Table(td, colWidths=[2*inch, 1*inch])
            t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))
            story.append(t)
            story.append(Spacer(1, 0.2*inch))
        if report.get('invoices'):
            story.append(Paragraph("Invoice Summary", self.styles['SectionHeader']))
            td = [['Metric','Amount']]
            for k,v in report['invoices'].items():
                td.append([k, f"{v:.2f}"])
            t = Table(td, colWidths=[2*inch, 1.5*inch])
            t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))
            story.append(t)
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def _build_terms_section(self, terms_text: str) -> List:
        """Build terms and conditions section"""
        story = []
        
        story.append(Paragraph("Client Acceptance", self.styles['SectionHeader']))
        story.append(Paragraph("Name: ____________________    Signature: ____________________    Date: _____________", self.styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Terms & Conditions", self.styles['SectionHeader']))
        story.append(Paragraph(terms_text, self.styles['Normal']))
        
        return story
    
    def _format_date(self, date_str: Optional[str]) -> str:
        """Format date string for display"""
        if not date_str:
            return 'N/A'
        
        try:
            if 'T' in date_str:  # ISO format
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.strftime('%d-%m-%Y')
        except:
            return date_str
    
    def _number_to_words(self, number: int) -> str:
        """Convert number to words (basic implementation)"""
        if number == 0:
            return "Zero Dirhams"
        
        ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
                "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
                "Seventeen", "Eighteen", "Nineteen"]
        
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
        
        def convert_hundreds(n):
            result = ""
            if n >= 100:
                result += ones[n // 100] + " Hundred "
                n %= 100
            if n >= 20:
                result += tens[n // 10] + " "
                n %= 10
            if n > 0:
                result += ones[n] + " "
            return result
        
        if number < 1000:
            return convert_hundreds(number).strip() + " Dirhams"
        elif number < 1000000:
            thousands = number // 1000
            remainder = number % 1000
            result = convert_hundreds(thousands).strip() + " Thousand "
            if remainder > 0:
                result += convert_hundreds(remainder)
            return result.strip() + " Dirhams"
        else:
            return f"{number} Dirhams"  # Fallback for very large numbers

