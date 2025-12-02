import os

class Config:
    SECRET_KEY = 'your-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///medical.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # CHANGE THESE FOR EMAIL
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'careerpathai.solution@gmail.com'      # CHANGE
    MAIL_PASSWORD = 'mwyg hgtv hiqc pjcz'         # CHANGE (App Password!)
    MAIL_DEFAULT_SENDER = 'your-email@gmail.com'