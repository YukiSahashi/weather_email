"""メール送信。SMTP(SSL/STARTTLS両対応)。

必要な環境変数(GitHub Actions では Secrets に設定):
  SMTP_HOST      例: smtp.gmail.com
  SMTP_PORT      例: 465 (SSL) / 587 (STARTTLS)
  SMTP_USER      送信元アカウント
  SMTP_PASSWORD  Gmailなら「アプリパスワード」(通常パスワード不可)
  MAIL_TO        宛先(カンマ区切りで複数可)
  MAIL_FROM      省略時は SMTP_USER
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown as md


def send(cfg: dict, subject: str, body_markdown: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    mail_from = os.environ.get("MAIL_FROM", user)
    mail_to = [x.strip() for x in os.environ["MAIL_TO"].split(",") if x.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(mail_to)
    msg.attach(MIMEText(body_markdown, "plain", "utf-8"))
    html = md.markdown(body_markdown, extensions=["tables", "nl2br"])
    msg.attach(MIMEText(f"<html><body>{html}</body></html>", "html", "utf-8"))

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context) as s:
            s.login(user, password)
            s.sendmail(mail_from, mail_to, msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=context)
            s.login(user, password)
            s.sendmail(mail_from, mail_to, msg.as_string())
