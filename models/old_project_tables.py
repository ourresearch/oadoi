

# CRAN

# from app import db
# from sqlalchemy.dialects.postgresql import JSONB
# import requests
# from models import github_api
# from lxml import html
# from util import elapsed
# from time import time
# import re



# class CranProject(db.Model):
#     project_name = db.Column(db.Text, primary_key=True)
#     owner_name = db.Column(db.Text)

#     github_owner = db.Column(db.Text)
#     github_repo_name = db.Column(db.Text)

#     github_contributors = db.Column(JSONB)

#     api_raw = db.Column(JSONB)
#     downloads = db.Column(JSONB)
#     reverse_deps = db.Column(JSONB)
#     deps = db.Column(JSONB)
#     proxy_papers = db.Column(db.Text)

#     def __repr__(self):
#         return u'<CranProject {project_name}>'.format(
#             project_name=self.project_name)

#     def set_cran_about(self):
#         url_template = "http://crandb.r-pkg.org/%s"
#         data_url = url_template % self.project_name
#         print data_url
#         response = requests.get(data_url)
#         self.api_raw = response.json()

#     def set_github_contributors(self):
#         self.github_contributors = github_api.get_repo_contributors(
#             self.github_owner,
#             self.github_repo_name
#         )
#         print "added github contributors!"
#         print self.github_contributors


#     def set_downloads(self):
#         url_template = "http://cranlogs.r-pkg.org/downloads/daily/1900-01-01:2020-01-01/%s"
#         data_url = url_template % self.project_name
#         print data_url
#         response = requests.get(data_url)
#         if "day" in response.text:
#             data = {}
#             all_days = response.json()[0]["downloads"]
#             data["total_downloads"] = sum([int(day["downloads"]) for day in all_days])
#             data["first_download"] = min([day["day"] for day in all_days])
#             data["daily_downloads"] = all_days
#         else:
#             data = {"total_downloads": 0}
#         self.downloads = data

#     def set_github_repo(self):
#         try:
#             urls_str = self.api_raw['URL']
#         except KeyError:
#             return False

#         # People put all kinds of lists in this field. So we're splitting on
#         # newlines, commas, and spaces. Won't get everything, but will
#         # get most.
#         urls = re.compile(r",*\s*\n*").split(urls_str)

#         for url in urls:
#             login, repo_name = github_api.login_and_repo_name_from_url(url)
#             if login and repo_name:
#                 self.github_repo_name = repo_name
#                 self.github_owner = login

#                 # there may be more than one github url. if so, too bad,
#                 # we're just picking the first one.
#                 break

#         print "successfully set a github ID for {name}: {login}/{repo_name}.".format(
#             name=self.project_name,
#             login=self.github_owner,
#             repo_name=self.github_repo_name
#         )


#     def set_reverse_depends(self):
#         url_template = "https://cran.r-project.org/web/packages/%s/"
#         data_url = url_template % self.project_name
#         print data_url

#         # this call keeps timing out for some reason.  quick workaround:
#         response = None
#         while not response:
#             try:
#                 response = requests.get(data_url)
#             except requests.exceptions.ConnectionError:
#                 # try again
#                 print "connection timed out, trying again"
#                 pass

#         if "Reverse" in response.text:
#             page = response.text
#             page = page.replace("&nbsp;", " ")  # otherwise starts-with for lxml doesn't work
#             tree = html.fromstring(page)
#             data = {}
#             data["reverse_imports"] = tree.xpath('//tr[(starts-with(td[1], "Reverse imports"))]/td[2]/a/text()')
#             data["reverse_depends"] = tree.xpath('//tr[(starts-with(td[1], "Reverse depends"))]/td[2]/a/text()')
#             data["reverse_suggests"] = tree.xpath('//tr[(starts-with(td[1], "Reverse suggests"))]/td[2]/a/text()')
#             data["reverse_enhances"] = tree.xpath('//tr[(starts-with(td[1], "Reverse enhances"))]/td[2]/a/text()')
#             all_reverse_deps = set(data["reverse_imports"] + data["reverse_depends"] + data["reverse_suggests"] + data["reverse_enhances"])
#             data["all_reverse_deps"] = list(all_reverse_deps)

#         else:
#             data = {"all_reverse_deps": []}
#         self.reverse_deps = data


#     def set_proxy_papers(self):
#         url_template = "https://cran.r-project.org/web/packages/%s/citation.html"
#         data_url = url_template % self.project_name
#         print data_url

#         response = requests.get(data_url, timeout=30)

#         if response and response.status_code==200 and "<pre>" in response.text:
#             page = response.text
#             tree = html.fromstring(page)
#             proxy_papers = str(tree.xpath('//pre/text()'))
#             print proxy_papers
#         else:
#             print "no proxy paper found"
#             proxy_papers = "No proxy paper"

#         self.proxy_papers = proxy_papers



# #useful info: http://www.r-pkg.org/services
# def seed_all_cran_packages():
#     # maybe there is a machine readable version of this?  I couldn't find it.
#     url = "https://cran.r-project.org/web/packages/available_packages_by_name.html"
#     r = requests.get(url)
#     print "got page"

#     page = r.text
#     tree = html.fromstring(page)
#     print "finished parsing"
#     all_names = tree.xpath('//tr/td[1]/a/text()')
#     for project_name in all_names:
#         print project_name
#         project = CranProject(project_name=project_name)
#         db.session.add(project)
#         db.session.commit()


# """
# add cran download stats
# """
# def add_cran_downloads(project_name):
#     project = db.session.query(CranProject).get(project_name)
#     project.set_downloads()
#     if project.downloads:
#         print "got downloads!"
#     db.session.commit()
#     # print u"download data found: {}".format(project.downloads)

# def add_all_cran_downloads():
#     q = db.session.query(CranProject.project_name)
#     q = q.filter(CranProject.downloads == "null")
#     q = q.order_by(CranProject.project_name)

#     for row in q.all():
#         add_cran_downloads(row[0])


# """
# add cran reverse_deps
# """
# def add_cran_reverse_deps(project_name):
#     project = db.session.query(CranProject).get(project_name)
#     project.set_reverse_depends()
#     if project.reverse_deps:
#         print "got reverse_deps!"
#     db.session.commit()
#     print u"data found: {}".format(project.reverse_deps)


# def add_all_cran_reverse_deps():
#     q = db.session.query(CranProject.project_name)
#     q = q.filter(CranProject.reverse_deps == "null")
#     q = q.order_by(CranProject.project_name)

#     for row in q.all():
#         add_cran_reverse_deps(row[0])


# """
# add cran about
# """
# def add_cran_about(project_name):
#     project = db.session.query(CranProject).get(project_name)
#     project.set_cran_about()
#     if project.api_raw:
#         print "got api_raw!"
#     db.session.commit()
#     print u"data found: {}".format(project.api_raw)


# def add_all_cran_about():
#     q = db.session.query(CranProject.project_name)
#     q = q.filter(CranProject.api_raw == "null")
#     q = q.order_by(CranProject.project_name)

#     for row in q.all():
#         add_cran_about(row[0])


# """
# add cran proxy papers
# """
# def add_cran_proxy_papers(project_name):
#     project = db.session.query(CranProject).get(project_name)
#     project.set_proxy_papers()
#     db.session.commit()


# def add_all_cran_proxy_papers():
#     q = db.session.query(CranProject.project_name)
#     q = q.filter(CranProject.proxy_papers == None)
#     q = q.order_by(CranProject.project_name)

#     for row in q.all():
#         add_cran_proxy_papers(row[0])


# """
# set cran github info
# """

# def set_all_cran_github_ids():
#     q = db.session.query(CranProject.project_name)
#     q = q.filter(CranProject.api_raw.has_key("URL"))  # if there's no url, there's no github url.
#     q = q.order_by(CranProject.project_name)

#     update_fn = make_update_fn("set_github_repo")

#     for row in q.all():
#         update_fn(row[0])


# """
# get github contrib info
# """

# def set_all_cran_github_contributors():
#     q = db.session.query(CranProject.project_name)
#     q = q.filter(CranProject.github_repo_name != None)
#     q = q.order_by(CranProject.project_name)

#     update_fn = make_update_fn("set_github_contributors")

#     for row in q.all():
#         update_fn(row[0])




# def make_update_fn(method_name):
#     def fn(obj_id):
#         start_time = time()

#         obj = db.session.query(CranProject).get(obj_id)
#         if obj is None:
#             return None

#         method_to_run = getattr(obj, method_name)
#         method_to_run()

#         db.session.commit()

#         print "ran {repr}.{method_name}() method  and committed. took {elapsted}sec".format(
#             repr=obj,
#             method_name=method_name,
#             elapsted=elapsed(start_time, 4)
#         )
#         return None  # important for if we use this on RQ

#     return fn






# def test_cran_project():
#     print "testing cran project!"

    


# PYPI


# from app import db
# from sqlalchemy.dialects.postgresql import JSONB
# from models import github_api
# import requests
# import re
# import pickle
# from pathlib import Path
# from time import time
# from util import elapsed

# # set to nothing most of the time, so imports work
# pypi_package_names = None
# # comment this out here now, because usually not using
# #pypi_package_names = get_pypi_package_names()

# class PypiProject(db.Model):
#     project_name = db.Column(db.Text, primary_key=True)
#     owner_name = db.Column(db.Text)

#     github_owner = db.Column(db.Text)
#     github_repo_name = db.Column(db.Text)
#     github_contributors = db.Column(JSONB)

#     api_raw = db.Column(JSONB)
#     reverse_deps = db.Column(JSONB)
#     deps = db.Column(JSONB)

#     zip_download_elapsed = db.Column(db.Float)
#     zip_download_size = db.Column(db.Integer)
#     zip_download_error = db.Column(db.Text)

#     #dependency_lines = db.Column(db.Text)
#     #zip_grep_elapsed = db.Column(db.Float)

#     def __repr__(self):
#         return u'<PypiProject {project_name}>'.format(
#             project_name=self.project_name)

#     @property
#     def language(self):
#         return "python"


#     def set_github_contributors(self):
#         self.github_contributors = github_api.get_repo_contributors(
#             self.github_owner,
#             self.github_repo_name
#         )
#         print "added github contributors!"
#         print self.github_contributors


#     #def set_dependency_lines(self):
#     #    getter = github_zip_getter_factory(self.login, self.repo_name)
#     #    getter.get_dep_lines(self.language)
#     #
#     #    self.dependency_lines = getter.dep_lines
#     #    self.zip_download_elapsed = getter.download_elapsed
#     #    self.zip_download_size = getter.download_kb
#     #    self.zip_download_error = getter.error
#     #    self.zip_grep_elapsed = getter.grep_elapsed
#     #
#     #    return self.dependency_lines
#     #
#     #
#     #def zip_getter(self):
#     #    if not self.api_raw:
#     #        return None
#     #    if not "url" in self.api_raw:
#     #        return None
#     #
#     #    url = self.api_raw["url"]
#     #    getter = ZipGetter(url)
#     #    return getter


# """
# add pypi dependency lines
# """
# def add_pypi_dependency_lines(project_name):
#     project = db.session.query(PypiProject).get(project_name)
#     if project is None:
#         print "there's no pypi project called {}".format(project_name)
#         return False

#     project.set_dependency_lines()
#     db.session.commit()


# def add_all_pypi_dependency_lines():
#     q = db.session.query(PypiProject.project_name)
#     q = q.filter(~PypiProject.api_raw.has_key('error_code'))
#     q = q.filter(PypiProject.dependency_lines == None, 
#         PypiProject.zip_download_error == None, 
#         PypiProject.zip_download_elapsed == None)
#     q = q.order_by(PypiProject.project_name)

#     for row in q.all():
#         #print "setting this row", row
#         add_pypi_dependency_lines(row[0], row[1])










# """
# get github contrib info
# """

# def set_all_pypi_github_contributors(limit=100):
#     q = db.session.query(PypiProject.project_name)
#     q = q.filter(PypiProject.github_repo_name != None)
#     q = q.filter(PypiProject.github_contributors == None)
#     q = q.order_by(PypiProject.project_name)
#     q = q.limit(limit)

#     update_fn = make_update_fn("set_github_contributors")

#     for row in q.all():
#         update_fn(row[0])


# def make_update_fn(method_name):
#     def fn(obj_id):
#         start_time = time()

#         obj = db.session.query(PypiProject).get(obj_id)
#         if obj is None:
#             return None

#         method_to_run = getattr(obj, method_name)
#         method_to_run()

#         db.session.commit()

#         print "ran {repr}.{method_name}() method  and committed. took {elapsted}sec".format(
#             repr=obj,
#             method_name=method_name,
#             elapsted=elapsed(start_time, 4)
#         )
#         return None  # important for if we use this on RQ

#     return fn


# PYPI REPO


# from __future__ import division
# from app import db
# from models.github_api import make_ratelimited_call
# from models.github_api import GithubRateLimitException
# from models.github_user import GithubUser
# from util import elapsed
# from urlparse import urlparse
# import json
# from sqlalchemy.dialects.postgresql import JSON
# from sqlalchemy.sql.expression import func
# from sqlalchemy.exc import IntegrityError
# from sqlalchemy.exc import OperationalError
# from time import time



# def get_github_homepage(url):
#     try:
#         parsed = urlparse(url)
#     except AttributeError:
#         return None  # no url was given

#     # we are getting rid of things that
#     # 1. aren't on github (duh)
#     # 2. are just "github.com"
#     # this leaves some things that have multiple pypi project in one github repo
#     if parsed.netloc == "github.com" and len(parsed.path.split("/")) > 1:
#         return url
#     else:
#         return None


# def make_pypi_repo(pypi_dict):
#     # this is out of date and no longer will work...
#     name = pypi_dict["info"]["name"]
#     github_url = get_github_homepage(pypi_dict["info"]["home_page"])

#     # i'm pretty sure this will break when you give it None, fix later.
#     path = urlparse(github_url).path

#     return PyPiRepo(
#         pypi_name=name,
#         repo_owner=path[1],
#         repo_name=path[2],
#         github_url=github_url,
#         pypi_about=json.dumps(pypi_dict, indent=3, sort_keys=True)
#     )





# # class PyPiRepo(db.Model):
# #     __tablename__ = 'pypi_repo'
# #     pypi_name = db.Column(db.Text, primary_key=True)
# #     github_url = db.Column(db.Text)
# #     repo_name = db.Column(db.Text)
# #     repo_owner = db.Column(db.Text)

# #     commit_counts = db.Column(JSON)
# #     commit_percents = db.Column(JSON)
# #     key_committers = db.Column(JSON)

# #     is_404 = db.Column(db.Boolean)
# #     pypi_about = db.deferred(db.Column(db.Text))
# #     github_about = db.deferred(db.Column(JSON))

# #     #collected = db.Column(db.DateTime())
# #     #downloads_last_month = db.Column(db.Integer)
# #     #downloads_ever = db.Column(db.Integer)
# #     #requires = db.Column(JSON)

# #     @property
# #     def name_tuple(self):
# #         return (self.repo_owner, self.repo_name)

# #     def set_repo_commits(self):
# #         url = "https://api.github.com/repos/{username}/{repo_name}/contributors?per_page=100".format(
# #             username=self.repo_owner,
# #             repo_name=self.repo_name
# #         )
# #         resp = make_ratelimited_call(url)
# #         if resp is None:
# #             self.is_404 = True
# #             return False

# #         # set the commit_lines property
# #         self.commit_counts = {}
# #         for contrib_dict in resp:
# #             contrib_login = contrib_dict["login"]
# #             self.commit_counts[contrib_login] = contrib_dict["contributions"]

# #         # set the commit_percents property
# #         total_commits = sum(self.commit_counts.values())
# #         self.commit_percents = {}
# #         for username, count in self.commit_counts.iteritems():
# #             self.commit_percents[username] = int(round(count / total_commits * 100))

# #         # set the key_committer property
# #         # do later.
# #         self.key_committers = {}
# #         for username, count in self.commit_counts.iteritems():
# #             percent = self.commit_percents[username]
# #             if percent >= 25 or count >= 100:
# #                 self.key_committers[username] = True
# #             else:
# #                 self.key_committers[username] = False

# #         return True


# def save_all_repo_owners_and_key_committers():
#     start = time()
#     q = db.session.query(PyPiRepo.repo_owner)\
#         .filter(PyPiRepo.repo_owner.isnot(None))\
#         .filter(PyPiRepo.is_404.isnot(True))

#     logins = set()
#     for res in q.all():
#         logins.add(res[0])

#     print "got {} logins from repo owners".format(len(logins))

#     q2 = db.session.query(PyPiRepo.key_committers)\
#         .filter(PyPiRepo.key_committers.isnot(None))\
#         .filter(PyPiRepo.is_404.isnot(True))

#     for res in q2.all():
#         for login, is_key in res[0].iteritems():
#             if is_key:
#                 logins.add(login)

#     print "got {} logins including key committers".format(len(logins))

#     index = 0
#     for login in logins:
#         user = GithubUser(login=login)
#         db.session.add(user)
#         print "{}: {}".format(index, login)
#         index += 1
#         if index % 100 == 0:
#             print "flushing to db...\n\n"
#             db.session.flush()

#     db.session.commit()
#     return True



# def set_all_repo_commits():
#     start = time()
#     index = 0
#     q = db.session.query(PyPiRepo)\
#         .filter(PyPiRepo.repo_name.isnot(None))\
#         .filter(PyPiRepo.repo_owner.isnot(None))\
#         .filter(PyPiRepo.is_404.isnot(True))\
#         .filter(PyPiRepo.commit_counts.is_(None))\
#         .limit(5000)

#     for repo in q.yield_per(100):
#         try:
#             repo.set_repo_commits()
#             index += 1

#             print "#{index} ({sec}sec): ran set_repo_commits() for {owner}/{name}".format(
#                 index=index,
#                 sec=elapsed(start),
#                 owner=repo.repo_owner,
#                 name=repo.repo_name
#             )

#         except GithubRateLimitException:
#             print "ran out of api keys. committing...\n\n".format(
#                 num=index,
#                 sec=elapsed(start)
#             )
#             db.session.commit()
#             return False

#         if index % 100 == 0:
#             try:
#                 db.session.flush()
#             except OperationalError:
#                 print "problem with flushing the session. rolling back."
#                 db.session.rollback()
#                 continue



#     print "finished updating repos! committing...".format(
#         num=index,
#         sec=elapsed(start)
#     )
#     db.session.commit()
#     return True


























#     