from models.package import Package

from app import db
from sqlalchemy.dialects.postgresql import JSONB
from time import time
from distutils.version import StrictVersion
import requests
import hashlib
from lxml import html
import re

from models.person import get_or_make_person
from models.github_repo import GithubRepo
from models.zip_getter import ZipGetter
from models.byline import Byline
from models.academic import is_academic_project
from util import elapsed
from python import parse_requirements_txt



class PypiPackage(Package):
    class_host = "pypi"

    __mapper_args__ = {
        'polymorphic_identity': 'pypi'
    }

    def __repr__(self):
        return u'<PypiPackage {name}>'.format(
            name=self.id)

    @property
    def pagerank_min(self):
        return 0.00000199416

    @property
    def pagerank_99th(self):
        return 0.00210512287367236282  #academic

    @property
    def num_downloads_99th(self):
        return 716743 #academic

    @property
    def num_citations_99th(self):
        return 81 #academic


    @property
    def language(self):
        return "python"

    @property
    def host_url(self):
        return "https://pypi.python.org/pypi/{}".format(self.project_name)

    @property
    def source_url(self):
        if not self.api_raw:
            return None

        if "releases" in self.api_raw and self.api_raw["releases"]:
            versions = self.api_raw["releases"].keys()

            try:
                versions.sort(key=StrictVersion, reverse=True)
            except ValueError:
                versions #give up sorting, just go for it

            # trying these in priority order
            valid_type = ["sdist", "bdist_dumb", "bdist_wheel", "bdist_egg"]
            for packagetype in valid_type:
                for version in versions:
                    release_dict = self.api_raw["releases"][version]
                    for url_dict in release_dict:
                        if "packagetype" in url_dict:
                            if url_dict["packagetype"]==packagetype:
                                if "url" in url_dict and url_dict["url"].startswith("http"):
                                    return url_dict["url"]

            if "download_url" in self.api_raw["info"] and self.api_raw["info"]["download_url"]:
                if self.api_raw["info"]["download_url"].startswith("http"):
                    return self.api_raw["info"]["download_url"]

        return None


    def save_host_contributors(self):
        raw_byline_string = self.api_raw["info"]["author"]
        author_email = self.api_raw["info"]["author_email"]

        byline = Byline(raw_byline_string)

        extracted_name_dicts = byline.author_email_pairs()
        
        # use the author email field only if only one name
        if len(extracted_name_dicts)==1:
            extracted_name_dicts[0]["email"] = author_email

        for kwargs_dict in extracted_name_dicts:
            person = get_or_make_person(**kwargs_dict)
            self._save_contribution(person, "author")


    def set_github_repo_ids(self):
        q = db.session.query(GithubRepo.login, GithubRepo.repo_name)
        q = q.filter(GithubRepo.bucket.contains({"setup_py_name": self.project_name}))
        q = q.order_by(GithubRepo.api_raw['stargazers_count'].cast(db.Integer).desc())

        start = time()
        row = q.first()
        print "Github repo query took {}".format(elapsed(start, 4))

        if row is None:
            return None

        else:
            print "Setting a new github repo for {}: {}/{}".format(
                self,
                row[0],
                row[1]
            )
            self.github_owner = row[0]
            self.github_repo_name = row[1]
            self.bucket["matched_from_github_metadata"] = True


    def _get_files(self, filenames_to_get):

        print "getting requires files for {} from {}".format(
            self.id, self.source_url)
        if not self.source_url:
            print "No source_url, so skipping"
            return {"error": "error_no_source_url"}

        getter = ZipGetter(self.source_url)

        ret = getter.download_and_extract_files(filenames_to_get)

        if getter.error:
            print "Problems with the downloaded zip, quitting without getting filenames."
            ret = {"error": "error_with_zip"}

        return ret


    def set_requires_files(self):
        # from https://pythonhosted.org/setuptools/formats.html#dependency-metadata
        filenames_to_get = [
            "/requires.txt",
            "/metadata.json",
            "/METADATA"
        ]
        self.requires_files = self._get_files(filenames_to_get)
        return self.requires_files


    def set_setup_py(self):
        res = self._get_files(["setup.py"])
        if "error" in res:
            self.setup_py = res["error"]  # save the error string

        else:
            try:
                self.setup_py = res["setup.py"]

                # major hack! comment this in ONLY when there's nothing
                # left to check but weird files that break on UTF-8 errors.
                #self.setup_py = "error_utf8"

                self.setup_py_hash = hashlib.md5(res["setup.py"]).hexdigest()

            except KeyError:
                # seems there is in setup.py here.
                self.setup_py = "error_not_found"

        return self.setup_py



    def set_api_raw(self):
        requests.packages.urllib3.disable_warnings()
        url = 'https://pypi.python.org/pypi/{}/json'.format(self.project_name)
        r = requests.get(url)
        try:
            self.api_raw = r.json()
        except ValueError:
            self.api_raw = {"error": "no_json"}


    def set_host_deps(self):
        core_requirement_lines = ""

        if "METADATA" in self.requires_files:
            requirement_text = self.requires_files["METADATA"]
            # exclude everything after a heading
            core_requirement_list = []
            for line in requirement_text.split("\n"):

                # see spec at https://www.python.org/dev/peps/pep-0345/#download-url
                # "Requires" start is depricated
                if line.startswith("Requires-Dist:") or line.startswith("Requires:"):
                    line = line.replace("Requires-Dist:", "")
                    line = line.replace("Requires:", "")
                    if ";" in line:
                        # has extras in it... so isn't in core requirements, so skip
                        pass
                    else:
                        core_requirement_list += [line]
            core_requirement_lines = "\n".join(core_requirement_list)

        elif "requires.txt" in self.requires_files:
            requirement_text = self.requires_files["requires.txt"]

            # exclude everything after a heading
            core_requirement_list = []
            for line in requirement_text.split("\n"):
                if line.startswith("["):
                    break
                core_requirement_list += [line]
            core_requirement_lines = "\n".join(core_requirement_list)

        deps = parse_requirements_txt(core_requirement_lines)

        print "found requirements={}\n\n".format(deps)
        if not deps:
            self.host_deps = []
            return None

        # see if is in pypi, case insensitively, getting normalized case
        deps_in_pypi = []
        for dep in deps:
            if dep.lower() in pypi_package_names:
                pypi_package_normalized_case = pypi_package_names[dep.lower()]
                deps_in_pypi.append(pypi_package_normalized_case)

        if len(deps_in_pypi) != len(deps):
            print "some deps not in pypi for {}:{}".format(
                self.id, set(deps) - set(deps_in_pypi))
            print deps
            print deps_in_pypi
        self.host_deps = deps_in_pypi


    def set_tags(self):
        self.tags = []
        self.tags += self._get_tags_from_classifiers()
        self.tags += self._get_tags_from_keywords()
        self.tags = list(set(self.tags))  # dedup
        return self.tags

    @property
    def intended_audience(self):
        try:
            pypi_classifiers = self.api_raw["info"]["classifiers"]
        except KeyError:
            return None

        for classifier in pypi_classifiers:
            if classifier.startswith("Intended Audience"):
                return classifier.split(" :: ")[1]


    def set_intended_audience(self):
        self.bucket["intended_audience"] = self.intended_audience


    def set_is_academic(self):
        self.is_academic = is_academic_project(self)
        return self.is_academic




    def _get_tags_from_keywords(self):
        try:
            pypi_keywords_str = self.api_raw["info"]["keywords"]
        except KeyError:
            pypi_keywords_str = None

        if pypi_keywords_str is None:
            return []

        if "," in pypi_keywords_str:
            # try splitting on commas *first*
            keywords = pypi_keywords_str.split(",")
        elif " " in pypi_keywords_str:
            # split on spaces, not as good, but that's what we've got
            keywords = pypi_keywords_str.split(" ")
        else:
            # the whole string is just one keyword
            keywords = [pypi_keywords_str]

        # remove whitespace and empty strings
        ret = [x.strip().lower() for x in keywords if len(x)]

        # dedup
        ret = list(set(ret))

        return ret



    def _get_tags_from_classifiers(self):
        self.tags = []
        tags_to_reject = [
            "Python Modules",
            "Libraries",
            "Software Development",
            "Dynamic Content",
            "Internet",
            "WWW/HTTP"
        ]
        try:
            pypi_classifiers = self.api_raw["info"]["classifiers"]
        except KeyError:
            print "no keywords for {}".format(self)
            return None

        working_tag_list = []
        for classifier in pypi_classifiers:
            if classifier.startswith("Topic"):
                # the first level of the classifier str is useless, discard
                my_tags = classifier.split(" :: ")[1:]
                working_tag_list += my_tags

            if classifier.startswith("Framework"):
                working_tag_list.append(classifier.split(" :: ")[1])

        unique_tags = list(set(working_tag_list))

        # reject blacklisted tags and lowercase
        for tag in unique_tags:
            if len(tag) > 1 and tag not in tags_to_reject:
                self.tags.append(tag.lower())

        if len(self.tags):
            print "set tags for {}: {}".format(self, ",".join(self.tags))
        else:
            print "found no tags for {}".format(self)

        return self.tags


    def set_import_name(self):

        # assume names with dots have same import name as project name.
        if "." in self.project_name:
            self.import_name = self.project_name
            return self.import_name


        url_template = "http://pydoc.net/Python/{}"
        url = url_template.format(self.project_name)

        response = requests.get(url)
        if response.status_code == 404:
            self.import_name = "ERROR: 404"
            return self.import_name

        page = response.text
        tree = html.fromstring(page)
        try:
            self.import_name = tree.xpath("//span[@class='folder']/text()")[0]
        except IndexError:
            self.import_name = "ERROR: malformed page"

        return self.import_name


    def set_setup_py_import_name(self):
        """
        Get the import names from setup.py instead of pydoc.net scrape.

        in sql we are later stomping the pydoc.net ones with the results of this.
        """

        if self.setup_py is None:
            self.setup_py_import_name = None
            return self


        package_regex = re.compile(ur'^\s*\bpackages\s*=\s*\[\s*[\'"](.*?)[\'"]', re.MULTILINE)
        module_regex = re.compile(ur'^\s*\bpy_modules\s*=\s*\[\s*[\'"](.*?)[\'"]', re.MULTILINE)

        try:
            self.setup_py_import_name = package_regex.findall(self.setup_py)[0]
        except IndexError:
            try:
                self.setup_py_import_name = module_regex.findall(self.setup_py)[0]
            except IndexError:
                self.setup_py_import_name = "none_found"


        return self.setup_py_import_name


    @property
    def distinctiveness_query_prefix(self):
        return 'python AND '



def shortcut_get_pypi_package_names():
    start_time = time()
    q = db.session.query(PypiPackage.import_name, PypiPackage.project_name)
    q = q.filter(PypiPackage.unique_import_name == True)

    import_names = {}
    for row in q.all():
        # import_name -> project_name
        import_names[row[0]] = row[1]


    print "got {} PyPi import names in {}sec.".format(
        len(import_names),
        elapsed(start_time)
    )

    return import_names











