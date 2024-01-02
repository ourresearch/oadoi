import re
from urllib.parse import unquote

from requests import Response


# def common_redirector(resp: Response):
#     if ('<title>Handle Redirect') in resp.text and (
#             matches := re.findall(r'<body><a href="(http.*?)"', resp.text)):
#         return matches[0]
#     return None


def sd_redirector(resp: Response):
    target = None
    if matches := re.findall(r'name="redirectURL" value="(http.*?)"',
                             resp.text):
        target = unquote(matches[0])

    return target if (target and 'pii' in target) else None


def wiley_redirector(resp: Response):
    if 'onlinelibrary.wiley.com' in resp.url and 'epdf/' in resp.url:
        doi = resp.url.split('epdf/')[-1]
        return f'https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}'
    return None


ALL_REDIRECTORS = [
    # common_redirector,
    sd_redirector,
    wiley_redirector]
