import os
from pathlib import Path
from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from dotenv import load_dotenv

OTP_EXPIRATION_TIME_MINUTES = 15

def getMailConfig():
    load_dotenv()

    config = ConnectionConfig(
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
        MAIL_FROM=os.getenv('MAIL_FROM'),
        MAIL_PORT=int(os.getenv('MAIL_PORT')),
        MAIL_SERVER=os.getenv('MAIL_SERVER'),
        MAIL_FROM_NAME=os.getenv('MAIL_FROM_NAME'),
        MAIL_STARTTLS=os.getenv('MAIL_TLS'),
        MAIL_SSL_TLS=os.getenv('MAIL_SSL'),
        USE_CREDENTIALS=os.getenv('USE_CREDENTIALS'),
        VALIDATE_CERTS=os.getenv('VALIDATE_CERTS'),
        TEMPLATE_FOLDER= Path(__file__).parent / 'mail_templates'
    )

    return config

def testEmail(email: str):
    message = MessageSchema(
        subject="Test from FastAPI Mail",
        recipients=[email],
        body="This is a simple test email sent from FastAPI mail.",
        subtype="plain"
    )

    BackgroundTasks.add_task(FastMail(getMailConfig()).send_message, message)

    print("Test email sending initiated in the background")

def otpMailMessage(email: str, otp: str, backgroundTasks: BackgroundTasks):
    return mailMessage(
        message=MessageSchema(
            subject="Password Reset for Identiflora",
            recipients=[email],
            template_body={"otp": list(otp), "exp_time": str(OTP_EXPIRATION_TIME_MINUTES)},
            subtype=MessageType.html
        ),
        backgroundTasks=backgroundTasks
    )

def mailMessage(message: MessageSchema, backgroundTasks: BackgroundTasks):
    fm = FastMail(getMailConfig())
    backgroundTasks.add_task(fm.send_message, message, "password_reset.html")
    return {"message": "Email sending initiated in the background", "success": True}