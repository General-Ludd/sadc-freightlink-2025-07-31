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
    Image,
    KeepTogether,
)

from PIL import Image as PILImage


# ============================================================
# BRANDING
# ============================================================

SADC_FREIGHTLINK_LOGO = None

# Example:
#
# SADC_FREIGHTLINK_LOGO = (
#     "https://your-domain.com/static/"
#     "sadc-freightlink-logo.png"
# )
#
# Or use a local static file path.


# ============================================================
# LOGO LOADER
# ============================================================

def load_logo(
    logo_source: str,
    max_width: float,
    max_height: float
):

    if not logo_source:
        return None

    try:

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        if logo_source.startswith(
            "http://"
        ) or logo_source.startswith(
            "https://"
        ):

            image_bytes = urlopen(
                logo_source,
                timeout=10
            ).read()

            image_buffer = BytesIO(
                image_bytes
            )

        # ----------------------------------------------------
        # Local file
        # ----------------------------------------------------

        else:

            with open(
                logo_source,
                "rb"
            ) as file:

                image_buffer = BytesIO(
                    file.read()
                )

        # ----------------------------------------------------
        # Determine dimensions
        # ----------------------------------------------------

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

def format_date(value):

    if not value:
        return "—"

    if isinstance(value, str):

        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
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


def format_number(value):

    if value is None:
        return "—"

    if isinstance(value, float):
        return f"{value:,.2f}"

    if isinstance(value, int):
        return f"{value:,}"

    return str(value)


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


# ============================================================
# PDF STYLES
# ============================================================

def build_styles():

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="RFQTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            alignment=TA_CENTER,
            spaceAfter=8 * mm,
        )
    )

    styles.add(
        ParagraphStyle(
            name="RFQSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            spaceAfter=10 * mm,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            spaceBefore=8 * mm,
            spaceAfter=4 * mm,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SubHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        )
    )

    styles.add(
        ParagraphStyle(
            name="BodyCorporate",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            spaceAfter=3 * mm,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SmallText",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableHeader",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
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

    for row in rows:

        formatted_rows.append([
            Paragraph(
                display(cell),
                styles["TableBody"]
            )
            for cell in row
        ])

    table = Table(
        formatted_rows,
        colWidths=widths,
        repeatRows=1
        if formatted_rows
        else 0
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#E9EDF2")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.HexColor("#1F2933")
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.35,
                colors.HexColor("#C7CDD4")
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
                5
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                5
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5
            ),
        ])
    )

    return table


# ============================================================
# HEADER / FOOTER
# ============================================================

def add_page_header_footer(
    canvas,
    doc
):

    canvas.saveState()

    width, height = A4

    # --------------------------------------------------------
    # Footer
    # --------------------------------------------------------

    canvas.setFont(
        "Helvetica",
        7
    )

    canvas.setFillColor(
        colors.HexColor("#6B7280")
    )

    canvas.drawString(
        20 * mm,
        12 * mm,
        "Private & Confidential"
    )

    canvas.drawRightString(
        width - 20 * mm,
        12 * mm,
        f"Page {doc.page}"
    )

    canvas.restoreState()


# ============================================================
# DOCUMENT BUILDER
# ============================================================

def build_tender_rfq_document(
    tender_data: Dict[str, Any]
) -> BytesIO:

    styles = build_styles()

    output = BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=A4,

        rightMargin=18 * mm,
        leftMargin=18 * mm,

        topMargin=18 * mm,
        bottomMargin=20 * mm,

        title=(
            tender_data
            .get("tender_summary", {})
            .get("titles", ["Request for Quotation"])[0]
        ),

        author="SADC FREIGHTLINK",
    )

    story = []

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

    # ========================================================
    # COVER
    # ========================================================

    client_logo = (
        client
        .get("company_profile", {})
        .get("company_logo")
    )

    logo = load_logo(
        client_logo,
        65 * mm,
        30 * mm
    )

    if logo:

        story.append(logo)
        story.append(
            Spacer(
                1,
                8 * mm
            )
        )

    if SADC_FREIGHTLINK_LOGO:

        sadc_logo = load_logo(
            SADC_FREIGHTLINK_LOGO,
            65 * mm,
            30 * mm
        )

        if sadc_logo:

            story.append(
                sadc_logo
            )

            story.append(
                Spacer(
                    1,
                    8 * mm
                )
            )

    story.append(
        Paragraph(
            "REQUEST FOR QUOTATION",
            styles["RFQTitle"]
        )
    )

    story.append(
        Paragraph(
            "for Transportation of Goods",
            styles["RFQSubtitle"]
        )
    )

    story.append(
        Paragraph(
            f"<b>On behalf of:</b><br/>{client_name}",
            styles["RFQSubtitle"]
        )
    )

    story.append(
        Paragraph(
            "Private & Confidential",
            styles["RFQSubtitle"]
        )
    )

    story.append(
        Spacer(
            1,
            12 * mm
        )
    )

    # ========================================================
    # EXECUTIVE SUMMARY
    # ========================================================

    story.append(
        Paragraph(
            "1. Executive Summary",
            styles["SectionHeading"]
        )
    )

    story.append(
        Paragraph(
            summary.get(
                "corporate_summary",
                ""
            ),
            styles["BodyCorporate"]
        )
    )

    story.append(
        Paragraph(
            "<b>Procurement Administration</b>",
            styles["SubHeading"]
        )
    )

    story.append(
        Paragraph(
            "SADC FREIGHTLINK has been appointed as the "
            "freight procurement and transportation partner "
            "acting on behalf of the Client. The RFQ process, "
            "carrier communication, qualification, quotation "
            "submission, bid administration, evaluation, "
            "appointment administration and transportation "
            "execution are administered through the SADC "
            "FREIGHTLINK platform.",
            styles["BodyCorporate"]
        )
    )

    # ========================================================
    # PROCUREMENT OVERVIEW
    # ========================================================

    story.append(
        Paragraph(
            "2. Procurement Overview",
            styles["SectionHeading"]
        )
    )

    overview_rows = [
        [
            "Item",
            "Requirement"
        ],

        [
            "Client",
            client_name
        ],

        [
            "Tender Category",
            display(
                summary.get(
                    "tender_categories"
                )
            )
        ],

        [
            "Contract Duration",
            (
                f"{format_date(summary.get('contract_period', {}).get('start_date'))}"
                f" – "
                f"{format_date(summary.get('contract_period', {}).get('end_date'))}"
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
            "Estimated Volume",
            summary.get(
                "volume_statement",
                "As specified in tender schedules"
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
            overview_rows,
            styles,
            widths=[
                55 * mm,
                112 * mm
            ]
        )
    )

    # ========================================================
    # TENDER CONDITIONS
    # ========================================================

    story.append(
        Paragraph(
            "3. Tender Conditions and Confidentiality",
            styles["SectionHeading"]
        )
    )

    story.append(
        Paragraph(
            "This Request for Quotation is issued for the "
            "purpose of obtaining competitive transportation "
            "quotations from suitably qualified and compliant "
            "transport operators.",
            styles["BodyCorporate"]
        )
    )

    story.append(
        Paragraph(
            "All information contained in this document is "
            "provided solely for the purpose of preparing and "
            "submitting a quotation. Participants are required "
            "to treat the information as confidential and may "
            "not disclose it to third parties without the "
            "Client's or SADC FREIGHTLINK's written consent.",
            styles["BodyCorporate"]
        )
    )

    # ========================================================
    # TENDER PROCESS
    # ========================================================

    story.append(
        Paragraph(
            "4. Tender Process",
            styles["SectionHeading"]
        )
    )

    story.append(
        Paragraph(
            "SADC FREIGHTLINK administers the procurement "
            "process on behalf of the Client. Carrier "
            "participation, quotation submission, RFQ "
            "communications and bid administration are "
            "conducted through the SADC FREIGHTLINK platform.",
            styles["BodyCorporate"]
        )
    )

    story.append(
        Paragraph(
            "The Client and SADC FREIGHTLINK reserve the right "
            "to evaluate quotations on commercial, capacity, "
            "service, compliance and operational criteria.",
            styles["BodyCorporate"]
        )
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

        story.append(
            PageBreak()
        )

        title = (
            tender.get(
                "tender_title"
            )
            or f"Tender Lane {index}"
        )

        story.append(
            Paragraph(
                f"5.{index} {title}",
                styles["SectionHeading"]
            )
        )

        reference = tender.get(
            "tender_reference"
        )

        if reference:

            story.append(
                Paragraph(
                    f"<b>Tender Reference:</b> "
                    f"{reference}",
                    styles["BodyCorporate"]
                )
            )

        # ----------------------------------------------------
        # Scope
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Routing
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Routing",
                styles["SubHeading"]
            )
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
            [
                "Route Element",
                "Details"
            ],

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

        # ----------------------------------------------------
        # Intermediate Stops
        # ----------------------------------------------------

        intermediate_stops = routing.get(
            "intermediate_stops",
            []
        )

        if intermediate_stops:

            story.append(
                Paragraph(
                    "Intermediate Stops",
                    styles["SubHeading"]
                )
            )

            stop_rows = [
                [
                    "Sequence",
                    "Facility",
                    "Location",
                    "Demurrage"
                ]
            ]

            for stop in intermediate_stops:

                protocol = stop.get(
                    "turnaround_window_demurrage_protocol"
                ) or {}

                demurrage = (
                    f"Free: "
                    f"{display(protocol.get('free_demurrage_hours'))} hrs"
                )

                stop_rows.append([
                    stop.get(
                        "stop_sequence"
                    ),

                    stop.get(
                        "facility_name"
                    ),

                    stop.get(
                        "complete_address"
                    )
                    or stop.get(
                        "address"
                    ),

                    demurrage
                ])

            story.append(
                corporate_table(
                    stop_rows,
                    styles,
                    widths=[
                        18 * mm,
                        42 * mm,
                        72 * mm,
                        35 * mm
                    ]
                )
            )

        # ----------------------------------------------------
        # Cargo
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Cargo Specification",
                styles["SubHeading"]
            )
        )

        cargo = tender.get(
            "cargo",
            {}
        )

        cargo_rows = [
            [
                "Requirement",
                "Specification"
            ],

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
                (
                    f"{format_number(cargo.get('average_shipment_weight_kg'))} kg"
                )
            ],

            [
                "Minimum Weight Bracket",
                (
                    f"{format_number(cargo.get('minimum_weight_bracket_kg'))} kg"
                )
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

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Volume and Schedule",
                styles["SubHeading"]
            )
        )

        volume = tender.get(
            "volume",
            {}
        )

        volume_rows = [
            [
                "Volume Requirement",
                "Details"
            ],

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

        profiles = volume.get(
            "profiles",
            []
        )

        for profile in profiles:

            volume_rows.append([
                profile.get(
                    "period_label"
                )
                or profile.get(
                    "day_of_week"
                ),

                (
                    f"{format_number(profile.get('expected_loads'))} "
                    f"loads"
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

        # ----------------------------------------------------
        # Equipment
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Vehicle and Equipment Requirements",
                styles["SubHeading"]
            )
        )

        equipment = (
            tender
            .get(
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

        # ----------------------------------------------------
        # Carrier requirements
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Carrier and Driver Requirements",
                styles["SubHeading"]
            )
        )

        requirements = tender.get(
            "carrier_requirements",
            {}
        )

        carrier_rows = [
            [
                "Requirement",
                "Specification"
            ],

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
                ),
            ],
        ]

        for certification in requirements.get(
            "certifications",
            []
        ):

            carrier_rows.append([
                "Certification / Standard",
                (
                    f"{certification.get('certification_name')} — "
                    f"{certification.get('driver_qualification_security_directives')}"
                )
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

        # ----------------------------------------------------
        # Risk
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Risk, Liability and Insurance",
                styles["SubHeading"]
            )
        )

        risk = tender.get(
            "risk_and_insurance",
            {}
        )

        risk_rows = [
            [
                "Requirement",
                "Specification"
            ],

            [
                "Minimum GIT Cover",
                risk.get(
                    "minimum_git_cover_amount"
                )
            ],

            [
                "Minimum Liability Cover",
                risk.get(
                    "minimum_liability_cover_amount"
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
                ),
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

        # ----------------------------------------------------
        # Commercial
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "Commercial and Fuel Conditions",
                styles["SubHeading"]
            )
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
            [
                "Commercial Item",
                "Requirement"
            ],

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
                "Fuel Treatment",
                fuel.get(
                    "treatment_type"
                )
            ],

            [
                "Fuel Review Period",
                fuel.get(
                    "review_period"
                )
            ],

            [
                "VAT",
                display(
                    fuel.get(
                        "vat_included"
                    )
                )
            ],

            [
                "Rate Validity",
                commercial.get(
                    "rate_validity"
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

        # ----------------------------------------------------
        # SLA
        # ----------------------------------------------------

        sla = tender.get(
            "sla_reporting"
        )

        if sla:

            story.append(
                Paragraph(
                    "Service Levels and Incident Reporting",
                    styles["SubHeading"]
                )
            )

            sla_rows = [
                [
                    "Requirement",
                    "Specification"
                ],

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

    # ========================================================
    # ADMINISTRATION
    # ========================================================

    story.append(
        PageBreak()
    )

    story.append(
        Paragraph(
            "6. SADC FREIGHTLINK Procurement and "
            "Transportation Administration",
            styles["SectionHeading"]
        )
    )

    story.append(
        Paragraph(
            "SADC FREIGHTLINK is responsible for administering "
            "the transportation procurement process on behalf "
            "of the Client. This includes RFQ communication, "
            "carrier participation and qualification, quotation "
            "submission, bid administration, evaluation support, "
            "appointment and award administration, transportation "
            "booking, operational coordination, payment "
            "administration, documentation and POD administration, "
            "carrier SLA review, fuel adjustment review, and "
            "coordination of disputes and claims.",
            styles["BodyCorporate"]
        )
    )

    story.append(
        Paragraph(
            "All participating transport operators are required "
            "to conduct tender participation, quotation submission "
            "and relevant procurement communication through the "
            "SADC FREIGHTLINK platform unless otherwise instructed.",
            styles["BodyCorporate"]
        )
    )

    # ========================================================
    # CLOSING
    # ========================================================

    story.append(
        Paragraph(
            "7. Closing Statement",
            styles["SectionHeading"]
        )
    )

    story.append(
        Paragraph(
            "The Client and SADC FREIGHTLINK appreciate the "
            "interest of suitably qualified transport operators "
            "and look forward to receiving commercially competitive "
            "and operationally compliant quotations.",
            styles["BodyCorporate"]
        )
    )

    # ========================================================
    # BUILD
    # ========================================================

    doc.build(
        story,
        onFirstPage=add_page_header_footer,
        onLaterPages=add_page_header_footer
    )

    output.seek(0)

    return output