"""Verified directory of official Indian central & state government portals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class GovServiceSpec:
    id: str
    name: str
    category: str
    official_url: str
    secondary_urls: tuple[str, ...]
    required_documents: tuple[str, ...]
    eligibility_summary: str
    status_check_guide: str
    typical_form_fields: tuple[str, ...]


GOV_SERVICES: dict[str, GovServiceSpec] = {
    "aadhaar": GovServiceSpec(
        id="aadhaar",
        name="Aadhaar Services (UIDAI)",
        category="Identity",
        official_url="https://myaadhaar.uidai.gov.in/",
        secondary_urls=("https://uidai.gov.in/",),
        required_documents=("Proof of Identity (PoI)", "Proof of Address (PoA)", "Registered Mobile Number for OTP"),
        eligibility_summary="Indian residents; demographic/address updates online via myAadhaar; biometric updates at Aadhaar Seva Kendra.",
        status_check_guide="Visit myaadhaar.uidai.gov.in -> Check Enrolment & Update Status -> enter SRN/URN and manual CAPTCHA.",
        typical_form_fields=("full_name", "dob", "address_line", "pincode", "mobile_hint"),
    ),
    "pan": GovServiceSpec(
        id="pan",
        name="PAN Card Application & Correction",
        category="Tax & Identity",
        official_url="https://www.incometax.gov.in/iec/foportal/",
        secondary_urls=("https://www.protean-tinpan.com/", "https://www.pan.utiitsl.com/"),
        required_documents=("Aadhaar Card / PoI", "PoA", "Date of Birth Proof", "2 Passport Photos + Signature"),
        eligibility_summary="Indian citizens, NRIs, or entities needing PAN (Form 49A / CSF correction).",
        status_check_guide="Use Instant e-PAN status on incometax.gov.in or Track PAN Application with 15-digit Acknowledgement Number.",
        typical_form_fields=("applicant_category", "full_name", "father_name", "dob", "email", "mobile_hint", "ao_code"),
    ),
    "voter_id": GovServiceSpec(
        id="voter_id",
        name="Voter ID Services (ECI)",
        category="Identity",
        official_url="https://voters.eci.gov.in/",
        secondary_urls=("https://eci.gov.in/",),
        required_documents=("Age Proof (18+ years)", "Address Proof", "Passport Size Photo"),
        eligibility_summary="Indian citizens aged 18 years or above on qualifying date (Form 6 new, Form 8 correction/transfer).",
        status_check_guide="Login to voters.eci.gov.in -> Track Application Status using Reference ID.",
        typical_form_fields=("state", "constituency", "full_name", "relative_name", "dob", "address_line", "pincode"),
    ),
    "passport": GovServiceSpec(
        id="passport",
        name="Passport Seva",
        category="Travel & Identity",
        official_url="https://www.passportindia.gov.in/",
        secondary_urls=("https://portal2.passportindia.gov.in/",),
        required_documents=("Present Address Proof", "Date of Birth Proof", "ECR/Non-ECR Educational Proof"),
        eligibility_summary="Indian citizens applying for Fresh/Re-issue Passport (Normal or Tatkaal).",
        status_check_guide="Visit passportindia.gov.in -> Track Application Status with File Number & DOB.",
        typical_form_fields=("passport_office", "application_type", "full_name", "dob", "place_of_birth", "address_line", "pincode"),
    ),
    "income_cert": GovServiceSpec(
        id="income_cert",
        name="Income Certificate",
        category="State Certificates",
        official_url="https://serviceonline.gov.in/",
        secondary_urls=("https://services.india.gov.in/",),
        required_documents=("Identity Proof", "Address Proof", "Self-Declaration / Salary Slip / Revenue Report", "Ration Card (if applicable)"),
        eligibility_summary="Residents applying via State e-District / ServicePlus portal for scholarships or welfare schemes.",
        status_check_guide="Open your State e-District or serviceonline.gov.in -> Track Application Status with Application Reference Number.",
        typical_form_fields=("state", "district", "block_tehsil", "full_name", "annual_family_income", "purpose"),
    ),
    "caste_cert": GovServiceSpec(
        id="caste_cert",
        name="Caste Certificate",
        category="State Certificates",
        official_url="https://serviceonline.gov.in/",
        secondary_urls=("https://services.india.gov.in/",),
        required_documents=("Identity & Residence Proof", "Family Caste Proof / Father's Certificate", "Self-Declaration / Affidavit"),
        eligibility_summary="SC/ST/OBC/EWS eligible applicants via respective State Revenue / e-District portal.",
        status_check_guide="Track via your State e-District or ServicePlus portal using Application ID.",
        typical_form_fields=("state", "district", "full_name", "father_name", "category_claimed", "sub_caste"),
    ),
    "residence_cert": GovServiceSpec(
        id="residence_cert",
        name="Residence / Domicile Certificate",
        category="State Certificates",
        official_url="https://serviceonline.gov.in/",
        secondary_urls=("https://services.india.gov.in/",),
        required_documents=("Identity Proof", "Proof of Continuous Residence (Electricity/Water Bill, Rent/Sale Deed, Voter ID)"),
        eligibility_summary="Residents meeting state domicile residency criteria.",
        status_check_guide="Track on State e-District / ServicePlus portal with Reference ID.",
        typical_form_fields=("state", "district", "full_name", "years_of_residence", "address_line", "pincode"),
    ),
    "birth_death_cert": GovServiceSpec(
        id="birth_death_cert",
        name="Birth & Death Certificates (CRS)",
        category="Civil Registry",
        official_url="https://dc.crsorgi.gov.in/",
        secondary_urls=("https://crsorgi.gov.in/",),
        required_documents=("Hospital Discharge/Birth/Death Report", "Parents'/Applicant's ID Proof", "Address Proof"),
        eligibility_summary="Registrations within 21 days via Civil Registration System (CRS) or municipal portal; delayed needs SDM/Magistrate order.",
        status_check_guide="Check with local Municipal/Gram Panchayat Registrar or CRS portal.",
        typical_form_fields=("event_date", "place_of_event", "hospital_or_address", "parent_names", "district", "state"),
    ),
    "ration_card": GovServiceSpec(
        id="ration_card",
        name="Ration Card Services (NFSA)",
        category="Welfare",
        official_url="https://nfsa.gov.in/",
        secondary_urls=("https://services.india.gov.in/",),
        required_documents=("Head of Family & Member IDs", "Address Proof", "Passport Photos", "Family Income Details", "Bank Passbook"),
        eligibility_summary="State Food & Civil Supplies portals determine Priority Household / Antyodaya eligibility.",
        status_check_guide="Check State PDS / NFSA portal -> Citizen Corner -> Know Your Ration Card Status.",
        typical_form_fields=("state", "district", "head_of_family", "family_member_count", "annual_income", "ifsc_code"),
    ),
    "labour_card": GovServiceSpec(
        id="labour_card",
        name="Labour Card & BOCW Welfare",
        category="Welfare",
        official_url="https://labour.gov.in/",
        secondary_urls=("https://serviceonline.gov.in/",),
        required_documents=("Identity Proof", "Bank Account Passbook + IFSC", "90-day Work Certificate / Self-Declaration", "Passport Photo"),
        eligibility_summary="Registered building, construction, and state unorganized sector workers aged 18–60.",
        status_check_guide="Track on your State Labour / BOCW Board portal.",
        typical_form_fields=("state", "worker_type", "full_name", "dob", "bank_ifsc", "employer_or_work_days"),
    ),
    "eshram": GovServiceSpec(
        id="eshram",
        name="e-Shram Portal",
        category="Welfare",
        official_url="https://eshram.gov.in/",
        secondary_urls=("https://register.eshram.gov.in/",),
        required_documents=("Aadhaar-linked Mobile Number", "Active Bank Account + IFSC", "NCO Occupation Skill Details"),
        eligibility_summary="Unorganized workers aged 16–59 who are not EPFO/ESIC members.",
        status_check_guide="Visit register.eshram.gov.in -> Already Registered -> Update/Download UAN Card via mobile OTP.",
        typical_form_fields=("full_name", "occupation_nco", "education_level", "bank_ifsc", "state", "pincode"),
    ),
    "pm_kisan": GovServiceSpec(
        id="pm_kisan",
        name="PM-KISAN Samman Nidhi",
        category="Agriculture",
        official_url="https://pmkisan.gov.in/",
        secondary_urls=(),
        required_documents=("Landholding / Khatauni Record", "Bank Account seeded with Aadhaar (NPCI)", "e-KYC completion"),
        eligibility_summary="Eligible landholding farmer families subject to scheme exclusion criteria.",
        status_check_guide="Visit pmkisan.gov.in -> Farmers Corner -> Know Your Status using Registration Number + OTP.",
        typical_form_fields=("state", "district", "sub_district", "village", "land_khata_no", "ifsc_code"),
    ),
    "scholarship": GovServiceSpec(
        id="scholarship",
        name="National Scholarship Portal (NSP)",
        category="Education",
        official_url="https://scholarships.gov.in/",
        secondary_urls=(),
        required_documents=("OTR Registration", "Previous Marksheet", "Bonafide Student Certificate", "Income & Caste Certificate", "Fee Receipt", "Bank Passbook"),
        eligibility_summary="Students meeting Central/State/UGC/AICTE scholarship income, merit, and institution criteria.",
        status_check_guide="Login on scholarships.gov.in -> Check Application Status & PFMS payment status.",
        typical_form_fields=("academic_year", "scheme_name", "institute_aishe_code", "annual_income", "percentage_marks"),
    ),
    "govt_jobs": GovServiceSpec(
        id="govt_jobs",
        name="Government Job Portals (NCS & Employment News)",
        category="Careers",
        official_url="https://www.ncs.gov.in/",
        secondary_urls=("https://employmentnews.gov.in/",),
        required_documents=("Educational Certificates", "Scanned Photo & Signature (exact KB/dimensions)", "Category/PwBD Certificate if applicable"),
        eligibility_summary="Varies strictly by official recruitment notification (age, qualification, cut-off date).",
        status_check_guide="Always verify notifications and admit cards only on official .gov.in / .nic.in recruitment portals.",
        typical_form_fields=("full_name", "dob", "qualification", "category", "email", "pincode"),
    ),
    "upsc_ssc": GovServiceSpec(
        id="upsc_ssc",
        name="UPSC & SSC Exam Portals",
        category="Exams",
        official_url="https://upsconline.nic.in/",
        secondary_urls=("https://ssc.gov.in/", "https://upsc.gov.in/"),
        required_documents=("OTR Profile", "Photo ID", "Live/Specified Photo & Signature", "Degree/10th/12th Marksheets", "Category/EWS Certificate"),
        eligibility_summary="As per official UPSC/SSC exam notification age limits and educational criteria.",
        status_check_guide="Login to upsconline.nic.in or ssc.gov.in OTR dashboard to view application status & admit card.",
        typical_form_fields=("exam_name", "otr_ready", "exam_center_choice", "qualification_status", "category"),
    ),
    "railway": GovServiceSpec(
        id="railway",
        name="Indian Railways / RRB Recruitment",
        category="Exams",
        official_url="https://www.rrbapply.gov.in/",
        secondary_urls=("https://indianrailways.gov.in/",),
        required_documents=("RRB Account Details", "10th/ITI/Diploma/Degree Proof", "Photo & Signature", "Community/EBC Certificate"),
        eligibility_summary="Per CEN notification from respective Railway Recruitment Board.",
        status_check_guide="Login to rrbapply.gov.in or zonal RRB .gov.in website for application & CBT status.",
        typical_form_fields=("rrb_zone", "post_preference", "qualification", "category", "pincode"),
    ),
    "state_portals": GovServiceSpec(
        id="state_portals",
        name="State Portals, DigiLocker & UMANG",
        category="Unified Portals",
        official_url="https://www.india.gov.in/",
        secondary_urls=("https://www.digilocker.gov.in/", "https://web.umang.gov.in/"),
        required_documents=("Registered Mobile / DigiLocker Account"),
        eligibility_summary="Unified citizen access to central & state services, certificates, and verified digital documents.",
        status_check_guide="Open State e-District portal listed on india.gov.in or check issued docs in DigiLocker.",
        typical_form_fields=("state", "service_name", "reference_id"),
    ),
    "bill_payments": GovServiceSpec(
        id="bill_payments",
        name="Official Utility & Municipal Bill Portals",
        category="Payments",
        official_url="https://services.india.gov.in/",
        secondary_urls=("https://web.umang.gov.in/",),
        required_documents=("Consumer / CA / Property Tax Account Number", "Official Discom / Municipal URL"),
        eligibility_summary="Electricity, water, gas, and municipal tax payments via official utility portals.",
        status_check_guide="Download official receipt immediately after user-approved payment.",
        typical_form_fields=("state", "utility_provider", "consumer_number", "bill_amount_inr"),
    ),
    "schemes": GovServiceSpec(
        id="schemes",
        name="Government Scheme Research (MyScheme)",
        category="Schemes",
        official_url="https://www.myscheme.gov.in/",
        secondary_urls=("https://www.india.gov.in/",),
        required_documents=("Basic Profile (Age, State, Gender, Occupation, Income Bracket — no Aadhaar needed for discovery)"),
        eligibility_summary="Official National Platform to discover eligible Central & State welfare schemes.",
        status_check_guide="Use myscheme.gov.in Eligibility Checker before applying on the linked official portal.",
        typical_form_fields=("state", "age", "occupation", "income_bracket", "social_category"),
    ),
}

STATE_E_DISTRICT_PORTALS: dict[str, str] = {
    "bihar": "https://serviceonline.bihar.gov.in/",
    "uttar pradesh": "https://edistrict.up.gov.in/",
    "delhi": "https://edistrict.delhigovt.nic.in/",
    "maharashtra": "https://aaplesarkar.mahaonline.gov.in/",
    "west bengal": "https://edistrict.wb.gov.in/",
    "madhya pradesh": "https://mpedistrict.gov.in/",
    "rajasthan": "https://sso.rajasthan.gov.in/",
    "tamil nadu": "https://www.tnesevai.tn.gov.in/",
    "karnataka": "https://sevasindhu.karnataka.gov.in/",
    "kerala": "https://edistrict.kerala.gov.in/",
    "gujarat": "https://www.digitalgujarat.gov.in/",
    "odisha": "https://edistrict.odisha.gov.in/",
    "assam": "https://sewasetu.assam.gov.in/",
    "jharkhand": "https://jharsewa.jharkhand.gov.in/",
    "punjab": "https://eservices.punjab.gov.in/",
    "haryana": "https://saralharyana.gov.in/",
}


def is_official_indian_gov_domain(url: str) -> bool:
    """Return True strictly for official .gov.in / .nic.in domains."""
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return host.endswith(".gov.in") or host.endswith(".nic.in")


def list_services() -> list[dict[str, Any]]:
    return [
        {
            "id": s.id,
            "name": s.name,
            "category": s.category,
            "official_url": s.official_url,
            "official_domain_verified": is_official_indian_gov_domain(s.official_url),
            "secondary_urls": list(s.secondary_urls),
            "required_documents": list(s.required_documents),
            "eligibility_summary": s.eligibility_summary,
            "status_check_guide": s.status_check_guide,
            "typical_form_fields": list(s.typical_form_fields),
        }
        for s in GOV_SERVICES.values()
    ]


def lookup_state_portal(state_name: str) -> dict[str, Any]:
    key = state_name.strip().lower()
    url = STATE_E_DISTRICT_PORTALS.get(key)
    return {
        "state": state_name.strip(),
        "found": bool(url),
        "official_url": url or "https://services.india.gov.in/",
        "official_domain_verified": is_official_indian_gov_domain(url or "https://services.india.gov.in/"),
    }
