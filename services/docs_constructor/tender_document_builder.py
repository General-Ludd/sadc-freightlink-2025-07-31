from io import BytesIO
from typing import Dict, Any, List
from datetime import datetime
from urllib.request import urlopen

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
    Image,
)


from PIL import Image as PILImage

# BRANDING
# ============================================================

SADC_FREIGHTLINK_LOGO = (
    "https://ik.imagekit.io/0bf9ktdig/"
    "ChatGPT%20Image%20Sep%202,%202025,%2009_25_07%20PM.png"
    "?updatedAt=1762145054656"
)


# ============================================================
# LOGO LOADER
# ============================================================

def load_logo(
    logo_source,
    max_width,
    max_height
):
    if not logo_source:
        return None

    try:

        if (
            isinstance(logo_source, str)
            and (
                logo_source.startswith("http://")
                or logo_source.startswith("https://")
            )
        ):
            image_bytes = urlopen(
                logo_source,
                timeout=15
            ).read()

            image_buffer = BytesIO(
                image_bytes
            )

        else:

            with open(
                logo_source,
                "rb"
            ) as file:

                image_buffer = BytesIO(
                    file.read()
                )

        pil_image = PILImage.open(
            image_buffer
        )

        width, height = pil_image.size

        ratio = min(
            max_width / width,
            max_height / height
        )

        final_width = width * ratio
        final_height = height * ratio

        image_buffer.seek(0)

        return Image(
            image_buffer,
            width=final_width,
            height=final_height
        )

    except Exception as e:

        print(
            f"Unable to load logo: {e}"
        )

        return None


# ============================================================
# FORMATTING
# ============================================================

def display(value):

    if value is None:
        return "—"

    if value is True:
        return "Yes"

    if value is False:
        return "No"

    if isinstance(value, list):

        if not value:
            return "—"

        return ", ".join(
            str(item)
            for item in value
        )

    return str(value)


def format_number(value):

    if value is None:
        return "—"

    if isinstance(value, float):

        if value.is_integer():
            return f"{int(value):,}"

        return f"{value:,.2f}"

    if isinstance(value, int):
        return f"{value:,}"

    return str(value)


def format_date(value):

    if not value:
        return "—"

    if isinstance(value, str):

        try:

            parsed = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00"
                )
            )

            return parsed.strftime(
                "%d %B %Y"
            )

        except Exception:
            return value

    try:

        return value.strftime(
            "%d %B %Y"
        )

    except Exception:

        return str(value)


def format_datetime(value):

    if not value:
        return "—"

    if isinstance(value, str):

        try:

            parsed = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00"
                )
            )

            return parsed.strftime(
                "%d %B %Y %H:%M"
            )

        except Exception:
            return value

    try:

        return value.strftime(
            "%d %B %Y %H:%M"
        )

    except Exception:

        return str(value)


def money(value):

    if value is None:
        return "—"

    try:
        return f"R {float(value):,.2f}"
    except Exception:
        return str(value)


# ============================================================
# STYLES
# ============================================================

def build_styles():

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            alignment=TA_CENTER,
            textColor=colors.black,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CoverSubtitle",
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#333333"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="DocumentTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            alignment=TA_LEFT,
            spaceAfter=5 * mm,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            spaceBefore=0,
            spaceAfter=6 * mm,
            textColor=colors.black,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionNumber",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#555555"),
            spaceAfter=2 * mm,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SubHeading",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            spaceBefore=4 * mm,
            spaceAfter=3 * mm,
        )
    )

    styles.add(
        ParagraphStyle(
            name="BodyCorporate",
            fontName="Helvetica",
            fontSize=9,
            leading=14,
            spaceAfter=4 * mm,
            textColor=colors.HexColor("#222222"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="BodySmall",
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#333333"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableHeader",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=colors.white,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableBody",
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#222222"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="RoleHeading",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            spaceAfter=3 * mm,
        )
    )

    return styles


# ============================================================
# CORPORATE TABLE
# ============================================================

def corporate_table(
    rows,
    styles,
    widths=None
):

    formatted_rows = []

    for row_index, row in enumerate(rows):

        formatted_row = []

        for cell in row:

            style = (
                styles["TableHeader"]
                if row_index == 0
                else styles["TableBody"]
            )

            formatted_row.append(
                Paragraph(
                    display(cell),
                    style
                )
            )

        formatted_rows.append(
            formatted_row
        )

    table = Table(
        formatted_rows,
        colWidths=widths,
        repeatRows=1
    )

    table.setStyle(
        TableStyle([

            # Header
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.black
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            # Body
            (
                "BACKGROUND",
                (0, 1),
                (-1, -1),
                colors.white
            ),

            # Fine corporate grid
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.25,
                colors.HexColor("#BDBDBD")
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

        ])
    )

    return table


# ============================================================
# SECTION PAGE HEADER
# ============================================================

def section_page_title(
    story,
    styles,
    section_number,
    title
):

    story.append(
        Paragraph(
            section_number,
            styles["SectionNumber"]
        )
    )

    story.append(
        Paragraph(
            title,
            styles["SectionHeading"]
        )
    )

    story.append(
        HRFlowable(
            width="100%",
            thickness=0.8,
            color=colors.black,
            spaceBefore=0,
            spaceAfter=7 * mm
        )
    )


# ============================================================
# HEADER / FOOTER
# ============================================================

def make_header_footer(
    client_logo_source
):

    def header_footer(
        canvas,
        doc
    ):

        canvas.saveState()

        width, height = A4

        # ----------------------------------------------------
        # Header logos
        # ----------------------------------------------------

        sadc_logo = load_logo(
            SADC_FREIGHTLINK_LOGO,
            42 * mm,
            13 * mm
        )

        client_logo = load_logo(
            client_logo_source,
            42 * mm,
            13 * mm
        )

        if sadc_logo:

            sadc_logo.drawOn(
                canvas,
                18 * mm,
                height - 20 * mm
            )

        if client_logo:

            client_logo.drawOn(
                canvas,
                width - 18 * mm - client_logo.drawWidth,
                height - 20 * mm
            )

        # ----------------------------------------------------
        # Header line
        # ----------------------------------------------------

        canvas.setStrokeColor(
            colors.black
        )

        canvas.setLineWidth(
            0.4
        )

        canvas.line(
            18 * mm,
            height - 23 * mm,
            width - 18 * mm,
            height - 23 * mm
        )

        # ----------------------------------------------------
        # Footer line
        # ----------------------------------------------------

        canvas.setStrokeColor(
            colors.HexColor("#BDBDBD")
        )

        canvas.line(
            18 * mm,
            16 * mm,
            width - 18 * mm,
            16 * mm
        )

        # ----------------------------------------------------
        # Footer text
        # ----------------------------------------------------

        canvas.setFont(
            "Helvetica",
            7
        )

        canvas.setFillColor(
            colors.HexColor("#555555")
        )

        canvas.drawString(
            18 * mm,
            10 * mm,
            "Private & Confidential"
        )

        canvas.drawCentredString(
            width / 2,
            10 * mm,
            "SADC FREIGHTLINK"
        )

        canvas.drawRightString(
            width - 18 * mm,
            10 * mm,
            f"Page {doc.page}"
        )

        canvas.restoreState()

    return header_footer


# ============================================================
# COVER PAGE
# ============================================================

def build_cover(
    story,
    styles
):

    story.append(
        Spacer(
            1,
            82 * mm
        )
    )

    sadc_logo = load_logo(
        SADC_FREIGHTLINK_LOGO,
        95 * mm,
        45 * mm
    )

    if sadc_logo:

        story.append(
            sadc_logo
        )

    story.append(
        PageBreak()
    )


# ============================================================
# DOCUMENT CONTROL / INDEX
# ============================================================

def build_document_control(
    story,
    styles,
    summary,
    client_name
):

    story.append(
        Paragraph(
            "REQUEST FOR QUOTATION",
            styles["DocumentTitle"]
        )
    )

    story.append(
        Paragraph(
            "Transportation of Goods",
            styles["CoverSubtitle"]
        )
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    story.append(
        Paragraph(
            f"<b>On behalf of:</b> {client_name}",
            styles["BodyCorporate"]
        )
    )

    overview = [
        [
            "Document Control",
            "Details"
        ],
        [
            "Client",
            client_name
        ],
        [
            "Tender Reference",
            display(
                summary.get(
                    "tender_family_id"
                )
            )
        ],
        [
            "Tender Structure",
            display(
                summary.get(
                    "tender_structure"
                )
            )
        ],
        [
            "Tender Count",
            display(
                summary.get(
                    "total_tenders"
                )
            )
        ],
        [
            "Contract Period",
            (
                f"{format_date(summary.get('contract_period', {}).get('start_date'))}"
                f" – "
                f"{format_date(summary.get('contract_period', {}).get('end_date'))}"
            )
        ],
        [
            "Closing Date",
            format_datetime(
                summary.get(
                    "closing_date"
                )
            )
        ],
    ]

    story.append(
        corporate_table(
            overview,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    story.append(
        Paragraph(
            "DOCUMENT INDEX",
            styles["SectionHeading"]
        )
    )

    index_rows = [
        ["Section", "Description"],
        ["1", "Executive Summary"],
        ["2", "Procurement Overview"],
        ["3", "Roles and Responsibilities"],
        ["4", "Tender Conditions and Confidentiality"],
        ["5", "Tender Process and Submission"],
        ["6", "Tender Lane Requirements"],
        ["7", "SADC FREIGHTLINK Administration"],
        ["8", "General Carrier Obligations"],
        ["9", "Closing Statement"],
    ]

    story.append(
        corporate_table(
            index_rows,
            styles,
            widths=[
                25 * mm,
                142 * mm
            ]
        )
    )

    story.append(
        PageBreak()
    )


# ============================================================
# EXECUTIVE SUMMARY
# ============================================================

def build_executive_summary(
    story,
    styles,
    summary,
    client_name
):

    section_page_title(
        story,
        styles,
        "01",
        "Executive Summary"
    )

    corporate_summary = summary.get(
        "corporate_summary"
    )

    if corporate_summary:

        story.append(
            Paragraph(
                corporate_summary,
                styles["BodyCorporate"]
            )
        )

    story.append(
        Paragraph(
            "Procurement Mandate",
            styles["SubHeading"]
        )
    )

    story.append(
        Paragraph(
            f"""
            <b>{client_name}</b> has appointed
            <b>SADC FREIGHTLINK</b> as its freight procurement
            and transportation partner for the procurement and
            administration of the transportation services described
            in this Request for Quotation.
            """,
            styles["BodyCorporate"]
        )
    )

    story.append(
        Paragraph(
            """
            SADC FREIGHTLINK will administer the RFQ process,
            facilitate carrier participation, manage quotation
            submissions, administer the tender process and support
            the subsequent transportation execution through the
            SADC FREIGHTLINK platform.
            """,
            styles["BodyCorporate"]
        )
    )

    rows = [
        ["Procurement Indicator", "Requirement"],
        [
            "Tender Structure",
            summary.get(
                "tender_structure"
            )
        ],
        [
            "Tender Categories",
            display(
                summary.get(
                    "tender_categories"
                )
            )
        ],
        [
            "Tender Length",
            display(
                summary.get(
                    "tender_length_categories"
                )
            )
        ],
        [
            "Commodities",
            display(
                summary.get(
                    "commodities"
                )
            )
        ],
        [
            "Load Types",
            display(
                summary.get(
                    "load_types"
                )
            )
        ],
        [
            "Combined Volume",
            display(
                summary.get(
                    "volume_statement"
                )
            )
        ],
        [
            "Primary Equipment",
            display(
                summary.get(
                    "primary_equipment"
                )
            )
        ],
    ]

    story.append(
        corporate_table(
            rows,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    story.append(
        PageBreak()
    )


# ============================================================
# ROLES AND RESPONSIBILITIES
# ============================================================

def build_roles_and_responsibilities(
    story,
    styles,
    client_name
):

    section_page_title(
        story,
        styles,
        "03",
        "Roles and Responsibilities"
    )

    # --------------------------------------------------------
    # CLIENT
    # --------------------------------------------------------

    story.append(
        Paragraph(
            "Client Responsibilities",
            styles["RoleHeading"]
        )
    )

    story.append(
        Paragraph(
            f"""
            <b>{client_name}</b> remains the principal requiring
            the transportation services and is responsible for
            providing accurate operational, commercial and
            service requirements to SADC FREIGHTLINK.
            """,
            styles["BodyCorporate"]
        )
    )

    client_rows = [
        ["Responsibility", "Client Role"],
        [
            "Freight Requirement",
            "Define the transportation requirements, lanes, cargo,
             expected volumes and operational requirements."
        ],
        [
            "Operational Information",
            "Provide accurate facility, loading, delivery and
             cargo information required for execution."
        ],
        [
            "Commercial Requirements",
            "Approve the applicable commercial framework,
             payment terms and procurement objectives."
        ],
        [
            "Operational Decisions",
            "Provide required approvals and instructions relating
             to the Client's freight operations."
        ],
    ]

    story.append(
        corporate_table(
            client_rows,
            styles,
            widths=[
                45 * mm,
                122 * mm
            ]
        )
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    # --------------------------------------------------------
    # SADC FREIGHTLINK
    # --------------------------------------------------------

    story.append(
        Paragraph(
            "SADC FREIGHTLINK Responsibilities",
            styles["RoleHeading"]
        )
    )

    sadc_rows = [
        ["Responsibility", "SADC FREIGHTLINK Role"],
        [
            "RFQ Administration",
            "Prepare, issue and administer the RFQ process."
        ],
        [
            "Carrier Communication",
            "Manage carrier communication and procurement
             correspondence through the platform."
        ],
        [
            "Carrier Qualification",
            "Facilitate carrier participation and qualification
             against the requirements of the RFQ."
        ],
        [
            "Quotation Management",
            "Receive, administer and manage carrier quotations
             and bid submissions."
        ],
        [
            "Evaluation Support",
            "Provide procurement administration and evaluation
             support to the Client."
        ],
        [
            "Award Administration",
            "Administer carrier appointment, award and
             onboarding processes."
        ],
        [
            "Transportation Booking",
            "Manage transportation bookings and execution
             administration through the platform."
        ],
        [
            "Payment Administration",
            "Administer the agreed payment workflow and
             supporting documentation."
        ],
        [
            "POD Administration",
            "Manage submission and administration of delivery
             documentation and proof of delivery."
        ],
        [
            "SLA Review",
            "Monitor and review carrier service-level
             performance."
        ],
        [
            "Fuel Review",
            "Administer agreed fuel adjustment and review
             mechanisms where applicable."
        ],
        [
            "Disputes and Claims",
            "Coordinate the administration and communication
             of transportation disputes and claims."
        ],
    ]

    story.append(
        corporate_table(
            sadc_rows,
            styles,
            widths=[
                45 * mm,
                122 * mm
            ]
        )
    )

    story.append(
        PageBreak()
    )

    # --------------------------------------------------------
    # CARRIER
    # --------------------------------------------------------

    section_page_title(
        story,
        styles,
        "",
        "Participating Carrier Responsibilities"
    )

    carrier_rows = [
        ["Responsibility", "Carrier Role"],
        [
            "Quotation",
            "Submit accurate, complete and commercially binding
             quotations through SADC FREIGHTLINK."
        ],
        [
            "Capacity",
            "Maintain the vehicle and capacity commitments
             represented during the tender process."
        ],
        [
            "Compliance",
            "Maintain all licences, permits, insurance,
             certifications and regulatory compliance."
        ],
        [
            "Execution",
            "Execute awarded transportation services in accordance
             with the RFQ and agreed service levels."
        ],
        [
            "Drivers",
            "Ensure drivers meet all qualification, documentation,
             security and operational requirements."
        ],
        [
            "Tracking",
            "Provide required vehicle tracking and operational
             visibility."
        ],
        [
            "Documentation",
            "Submit PODs, delivery documentation and incident
             documentation within the required SLA."
        ],
        [
            "Incidents",
            "Immediately report accidents, theft, delays,
             damages and other material incidents."
        ],
        [
            "Claims",
            "Cooperate fully with claims investigation and
             settlement processes."
        ],
        [
            "Platform Usage",
            "Use the SADC FREIGHTLINK platform for applicable
             tender, booking and execution processes."
        ],
    ]

    story.append(
        corporate_table(
            carrier_rows,
            styles,
            widths=[
                45 * mm,
                122 * mm
            ]
        )
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    story.append(
        Paragraph(
            """
            Participation in this RFQ constitutes acknowledgement
            that the carrier understands the respective roles of
            the Client, SADC FREIGHTLINK and the carrier and agrees
            to comply with the applicable requirements communicated
            through the RFQ and SADC FREIGHTLINK platform.
            """,
            styles["BodyCorporate"]
        )
    )

    story.append(
        PageBreak()
    )


# ============================================================
# TENDER CONDITIONS
# ============================================================

def build_conditions(
    story,
    styles,
    client_name
):

    section_page_title(
        story,
        styles,
        "04",
        "Tender Conditions and Confidentiality"
    )

    paragraphs = [

        """
        This Request for Quotation is issued by SADC FREIGHTLINK
        in its capacity as the appointed freight procurement and
        transportation partner acting on behalf of the Client.
        The purpose of the RFQ is to identify suitably qualified,
        compliant and commercially competitive transportation
        service providers.
        """,

        """
        All information contained in this RFQ, including operational,
        commercial, route, volume, facility and service information,
        is confidential and is provided solely for the purpose of
        preparing a response to this procurement event.
        """,

        """
        Participating carriers shall not disclose, reproduce,
        distribute or otherwise make available any confidential
        information contained within this RFQ to any third party
        without the prior written approval of the Client or
        SADC FREIGHTLINK.
        """,

        """
        The issuance of this RFQ does not constitute an obligation
        on the part of the Client or SADC FREIGHTLINK to award any
        volume, lane or transportation service to any participating
        carrier.
        """,

        """
        The Client and SADC FREIGHTLINK reserve the right to
        evaluate submissions using commercial, operational,
        capacity, compliance, service and other procurement
        criteria considered relevant to the requirements.
        """,

        """
        SADC FREIGHTLINK may communicate amendments, clarifications,
        responses to questions and other procurement instructions
        through the SADC FREIGHTLINK platform. Participating
        carriers are responsible for monitoring such communications.
        """,
    ]

    for paragraph in paragraphs:

        story.append(
            Paragraph(
                paragraph,
                styles["BodyCorporate"]
            )
        )

    story.append(
        PageBreak()
    )


# ============================================================
# TENDER PROCESS
# ============================================================

def build_tender_process(
    story,
    styles,
    summary
):

    section_page_title(
        story,
        styles,
        "05",
        "Tender Process and Submission"
    )

    rows = [
        ["Process Item", "Requirement"],
        [
            "Tender Issue",
            format_date(
                summary.get(
                    "issued_date"
                )
            )
        ],
        [
            "Questions Deadline",
            format_datetime(
                summary.get(
                    "questions_deadline"
                )
            )
        ],
        [
            "Submission Deadline",
            format_datetime(
                summary.get(
                    "closing_date"
                )
            )
        ],
        [
            "Submission Platform",
            "SADC FREIGHTLINK"
        ],
        [
            "Quotation Method",
            "Electronic quotation through the SADC FREIGHTLINK platform"
        ],
    ]

    story.append(
        corporate_table(
            rows,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    process_text = [

        """
        All participating carriers are required to submit their
        quotations through the SADC FREIGHTLINK platform in the
        format and within the timeframes specified for the tender.
        """,

        """
        Carriers are responsible for ensuring that their submissions
        are complete, accurate and submitted before the applicable
        closing deadline.
        """,

        """
        SADC FREIGHTLINK will administer carrier communication,
        questions, clarifications, bid administration and relevant
        procurement notifications through the platform.
        """,

        """
        Late submissions may not be considered unless expressly
        authorised by SADC FREIGHTLINK or the Client.
        """,

    ]

    for paragraph in process_text:

        story.append(
            Paragraph(
                paragraph,
                styles["BodyCorporate"]
            )
        )

    story.append(
        PageBreak()
    )


# ============================================================
# INDIVIDUAL TENDER
# ============================================================

def build_individual_tender(
    story,
    styles,
    tender,
    index
):

    reference = (
        tender.get(
            "tender_reference"
        )
        or f"Tender Lane {index}"
    )

    title = (
        tender.get(
            "tender_title"
        )
        or f"Tender Lane {index}"
    )

    # ========================================================
    # TENDER OVERVIEW
    # ========================================================

    section_page_title(
        story,
        styles,
        f"06.{index}",
        title
    )

    story.append(
        Paragraph(
            f"<b>Tender Reference:</b> {reference}",
            styles["BodyCorporate"]
        )
    )

    story.append(
        Paragraph(
            "Scope of Work",
            styles["SubHeading"]
        )
    )

    story.append(
        Paragraph(
            display(
                tender.get(
                    "scope_description"
                )
            ),
            styles["BodyCorporate"]
        )
    )

    tender_info = [
        ["Tender Information", "Requirement"],
        [
            "Tender Category",
            tender.get(
                "tender_category"
            )
        ],
        [
            "Tender Length",
            tender.get(
                "tender_length_category"
            )
        ],
        [
            "Contract Start",
            format_date(
                tender.get(
                    "contract_start_date"
                )
            )
        ],
        [
            "Contract End",
            format_date(
                tender.get(
                    "contract_end_date"
                )
            )
        ],
        [
            "Load Type",
            tender.get(
                "load_type"
            )
        ],
        [
            "Trip Type",
            tender.get(
                "trip_type"
            )
        ],
        [
            "Priority",
            tender.get(
                "priority_level"
            )
        ],
        [
            "Customer Reference",
            tender.get(
                "customer_reference"
            )
        ],
    ]

    story.append(
        corporate_table(
            tender_info,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    story.append(
        PageBreak()
    )

    # ========================================================
    # ROUTING
    # ========================================================

    section_page_title(
        story,
        styles,
        f"06.{index}.1",
        "Route and Facilities"
    )

    routing = tender.get(
        "routing",
        {}
    )

    origin = routing.get(
        "origin"
    ) or {}

    destination = routing.get(
        "destination"
    ) or {}

    route_rows = [
        ["Route Element", "Details"],
        [
            "Origin Facility",
            origin.get(
                "facility_name"
            )
        ],
        [
            "Origin",
            origin.get(
                "complete_address"
            )
            or origin.get(
                "address"
            )
        ],
        [
            "Destination Facility",
            destination.get(
                "facility_name"
            )
        ],
        [
            "Destination",
            destination.get(
                "complete_address"
            )
            or destination.get(
                "address"
            )
        ],
        [
            "Distance",
            (
                f"{format_number(routing.get('actual_distance_km'))} km"
            )
        ],
        [
            "Trip Type",
            routing.get(
                "trip_type"
            )
        ],
        [
            "Customs Responsibility",
            routing.get(
                "border_customs_responsibility"
            )
        ],
    ]

    story.append(
        corporate_table(
            route_rows,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    intermediate_stops = routing.get(
        "intermediate_stops",
        []
    )

    if intermediate_stops:

        story.append(
            Paragraph(
                "Intermediate Stops and Facility Requirements",
                styles["SubHeading"]
            )
        )

        stop_rows = [
            [
                "Seq.",
                "Facility",
                "Location",
                "Turnaround",
                "Demurrage"
            ]
        ]

        for stop in intermediate_stops:

            protocol = (
                stop.get(
                    "turnaround_window_demurrage_protocol"
                )
                or {}
            )

            turnaround = (
                f"{display(protocol.get('loading_offloading_turnaround_hours'))} hrs"
            )

            demurrage = (
                f"{display(protocol.get('free_demurrage_hours'))} hrs free"
            )

            stop_rows.append([
                stop.get(
                    "stop_sequence"
                ),
                stop.get(
                    "facility_name"
                ),
                (
                    stop.get(
                        "complete_address"
                    )
                    or stop.get(
                        "address"
                    )
                ),
                turnaround,
                demurrage
            ])

        story.append(
            corporate_table(
                stop_rows,
                styles,
                widths=[
                    14 * mm,
                    38 * mm,
                    67 * mm,
                    24 * mm,
                    24 * mm
                ]
            )
        )

    story.append(
        PageBreak()
    )

    # ========================================================
    # CARGO
    # ========================================================

    section_page_title(
        story,
        styles,
        f"06.{index}.2",
        "Cargo and Volume Requirements"
    )

    cargo = tender.get(
        "cargo",
        {}
    )

    cargo_rows = [
        ["Requirement", "Specification"],
        [
            "Commodity",
            cargo.get(
                "commodity"
            )
        ],
        [
            "Load Type",
            cargo.get(
                "load_type"
            )
        ],
        [
            "Average Shipment Weight",
            f"{format_number(cargo.get('average_shipment_weight_kg'))} kg"
        ],
        [
            "Minimum Weight",
            f"{format_number(cargo.get('minimum_weight_bracket_kg'))} kg"
        ],
        [
            "Packaging",
            cargo.get(
                "packaging_type"
            )
        ],
        [
            "Packaging Quantity",
            cargo.get(
                "packaging_quantity"
            )
        ],
        [
            "Temperature Control",
            cargo.get(
                "temperature_control"
            )
        ],
        [
            "Target Temperature",
            cargo.get(
                "target_temperature_spec"
            )
        ],
        [
            "Hazardous Materials",
            display(
                cargo.get(
                    "hazardous_materials"
                )
            )
        ],
        [
            "Hazchem Classification",
            cargo.get(
                "hazchem_classification"
            )
        ],
        [
            "Under Bond",
            display(
                cargo.get(
                    "under_bond"
                )
            )
        ],
    ]

    story.append(
        corporate_table(
            cargo_rows,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    volume = tender.get(
        "volume",
        {}
    )

    story.append(
        Paragraph(
            "Volume Commitment and Schedule",
            styles["SubHeading"]
        )
    )

    volume_rows = [
        ["Volume Requirement", "Details"],
        [
            "Entry Method",
            volume.get(
                "entry_method"
            )
        ],
        [
            "Volume Commitment",
            volume.get(
                "commitment"
            )
        ],
    ]

    for profile in volume.get(
        "profiles",
        []
    ):

        label = (
            profile.get(
                "period_label"
            )
            or profile.get(
                "day_of_week"
            )
        )

        volume_rows.append([
            label,
            (
                f"{format_number(profile.get('expected_loads'))} loads"
            )
        ])

    story.append(
        corporate_table(
            volume_rows,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    story.append(
        PageBreak()
    )

    # ========================================================
    # EQUIPMENT
    # ========================================================

    section_page_title(
        story,
        styles,
        f"06.{index}.3",
        "Vehicle and Equipment Requirements"
    )

    equipment = (
        tender.get(
            "equipment",
            {}
        )
        .get(
            "configurations",
            []
        )
    )

    equipment_rows = [
        [
            "Configuration",
            "Truck",
            "Equipment",
            "Trailer",
            "Length"
        ]
    ]

    for config in equipment:

        equipment_rows.append([
            config.get(
                "configuration_type"
            ),
            config.get(
                "truck_type"
            ),
            config.get(
                "equipment_type"
            ),
            config.get(
                "trailer_type"
            ),
            config.get(
                "trailer_length"
            ),
        ])

    if len(equipment_rows) > 1:

        story.append(
            corporate_table(
                equipment_rows,
                styles,
                widths=[
                    27 * mm,
                    32 * mm,
                    36 * mm,
                    40 * mm,
                    32 * mm
                ]
            )
        )

    requirements = tender.get(
        "equipment",
        {}
    ).get(
        "compliance",
        {}
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    compliance_rows = [
        ["Equipment Compliance", "Required"],
        [
            "Tarpaulin Compliance",
            display(
                requirements.get(
                    "tarpaulin_compliance_required"
                )
            )
        ],
        [
            "Corner Plates",
            display(
                requirements.get(
                    "corner_plates_required"
                )
            )
        ],
        [
            "Chock Blocks",
            display(
                requirements.get(
                    "chock_blocks_required"
                )
            )
        ],
        [
            "Ratchets / Belts",
            display(
                requirements.get(
                    "ratchets_belts_required"
                )
            )
        ],
        [
            "Other Requirements",
            requirements.get(
                "other_equipment_requirements"
            )
        ],
    ]

    story.append(
        corporate_table(
            compliance_rows,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    story.append(
        PageBreak()
    )

    # ========================================================
    # CARRIER REQUIREMENTS
    # ========================================================

    section_page_title(
        story,
        styles,
        f"06.{index}.4",
        "Carrier, Driver and Security Requirements"
    )

    requirements = tender.get(
        "carrier_requirements",
        {}
    )

    carrier_rows = [
        ["Requirement", "Specification"],
        [
            "Subcontracting Policy",
            requirements.get(
                "subcontracting_policy"
            )
        ],
        [
            "Driver Mobile Phone",
            display(
                requirements.get(
                    "driver_mobile_phone"
                )
            )
        ],
        [
            "24-Hour Control Room",
            display(
                requirements.get(
                    "all_time_hour_control_room"
                )
            )
        ],
        [
            "Vehicle Tracking",
            display(
                requirements.get(
                    "vehicle_tracking_required"
                )
            )
        ],
        [
            "Clean / Compliant Equipment",
            display(
                requirements.get(
                    "clean_compliant_equipment"
                )
            )
        ],
        [
            "Pallet Management",
            display(
                requirements.get(
                    "pallet_management"
                )
            )
        ],
    ]

    for certification in requirements.get(
        "certifications",
        []
    ):

        carrier_rows.append([
            "Certification / Standard",
            (
                f"{display(certification.get('certification_name'))}"
                f" — "
                f"{display(certification.get('driver_qualification_security_directives'))}"
            )
        ])

    escort = requirements.get(
        "escort_policy"
    )

    if escort:

        carrier_rows.extend([
            [
                "Armed Escort Required",
                display(
                    escort.get(
                        "armed_escort_required"
                    )
                )
            ],
            [
                "Escort Expense Responsibility",
                display(
                    escort.get(
                        "escort_expense_responsible_party"
                    )
                )
            ],
        ])

    story.append(
        corporate_table(
            carrier_rows,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    story.append(
        PageBreak()
    )

    # ========================================================
    # RISK
    # ========================================================

    section_page_title(
        story,
        styles,
        f"06.{index}.5",
        "Risk, Liability and Insurance"
    )

    risk = tender.get(
        "risk_and_insurance",
        {}
    )

    risk_rows = [
        ["Requirement", "Specification"],
        [
            "Minimum GIT Cover",
            money(
                risk.get(
                    "minimum_git_cover_amount"
                )
            )
        ],
        [
            "Minimum Liability Cover",
            money(
                risk.get(
                    "minimum_liability_cover_amount"
                )
            )
        ],
        [
            "GIT All Risk",
            display(
                risk.get(
                    "git_all_risk_required"
                )
            )
        ],
        [
            "GIT First Loss",
            display(
                risk.get(
                    "git_first_loss_required"
                )
            )
        ],
        [
            "Driver Fidelity",
            display(
                risk.get(
                    "git_driver_fidelity_required"
                )
            )
        ],
        [
            "Claims Policy",
            risk.get(
                "claims_risk_policy"
            )
        ],
        [
            "Claims Requirements",
            risk.get(
                "claims_risk_requirements"
            )
        ],
    ]

    story.append(
        corporate_table(
            risk_rows,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    story.append(
        PageBreak()
    )

    # ========================================================
    # COMMERCIAL
    # ========================================================

    section_page_title(
        story,
        styles,
        f"06.{index}.6",
        "Commercial and Fuel Conditions"
    )

    commercial = tender.get(
        "commercial_terms",
        {}
    )

    fuel = commercial.get(
        "fuel",
        {}
    )

    commercial_rows = [
        ["Commercial Item", "Requirement"],
        [
            "Pricing Basis",
            commercial.get(
                "pricing_basis"
            )
        ],
        [
            "Rate Direction",
            commercial.get(
                "rate_direction"
            )
        ],
        [
            "Rate Validity",
            commercial.get(
                "rate_validity"
            )
        ],
        [
            "VAT Treatment",
            display(
                commercial.get(
                    "vat_included"
                )
            )
        ],
        [
            "Fuel Treatment",
            fuel.get(
                "treatment_type"
            )
        ],
        [
            "Base Diesel Price",
            money(
                fuel.get(
                    "base_diesel_price"
                )
            )
        ],
        [
            "Fuel Review Period",
            fuel.get(
                "review_period"
            )
        ],
        [
            "Fuel Component",
            (
                f"{format_number(fuel.get('fuel_component_percentage'))}%"
                if fuel.get(
                    "fuel_component_percentage"
                ) is not None
                else "—"
            )
        ],
        [
            "Payment Terms",
            commercial.get(
                "payment_terms"
            )
        ],
        [
            "Invoice Frequency",
            commercial.get(
                "invoice_submission_frequency"
            )
        ],
    ]

    story.append(
        corporate_table(
            commercial_rows,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    story.append(
        Paragraph(
            """
            <b>Confidential Procurement Information:</b>
            incumbent transport rates and procurement target rates
            are intentionally excluded from the carrier-facing RFQ
            document.
            """,
            styles["BodySmall"]
        )
    )

    story.append(
        PageBreak()
    )

    # ========================================================
    # SLA
    # ========================================================

    sla = tender.get(
        "sla_reporting"
    )

    if sla:

        section_page_title(
            story,
            styles,
            f"06.{index}.7",
            "Service Levels and Incident Reporting"
        )

        sla_rows = [
            ["Requirement", "Specification"],
            [
                "Incident Reporting SLA",
                sla.get(
                    "incident_reporting_sla"
                )
            ],
            [
                "Service Level Agreement",
                sla.get(
                    "service_level_agreement"
                )
            ],
            [
                "POD - Local",
                requirements.get(
                    "pod_submission_local"
                )
            ],
            [
                "POD - Long Haul",
                requirements.get(
                    "pod_submission_long_haul"
                )
            ],
            [
                "POD - Cross Border",
                requirements.get(
                    "pod_submission_cross_border"
                )
            ],
            [
                "Delivery Documentation SLA",
                tender.get(
                    "delivery_documentation_sla"
                )
            ],
        ]

        story.append(
            corporate_table(
                sla_rows,
                styles,
                widths=[
                    55 * mm,
                    112 * mm
                ]
            )
        )

        story.append(
            PageBreak()
        )


# ============================================================
# SADC FREIGHTLINK ADMINISTRATION
# ============================================================

def build_sadc_administration(
    story,
    styles
):

    section_page_title(
        story,
        styles,
        "07",
        "SADC FREIGHTLINK Procurement and Transportation Administration"
    )

    story.append(
        Paragraph(
            """
            SADC FREIGHTLINK acts as the Client's appointed freight
            procurement and transportation partner and provides the
            central administrative and technology platform through
            which the RFQ and subsequent transportation process are
            managed.
            """,
            styles["BodyCorporate"]
        )
    )

    rows = [
        ["Administration Area", "SADC FREIGHTLINK Responsibility"],

        [
            "Procurement",
            "RFQ preparation, publication, carrier participation,
             quotation administration and procurement coordination."
        ],

        [
            "Carrier Communication",
            "Centralised communication with participating and
             appointed carriers."
        ],

        [
            "Qualification",
            "Administration of carrier qualification and compliance
             requirements."
        ],

        [
            "Bidding",
            "Management of quotation submission, bid administration
             and procurement event controls."
        ],

        [
            "Award Administration",
            "Administration of carrier appointment, award and
             onboarding."
        ],

        [
            "Booking",
            "Transportation booking and allocation administration
             through the platform."
        ],

        [
            "Execution Management",
            "Coordination and visibility of transportation execution,
             operational exceptions and service events."
        ],

        [
            "Payment Administration",
            "Administration of the agreed payment workflow,
             supporting documents and payment records."
        ],

        [
            "POD Administration",
            "Collection, review and administration of proof of
             delivery and supporting documentation."
        ],

        [
            "Carrier SLA Review",
            "Review of carrier performance against agreed service
             levels and operational requirements."
        ],

        [
            "Fuel Adjustment Review",
            "Administration and review of applicable fuel adjustment
             mechanisms."
        ],

        [
            "Disputes",
            "Central coordination and administration of disputes,
             exceptions and commercial queries."
        ],

        [
            "Claims",
            "Coordination of claims communication, documentation
             and resolution processes."
        ],
    ]

    story.append(
        corporate_table(
            rows,
            styles,
            widths=[
                50 * mm,
                117 * mm
            ]
        )
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    story.append(
        Paragraph(
            """
            Unless otherwise communicated in writing, participating
            carriers are required to conduct tender participation,
            quotation submission, applicable booking activity,
            procurement communication and required documentation
            through the SADC FREIGHTLINK platform.
            """,
            styles["BodyCorporate"]
        )
    )

    story.append(
        PageBreak()
    )


# ============================================================
# GENERAL CARRIER OBLIGATIONS
# ============================================================

def build_general_carrier_obligations(
    story,
    styles
):

    section_page_title(
        story,
        styles,
        "08",
        "General Carrier Obligations"
    )

    obligations = [

        (
            "Regulatory Compliance",
            """
            The carrier shall maintain all licences, permits,
            registrations, insurance and regulatory approvals
            required to lawfully perform the transportation services.
            """
        ),

        (
            "Equipment",
            """
            The carrier shall provide vehicles and equipment that
            comply with the requirements specified in the applicable
            tender lane and shall maintain such equipment in a safe,
            clean and roadworthy condition.
            """
        ),

        (
            "Driver Compliance",
            """
            Drivers assigned to the services must possess the
            qualifications, licences, permits, identification,
            security documentation and other credentials required
            by the tender.
            """
        ),

        (
            "Cargo Security",
            """
            The carrier remains responsible for maintaining the
            required cargo security controls and complying with
            applicable insurance and risk requirements.
            """
        ),

        (
            "Operational Visibility",
            """
            Where tracking, control-room or communication
            requirements are specified, the carrier shall maintain
            the required operational visibility for the duration
            of the transportation service.
            """
        ),

        (
            "Incident Management",
            """
            Material incidents, delays, accidents, theft, damages,
            shortages and other operational exceptions must be
            reported within the applicable SLA.
            """
        ),

        (
            "Documentation",
            """
            Proof of delivery, delivery documentation and other
            required records must be submitted within the specified
            documentation SLA.
            """
        ),

        (
            "Service Levels",
            """
            The carrier shall execute awarded transportation
            services in accordance with the applicable service
            levels, tender requirements and agreed commercial terms.
            """
        ),

    ]

    for title, body in obligations:

        story.append(
            Paragraph(
                title,
                styles["SubHeading"]
            )
        )

        story.append(
            Paragraph(
                body,
                styles["BodyCorporate"]
            )
        )

    story.append(
        PageBreak()
    )


# ============================================================
# CLOSING
# ============================================================

def build_closing(
    story,
    styles,
    client_name
):

    section_page_title(
        story,
        styles,
        "09",
        "Closing Statement"
    )

    story.append(
        Spacer(
            1,
            15 * mm
        )
    )

    story.append(
        Paragraph(
            f"""
            SADC FREIGHTLINK, acting as the appointed freight
            procurement and transportation partner for
            <b>{client_name}</b>, appreciates the interest of
            suitably qualified transport operators in this
            procurement event.
            """,
            styles["BodyCorporate"]
        )
    )

    story.append(
        Paragraph(
            """
            Participating carriers are invited to submit
            commercially competitive and operationally compliant
            quotations through the SADC FREIGHTLINK platform.
            """,
            styles["BodyCorporate"]
        )
    )

    story.append(
        Paragraph(
            """
            By participating in this RFQ, carriers acknowledge the
            requirements contained within this document and agree
            to comply with the applicable procurement, operational,
            compliance, documentation and service requirements.
            """,
            styles["BodyCorporate"]
        )
    )

    story.append(
        Spacer(
            1,
            25 * mm
        )
    )

    story.append(
        Paragraph(
            "<b>SADC FREIGHTLINK</b>",
            styles["SubHeading"]
        )
    )

    story.append(
        Paragraph(
            "Freight Procurement & Transportation Partner",
            styles["BodyCorporate"]
        )
    )


# ============================================================
# MAIN DOCUMENT BUILDER
# ============================================================

def build_tender_rfq_document(
    tender_data
):

    styles = build_styles()

    output = BytesIO()

    summary = tender_data.get(
        "tender_summary",
        {}
    )

    client = summary.get(
        "client",
        {}
    )

    client_name = (
        client.get(
            "legal_business_name"
        )
        or "Client"
    )

    client_logo = (
        client.get(
            "company_profile",
            {}
        )
        .get(
            "company_logo"
        )
    )

    doc = SimpleDocTemplate(

        output,

        pagesize=A4,

        rightMargin=18 * mm,
        leftMargin=18 * mm,

        # Extra space for corporate header
        topMargin=31 * mm,

        bottomMargin=22 * mm,

        title=(
            f"Request for Quotation - "
            f"{client_name}"
        ),

        author="SADC FREIGHTLINK",

        subject=(
            "Transportation Services Request for Quotation"
        ),
    )

    story = []

    # ========================================================
    # PAGE 1
    # BRAND COVER
    # ========================================================

    build_cover(
        story,
        styles
    )

    # ========================================================
    # PAGE 2
    # DOCUMENT CONTROL / INDEX
    # ========================================================

    build_document_control(
        story,
        styles,
        summary,
        client_name
    )

    # ========================================================
    # EXECUTIVE SUMMARY
    # ========================================================

    build_executive_summary(
        story,
        styles,
        summary,
        client_name
    )

    # ========================================================
    # ROLES
    # ========================================================

    build_roles_and_responsibilities(
        story,
        styles,
        client_name
    )

    # ========================================================
    # CONDITIONS
    # ========================================================

    build_conditions(
        story,
        styles,
        client_name
    )

    # ========================================================
    # PROCESS
    # ========================================================

    build_tender_process(
        story,
        styles,
        summary
    )

    # ========================================================
    # INDIVIDUAL TENDERS
    # ========================================================

    tenders = tender_data.get(
        "tenders",
        []
    )

    for index, tender in enumerate(
        tenders,
        start=1
    ):

        build_individual_tender(
            story,
            styles,
            tender,
            index
        )

    # ========================================================
    # SADC ADMINISTRATION
    # ========================================================

    build_sadc_administration(
        story,
        styles
    )

    # ========================================================
    # GENERAL CARRIER OBLIGATIONS
    # ========================================================

    build_general_carrier_obligations(
        story,
        styles
    )

    # ========================================================
    # CLOSING
    # ========================================================

    build_closing(
        story,
        styles,
        client_name
    )

    # ========================================================
    # BUILD PDF
    # ========================================================

    header_footer = make_header_footer(
        client_logo
    )

    doc.build(
        story,
        onFirstPage=header_footer,
        onLaterPages=header_footer
    )

    output.seek(0)

    return output