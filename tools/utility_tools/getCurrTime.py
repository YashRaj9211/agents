from datetime import datetime

def getCurrentTime():
    """Return the current date and time"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")