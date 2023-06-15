from bs4 import BeautifulSoup


# Royal Society of Chemistry
def rsoc(s3_soup: BeautifulSoup):
    return not s3_soup.select_one('.article__author-affiliation')


ORGS_NEED_RESCRAPE_MAP = {'P4310320556': rsoc}
