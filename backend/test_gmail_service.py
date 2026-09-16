from app.services.gmail_service import GmailResumeService


gmail_service = GmailResumeService()


resumes = gmail_service.fetch_resumes(
    query="has:attachment"
)


print(
    f"\nFound {len(resumes)} resumes\n"
)


for index, resume in enumerate(
    resumes,
    start=1
):

    print("\n" + "=" * 80)

    print(
        f"RESUME {index}"
    )

    print("=" * 80)

    print(
        "Candidate:",
        resume["candidate_name"]
    )

    print(
        "Email:",
        resume["email_address"]
    )

    print(
        "Filename:",
        resume["filename"]
    )

    print(
        "Message ID:",
        resume["gmail_message_id"]
    )

    print("\nResume Text:\n")

    print(
        resume["resume_text"]
    )