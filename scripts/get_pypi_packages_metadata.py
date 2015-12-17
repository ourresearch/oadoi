"""
Downloads all the json metadata for each package on PyPi.

Uses several parts from https://gist.github.com/brettcannon/d03fbcf365a9c76d4aaa
You must run this file from
"""

import json
from concurrent import futures
from xml import sax
from xml.sax import handler
from pathlib import Path
from urlparse import urlparse

import requests
import time




data_dir = Path(__file__, "../../data").resolve()
pypi_projects_path = Path(data_dir, "pypi_projects.json")
github_usernames_path = Path(data_dir, "github_usernames.json")

class PyPiException(Exception):
    pass


class PyPIIndexHandler(handler.ContentHandler):

    """Parse PyPI's simple index page."""

    def __init__(self):
        handler.ContentHandler.__init__(self)
        self.projects = set()

    def startElement(self, name, attrs):
        # TODO: Check for <meta name="api-version" value="2" /> .
        if name != 'a':
            return

        project_name = attrs.get('href', None)
        if project_name is not None:
            self.projects.add(project_name)


def fetch_index():
    """Return an iterable of every project name on PyPI."""

    r = requests.get('https://pypi.python.org/simple/')
    sax_handler = PyPIIndexHandler()
    sax.parseString(r.text, sax_handler)
    return sax_handler.projects


def fetch_project(name):
    """Return the loaded JSON data from PyPI for a project."""
    url = 'https://pypi.python.org/pypi/{}/json'.format(name)
    r = requests.get(url)
    try:
        return r.json()
    except ValueError:
        # has to *return* an error instead of raising one,
        # cos there seems to be no way to handle errors from here in
        # ThreadPoolExecutor.map()
        return PyPiException("error on package'{}'".format(name))


def get_edu_emails(projects):
    edu_emails = []
    for project in projects:
        email = project["info"]["author_email"]  # can be None or ''
        if email and (".edu" in email or ".ac." in email):
            edu_emails.append(email)
            print email
    print "\n{num_emails} academic emails total ({num_unique} unique)\n".format(
        num_emails=len(edu_emails),
        num_unique=len(set(edu_emails))
    )

def get_github_homepages(projects):
    github_homepages = []
    for project in projects:
        homepage_url = project["info"]["home_page"]

        try:
            parsed = urlparse(homepage_url)
        except AttributeError:
            # no url given, move along
            continue

        if parsed.netloc == "github.com" and len(parsed.path.split("/")) > 1:
            github_homepages.append(homepage_url)

    print "\n{} GitHub homepages total\n".format(len(github_homepages))
    return github_homepages


def get_github_users(projects):
    homepages = get_github_homepages(projects)
    usernames = []
    for url in homepages:
        parsed = urlparse(url)
        path_parts = parsed.path.split("/")
        try:
            usernames.append(path_parts[1])
        except IndexError:
            print "broke url:", url
            continue

    # dedup and removes empty strings
    unique_usernames = list(set([u for u in usernames if u]))

    print "\n{} GitHub unique users\n".format(len(unique_usernames))

    # do a case-insensitive sort
    # usernames are not case-sensitive, turns out
    return sorted(unique_usernames, key=lambda s: s.lower())


def fetch_main():
    start_time = time.time()
    project_data = []
    errors = []

    print('Fetching index ...')
    project_names_set = sorted(fetch_index())

    print('Fetching {} projects ...').format(len(project_names_set))
    with futures.ThreadPoolExecutor(10) as executor:
        for data in executor.map(fetch_project, project_names_set):
            if isinstance(data, PyPiException):
                print "   *** ERROR: {} ***".format(data)
                errors.append(str(data))

            else:
                project_data.append(data)
                print "   {} ".format(data["info"]["name"])


    print "finished getting data in {} seconds".format(
        round(time.time() - start_time, 2)
    )
    print "saving projects file to {}".format(pypi_projects_path)
    with open(str(pypi_projects_path), "w") as f:
        json.dump(project_data, f, indent=3, sort_keys=True)

    print "got these errors:"
    for msg in errors:
        print "  " + msg


def analyze_main():
    print "opening the data file..."
    with open(str(pypi_projects_path), "r") as file:
        projects = json.load(file)

    #get_edu_emails(projects)
    print "saving the users to {}".format(github_usernames_path)
    users = get_github_users(projects)
    with open(str(github_usernames_path), "w") as f:
        json.dump(users, f, indent=3, sort_keys=True)


if __name__ == '__main__':

    # get from PyPi
    #fetch_main()

    # analyze data
    analyze_main()




