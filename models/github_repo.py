from app import db
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import DataError
from sqlalchemy import or_
from sqlalchemy.orm import deferred

from models import github_api
from models.github_api import login_and_repo_name_from_url
from models.github_api import github_zip_getter_factory
from models.python import PythonStandardLibs
from models import python

from jobs import enqueue_jobs
from jobs import update_registry
from jobs import Update


from models import github_api
import requests
from util import elapsed
from time import time
from time import sleep
import ast
import subprocess
import re
import hashlib
from lxml import html


class GithubRepo(db.Model):
    login = db.Column(db.Text, primary_key=True)
    repo_name = db.Column(db.Text, primary_key=True)
    id = db.Column(db.Text)

    language = db.Column(db.Text)
    api_raw = deferred(db.Column(JSONB))
    named_deps = db.Column(JSONB)
    pypi_dependencies = db.Column(JSONB)
    requirements_pypi = db.Column(JSONB)
    cran_dependencies = db.Column(JSONB)
    cran_descr_file = db.Column(db.Text)
    bucket = db.Column(JSONB)
    cran_descr_file = db.Column(db.Text)
    setup_py = db.Column(db.Text)
    setup_py_hash = db.Column(db.Text)

    dep_lines = deferred(db.Column(db.Text))
    lib_matches_raw = deferred(db.Column(JSONB))
    lib_matches_final = deferred(db.Column(JSONB))

    # old, and removed from current database.  only in backups of database.
    # requirements = db.Column(JSONB)
    # reqs_file = deferred(db.Column(db.Text))
    # reqs_file_tried = db.Column(db.Boolean)
    # zip_filenames = deferred(db.Column(JSONB))
    # zip_filenames_tried = db.Column(db.Boolean)
    # pypi_in_formal_only = db.Column(JSONB)
    # zip_download_elapsed = db.Column(db.Float)
    # zip_download_size = db.Column(db.Integer)
    # zip_download_error = db.Column(db.Text)
    # zip_grep_elapsed = db.Column(db.Float)
    # setup_py_no_forks = deferred(db.Column(db.Text))


    def __repr__(self):
        return u'<GithubRepo {language} {login}/{repo_name}>'.format(
            language=self.language, login=self.login, repo_name=self.repo_name)


    def to_dict(self, exclude=None):
        if exclude is None:
            exclude = []

        property_names = [
            "login",
            "repo_name",
            "api_raw",
            "language",
            "impact"
        ]

        ret = {}
        for property_name in property_names:
            if property_name not in exclude:
                ret[property_name] = getattr(self, property_name)

        # special cases
        ret["is_github"] = True
        try:
            ret["stars"] = self.api_raw["stargazers_count"]
            ret["summary"] = self.api_raw["description"]
        except KeyError:
            ret["stars"] = 0
            ret["summary"] = ""
        return ret


    @property
    def stars(self):
        try:
            return self.api_raw["stargazers_count"]
        except KeyError:
            return 0


    @property
    def impact(self):
        return self.stars

    @property
    def as_snippet(self):
        return self.to_dict(exclude=["api_raw"])


    def set_github_about(self):
        self.api_raw = github_api.get_repo_data(self.login, self.repo_name)
        return self.api_raw

    def set_github_dependency_lines(self):

        getter = github_zip_getter_factory(self.login, self.repo_name)
        getter.set_dep_lines(self.language)

        self.dependency_lines = getter.dep_lines
        if self.dependency_lines:
            try:
                print u"FOUND depencency lines: {}".format(self.dependency_lines)
            except UnicodeDecodeError:
                pass
        else:
            print "NO dependency lines found"
        self.zip_download_elapsed = getter.download_elapsed
        self.zip_download_size = getter.download_kb
        self.zip_download_error = getter.error
        self.zip_grep_elapsed = getter.grep_elapsed

        return self.dependency_lines

    def set_zip_filenames(self):
        print "getting zip filenames for {}".format(self.full_name)

        getter = github_zip_getter_factory(self.login, self.repo_name)
        self.zip_filenames = getter.get_filenames()
        self.zip_filenames_tried = True


    def set_requirements_pypi(self):
        matching_pypi_packages = set()

        for module_name in self.requirements:
            pypi_package = self._get_pypi_package(module_name, pypi_package_names)
            if pypi_package:
                matching_pypi_packages.add(pypi_package)
                # print "got matching_pypi_packages", matching_pypi_packages

        self.requirements_pypi = list(matching_pypi_packages)
        print "self.requirements", self.requirements
        print "matching_pypi_packages", matching_pypi_packages
        print "removed_packages", set(self.requirements) - matching_pypi_packages
        print "added_packages", matching_pypi_packages - set(self.requirements)
        return self.requirements_pypi



    def set_requirements(self):
        return self.set_reqs_file()


    def set_reqs_file(self):
        try:
            # requirements.txt is better, let's try that first.
            self.reqs_file = github_api.get_requirements_txt_contents(
                self.login,
                self.repo_name
            )
            print "found a requirements.txt for {}".format(self.full_name)
            self.requirements = python.reqs_from_file(
                self.reqs_file,
                "requirements.txt"
            )
        except github_api.NotFoundException:
            # darn, no requirements.txt...maybe setup.py tho?
            try:
                self.reqs_file = github_api.get_setup_py_contents(
                    self.login,
                    self.repo_name
                )
                print "found a setup.py for {}".format(self.full_name)
                self.requirements = python.reqs_from_file(
                    self.reqs_file,
                    "setup.py"
                )
            except github_api.NotFoundException:
                # nope, no setup.py either. oh well we tried. quit now.
                self.reqs_file = None
                self.requirements = []


        self.reqs_file_tried = True
        print "found {} requirements for {}".format(
            len(self.requirements),
            self.full_name
        )


    @property
    def full_name(self):
        return self.login + "/" + self.repo_name

    def set_save_error(self):
        # the db threw an error when we tried to save this.
        # likely a 'invalid byte sequence for encoding "UTF8"'
        self.zip_download_error = "save_error"

    def set_pypi_in_formal_only(self):

        self.pypi_in_formal_only = []
        for name in self.requirements_pypi:
            if name not in self.pypi_dependencies:
                # print "only in requirements:", name
                self.pypi_in_formal_only += [name]
            # else:
            #     print "also in imports", name
        print "ending with:", self.pypi_in_formal_only
        return self.pypi_in_formal_only

    def set_pypi_dependencies(self):
        """
        using self.dependency_lines, finds all pypi libs imported by repo.

        ignores libs that are part of the python 2.7 standard library, even
        if they are on pypi

        known false-positive issues:
        * counts imports of local libs that have the same name as pypi libs.
          this is a serious problem for common local-library names like
          'models', 'utils', 'config', etc
        * counts imports within multi-line quote comments.

        known false-negative issues:
        * ignores imports done with importlib.import_module
        * ignores dynamic importing techniques like map(__import__, moduleNames)
        """
        start_time = time()
        self.pypi_dependencies = []
        lines = self.dependency_lines.split("\n")
        import_lines = [l.split(":")[1] for l in lines if ":" in l]
        modules_imported = set()

        # this is SUPER slow here.
        # make get get_pypi_package_names() open a pickle file instead.

        # If we want to speed this up, comment back in the module-level version
        # at the top of this file, and comment it out here.
        # another alternative: filter query against PyPiProject table for the set of names
        # that are included in that table

        # pypi_package_names = get_pypi_package_names()


        for line in import_lines:
            # print u"checking this line: {}".format(line)
            try:
                nodes = ast.parse(line.strip()).body
            except SyntaxError:
                # not well-formed python...prolly part of a comment str
                continue

            try:
                node = nodes[0]
            except IndexError:
                continue

            # from foo import bar # finds foo
            if isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    # relative imports unlikely to be from PyPi
                    continue
                modules_imported.add(node.module)

            # import foo, bar  # finds foo, bar
            elif isinstance(node, ast.Import):
                for my_name in node.names:
                    modules_imported.add(my_name.name)


        for module_name in modules_imported:
            print "*** trying module_name", module_name
            pypi_package = self._get_pypi_package(module_name, pypi_package_names)
            if pypi_package is not None:
                self.pypi_dependencies.append(pypi_package)

        #dedup
        self.pypi_dependencies = list(set(self.pypi_dependencies))

        print "done finding pypi deps for {}: {} (took {}sec)".format(
            self.full_name,
            self.pypi_dependencies,
            elapsed(start_time, 4)
        )
        return self.pypi_dependencies


    def _in_filepath(self, module_name):
        python_filenames = []
        if not self.zip_filenames:
            return False

        for filename in self.zip_filenames:
            if "/venv/" in filename or "/virtualenv/" in filename:
                print "skipping a venv directory"
                pass
            elif filename.endswith(".py"):
                python_filenames += [filename]

        filenames_string = "\n".join(python_filenames)

        filenames_string_with_dots = filenames_string.replace("/", ".")
        module_name_surrounded_by_dots = ".{}.".format(module_name)
        if module_name_surrounded_by_dots in filenames_string_with_dots:
            print "found in filepath! removing as dependency:", module_name_surrounded_by_dots
            return True
        else:
            return False



    def _get_pypi_package(self, module_name, pypi_package_names):
        if len(module_name.split(".")) > 5:
            print "too many parts to be a pypi lib, skipping", module_name            
            return None

        # if it's in the standard lib it doesn't count,
        # even if in might be in pypi
        if module_name in PythonStandardLibs.get():
            print "found in standard lib, skipping", module_name
            return None

        def return_match_if_found(match, replace_with):
            if match in module_name.lower():
                lookup_key = module_name.lower().replace(match, replace_with)
                # pypi_package_names is loaded as module import, it's a cache.
                # search the keys of pypi_package_names, which are all lowercase
                if lookup_key in pypi_package_names:
                    return lookup_key
            return None   

        # try the originals first
        found_key = return_match_if_found("", "")

        # try lots of things, to work around hyphens
        # format is  {<the name you use to import>: <the official PyPi name>}
        special_cases = {
            "dateutil": "python-dateutil",
            "bs4": "beautifulsoup4",
            "yaml": "PyYAML",
            "Image": "Pillow",
            "_imaging": "Pillow"
        }
        if not found_key:
            if module_name in special_cases:
                found_key = special_cases[module_name].lower()
        if not found_key:
            if module_name in special_cases.values():
                found_key = module_name.lower()
        if not found_key:
            found_key = return_match_if_found("-", "_")
        if not found_key:
            found_key = return_match_if_found("-", "-")
        if not found_key:
            found_key = return_match_if_found("_", "-")
        if not found_key:
            found_key = return_match_if_found(".", "-")
        if not found_key:
            found_key = return_match_if_found(".ext.", "-")
        if not found_key:
            found_key = return_match_if_found("ext.", "-")

        if found_key:
            official_pypi_name = pypi_package_names[found_key]
            # a last check:
            # don't include modules that are in their filepaths
            # because those are more likely their personal code 
            # with accidental pypi names than than pypi libraries
            if self._in_filepath(found_key):
                return None
            else:
                print "found one!", official_pypi_name
                return official_pypi_name

        # if foo.bar.baz is not in pypi, maybe foo.bar is. let's try that.
        elif '.' in module_name:
            shortened_name = module_name.rsplit('.', 1)[0]
            # print "now trying shortened_name", shortened_name
            return self._get_pypi_package(shortened_name, pypi_package_names)

        # if there's no dot in your name, there are no more options, you're done
        else:
            return None


    # def _get_pypi_packages(self, candidate_names):

    #     found_in_pypi = set(PypiPackage.valid_package_names(candidate_names))

    #     # if foo.bar.baz is not in pypi, maybe foo.bar is. let's try that.
    #     not_found_in_pypi = candidate_names - found_in_pypi
    #     shortened_names = [name.split('.')[-1] for name in not_found_in_pypi]
    #     if shortened_names:
    #         new_finds = PypiPackage.valid_package_names(shortened_names)
    #         found_in_pypi.update(new_finds)

    #     # if it's in the standard lib it doesn't count, even if in might be in pypi
    #     names_only_in_pypi = [name for name in found_in_pypi if name not in PythonStandardLibs.get()]

    #     # exclude if it is in filepath
    #     names_not_in_filepath = [name for name in names_only_in_pypi if not self._in_filepath(name)]

    #     return names_not_in_filepath


    def set_cran_dependencies(self):
        """
        using self.dependency_lines, finds all cran libs imported by repo.
        """
        start_time = time()
        self.cran_dependencies = []
        if not self.dep_lines:
            return []

        lines = self.dep_lines.split("\n")
        import_lines = [l.split(":")[1] for l in lines if ":" in l]
        modules_imported = set()
        library_or_require_re = re.compile(ur'(?:library|require)\((.*?)[\)|,|\s]', re.IGNORECASE)


        for line in import_lines:
            for clause in line.split(";"):
                # print u"\nchecking this line: {}".format(clause)
                clean_line = clause.strip()
                clean_line = clean_line.replace("'", "")
                clean_line = clean_line.replace('"', "")
                clean_line = clean_line.replace(' ', "")
                clean_line = clean_line.replace('library.dynam', "library")
                clean_line = clean_line.replace('install.packages', "library")
                clean_line = clean_line.replace('require.package', "require")
                if clean_line.startswith("#"):
                    # print "skipping, is a comment"
                    pass # is a comment
                else:
                    modules = library_or_require_re.findall(clean_line)
                    for module in modules:
                        modules_imported.add(module)
                    if modules:
                        # print "found modules", modules
                        pass
                    else:
                        print "NO MODULES found in ", clean_line 
        print "all modules found:", modules_imported

        self.lib_matches_raw = list(modules_imported)

        from models.package import CranPackage
        matching_cran_packages = set(CranPackage.valid_package_names(modules_imported))

        # print "and here are the ones that match cran!", matching_cran_packages
        # print "*********here are the ones that didn't match", modules_imported - matching_cran_packages
        self.lib_matches_final = list(matching_cran_packages)

        print "done finding cran deps for {}: {} (took {}sec)".format(
            self.full_name,
            self.lib_matches_final,
            elapsed(start_time, 4)
        )
        return self.lib_matches_final


    def set_setup_py_no_forks(self):

        # isn't going to get called if the repo has a fork
        if self.api_raw["fork"]:
            print "is a fork, so skipping"
            return

        try:
            self.setup_py_no_forks = github_api.get_setup_py_contents(
                self.login,
                self.repo_name
            )
            print "found a setup.py for {}".format(self.full_name)
        except github_api.NotFoundException:
            self.setup_py_no_forks = "not_found"


    def set_setup_py(self):
        try:
            self.setup_py = github_api.get_setup_py_contents(
                self.login,
                self.repo_name
            )

            # set the hash while we're at it.
            self.setup_py_hash = hashlib.md5(self.setup_py).hexdigest()

        except github_api.NotFoundException:
            print "No setup.py found for {}".format(self.full_name)
            self.setup_py = "not_found"


    def set_cran_descr_file(self):
        # isn't going to get called if the repo has a fork
        if self.api_raw["fork"]:
            print "is a fork, so skipping"
            return

        try:
            self.cran_descr_file = github_api.get_cran_descr_contents(
                self.login,
                self.repo_name
            )
            print "found a REQUIREMENTS file for {}".format(self.full_name)
        except github_api.NotFoundException:
            self.cran_descr_file = "not_found"


    def set_setup_py_name(self):
        if self.setup_py_no_forks is None:
            return None

        m = re.compile(r'name\s*=\s*[\'"](.+?)[\'"]').findall(self.setup_py_no_forks)

        try:
            if self.bucket is None:
                self.bucket = {}

            self.bucket["setup_py_name"] = m[0]
            print "set {} setup_py_name to '{}'".format(
                self,
                m[0]
            )
        except IndexError:
            return None


    def set_cran_descr_file_name(self):
        if self.cran_descr_file is None:
            return None

        m = re.compile(r'^Package\s*:\s*(.+?)\s').findall(self.cran_descr_file)

        try:
            if self.bucket is None:
                self.bucket = {}

            self.bucket["cran_descr_file_name"] = m[0]
            print "set {} cran_descr_file_name to '{}'".format(
                self.full_name,
                m[0]
            )
        except IndexError:
            return None



    def set_named_deps(self):

        self.named_deps = []

        if self.pypi_dependencies:
            self.named_deps += self.pypi_dependencies

        if self.requirements_pypi:
            self.named_deps += self.requirements_pypi

        #uniquify
        self.named_deps = list(set(self.named_deps))
        print "self.named_deps", self.named_deps


    def set_r_named_deps(self):
        if self.language == "r":
            self.named_deps = []
            for dep_kind in ["reverse_depends", "reverse_imports"]:
                if dep_kind in self.lib_matches_final:
                    self.named_deps += self.lib_matches_final[dep_kind]



"""
add the github repo-about api info
"""
def add_github_about(login, repo_name):
    repo = db.session.query(GithubRepo).get((login, repo_name))
    repo.set_github_about()
    db.session.commit()

    print repo

def add_all_github_about():
    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.api_raw == 'null')
    q = q.order_by(GithubRepo.login)

    for row in q.all():
        #print "setting this row", row
        add_github_about(row[0], row[1])








"""
add github dependency lines
"""
def add_github_dependency_lines(login, repo_name):
    repo = get_repo(login, repo_name)
    if repo:
        repo.set_github_dependency_lines()
        commit_repo(repo)
    return None  # important that it returns None for RQ


def add_all_github_dependency_lines(q_limit=100):
    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(~GithubRepo.api_raw.has_key('error_code'))
    q = q.filter(GithubRepo.zip_download_error == None)
    q = q.filter(GithubRepo.zip_download_elapsed == None)
    q = q.order_by(GithubRepo.login)
    q = q.limit(q_limit)

    return enqueue_jobs(q, add_github_dependency_lines, 0)


def add_all_r_github_dependency_lines(q_limit=100):
    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.dependency_lines == None)
    q = q.filter(GithubRepo.zip_download_error == None)
    q = q.filter(GithubRepo.zip_download_elapsed == None)
    q = q.filter(GithubRepo.language == 'r')
    q = q.order_by(GithubRepo.login)
    q = q.limit(q_limit)

    return enqueue_jobs(q, add_github_dependency_lines, 0)

    # return enqueue_jobs(q, add_github_dependency_lines, 0)
    # for row in q.all():
    #     #print "setting this row", row
    #     add_github_dependency_lines(row[0], row[1])



"""
add github repo zip filenames
"""
def set_zip_filenames(login, repo_name):
    repo = get_repo(login, repo_name)
    if repo:
        repo.set_zip_filenames()
        commit_repo(repo)
    return None  # important that it returns None for RQ


def set_all_zip_filenames(q_limit=100):
    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(~GithubRepo.api_raw.has_key('error_code'))
    q = q.filter(GithubRepo.zip_download_error == None)
    q = q.filter(GithubRepo.zip_filenames_tried == None)
    q = q.order_by(GithubRepo.login)
    q = q.limit(q_limit)

    return enqueue_jobs(q, set_zip_filenames, 0)







"""
find and save list of cran dependencies for each repo
"""
def set_cran_dependencies(login, repo_name):
    start_time = time()
    repo = get_repo(login, repo_name)
    if repo is None:
        return None

    repo.set_cran_dependencies()
    commit_repo(repo)
    print "found deps and committed. took {}sec".format(elapsed(start_time), 4)
    return None  # important that it returns None for RQ


def set_all_cran_dependencies(q_limit=100):
    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.dependency_lines != None)
    q = q.filter(GithubRepo.cran_dependencies == None)
    q = q.filter(GithubRepo.language == "r")
    q = q.order_by(GithubRepo.login)
    q = q.limit(q_limit)

    return enqueue_jobs(q, set_cran_dependencies, 0)

    # for row in q.all():
    #     #print "setting this row", row
    #     set_cran_dependencies(row[0], row[1])





"""
save python requirements from requirements.txt and setup.py
"""
def set_requirements(login, repo_name):
    start_time = time()
    repo = get_repo(login, repo_name)
    if repo is None:
        return None

    repo.set_requirements()
    commit_repo(repo)
    print "sought requirements, committed. took {}sec".format(elapsed(start_time), 4)
    return None  # important that it returns None for RQ




def set_all_requirements(q_limit=9500):
    # note the low q_limit: it's cos we've got about 10 api keys @ 5000 each
    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.reqs_file_tried == None)
    q = q.filter(GithubRepo.language == "python")
    q = q.order_by(GithubRepo.login)
    q = q.limit(q_limit)

    return enqueue_jobs(q, set_requirements, 0)






"""
save python requirements from requirements.txt and setup.py
"""
def set_pypi_in_formal_only(login, repo_name):
    print "working on ", login, repo_name
    start_time = time()
    repo = get_repo(login, repo_name)
    if repo is None:
        return None

    repo.set_pypi_in_formal_only()

    commit_repo(repo)
    print "calculated pypi_in_formal_only, committed. took {}sec".format(elapsed(start_time), 4)
    return None  # important that it returns None for RQ


def set_all_pypi_in_formal_only(q_limit=9500, run_mode='with_rq'):
    # note the low q_limit: it's cos we've got about 10 api keys @ 5000 each
    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.requirements_pypi != [])
    q = q.filter(GithubRepo.pypi_dependencies != [])
    q = q.order_by(GithubRepo.login)
    q = q.limit(q_limit)

    if run_mode=='with_rq':  
        return enqueue_jobs(q, set_pypi_in_formal_only, 0)
    else:                   
        for row in q.all():
            #print "setting this row", row
            set_pypi_in_formal_only(row[0], row[1])






"""
utility functions
"""



def get_repo(login, repo_name):
    repo = db.session.query(GithubRepo).get((login, repo_name))
    if repo is None:
        print "there's no repo called {}/{}".format(login, repo_name)
    return repo


def commit_repo(repo):
    try:
        db.session.commit()
    except DataError:
        print "error committing repo, rolling back and setting save error for ", repo
        db.session.rollback()
        repo.set_save_error()
        db.session.commit()











"""
populate the github_repo table from a remote CSV with repo names
"""
# call python main.py add_python_repos_from_google_bucket to run
def add_python_repos_from_google_bucket():
    url = "https://storage.googleapis.com/impactstory/github_python_repo_names.csv"
    add_repos_from_remote_csv(url, "python")

# call python main.py add_r_repos_from_google_bucket to run
def add_r_repos_from_google_bucket():
    url = "https://storage.googleapis.com/impactstory/github_r_repo_names.csv"
    add_repos_from_remote_csv(url, "r")

def add_repos_from_remote_csv(csv_url, language):
    start = time()

    print "going to go get file"
    response = requests.get(csv_url, stream=True)
    index = 0

    for github_url in response.iter_lines(chunk_size=1000):
        login, repo_name = login_and_repo_name_from_url(github_url)
        if login and repo_name:
            repo = GithubRepo(
                login=login,
                repo_name=repo_name,
                language=language
            )
            print repo
            db.session.merge(repo)
            index += 1
            if index % 1000 == 0:
                db.session.commit()
                print "flushing on index {index}, elapsed: {elapsed}".format(
                    index=index,
                    elapsed=elapsed(start))

    db.session.commit()






"""
find and save list of pypi dependencies for each repo
"""
def set_one_pypi_dependencies(login, repo_name):
    print "running with", login, repo_name
    start_time = time()
    repo = get_repo(login, repo_name)
    if repo is None:
        return None

    repo.set_pypi_dependencies()
    commit_repo(repo)
    print "found deps and committed. took {}sec".format(elapsed(start_time), 4)
    return None  # important that it returns None for RQ


def set_all_pypi_dependencies(q_limit=100, use_rq='rq'):
    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.dependency_lines != None)
    q = q.filter(GithubRepo.pypi_dependencies == None)
    q = q.filter(GithubRepo.language == "python")
    q = q.order_by(GithubRepo.login)
    q = q.limit(q_limit)

    enqueue_jobs(GithubRepo, "set_pypi_dependencies", q, 6, use_rq)





"""
save python requirements from requirements.txt and setup.py
"""
def set_one_requirements_pypi(login, repo_name):
    start_time = time()
    repo = get_repo(login, repo_name)
    if repo is None:
        return None

    repo.set_requirements_pypi()
    commit_repo(repo)
    print "cleaned requirements, committed. took {}sec".format(elapsed(start_time), 4)
    return None  # important that it returns None for RQ


def set_all_requirements_pypi(q_limit=9500, use_rq="rq"):
    # note the low q_limit: it's cos we've got about 10 api keys @ 5000 each
    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.requirements_pypi == None)
    q = q.filter(GithubRepo.requirements != [])
    q = q.order_by(GithubRepo.login)
    q = q.limit(q_limit)

    enqueue_jobs(GithubRepo, "set_requirements_pypi", q, 7, use_rq)



def get_all_setup_py_no_forks(limit=10, use_rq="rq"):

    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.reqs_file != None)
    q = q.filter(GithubRepo.setup_py_no_forks == None)
    q = q.filter(GithubRepo.api_raw.contains({"fork":False}))
    q = q.order_by(GithubRepo.login)
    q = q.limit(limit)

    enqueue_jobs(GithubRepo, "set_setup_py_no_forks", q, 8, use_rq)


def get_all_set_named_deps(limit=10, use_rq="rq"):
    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.named_deps == None)
    q = q.order_by(GithubRepo.login)
    q = q.limit(limit)

    enqueue_jobs(GithubRepo, "set_named_deps", q, 5, use_rq)






def set_all_setup_py_names(limit=10, use_rq="rq"):

    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.setup_py_no_forks != None)

    q = q.filter(GithubRepo.bucket == None)  # just a speed optimization
    q = q.filter(GithubRepo.api_raw.contains({"fork": False}))
    q = q.order_by(GithubRepo.login)
    q = q.limit(limit)

    enqueue_jobs(GithubRepo, "set_setup_py_name", q, 1, use_rq)



def set_all_cran_descr_file_names(limit=10, use_rq="rq"):

    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.cran_descr_file != None)
    q = q.filter(GithubRepo.cran_descr_file != "not_found")
    # q = q.filter(GithubRepo.api_raw.contains({"fork": False}))  #already did this when we made it
    q = q.order_by(GithubRepo.login)
    q = q.limit(limit)

    enqueue_jobs(GithubRepo, "set_cran_descr_file_name", q, 9, use_rq)






def set_all_cran_descr_file(limit=10, use_rq="rq"):

    q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
    q = q.filter(GithubRepo.api_raw.contains({"fork": False}))
    q = q.filter(GithubRepo.language == 'r')
    q = q.filter(GithubRepo.cran_descr_file == None)
    q = q.order_by(GithubRepo.login)
    q = q.limit(limit)

    enqueue_jobs(GithubRepo, "set_cran_descr_file", q, 3, use_rq)



q = db.session.query(GithubRepo.id)
q = q.filter(GithubRepo.bucket != None)
q = q.filter(GithubRepo.setup_py == None)

update_registry.register(Update(
    job=GithubRepo.set_setup_py,
    query=q,
    queue_id=4
))


q = db.session.query(GithubRepo.id)
q = q.filter(GithubRepo.api_raw == None)

update_registry.register(Update(
    job=GithubRepo.set_github_about,
    query=q,
    queue_id=4
))


q = db.session.query(GithubRepo.id)
q = q.filter(GithubRepo.language == 'r')
q = q.filter(GithubRepo.dep_lines != None)
update_registry.register(Update(
    job=GithubRepo.set_cran_dependencies,
    query=q,
    queue_id=6
))


q = db.session.query(GithubRepo.id)
q = q.filter(GithubRepo.language == 'r')
q = q.filter(GithubRepo.lib_matches_final != None)
update_registry.register(Update(
    job=GithubRepo.set_r_named_deps,
    query=q,
    queue_id=6
))




def get_readme(owner, repo_name):
    url = "https://github.com/{}/{}".format(
        owner,
        repo_name
    )
    r = requests.get(url)
    p = re.compile(
        ur'<article class="markdown-body entry-content" itemprop="mainContentOfPage">(.+?)</article>',
        re.MULTILINE | re.DOTALL
    )
    res = re.findall(p, r.text)[0]
    return res



















