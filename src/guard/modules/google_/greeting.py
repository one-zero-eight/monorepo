from typing import Literal

Role = Literal["writer", "reader"]


def setup_greeting_sheet(sheets_service, spreadsheet_id: str, join_link: str, respondent_role: Role) -> str:
    target_title = "Hello from InNoHassle Guard"

    meta = (
        sheets_service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title,sheetId))")
        .execute()
    )
    titles = {s["properties"]["title"] for s in meta.get("sheets", [])}

    reqs = []
    if target_title not in titles:
        reqs.append({"addSheet": {"properties": {"title": target_title}}})
    if reqs:
        sheets_service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": reqs}).execute()

    description_text = [
        ["📋 InNoHassle Guard Service"],
        [""],
        ["Welcome! This service helps manage secure access to your Google Spreadsheet."],
        [""],
        ["═══════════════════════════════════════════════════════════════════════════════"],
        [""],
        ["📝 INSTRUCTIONS FOR RESPONDENTS:"],
        [""],
        ["To edit this spreadsheet, you must:"],
        ["   1️⃣  Click the join link below"],
        ["   2️⃣  Connect your Gmail account (required - only Gmail addresses work!)"],
        ["   3️⃣  After connecting, you'll get access to edit this spreadsheet"],
        [""],
        ["⚠️  Important: You MUST use a Gmail address (@gmail.com) to access this spreadsheet."],
        ["              Other email providers will not work."],
        [""],
        ["🔗 Join Link:"],
        [join_link],
        [""],
        ["═══════════════════════════════════════════════════════════════════════════════"],
        [""],
        ["📊 Access level for respondents: " + respondent_role.upper()],
        [""],
        ["💬 For support, contact: https://t.me/one_zero_eight"],
    ]

    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{target_title}'!A1",
        valueInputOption="RAW",
        body={"values": description_text},
    ).execute()

    sheet_id = None
    for sheet in meta.get("sheets", []):
        if sheet["properties"]["title"] == target_title:
            sheet_id = sheet["properties"]["sheetId"]
            break
    if sheet_id is None:
        meta = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties)").execute()
        for sheet in meta.get("sheets", []):
            if sheet["properties"]["title"] == target_title:
                sheet_id = sheet["properties"]["sheetId"]
                break

    format_requests = [
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.26, "green": 0.52, "blue": 0.96},
                        "textFormat": {
                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            "fontSize": 11,
                            "bold": True,
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 40},
                "fields": "pixelSize",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 6, "endRowIndex": 7},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 1, "green": 0.95, "blue": 0.8},
                        "textFormat": {"fontSize": 11, "bold": True},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 13, "endRowIndex": 15},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 1, "green": 0.92, "blue": 0.92},
                        "textFormat": {"fontSize": 11, "bold": True},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 16, "endRowIndex": 18},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.85, "green": 0.92, "blue": 0.83},
                        "textFormat": {"fontSize": 11, "bold": True},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 21, "endRowIndex": 22},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        "textFormat": {"fontSize": 11, "bold": True},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": 3},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"fontSize": 11, "bold": False},
                    }
                },
                "fields": "userEnteredFormat(textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 8, "endRowIndex": 12},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"fontSize": 11, "bold": False},
                    }
                },
                "fields": "userEnteredFormat(textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 17, "endRowIndex": 18},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"fontSize": 11, "bold": False},
                    }
                },
                "fields": "userEnteredFormat(textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 23, "endRowIndex": 24},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"fontSize": 11, "bold": False},
                    }
                },
                "fields": "userEnteredFormat(textFormat)",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 900},
                "fields": "pixelSize",
            }
        },
    ]

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body={"requests": format_requests}
    ).execute()

    return target_title
