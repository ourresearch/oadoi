from app import db
from sqlalchemy.dialects.postgresql import JSONB
from models.python import PythonStandardLibs
from util import elapsed
from time import time
import ast


class GithubRepoDeplines(db.Model):
    __bind_key__ = "old_db"
    __tablename__ = "old_github_repo"

    id = db.Column(db.Text)
    login = db.Column(db.Text, primary_key=True)
    repo_name = db.Column(db.Text, primary_key=True)
    dependency_lines = db.Column(db.Text)
    zip_filenames = db.Column(JSONB)
    language = db.Column(db.Text)
    pypi_dependencies = db.Column(JSONB)

    def __repr__(self):
        return u'<GithubRepo {language} {login}/{repo_name}>'.format(
            language=self.language, login=self.login, repo_name=self.repo_name)

    def say_hi(self):
        print u"hi! from {} {}.".format(self.login, self.repo_name)
        if self.dependency_lines:
            print u"my dep_lines is {} long".format(len(self.dependency_lines))


    @property
    def full_name(self):
        return self.login + "/" + self.repo_name


    def set_pypi_dependencies(self, pypi_import_names):
        """
        using self.dependency_lines, finds all pypi libs imported by repo.

        ignores libs that are part of the python 2.7 standard library, even
        if they are on pypi

        known false-positive issues:
        * counts imports within multi-line quote comments.

        known false-negative issues:
        * ignores imports done with importlib.import_module
        * ignores dynamic importing techniques like map(__import__, moduleNames)
        """

        start_time = time()
        self.pypi_dependencies = []
        pypy_import_names_found = set()
        lines = self.dependency_lines.split("\n")
        import_lines = [l.split(":")[1] for l in lines if ":" in l]
        packages_imported = set()

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
                packages_imported.add(node.module)

            # import foo, bar  # finds foo, bar
            elif isinstance(node, ast.Import):
                for my_name in node.names:
                    packages_imported.add(my_name.name)


        for import_name in packages_imported:
            #print "*** trying import_name", import_name
            pypi_package = self._get_pypi_package(import_name, pypi_import_names)

            if pypi_package is not None:
                pypy_import_names_found.add(pypi_package)

        # the thing we store is actual package names, not import names.
        self.pypi_dependencies = [pypi_import_names[x] for x in pypy_import_names_found]

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
                #print "skipping a venv directory"
                pass
            elif filename.endswith(".py"):
                python_filenames += [filename]

        filenames_string = "\n".join(python_filenames)

        filenames_string_with_dots = filenames_string.replace("/", ".")
        module_name_surrounded_by_dots = ".{}.".format(module_name)
        if module_name_surrounded_by_dots in filenames_string_with_dots:
            #print "found in filepath! removing as dependency:", module_name_surrounded_by_dots
            return True
        else:
            return False



    def _get_pypi_package(self, import_name, pypi_import_names):
        if len(import_name.split(".")) > 5:
            #print "too many parts to be a pypi lib, skipping", import_name
            return None

        # if it's in the standard lib it doesn't count,
        # even if in might be in pypi
        if import_name in PythonStandardLibs.get():
            #print "found in standard lib, skipping", import_name
            return None

        # maybe find flask stuff special here...

        if import_name in pypi_import_names:
            # a last check:
            # don't include modules that are in their filepaths
            # because those are more likely their personal code
            # with accidental pypi names than than pypi libraries
            if self._in_filepath(import_name):
                return None
            else:
                #print "found one!", import_name
                return import_name

        # if foo.bar.baz is not a pypi import name, maybe foo.bar is.  try that.
        elif '.' in import_name:
            shortened_name = import_name.rsplit('.', 1)[0]
            # print "now trying shortened_name", shortened_name
            return self._get_pypi_package(shortened_name, pypi_import_names)

        # if there's no dot in your name, there are no more options, you're done
        else:
            return None