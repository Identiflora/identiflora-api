import os
from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
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
        VALIDATE_CERTS=os.getenv('VALIDATE_CERTS')
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
        email, 
        "Password Reset for Identiflora", "Hi there!\n\nHere is your one time password regarding your recent password reset:\n\n" 
            + otp + "\n\nThis password will expire in " + str(OTP_EXPIRATION_TIME_MINUTES) + " minutes.\n\nDo not reply to this email, but if this was not you, please send an email to identiflora.app@gmail.com.", 
        backgroundTasks)

def mailMessage(email: str, subject: str, body: str, backgroundTasks: BackgroundTasks):
    message = MessageSchema(
        subject=subject,
        recipients=[email],
        body=body,
        subtype="plain"
    )

    backgroundTasks.add_task(FastMail(getMailConfig()).send_message, message)
    return {"message": "Email sending initiated in the background", "success": True}