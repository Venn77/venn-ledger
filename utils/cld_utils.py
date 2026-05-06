import os
from config import CREDENTIALS_PATH, TOKEN_PATH
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = ['https://www.googleapis.com/auth/drive.file']

def _get_or_create_folder(service, folder_name):
    """Finds a folder created by the app, or creates it if it doesn't exist."""
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    folders = response.get('files', [])

    if folders:
        return folders[0].get('id')
    else:
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

def upload_to_drive(filepath, filename):
    """Authenticates with Google Drive and uploads a file to a specified Google Drive folder."""
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                error_msg = (
                    "Missing credentials.json!\n\n"
                    "Please download your OAuth 2.0 Client ID from Google Cloud Console "
                    "and place the 'credentials.json' file in the following folder:\n\n"
                    f"{CREDENTIALS_PATH}"
                )
                return False, error_msg

            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('drive', 'v3', credentials=creds)

        folder_name = "Venn Ledger Backups"
        folder_id = _get_or_create_folder(service, folder_name)

        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        media = MediaFileUpload(filepath, mimetype='application/octet-stream')

        service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        return True, f"Successfully uploaded backup to '{folder_name}' on Google Drive!"

    except Exception as e:
        return False, f"Drive upload failed:\n{e}"


