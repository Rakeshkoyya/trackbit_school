"""P0-C done-when: roster xlsx import round-trips the sheet (SPRD §5.6, heuristic)."""

import io
import uuid

from openpyxl import Workbook

from app.services import roster_import


def _sheet_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Student Name", "Adm No", "Class", "Section", "Father Name", "Father Mobile", "Category"])
    ws.append(["Asha Rao", "A101", "6", "B", "Ravi Rao", "+919800000001", "Day Scholar"])
    ws.append(["Bina Das", "A102", "6", "B", "Sunil Das", "+919800000002", "Hosteller"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_heuristic_mapping_matches_common_headers():
    cols = ["Student Name", "Adm No", "Class", "Section", "Father Name", "Father Mobile"]
    mapping = roster_import.heuristic_mapping(cols)
    assert mapping["full_name"] == "Student Name"
    assert mapping["admission_no"] == "Adm No"
    assert mapping["class_name"] == "Class"
    assert mapping["father_phone"] == "Father Mobile"


def _register_admin(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    r = client.post("/api/v1/auth/register-org",
                    json={"org_name": "Roster Org", "name": "Director", "email": email,
                          "password": "supersecret1", "timezone": "Asia/Kolkata"})
    body = r.json()
    cleanup["orgs"].append(uuid.UUID(body["org"]["id"]))
    cleanup["users"].append(uuid.UUID(body["user"]["id"]))
    return body


def test_import_round_trips_the_sheet(client, cleanup):
    admin = _register_admin(client, cleanup)
    h = {"Authorization": f"Bearer {admin['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    client.post("/api/v1/academics/classes", headers=h,
                json={"academic_year_id": year["id"], "name": "6", "section": "B"})

    # analyze the uploaded sheet
    analyzed = client.post(
        "/api/v1/students/import/analyze", headers=h,
        files={"file": ("roster.xlsx", _sheet_bytes(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert analyzed.status_code == 200, analyzed.text
    data = analyzed.json()
    assert data["row_count"] == 2
    assert data["mapping"]["full_name"] == "Student Name"

    # commit with the (confirmed) mapping + rows
    committed = client.post("/api/v1/students/import/commit", headers=h, json={
        "mapping": data["mapping"], "rows": data["rows"], "academic_year_id": year["id"]})
    assert committed.status_code == 200, committed.text
    assert committed.json()["created"] == 2

    # the roster now holds both, with class matched + category auto-created + guardian
    students = client.get("/api/v1/students", headers=h).json()
    assert len(students) == 2
    asha = next(s for s in students if s["full_name"] == "Asha Rao")
    detail = client.get(f"/api/v1/students/{asha['id']}", headers=h).json()
    assert detail["class_label"] == "6-B"
    assert detail["category_name"] == "Day Scholar"
    assert detail["guardians"][0]["phone"] == "+919800000001"

    # re-committing the same rows skips the duplicates (append-safe)
    again = client.post("/api/v1/students/import/commit", headers=h, json={
        "mapping": data["mapping"], "rows": data["rows"], "academic_year_id": year["id"]})
    assert again.json() == {"created": 0, "skipped": 2, "errors": []}
