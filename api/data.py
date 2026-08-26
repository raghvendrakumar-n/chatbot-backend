"""In-memory demo data, ported 1:1 from the Angular ``ChatService``.

Swap these structures for Django models later; the view layer only depends on
the accessor functions at the bottom of this module.
"""
from __future__ import annotations

from datetime import date, timedelta

COUNTRIES: list[dict] = [
    {"id": 1, "name": "India", "iso_code": "IN", "phone_code": "+91"},
    {"id": 2, "name": "United States", "iso_code": "US", "phone_code": "+1"},
    {"id": 3, "name": "South Korea", "iso_code": "SK", "phone_code": "+82"},
]

BRANCHES: list[dict] = [
    {"id": 1, "branch_name": "NU Hospitals - Rajajinagar"},
    {"id": 2, "branch_name": "NU Hospitals - Kalyan Nagar"},
    {"id": 3, "branch_name": "NU Hospitals - Padmanabhanagar"},
]

DEPARTMENTS: list[dict] = [
    {"id": 101, "department": "Urology"},
    {"id": 102, "department": "Nephrology"},
    {"id": 103, "department": "Gynaecology"},
    {"id": 104, "department": "Andrology"},
    {"id": 105, "department": "Orthopaedics"},
    {"id": 106, "department": "General Medicine"},
]

DEPARTMENTS_BY_BRANCH: dict[int, list[int]] = {
    1: [101, 102, 103, 105, 106],
    2: [101, 102, 104, 106],
    3: [101, 102, 103, 104, 105, 106],
}

DOCTORS_BY_DEPARTMENT: dict[int, list[dict]] = {
    101: [
        {
            "id": 1001,
            "doctor_name": "Dr. Anil Kumar",
            "qualification": "MBBS, MS, MCh (Urology)",
            "profile_photo": "assets/userIcons/doctor-dummy.svg",
            "profile_url": "https://www.nuhospitals.com/doctors/dr-anil-kumar",
            "department_details": {"id": 101, "department": "Urology"},
        },
        {
            "id": 1002,
            "doctor_name": "Dr. Meera Nair",
            "qualification": "MBBS, MS, DNB (Urology)",
            "profile_photo": "assets/userIcons/doctor-dummy.svg",
            "profile_url": "https://www.nuhospitals.com/doctors/dr-meera-nair",
            "department_details": {"id": 101, "department": "Urology"},
        },
    ],
    102: [
        {
            "id": 1003,
            "doctor_name": "Dr. Rajesh Iyer",
            "qualification": "MBBS, MD, DM (Nephrology)",
            "profile_photo": "assets/userIcons/doctor-dummy.svg",
            "profile_url": "https://www.nuhospitals.com/doctors/dr-rajesh-iyer",
            "department_details": {"id": 102, "department": "Nephrology"},
        },
        {
            "id": 1004,
            "doctor_name": "Dr. Sneha Reddy",
            "qualification": "MBBS, MD, DNB (Nephrology)",
            "profile_photo": "assets/userIcons/doctor-dummy.svg",
            "profile_url": "https://www.nuhospitals.com/doctors/dr-sneha-reddy",
            "department_details": {"id": 102, "department": "Nephrology"},
        },
    ],
    103: [
        {
            "id": 1005,
            "doctor_name": "Dr. Priya Sharma",
            "qualification": "MBBS, MS, DGO (Gynaecology)",
            "profile_photo": "assets/userIcons/doctor-dummy.svg",
            "profile_url": "https://www.nuhospitals.com/doctors/dr-priya-sharma",
            "department_details": {"id": 103, "department": "Gynaecology"},
        }
    ],
    104: [
        {
            "id": 1006,
            "doctor_name": "Dr. Vikram Menon",
            "qualification": "MBBS, MS, MCh (Andrology)",
            "profile_photo": "assets/userIcons/doctor-dummy.svg",
            "profile_url": "https://www.nuhospitals.com/doctors/dr-vikram-menon",
            "department_details": {"id": 104, "department": "Andrology"},
        }
    ],
    105: [
        {
            "id": 1007,
            "doctor_name": "Dr. Suresh Babu",
            "qualification": "MBBS, MS (Orthopaedics)",
            "profile_photo": "assets/userIcons/doctor-dummy.svg",
            "profile_url": "https://www.nuhospitals.com/doctors/dr-suresh-babu",
            "department_details": {"id": 105, "department": "Orthopaedics"},
        },
        {
            "id": 1008,
            "doctor_name": "Dr. Kavya Rao",
            "qualification": "MBBS, DNB (Orthopaedics)",
            "profile_photo": "assets/userIcons/doctor-dummy.svg",
            "profile_url": "https://www.nuhospitals.com/doctors/dr-kavya-rao",
            "department_details": {"id": 105, "department": "Orthopaedics"},
        },
    ],
    106: [
        {
            "id": 1009,
            "doctor_name": "Dr. Arjun Deshpande",
            "qualification": "MBBS, MD (General Medicine)",
            "profile_photo": "assets/userIcons/doctor-dummy.svg",
            "profile_url": "https://www.nuhospitals.com/doctors/dr-arjun-deshpande",
            "department_details": {"id": 106, "department": "General Medicine"},
        },
        {
            "id": 1010,
            "doctor_name": "Dr. Fatima Sheikh",
            "qualification": "MBBS, MD (General Medicine)",
            "profile_photo": "assets/userIcons/doctor-dummy.svg",
            "profile_url": "https://www.nuhospitals.com/doctors/dr-fatima-sheikh",
            "department_details": {"id": 106, "department": "General Medicine"},
        },
    ],
}

SURGERIES_BY_DEPARTMENT: dict[int, list[dict]] = {
    101: [
        {"id": 201, "surgery_name": "Kidney Stone Removal (RIRS)"},
        {"id": 202, "surgery_name": "Prostate Surgery (TURP)"},
        {"id": 203, "surgery_name": "Ureteroscopy"},
    ],
    102: [
        {"id": 204, "surgery_name": "Dialysis Access (AV Fistula)"},
        {"id": 205, "surgery_name": "Renal Biopsy"},
    ],
    103: [
        {"id": 206, "surgery_name": "Laparoscopic Hysterectomy"},
        {"id": 207, "surgery_name": "Ovarian Cyst Removal"},
    ],
    104: [
        {"id": 208, "surgery_name": "Varicocele Surgery"},
        {"id": 209, "surgery_name": "Microsurgical Vasectomy Reversal"},
    ],
    105: [
        {"id": 210, "surgery_name": "Total Knee Replacement"},
        {"id": 211, "surgery_name": "Arthroscopy"},
    ],
    106: [
        {"id": 212, "surgery_name": "Routine Health Check-up Procedure"},
    ],
}

TIME_SLOTS: list[dict] = [
    {"id": 301, "from_time": "09:00:00", "to_time": "09:30:00"},
    {"id": 302, "from_time": "09:30:00", "to_time": "10:00:00"},
    {"id": 303, "from_time": "10:00:00", "to_time": "10:30:00"},
    {"id": 304, "from_time": "11:00:00", "to_time": "11:30:00"},
    {"id": 305, "from_time": "12:00:00", "to_time": "12:30:00"},
    {"id": 306, "from_time": "14:00:00", "to_time": "14:30:00"},
    {"id": 307, "from_time": "15:00:00", "to_time": "15:30:00"},
    {"id": 308, "from_time": "16:00:00", "to_time": "16:30:00"},
    {"id": 309, "from_time": "16:30:00", "to_time": "17:00:00"},
    {"id": 310, "from_time": "17:30:00", "to_time": "18:00:00"},
    {"id": 311, "from_time": "18:00:00", "to_time": "18:30:00"},
    {"id": 312, "from_time": "19:00:00", "to_time": "19:30:00"},
]


def _demo_date(offset_days: int) -> str:
    return (date.today() + timedelta(days=offset_days)).isoformat()


# Mutable so cancel / reschedule can update in place (demo only).
APPOINTMENTS: list[dict] = [
    {
        "id": 5001,
        "reference_id": "NU-100201",
        "phone": "9876543210",
        "patient_name": "Rahul Sharma",
        "doctor_id": 1001,
        "doctor_name": "Dr. Anil Kumar",
        "department": "Urology",
        "branch_name": "NU Hospitals - Rajajinagar",
        "appointment_date": _demo_date(3),
        "from_time": "10:00:00",
        "to_time": "10:30:00",
        "slot_id": 303,
        "status": "booked",
    },
    {
        "id": 5002,
        "reference_id": "NU-100202",
        "phone": "9876543210",
        "patient_name": "Rahul Sharma",
        "doctor_id": 1003,
        "doctor_name": "Dr. Rajesh Iyer",
        "department": "Nephrology",
        "branch_name": "NU Hospitals - Kalyan Nagar",
        "appointment_date": _demo_date(7),
        "from_time": "15:00:00",
        "to_time": "15:30:00",
        "slot_id": 307,
        "status": "booked",
    },
    {
        "id": 5003,
        "reference_id": "NU-100203",
        "phone": "9123456789",
        "patient_name": "Priya Menon",
        "doctor_id": 1005,
        "doctor_name": "Dr. Priya Sharma",
        "department": "Gynaecology",
        "branch_name": "NU Hospitals - Padmanabhanagar",
        "appointment_date": _demo_date(5),
        "from_time": "11:00:00",
        "to_time": "11:30:00",
        "slot_id": 304,
        "status": "booked",
    },
]


# --- Accessors --------------------------------------------------------------


def get_countries() -> list[dict]:
    return COUNTRIES


def get_branches() -> list[dict]:
    return BRANCHES


def get_departments(branch_id: int) -> list[dict]:
    allowed = DEPARTMENTS_BY_BRANCH.get(int(branch_id), [])
    return [d for d in DEPARTMENTS if d["id"] in allowed]


def get_doctors(department_id: int) -> list[dict]:
    return DOCTORS_BY_DEPARTMENT.get(int(department_id), [])


def get_surgeries(department_id: int) -> list[dict]:
    return SURGERIES_BY_DEPARTMENT.get(int(department_id), [])


def get_time_slots() -> list[dict]:
    return TIME_SLOTS


def find_appointments_by_phone(phone: str) -> list[dict]:
    normalized = "".join(ch for ch in str(phone or "") if ch.isdigit())
    return [
        a for a in APPOINTMENTS
        if a["phone"] == normalized and a["status"] == "booked"
    ]


def find_appointment(appointment_id: int) -> dict | None:
    for a in APPOINTMENTS:
        if a["id"] == int(appointment_id):
            return a
    return None
