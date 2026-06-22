"""
Download the most recent .xlsx file from a Google Drive folder.

Uses a service account for authentication (no browser login needed).
Designed to run in GitHub Actions where credentials come from secrets.

Usage:
    python download_from_drive.py <output_path>

Env vars required:
    GOOGLE_SERVICE_ACCOUNT_JSON   - full JSON content of the service account key
    GOOGLE_DRIVE_FOLDER_ID        - ID of the shared Drive folder
"""

import json
import os
import sys

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


def get_drive_service():
    creds_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = Credentials.from_service_account_info(
        creds_json, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return build("drive", "v3", credentials=creds)


def find_latest_xlsx(service, folder_id: str) -> dict | None:
    """Find the most recently created .xlsx file in the folder."""
    results = service.files().list(
        q=(
            f"'{folder_id}' in parents"
            " and mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'"
            " and trashed=false"
        ),
        orderBy="createdTime desc",
        pageSize=1,
        fields="files(id, name, createdTime)",
    ).execute()

    files = results.get("files", [])
    return files[0] if files else None


def download_file(service, file_id: str, output_path: str):
    request = service.files().get_media(fileId=file_id)
    with open(output_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"  download {int(status.progress() * 100)}%")


def main():
    output_path = sys.argv[1] if len(sys.argv) > 1 else "latest.xlsx"
    folder_id = os.environ["GOOGLE_DRIVE_FOLDER_ID"]

    print("Connecting to Google Drive ...")
    service = get_drive_service()

    print(f"Looking for latest .xlsx in folder {folder_id} ...")
    latest = find_latest_xlsx(service, folder_id)

    if not latest:
        print("ERROR: No .xlsx files found in the folder.")
        sys.exit(1)

    print(f"  found: {latest['name']} (created {latest['createdTime']})")
    print(f"Downloading to {output_path} ...")
    download_file(service, latest["id"], output_path)
    print("Download complete.")


if __name__ == "__main__":
    main()
