import hashlib
import math
from collections import defaultdict
from time import sleep
import unicodedata

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import or_
from nameparser import HumanName

from app import db
from models.contribution import Contribution
from models.github_api import GithubRateLimitException
from github_api import get_profile
from util import dict_from_dir

# reused elsewhere
def add_person_leaderboard_filters(q):
    q = q.filter(or_(Person.name == None, Person.name != "UNKNOWN"))
    q = q.filter(or_(Person.email == None, Person.email != "UNKNOWN"))
    q = q.filter(Person.is_organization == False)
    return q

class Person(db.Model):
    __tablename__ = 'person'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.Text)
    name = db.Column(db.Text)
    other_names = db.Column(JSONB)
    github_login = db.Column(db.Text)
    github_about = db.deferred(db.Column(JSONB))
    parsed_name = db.Column(JSONB)

    impact = db.Column(db.Float)
    impact_percentile = db.Column(db.Float)
    num_downloads = db.Column(db.Integer)
    num_downloads_percentile = db.Column(db.Float)
    num_citations = db.Column(db.Integer)
    num_citations_percentile = db.Column(db.Float)   
    pagerank = db.Column(db.Float)
    pagerank_percentile = db.Column(db.Float)

    is_organization = db.Column(db.Boolean)
    main_language = db.Column(db.Text)


    def __repr__(self):
        return u'<Person "{name}" ({id})>'.format(
            name=self.name,
            id=self.id
        )

    contributions = db.relationship(
        'Contribution',
        # lazy='select',
        cascade="all, delete-orphan",
        backref="person"
    )


    def set_is_organization(self):
        # set this using the sql in the sql folder!  set_person_is_organization.sql
        # this is just a placeholder to remind us to run it :)
        pass

    @property
    def display_pagerank(self):
        return self.pagerank / 100.0

    @property
    def subscores(self):
        ret = []

        if not self.impact:
            # no academic impact, so don't return subscores
            return ret

        ret.append({
                "display_name": "Downloads", 
                "icon": "fa-download", 
                "name": "num_downloads",
                "percentile": self.num_downloads_percentile,
                "val": self.num_downloads
            })
        ret.append({
                "display_name": "Dependency PageRank",
                "icon": "fa-recycle", 
                "name": "pagerank", 
                "percentile": self.pagerank_percentile,
                "val": self.display_pagerank
            })
        ret.append({
                "display_name": "Citations", 
                "icon": "fa-file-text-o", 
                "name": "num_mentions", 
                "percentile": self.num_citations_percentile,
                "val": self.num_citations
            })

        return ret

    def to_dict(self, max_person_packages=None, include_top_collabs=True):
        ret = self.as_package_snippet

        person_packages = self.get_person_packages()
        ret["num_packages"] = len(person_packages)
        ret["num_packages_r"] = len([pp for pp in person_packages if pp.package.language=='r'])
        ret["num_packages_python"] = len([pp for pp in person_packages if pp.package.language=='python'])
        
        # tags
        tags_dict = defaultdict(int)
        for pp in person_packages:
            for tag in pp.package.tags:
                tags_dict[tag] += 1
        tags_to_return = min(5, len(tags_dict))
        sorted_tags_to_return = sorted(tags_dict.items(), key=lambda x: x[1], reverse=True)[0:tags_to_return]
        ret["top_person_tags"] = [{"name": name, "count": count} for name, count in sorted_tags_to_return]

        # co-collaborators
        if include_top_collabs:
            my_collabs = defaultdict(float)
            for pp in person_packages:
                for collab_person_id, collab_credit in pp.package.credit.iteritems():
                    if int(collab_person_id) != self.id:  #don't measure my own collab strength
                        collab_strength = collab_credit * pp.person_package_credit
                        my_collabs[collab_person_id] += collab_strength
            sorted_collabs_to_return = sorted(my_collabs.items(), key=lambda x: x[1], reverse=True)
            ret["top_collabs"] = []    
            num_collabs_to_return = min(5, len(sorted_collabs_to_return))    
            for person_id, collab_score in sorted_collabs_to_return[0:num_collabs_to_return]:
                person = Person.query.get(int(person_id))
                if person:
                    person_dict = person.as_package_snippet
                    person_dict["collab_score"] = collab_score * 4  # to make a 0.25*0.25 connection strength of 1
                    ret["top_collabs"].append(person_dict)
                else:
                    print u"ERROR: person {} not found; maybe deduped? skipping.".format(person_id)

        # person packages
        if max_person_packages:
            person_packages_to_return = min(max_person_packages, len(person_packages))
            ret["person_packages"] = [p.as_person_snippet for p in person_packages[0:person_packages_to_return]]
        else:
            ret["person_packages"] = [p.to_dict() for p in person_packages]


        ret["subscores"] = self.subscores

        return ret


    @property
    def as_snippet(self):
        return self.to_dict(max_person_packages=3, include_top_collabs=False)

    @property
    def as_package_snippet(self):
        ret = {
            "id": self.id, 
            "name": self.display_name,
            "single_name": self.single_name,
            "person_name": self.name,  # helps with namespacing in UI
            "github_login": self.github_login, 
            "icon": self.icon, 
            "icon_small": self.icon_small, 
            "is_organization": self.is_organization,             
            "main_language": self.main_language,             
            "impact": self.impact, 
            "impact_percentile": self.impact_percentile, 
            "id": self.id,
            "subscores": self.subscores
        }
        return ret


    def set_main_language(self):
        person_package_summary_dict = self.as_snippet
        if person_package_summary_dict["num_packages_r"] > person_package_summary_dict["num_packages_python"]:
            self.main_language = "r"
        else:
            self.main_language = "python"


    @classmethod
    def shortcut_percentile_refsets(cls):
        print "getting the percentile refsets...."
        ref_list = defaultdict(dict)
        q = db.session.query(
            cls.num_downloads,
            cls.pagerank,
            cls.num_citations,
            cls.impact
        )
        q = q.filter(cls.num_downloads != None)  # only academic contributions, so would have some fractional downloads
        q = q.filter(or_(cls.pagerank > 0, cls.num_citations > 0, cls.num_downloads > 0))  # only academic contributions
        rows = q.all()

        ref_list["num_downloads"] = sorted([row[0] for row in rows if row[0] != None])
        ref_list["pagerank"] = sorted([row[1] for row in rows if row[1] != None])
        ref_list["num_citations"] = sorted([row[2] for row in rows if row[2] != None])
        ref_list["impact"] = sorted([row[3] for row in rows if row[3] != None])

        # only compare impacts against other things with impacts
        ref_list["impact"] = [val for val in ref_list["impact"] if val>0]

        return ref_list


    def _calc_percentile(self, refset, value):
        if value is None:  # distinguish between that and zero
            return None
         
        try:
            matching_index = refset.index(value)
            percentile = float(matching_index) / len(refset)
        except ValueError:
            # not in index.  maybe has no impact because no academic contributions
            print u"not setting percentile for {}; looks like not academic".format(self.name)
            percentile = None
        return percentile

    def set_num_downloads_percentile(self, refset):
        self.num_downloads_percentile = self._calc_percentile(refset, self.num_downloads)

    def set_pagerank_percentile(self, refset):
        self.pagerank_percentile = self._calc_percentile(refset, self.pagerank)

    def set_num_citations_percentile(self, refset):
        self.num_citations_percentile = self._calc_percentile(refset, self.num_citations)

    def set_impact_percentile(self, refset):
        self.impact_percentile = self._calc_percentile(refset, self.impact)

    def set_subscore_percentiles(self, refsets_dict):
        self.set_num_downloads_percentile(refsets_dict["num_downloads"])
        self.set_pagerank_percentile(refsets_dict["pagerank"])
        self.set_num_citations_percentile(refsets_dict["num_citations"])


    def set_impact_percentiles(self, refsets_dict):
        self.set_impact_percentile(refsets_dict["impact"])


    def set_github_about(self):
        if self.github_login is None:
            return None

        self.github_about = get_profile(self.github_login)
        try:
            if not self.name:
                self.name = self.github_about["name"]

            if not self.email :
                self.email = self.github_about["email"]
        except KeyError:

            # our github_about is an error object,
            # it's got no info about the person in it.
            return False



    def set_impact(self):

        try:
            self.impact = (self.pagerank_percentile + self.num_downloads_percentile + self.num_citations_percentile) / 3.0
        except TypeError:  #something was null
            self.impact = 0

    def set_scores(self):
        self.pagerank = 0
        self.num_downloads = 0
        self.num_citations = 0

        for pp in self.get_person_packages():
            # only count up academic packages

            if pp.package.is_academic:
                # only count up impact for packages in our main language            
                if pp.package.language == self.main_language:
                    if pp.person_package_pagerank:
                        self.pagerank += pp.person_package_pagerank
                    if pp.person_package_num_downloads:
                        self.num_downloads += pp.person_package_num_downloads
                    if pp.person_package_num_citations:
                        self.num_citations += pp.person_package_num_citations
        db.session.commit()

    @property
    def name_normalized_for_maximal_deduping(self):
        if not self.name:
            return None

        if self.is_organization:
            return self.name.lower()

        try:
            first_initial = self.parsed_name["first"][0].lower()
        except (KeyError, AttributeError, IndexError):
            first_initial = "?"

        try:
            last_orig = self.parsed_name["last"]
            last = unicodedata.normalize('NFKD', last_orig).encode('ascii', 'ignore')
            last = last.lower()
        except (KeyError, AttributeError):
            last = "?"

        normalized_name = u"{} {}".format(first_initial, last)
        print normalized_name
        return normalized_name


    def set_parsed_name(self):
        if not self.name:
            self.parsed_name = None
            return

        name = HumanName(self.name)
        self.parsed_name = name.as_dict()

    def _make_gravatar_url(self, size):
        try:
            if self.email is not None:
                hash = hashlib.md5(self.email).hexdigest()
            else:
                hash = hashlib.md5(str(self.id)).hexdigest()

        except UnicodeEncodeError:
            print "UnicodeEncodeError making gravatar url from email"
            hash = 42

        url = "http://www.gravatar.com/avatar/{hash}.jpg?s={size}&d=retro".format(
            hash=hash,
            size=size
        )
        return url

    @property
    def icon(self):
        return self._make_gravatar_url(160)

    @property
    def icon_small(self):
        return self._make_gravatar_url(30)

    def has_role_on_project(self, role, package_id):
        for c in self.contributions:
            if c.role == role and c.package_id == package_id:
                return True
        return False

    def num_commits_on_project(self, package_id):
        for c in self.contributions:
            if c.role == "github_contributor" and c.package_id == package_id:
                return c.quantity
        return False

    @property
    def single_name(self):
        if self.is_organization:
            return self.display_name
        elif self.parsed_name and self.parsed_name["last"]:
            return self.parsed_name["last"]
        return self.display_name


    @property
    def display_name(self):
        if self.name:
            return self.name
        elif self.github_login:
            return self.github_login
        elif self.email:
            return self.email.split("@")[0]
        else:
            return "name unknown"

    # could be a property, but kinda slow, so better as explicity method methinks
    def get_person_packages(self):
        person_packages = defaultdict(PersonPackage)
        for contrib in self.contributions:
            person_packages[contrib.package.id].set_role(contrib)

        person_packages_list = person_packages.values()
        person_packages_list.sort(key=lambda x: x.person_package_impact, reverse=True)
        return person_packages_list

    def num_commits_on_project(self, package_id):
        for c in self.contributions:
            if c.role == "github_contributor" and c.package_id == package_id:
                return c.quantity
        return False


    @classmethod
    def decide_who_to_dedup(cls, people):
        if len(people) <= 1:
            # this name has no dups
            return None

        people_with_github = [p for p in people if p.github_login]
        people_with_no_github = [p for p in people if not p.github_login]

        # don't merge people with github together
        # so we only care about merging if there are people with no github
        if not people_with_no_github:
            return None

        if people_with_github:
            # merge people with no github into first person with github
            dedup_target = people_with_github[0]
            people_to_merge = people_with_no_github
        else:
            # pick first person with no github as target, rest as mergees
            dedup_target = people_with_no_github[0]
            people_to_merge = people_with_no_github[1:]   
        return {"dedup_target": dedup_target, "people_to_merge": people_to_merge}     

    @classmethod
    def dedup(cls, dedup_target, people_to_merge):
        print u"person we will merge into: {}".format(dedup_target.id)
        print u"people to merge: {}".format([p.id for p in people_to_merge])

        for person_to_delete in people_to_merge:
            contributions_to_change = person_to_delete.contributions
            for contrib in contributions_to_change:
                contrib.person = dedup_target
                db.session.add(contrib)
            print u"now going to delete {}".format(person_to_delete)
            db.session.delete(person_to_delete)
        # have to run set_credit on everything after this


class PersonPackage():
    def __init__(self):
        self.package = None
        self.person = None
        self.person_package_commits = None
        self.roles = []

    def set_role(self, contrib):
        if not self.package:
            self.package = contrib.package
        if not self.person:
            self.person = contrib.person
        if contrib.role == "github_contributor":
            self.person_package_commits = contrib.quantity
        self.roles.append(contrib)

    @property
    def person_package_credit(self):
        return self.package.get_credit_for_person(self.person.id)

    @property
    def person_package_impact(self):
        try:
            ret = self.person_package_credit * self.package.impact
        except TypeError:
            ret = 0
        return ret

    @property
    def person_package_pagerank(self):
        if self.package.pagerank_score_out_of_1000 == None:
            return None

        ret = self.person_package_credit * self.package.pagerank_score_out_of_1000
        return ret



    @property
    def person_package_num_citations(self):
        if not self.package.num_citations:
            return None        
        ret = self.person_package_credit * self.package.num_citations
        return ret

    @property
    def person_package_num_downloads(self):
        if not self.package.num_downloads:
            return None

        ret = self.person_package_credit * self.package.num_downloads
        return ret


    def to_dict(self):

        ret = self.package.as_snippet
        ret["person_package_credit"] = self.person_package_credit
        ret["person_package_commits"] = self.person_package_commits
        ret["person_package_impact"] = self.person_package_impact
        ret["person_package_pagerank"] = self.person_package_pagerank
        ret["person_package_num_citations"] = self.person_package_num_citations
        ret["person_package_num_downloads"] = self.person_package_num_downloads

        # set roles
        ret["roles"] = {}
        for role in self.roles:
            val = role.quantity
            if role.quantity is None:
                val = True
            ret["roles"][role.role] = val


        try:
            ret["roles"]["owner_only"] = len(self.roles) == 1 and ret["roles"]["github_owner"]
        except KeyError:
            pass

        return ret

    @property
    def as_person_snippet(self):
        ret = self.package.as_snippet_without_people
        ret["person_package_credit"] = self.person_package_credit
        ret["person_package_commits"] = self.person_package_commits
        ret["person_package_impact"] = self.person_package_impact
        ret["person_package_pagerank"] = self.person_package_pagerank
        ret["person_package_num_citations"] = self.person_package_num_citations
        ret["person_package_num_downloads"] = self.person_package_num_downloads 

        # set roles
        ret["roles"] = {}
        for role in self.roles:
            val = role.quantity
            if role.quantity is None:
                val = True
            ret["roles"][role.role] = val


        try:
            ret["roles"]["owner_only"] = len(self.roles) == 1 and ret["roles"]["github_owner"]
        except KeyError:
            pass

        return ret



def find_best_match(persons, **kwargs):
    # get them in this priority order
    for person in persons:
        if "github_login" in kwargs and kwargs["github_login"]:
            if person.github_login == kwargs["github_login"]:
                print "\n matched on github_login"
                return person

    for person in persons:
        if "email" in kwargs and kwargs["email"]:
            if person.email == kwargs["email"]:
                print "\n matched on email"
                return person

    for person in persons:
        if "name" in kwargs and kwargs["name"]:
            normalized_person_name = person.name.replace(".", "")
            normalized_match_name = kwargs["name"].replace(".", "")
            if normalized_person_name == normalized_match_name:
                print "\n matched on exact name"
                return person
    
    return None


def force_make_person(**kwargs):
    # call get_or_make_person unless you are really sure you don't mind a dup here
    new_person = Person(**kwargs)
    # do person attrib setting now so that can use them to detect dedups later this run
    # set_github_about sets name so has to go before parsed name

    keep_trying_github_call = True
    while keep_trying_github_call:
        try:
           new_person.set_github_about() 
           keep_trying_github_call = False
        except GithubRateLimitException:
           print "all github keys maxed out. sleeping...."
           sleep(5 * 60)
           print "trying github call again, mabye api keys refreshed?".format(url)

    new_person.set_parsed_name()
    new_person.set_main_language()
    session.db.commit()

    return new_person


def get_or_make_person(**kwargs):
    res = None

    if 'name' in kwargs and kwargs["name"] == "UNKNOWN":
        # pypi sets unknown people to have the name "UNKNOWN"
        # we don't want to make tons of these, it's just one 'person'.
        res = db.session.query(Person).filter(
            Person.name == "UNKNOWN"
        ).first()

    if 'name' in kwargs and kwargs["name"] == "ORPHANED":
        # cran sets this when the maintainer is gone.
        # we don't want to make tons of these, it's just one 'person'.
        res = db.session.query(Person).filter(
            Person.name == "ORPHANED"
        ).first()

    if res is not None:
        return res

    or_filters = []

    if "github_login" in kwargs and kwargs["github_login"]:
        or_filters.append(Person.github_login == kwargs["github_login"])

    elif "email" in kwargs and kwargs["email"]:
        or_filters.append(Person.email == kwargs["email"])

    elif "name" in kwargs and kwargs["name"]:
        incoming_parsed_name = HumanName(kwargs["name"])
        dict_for_matching = {
            "first": incoming_parsed_name.first,
            "last": incoming_parsed_name.last}
        or_filters.append(Person.parsed_name.contains(dict_for_matching))

    if or_filters:
        query = db.session.query(Person).filter(or_(*or_filters))
        persons = query.all()
        res = find_best_match(persons, **kwargs)

    if res is not None:
        return res
    else:
        print u"minting a new person using {}".format(kwargs)

        new_person = force_make_person(**kwargs)
        #need this commit to handle matching people added previously in this chunk
        db.session.add(new_person)
        db.session.commit()  
        return new_person






