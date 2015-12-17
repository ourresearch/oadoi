from time import time
import requests
import zipfile
import tarfile
import subprocess32


from util import elapsed

class ZipGetterException(Exception):
    db_str = None

class NotFoundException(Exception):
    pass

class ZipGetter():

    def __init__(self, url, login=None, token=None):
        self.url = url
        self.login = login
        self.token = token
        self.download_elapsed = 0
        self.grep_elapsed = 0
        self.download_kb = 0
        self.error = None
        self.temp_file_name = "_downloaded.temp.zip"
        self.dep_lines = None


    def download(self):
        # this is a cleaner way to handle errors, but not done yet...
        try:
            return self._download()
        except ZipGetterException:
            # do more stuff here
            print "zip getter exception"

    def _download(self):

        # @todo erase the temp file when something goes wrong...

        start = time()

        try:
            if self.login and self.token:
                print "Downloading zip from {} with HTTP basic auth {}:{}...".format(
                    self.url,
                    self.login,
                    self.token
                )

                r = requests.get(self.url, stream=True, auth=(self.login, self.token))
            else:
                print "Downloading zip from {}...".format(self.url)
                r = requests.get(self.url, stream=True)
        except requests.exceptions.RequestException:
            print "RequestException for {}".format(self.url)
            self.error = "request_error_RequestException"
            return None

        if r.status_code == 400:
            print "DOWNLOAD ERROR for {}: file not found".format(r.url)
            self.error = "request_error_400"
            return None
        elif r.status_code > 400:
            print "DOWNLOAD ERROR for {}: {} ({})".format(r.url, r.status_code, r.reason)
            self.error = "request_error"
            return None

        with open(self.temp_file_name, 'wb') as out_file:
            r.raw.decode_content = False

            try:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        out_file.write(chunk)
                        out_file.flush()
                        self.download_kb += 1
                        self.download_elapsed = elapsed(start, 4)
                        if self.download_kb > 256*1024:
                            print "DOWNLOAD ERROR for {}: file too big".format(self.url)
                            self.error = "file_too_big"
                            return None

                        if self.download_elapsed > 60:
                            print "DOWNLOAD ERROR for {}: taking too long".format(self.url)
                            self.error = "file_too_slow"
                            return None
            except SocketError:
                print "DOWNLOAD ERROR for {}: SocketError".format(r.url)
                self.error = "socket_error"
                return None


        self.download_elapsed = elapsed(start, 4)
        print "downloaded {} ({}kb) in {} sec".format(
            self.url,
            self.download_kb,
            self.download_elapsed
        )


    def _grep_for_dep_lines(self, query_str, include_globs, exclude_globs):
        arg_list =['zipgrep', query_str, self.temp_file_name]
        arg_list += include_globs
        arg_list.append("-x")
        arg_list += exclude_globs
        start = time()

        try:
            print "Running zipgrep: '{}'".format(" ".join(arg_list))
            self.dep_lines = subprocess32.check_output(
                arg_list,
                timeout=90
            )

        except subprocess32.CalledProcessError:
            # heroku throws an error here when there are no dep lines to find.
            # but it's fine. there just aren't no lines.
            pass

        except subprocess32.TimeoutExpired:
            # too many files, we'll skip it and move on.
            self.error = "grep_timeout"
            pass

        finally:
            self.grep_elapsed = elapsed(start, 4)
            #print "found these dep lines: {}".format(self.dep_lines)
            print "finished dep lines search in {} sec".format(self.grep_elapsed)


    def get_filenames(self):
        self.download()
        if self.error:
            print "Problems with the downloaded zip, quitting without getting filenames."
            return None

        z = zipfile.ZipFile(self.temp_file_name)
        return z.namelist()


    def download_and_extract_files(self, short_filenames):
        requests.packages.urllib3.disable_warnings()
        self.download()
        if self.error:
            print "Problems with the downloaded zip, quitting without getting filenames."
            return None

        contents = {}
        zip_type = "tarfile"
        try:
            zip_file_obj = tarfile.open(self.temp_file_name, "r")
            all_filenames_in_zip = zip_file_obj.getnames()

        except tarfile.ReadError:
            # isn't a tarfile.  try as a zip file
            zip_type = "zipfile"
            try:
                zip_file_obj = zipfile.ZipFile(self.temp_file_name)
                all_filenames_in_zip = zip_file_obj.namelist()
            except zipfile.BadZipfile:
                self.error = "unzip_error"
                return None

        # get the names that match the listing from the zip
        long_names = []
        for filename_in_zip in all_filenames_in_zip:
            for short_filename in short_filenames:
                if filename_in_zip.endswith(short_filename):
                    long_names.append(filename_in_zip)

        # print "now going to extract short_filenames:", short_filenames
        # print "all_filenames_in_zip", "\n".join(all_filenames_in_zip)
        # print "now going to extract long_names:", long_names

        for filename in long_names:
            try:
                if zip_type=="tarfile":
                    extracted_place = zip_file_obj.extractfile(filename)
                else:
                    extracted_place = zip_file_obj.open(filename)

                dict_key = filename.split("/")[-1]
                contents[dict_key] = extracted_place.read()
                if contents[dict_key]:
                    print "got it!!!!!  with zip_type=", zip_type
            except KeyError:
                print "not found", filename
                pass # isn't a problem
            except AttributeError:
                print "Couldn't open the archive file."
        
        if not contents:
            print "nothing found with ziptype", zip_type
        
        return contents


    def set_dep_lines(self, language):
        self.download()
        if self.error:
            print "There are problems with the downloaded zip, quitting without getting deps."
            return None

        if language == "r":
            print "getting dep lines in r"
            include_globs = []
            r_include_globs = ["*.R", "*.Rnw", "*.Rmd", "*.Rhtml", "*.Rtex", "*.Rst"]
            for r_include_glob in r_include_globs:
                include_globs.append(r_include_glob.upper())
                include_globs.append(r_include_glob.lower())

            include_globs += r_include_globs

            exclude_globs = ["*.foo"]  # hack, because some value is expected

            # heroku zipgrep doesn't allow ors
            self._grep_for_dep_lines("library", include_globs, exclude_globs)
            first_half_dependency = self.dep_lines
            self._grep_for_dep_lines("require", include_globs, exclude_globs)
            if first_half_dependency:
                self.dep_lines = "\n".join([first_half_dependency, self.dep_lines])

        elif language == "python":
            print "getting dep lines in python"
            query_str = "import"
            include_globs = ["*.py", "*.ipynb"]
            exclude_globs = ["*/venv/*", "*/virtualenv/*", "*/bin/*", "*/lib/*", "*/Lib/*", "*/library/*", "*/vendor/*"]
            self._grep_for_dep_lines(query_str, include_globs, exclude_globs)
