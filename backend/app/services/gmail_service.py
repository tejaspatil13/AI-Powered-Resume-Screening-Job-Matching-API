import base64
from email.utils import parseaddr
from io import BytesIO
import os
import json
import fitz
from docx import Document
from langchain_google_community import GmailToolkit




def setup_gmail_credentials():
    credentials_json = os.getenv("GMAIL_CREDENTIALS_JSON")
    token_json = os.getenv("GMAIL_TOKEN_JSON")

    if credentials_json:
        with open("credentials.json", "w") as f:
            f.write(credentials_json)

    if token_json:
        with open("token.json", "w") as f:
            f.write(token_json)



class GmailResumeService:

    def __init__(self):

        setup_gmail_credentials()

        self.toolkit = GmailToolkit()

        self.tools = self.toolkit.get_tools()

        self.search_tool = next(
            tool
            for tool in self.tools
            if tool.name == "search_gmail"
        )

        self.gmail_service = self.toolkit.api_resource


    # ========================================================
    # PDF TEXT EXTRACTION
    # ========================================================

    def extract_pdf_text(self, file_bytes: bytes) -> str:

        pdf = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )

        text = ""

        for page in pdf:
            text += page.get_text()

        pdf.close()

        return text.strip()


    # ========================================================
    # DOCX TEXT EXTRACTION
    # ========================================================

    def extract_docx_text(self, file_bytes: bytes) -> str:

        document = Document(
            BytesIO(file_bytes)
        )

        paragraphs = []

        for paragraph in document.paragraphs:

            if paragraph.text.strip():
                paragraphs.append(
                    paragraph.text
                )

        return "\n".join(paragraphs).strip()


    # ========================================================
    # DOWNLOAD ATTACHMENT
    # ========================================================

    def download_attachment(
        self,
        message_id: str,
        attachment_id: str
    ) -> bytes:

        response = (
            self.gmail_service
            .users()
            .messages()
            .attachments()
            .get(
                userId="me",
                messageId=message_id,
                id=attachment_id
            )
            .execute()
        )

        data = response.get("data")

        if not data:
            raise ValueError(
                "Attachment data was not returned"
            )

        return base64.urlsafe_b64decode(data)


    # ========================================================
    # GET EMAIL HEADER
    # ========================================================

    def get_header(
        self,
        headers: list,
        name: str
    ) -> str:

        for header in headers:

            if (
                header.get("name", "").lower()
                == name.lower()
            ):
                return header.get(
                    "value",
                    ""
                )

        return ""


    # ========================================================
    # FIND ATTACHMENTS RECURSIVELY
    # ========================================================

    def find_attachments(
        self,
        message_id: str,
        parts: list
    ):

        attachments = []

        for part in parts:

            filename = part.get(
                "filename",
                ""
            )

            mime_type = part.get(
                "mimeType",
                ""
            )

            body = part.get(
                "body",
                {}
            )

            attachment_id = body.get(
                "attachmentId"
            )

            # ----------------------------------------------
            # Check if this part is a file
            # ----------------------------------------------

            if filename and attachment_id:

                filename_lower = filename.lower()

                if (
                    filename_lower.endswith(".pdf")
                    or filename_lower.endswith(".docx")
                    or filename_lower.endswith(".doc")
                ):

                    attachments.append({
                        "filename": filename,
                        "mime_type": mime_type,
                        "attachment_id": attachment_id
                    })


            # ----------------------------------------------
            # Gmail can have nested MIME parts
            # ----------------------------------------------

            nested_parts = part.get(
                "parts",
                []
            )

            if nested_parts:

                attachments.extend(
                    self.find_attachments(
                        message_id,
                        nested_parts
                    )
                )

        return attachments


    # ========================================================
    # GET MESSAGE
    # ========================================================

    def get_message(
        self,
        message_id: str
    ):

        return (
            self.gmail_service
            .users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="full"
            )
            .execute()
        )


    # ========================================================
    # PROCESS ONE EMAIL
    # ========================================================

    def process_message(
        self,
        message_id: str
    ):

        message = self.get_message(
            message_id
        )

        payload = message.get(
            "payload",
            {}
        )

        headers = payload.get(
            "headers",
            []
        )

        subject = self.get_header(
            headers,
            "Subject"
        )

        sender = self.get_header(
            headers,
            "From"
        )

        candidate_name, email_address = parseaddr(
            sender
        )

        parts = payload.get(
            "parts",
            []
        )

        attachments = self.find_attachments(
            message_id,
            parts
        )

        resumes = []

        for attachment in attachments:

            filename = attachment["filename"]

            file_bytes = self.download_attachment(
                message_id,
                attachment["attachment_id"]
            )

            filename_lower = filename.lower()

            # ----------------------------------------------
            # Extract text
            # ----------------------------------------------

            if filename_lower.endswith(".pdf"):

                resume_text = self.extract_pdf_text(
                    file_bytes
                )

            elif filename_lower.endswith(".docx"):

                resume_text = self.extract_docx_text(
                    file_bytes
                )

            else:

                continue


            # ----------------------------------------------
            # Ignore empty documents
            # ----------------------------------------------

            if not resume_text:

                continue


            resumes.append({

                "gmail_message_id": message_id,

                "gmail_attachment_id":
                    attachment["attachment_id"],

                "candidate_name":
                    candidate_name,

                "email_address":
                    email_address,

                "filename":
                    filename,

                "subject":
                    subject,

                "resume_text":
                    resume_text
            })

        return resumes


    # ========================================================
    # FETCH ALL RESUMES
    # ========================================================

    def fetch_resumes(self, query: str = "has:attachment" ):

        messages = self.search_tool.invoke({"query": query})

        all_resumes = []

        for message in messages:

            message_id = message["id"]
            resumes = self.process_message(message_id)

            all_resumes.extend(resumes)

        return all_resumes