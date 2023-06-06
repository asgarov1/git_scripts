import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

APPLICATION_JSON_CONTENT_TYPE = "application/json"

# Dieses Token muss man mit eigenem Token ersetzen damit es funktioniert
GITLAB_TOKEN = "Bearer UCs3QNJgMgFYqXXXXXXX"
ENABLE_SSL_VERIFICATION = False


def get(url):
    return requests.get(
        url,
        headers={
            "Authorization": GITLAB_TOKEN,
            "Content-Type": APPLICATION_JSON_CONTENT_TYPE,
        },
        verify=ENABLE_SSL_VERIFICATION,
    ).json()


def post(url):
    return requests.post(
        url,
        headers={
            "Authorization": GITLAB_TOKEN,
            "Content-Type": APPLICATION_JSON_CONTENT_TYPE,
        },
        verify=ENABLE_SSL_VERIFICATION,
    ).json()


def put(url):
    return requests.put(
        url,
        headers={
            "Authorization": GITLAB_TOKEN,
            "Content-Type": APPLICATION_JSON_CONTENT_TYPE,
        },
        verify=ENABLE_SSL_VERIFICATION,
    ).json()
