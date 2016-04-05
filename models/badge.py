from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from models.country import country_info
from models.country import get_name_from_iso
from models.source import sources_metadata
from models.scientist_stars import scientists_twitter

from app import db
from util import date_as_iso_utc
from util import conversational_number
from util import calculate_percentile
from util import days_ago

import datetime
import shortuuid
from textstat.textstat import textstat
from collections import defaultdict
import math
from nameparser import HumanName
from gender_detector import GenderDetector

def get_badge_assigner(name):
    for assigner in all_badge_assigners():
        if assigner.__name__ == name:
            return assigner
    return None


def all_badge_assigners():

    # temporarily just run a few
    # assigners = []
    # for assigner in BadgeAssigner.__subclasses__():
    #     if assigner.__name__ in ["reading_level"]:
    #         assigners.append(assigner)
    #end temporary.  add next line back in

    assigners = BadgeAssigner.__subclasses__()

    assigners.sort(key=lambda x: x.group)
    return assigners

def badge_configs_without_functions():
    configs = {}
    for assigner in all_badge_assigners():
        configs[assigner.__name__] = assigner.config_dict()
    return configs


class Badge(db.Model):
    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text)
    orcid_id = db.Column(db.Text, db.ForeignKey('person.orcid_id'))
    created = db.Column(db.DateTime)
    level = db.Column(db.Float)
    value = db.Column(db.Float)
    percentile = db.Column(db.Float)
    support = db.Column(db.Text)
    products = db.Column(MutableDict.as_mutable(JSONB))


    def __init__(self, assigned=True, **kwargs):
        self.id = shortuuid.uuid()[0:10]
        self.created = datetime.datetime.utcnow().isoformat()
        self.assigned = assigned
        self.products = {}
        super(Badge, self).__init__(**kwargs)

    @property
    def dois(self):
        if self.products:
            return self.products.keys()
        return []

    @property
    def num_products(self):
        if self.products:
            return len(self.products)
        else:
            return 0

    def add_product(self, my_product):
        self.products[my_product.doi] = True

    def add_products(self, products_list):
        for my_product in products_list:
            self.add_product(my_product)

    def remove_all_products(self):
        self.products = {}

    @property
    def my_badge_type(self):
        assigner = get_badge_assigner(self.name)
        if assigner:
            my_assigner = assigner()
        else:
            my_assigner = dummy_badge_assigner()
        return my_assigner

    @property
    def threshold(self):
        return self.my_badge_type.get_threshold(self.level)

    @property
    def sort_score(self):

        try:
            sort_score = self.percentile * self.my_badge_type.importance

        # hack from jason. looks like sometimes self.percentile is None, which
        # causes this to break. not sure what correct fallback is.
        except TypeError:
            sort_score = 1

        if self.my_badge_type.group == "fun":
            sort_score -= 1
        return sort_score

    @property
    def description(self):
        description_string = self.my_badge_type.description
        if "{value}" in description_string:
            description_string = description_string.format(
                value=conversational_number(self.value)
            )

        return description_string

    @property
    def display_max_level(self):
        return math.ceil(self.my_badge_type.max_level/2.0)

    @property
    def display_level(self):
        return math.ceil(self.level/2.0)



    @property
    def support_items(self):
        try:
            parts = self.support.split(": ")
        except AttributeError:
            return None

        try:
            support_phrase = parts[1]
        except IndexError:
            return None

        items = support_phrase.split(",")
        trimmed = [x.strip() for x in items]
        deduped = list(set(trimmed))
        return deduped


    @property
    def support_intro(self):
        try:
            parts = self.support.split(": ")
        except AttributeError:
            return None

        return parts[0]



    def set_percentile(self, refset_list):
        self.percentile = calculate_percentile(refset_list, self.value)
        print u"set percentile for {} {} to {}".format(self.name, self.value, self.percentile)


    def __repr__(self):
        return u'<Badge {id} {name} ({value})>'.format(
            id=self.id,
            name=self.name,
            value=self.value
        )

    def to_dict(self):
        if self.products:
            product_list = self.products.keys()

        resp =  {
            "id": self.id,
            "name": self.name,
            "created": date_as_iso_utc(self.created),
            "support_items": self.support_items,
            "support_intro": self.support_intro,
            "value": self.value,
            "percentile": self.percentile,
            "sort_score": self.sort_score,
            "description": self.description,
            "extra_description": self.my_badge_type.extra_description,
            "group": self.my_badge_type.group,
            "display_name": self.my_badge_type.display_name
        }
        return resp


class BadgeLevel(object):
    def __init__(self, level, threshold=None, custom_description=None):
        self.level = level
        self.threshold = threshold
        self.custom_description = custom_description

    def __repr__(self):
        return u'<BadgeLevel level={level} (threshold={threshold})>'.format(
            level=self.level,
            threshold=self.threshold
        )


class BadgeAssigner(object):
    display_name = ""
    level = 1
    is_for_products = True
    group = None
    description = ""
    extra_description = None
    img_url = None
    video_url = None
    credit = None
    next_level = None
    levels = []
    threshold = None
    value = None
    is_valid_badge = True
    importance = 1

    def __init__(self):
        self.candidate_badge = Badge(name=self.__class__.__name__)
        self.assigned = False

    def get_threshold(self, level):
        for my_level in self.levels:
            if my_level.level == level:
                return my_level.threshold
        return None

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def max_level(self):
        if not self.levels:
            return 1  # is a single level badge

        ordered_levels_reversed = sorted(self.levels, key=lambda x: x.level, reverse=True)
        resp = ordered_levels_reversed[0].level
        return resp

    # override this in subclasses
    def decide_if_assigned(self, person):
        return None

    def decide_if_assigned_with_levels(self, person):
        ordered_levels_reversed = sorted(self.levels, key=lambda x: x.level, reverse=True)
        for my_level in ordered_levels_reversed:
            self.decide_if_assigned_threshold(person, my_level.threshold)
            if self.assigned:
                self.level = my_level.level
                self.threshold = my_level.threshold
                return
        return None

    def get_badge_or_None(self, person):
        if self.levels:
            self.decide_if_assigned_with_levels(person)
        else:
            self.decide_if_assigned(person)

        if self.assigned:
            self.candidate_badge.level = self.level
            return self.candidate_badge
        return None

    @classmethod
    def config_dict(cls):
        resp = {
            "name": cls.__name__,
            "display_name": cls.display_name,
            "is_for_products": cls.is_for_products,
            "group": cls.group,
            "description": cls.description,
        }
        return resp




# for use when other things have been deleted
class dummy_badge_assigner(BadgeAssigner):
    is_valid_badge = False

class depsy(BadgeAssigner):
    display_name = "Software reuse"
    is_for_products = False
    group = "openness"
    description = u"Your software impact is in the top {value} percent of all research software creators on Depsy"
    importance = .8
    levels = [
        BadgeLevel(1, threshold=0.01),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        if person.depsy_percentile:
            if person.depsy_percentile > threshold:
                self.assigned = True
                self.candidate_badge.value = person.depsy_percentile
                self.candidate_badge.support = u"You are in the {} percentile <a href='http://depsy.org/person/{}'>on Depsy</a>.".format(
                    round(person.depsy_percentile * 100, 0),
                    person.depsy_id
                )

class reading_level(BadgeAssigner):
    display_name = "Easy to understand"
    is_for_products = True
    group = "openness"
    description = u"Your abstracts and titles have an average reading level of grade {}."
    importance = .3
    levels = [
        BadgeLevel(1, threshold=.01),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        reading_levels = {}
        for my_product in person.products:
            text = ""
            if my_product.title:
                text += u" " + my_product.title
            if my_product.get_abstract():
                text += u" " + my_product.get_abstract()
            if text:
                try:
                    grade_level = textstat.flesch_kincaid_grade(text)
                    # print u"grade level is {} for {}; text: {}".format(grade_level, my_product.doi, text)
                    if grade_level > 0:
                        # is sometimes negative, strangely.  examples in ethan's profile
                        reading_levels[my_product.doi] = grade_level
                except TypeError:  #if text is too short it thows this
                    pass

        if reading_levels.values():
            average_reading_level = sum(reading_levels.values()) / float(len(reading_levels))
            self.candidate_badge.value = average_reading_level
            self.assigned = True


class gender_balance(BadgeAssigner):
    display_name = "Gender balance"
    is_for_products = False
    group = "influence"
    description = u"The people who tweet your research are {value}% female."
    importance = .2
    levels = [
        BadgeLevel(1, threshold=.01),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        self.candidate_badge.value = 0
        tweeter_names = person.get_tweeter_names(most_recent=100)

        counts = defaultdict(int)
        detector = GenderDetector('us')

        for name in tweeter_names:
            first_name = HumanName(name)["first"]
            if first_name:
                try:
                    # print u"{} guessed as {}".format(first_name, detector.guess(first_name))
                    counts[detector.guess(first_name)] += 1
                except KeyError:  # the detector throws this for some badly formed first names
                    pass

        if counts["male"] > 1:
            ratio_female = counts["female"] / float(counts["male"] + counts["female"])
            if ratio_female > threshold:
                print u"counts female={}, counts male={}, ratio={}".format(
                    counts["female"], counts["male"], ratio_female)
                self.candidate_badge.value = ratio_female * 100
                self.assigned = True


class big_hit(BadgeAssigner):
    display_name = "Big Hit"
    is_for_products = True
    group = "buzz"
    description = u"You have a product with an Altmetric.com score of more than {value}."
    importance = .9
    levels = [
        BadgeLevel(1, threshold=3),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        self.candidate_badge.value = 0
        for my_product in person.products:
            if my_product.altmetric_score > self.candidate_badge.value:
                self.assigned = True
                self.candidate_badge.value = my_product.altmetric_score
                self.candidate_badge.remove_all_products()
                self.candidate_badge.add_product(my_product)



class wiki_hit(BadgeAssigner):
    display_name = "Wiki hit"
    is_for_products = False
    group = "influence"
    description = u"Your research is mentioned in {value} Wikipedia articles!"
    extra_description = "Wikipedia is referenced by <a href='http://www.theatlantic.com/health/archive/2014/03/doctors-1-source-for-healthcare-information-wikipedia/284206/'>half of doctors!</a>"
    importance = .9
    levels = [
        BadgeLevel(1, threshold=1),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        num_wikipedia_posts = person.post_counts_by_source("wikipedia")
        if num_wikipedia_posts > threshold:
            self.assigned = True
            self.candidate_badge.value = num_wikipedia_posts

            urls = person.wikipedia_urls
            self.candidate_badge.add_products([p for p in person.products if p.has_source("wikipedia")])
            self.candidate_badge.support = u"Wikipedia titles include: {}.".format(
                ", ".join(urls))
            # print self.candidate_badge.support


# inspired by https://github.com/ThinkUpLLC/ThinkUp/blob/db6fbdbcc133a4816da8e7cc622fd6f1ce534672/webapp/plugins/insightsgenerator/insights/followcountvisualizer.php
class impressions(BadgeAssigner):
    display_name = "You make an impression"
    is_for_products = False
    group = "influence"
    description = u"The number of twitter impressions your work would fill {value}!"
    importance = .91
    img_url = "https://en.wikipedia.org/wiki/File:Avery_fisher_hall.jpg"
    credit = "Photo: Mikhail Klassen"
    levels = [
        BadgeLevel(1, threshold=100),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        if person.impressions > threshold:
            self.assigned = True
            self.candidate_badge.value = person.impressions


class babel(BadgeAssigner):
    display_name = "Babel"
    level = 1
    is_for_products = False
    group = "influence"
    description = u"Your impact is in {value} more languages than just English!"
    extra_description = "Due to issues with the Twitter API, we don't have language information for tweets yet."
    importance = .85
    levels = [
        BadgeLevel(1, threshold=1),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        languages_with_examples = {}

        for my_product in person.products:
            languages_with_examples.update(my_product.languages_with_examples)
            if len(set(my_product.languages_with_examples.keys()) - set(["en"])) > 0:
                self.candidate_badge.add_product(my_product)

        if len(languages_with_examples) >= threshold:
            self.assigned = True
            self.candidate_badge.value = len(languages_with_examples)
            language_url_list = [u"<a href='{}'>{}</a>".format(url, lang)
                 for (lang, url) in languages_with_examples.iteritems()]
            self.candidate_badge.support = u"Langauges include: {}".format(u", ".join(language_url_list))
            # print self.candidate_badge.support


class global_reach(BadgeAssigner):
    display_name = "Global reach"
    level = 1
    is_for_products = False
    group = "geo"
    description = u"Your research has made an impact in more than {value} countries"
    importance = .85
    levels = [
        BadgeLevel(1, threshold=1),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        if len(person.countries) > threshold:
            self.assigned = True
            self.candidate_badge.value = len(person.countries)
            self.candidate_badge.support = u"Countries include: {}.".format(", ".join(person.countries))



class long_legs(BadgeAssigner):
    display_name = "Consistency"
    level = 1
    is_for_products = True
    group = "consistency"
    description = u"Your research received news or blog mentions more than {value} months after it was published"
    importance = .5
    levels = [
        BadgeLevel(1, threshold=0.5),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        self.candidate_badge.value = 0
        for my_product in person.products:
            for source, days_since_pub in my_product.event_days_since_publication.iteritems():
                if source in ["news", "blogs"]:
                    events_after_two_years = [e for e in days_since_pub if e > threshold*365]
                    if len(events_after_two_years) > self.candidate_badge.value:
                        self.assigned = True
                        self.candidate_badge.value = len(events_after_two_years)
                        self.candidate_badge.remove_all_products()
                        self.candidate_badge.add_product(my_product)



class megafan(BadgeAssigner):
    display_name = "Megafan"
    level = 1
    is_for_products = True
    group = "influence"
    description = u"Someone with more than {value} followers has tweeted your research."
    importance = .4
    levels = [
        BadgeLevel(1, threshold=100000),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        fans = set()

        self.candidate_badge.value = 0
        for my_product in person.products:
            for fan_name, followers in my_product.twitter_posters_with_followers.iteritems():
                if followers >= self.candidate_badge.value:
                    self.assigned = True
                    self.candidate_badge.value = followers
                    self.candidate_badge.remove_all_products()  # clear them
                    self.candidate_badge.add_product(my_product)  # add the one for the new max
                    fans.add(fan_name)

        fan_urls = [u"<a href='http://twitter.com/{fan}'>@{fan}</a>".format(fan=fan) for fan in fans]
        self.candidate_badge.support = u"Megafans include: {}".format(u",".join(fan_urls))



class hot_streak(BadgeAssigner):
    display_name = "Hot streak"
    level = 1
    is_for_products = False
    group = "consistency"
    description = u"You made an impact in each of the last {value} months"
    importance = .7
    levels = [
        BadgeLevel(1, threshold=1),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        streak = True
        streak_length = 0
        all_event_days_ago = [days_ago(e) for e in person.get_event_dates()]
        for month in range(0, 10*12):  # do 10 years
            streak_length += 1
            relevant_days = [month*30 + day for day in range(0, 30)]
            matching_days_count = len([d for d in all_event_days_ago if d in relevant_days])
            if matching_days_count <= 0:
                # print "broke the streak"
                break
        if streak_length > 1:
            self.assigned = True
            self.candidate_badge.value = streak_length



class deep_interest(BadgeAssigner):
    display_name = "Deep interest"
    level = 1
    is_for_products = True
    group = "influence"
    description = u"People are deeply interested in your research.  Your ratio of (news + blogs) / (twitter + facebook) is {value}"
    extra_description = "Based on papers published since 2012 that have more than 10 relevant posts."
    importance = .4
    levels = [
        BadgeLevel(1, threshold=.001),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        self.candidate_badge.value = 0
        for my_product in person.products:
            longform_posts = 0.0
            shortform_posts = 0.0

            if my_product.year_int > 2011:
                longform_posts += my_product.post_counts_by_source("news")
                longform_posts += my_product.post_counts_by_source("blogs")
                shortform_posts += my_product.post_counts_by_source("twitter")
                shortform_posts += my_product.post_counts_by_source("facebook")

            if (shortform_posts > 0) and (longform_posts+shortform_posts > 10):
                ratio = longform_posts / shortform_posts
                # print u"deep-interest ratio: ", ratio
                if ratio >= self.candidate_badge.value:
                    self.assigned = True
                    self.candidate_badge.value = ratio
                    self.candidate_badge.remove_all_products()
                    self.candidate_badge.add_product(my_product)


class clean_sweep(BadgeAssigner):
    display_name = "Clean sweep"
    level = 1
    is_for_products = False
    group = "consistency"
    description = "All of your publications since 2012 have made impact, with at least {value} altmetric score."
    importance = .2
    levels = [
        BadgeLevel(1, threshold=1),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        num_with_posts = 0
        num_applicable = 0
        for my_product in person.products:
            if my_product.year > 2011:
                num_applicable += 1
                if my_product.altmetric_score >= threshold:
                    num_with_posts += 1
                    self.candidate_badge.add_product(my_product)

        if num_with_posts >= num_applicable:
            self.assigned = True
            self.candidate_badge.value = num_with_posts



class global_south(BadgeAssigner):
    display_name = "Global South"
    level = 1
    is_for_products = True
    group = "geo"
    description = u"More than {value}% of your impact is from the Global South."
    importance = .5
    levels = [
        BadgeLevel(1, threshold=.001),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        countries = []

        total_geo_located_posts = 0.0
        total_global_south_posts = 0.0

        for my_product in person.products:
            for country_iso, count in my_product.post_counts_by_country.iteritems():
                total_geo_located_posts += count
                country_name = get_name_from_iso(country_iso)
                if country_name:
                    try:
                        if country_info[country_name]["is_global_south"]:
                            total_global_south_posts += count
                            self.candidate_badge.add_product(my_product)
                            countries.append(country_name)
                    except KeyError:
                        print u"ERROR: Nothing in dict for country name {}".format(country_name)
                        raise # don't keep going

        if total_geo_located_posts > 0:
            # print u"PERCENT GLOBAL SOUTH {} / {} = {}".format(
            #     total_global_south_posts,
            #     total_geo_located_posts,
            #     (total_global_south_posts / total_geo_located_posts)
            # )
            # print u"global south countries: {}".format(countries)

            ratio = (total_global_south_posts / total_geo_located_posts)
            if ratio > threshold:
                self.assigned = True
                self.candidate_badge.value = 100.0 * ratio
                self.candidate_badge.support = "Impact from these Global South countries: {}.".format(
                    ", ".join(countries))



class ivory_tower(BadgeAssigner):
    display_name = "Ivory Tower"
    level = 1
    is_for_products = False
    group = "influence"
    description = u"More than {value}% of your impact is from other researchers."
    importance = .1

    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Scientists")
        if proportion > 0.01:
            self.assigned = True
            self.candidate_badge.value = proportion * 100


class practical_magic(BadgeAssigner):
    display_name = "Practical Magic"
    level = 1
    is_for_products = False
    group = "influence"
    description = u"More than {value}% of your impact is from practitioners."
    importance = .2

    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Practitioners (doctors, other healthcare professionals)")
        if proportion > 0.01:
            self.assigned = True
            self.candidate_badge.value = proportion * 100


class press_pass(BadgeAssigner):
    display_name = "Press pass"
    level = 1
    is_for_products = False
    group = "influence"
    description = u"More than {value}% of your impact is from science communicators."
    importance = .2

    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Science communicators (journalists, bloggers, editors)")
        if proportion > 0.01:
            self.assigned = True
            self.candidate_badge.value = proportion * 100



def proportion_poster_counts_by_type(person, poster_type):
    total_posters_with_type = 0.0
    my_type = 0.0
    for my_product in person.products:
        total_posters_with_type += sum(my_product.poster_counts_by_type.values())
        if poster_type in my_product.poster_counts_by_type:
            my_type += my_product.poster_counts_by_type[poster_type]

    if total_posters_with_type:
        return (my_type / total_posters_with_type)
    else:
        return 0

# class top_news(BadgeAssigner):
#     display_name = "Stop the presses"
#     is_for_products = False
#     group = "influence"
#     description = u"Your research was covered in {value} top news outlets."
#     importance = .9
#
#     def decide_if_assigned(self, person):
#         posts = person.get_top_news_posts()
#         if posts:
#             self.assigned = True
#             self.candidate_badge.value = len(posts)
#             self.candidate_badge.support_items = [p["title"] for p in posts]


class open_science_triathlete(BadgeAssigner):
    display_name = "Open Science triathlete"
    is_for_products = True
    group = "openness"
    description = u"You have an Open Access paper, dataset, and software."
    importance = .1

    def decide_if_assigned(self, person):
        has_oa_paper = [p.doi for p in person.products if p.is_oa_journal]
        has_data = [p.doi for p in person.products if p.type=="dataset"]
        has_software = person.depsy_percentile > 0
        if (has_oa_paper and has_data and has_software):
            self.assigned = True
            self.candidate_badge.value = 1


class oa_advocate(BadgeAssigner):
    display_name = "OA Advocate"
    is_for_products = True
    group = "openness"
    description = u"You've published {value}% of your publications in gold Open venues."
    importance = .1

    def decide_if_assigned(self, person):
        self.candidate_badge.value = person.openness_proportion
        if self.candidate_badge.value > 0 and person.num_products > 3:
            self.assigned = True


class oa_early_adopter(BadgeAssigner):
    display_name = "OA Early Adopter"
    is_for_products = True
    group = "openness"
    description = u"You published {value} papers in gold Open Access venues before it was cool."
    importance = .1

    def decide_if_assigned(self, person):
        self.candidate_badge.value = 0
        for my_product in person.products:
            if my_product.year_int < 2009 and my_product.is_oa_journal:
                self.assigned = True
                self.candidate_badge.value += 1


class first_steps(BadgeAssigner):
    display_name = "First steps"
    is_for_products = False
    group = "buzz"
    description = u"You have made online impact!  Congrats!"
    importance = .01

    def decide_if_assigned(self, person):
        for my_product in person.products:
            if my_product.altmetric_score > 0:
                self.assigned = True
                self.candidate_badge.value = 1


#############
# FUN
#############


class bff(BadgeAssigner):
    display_name = "bff"
    level = 1
    is_for_products = False
    group = "fun"
    description = u"You have a BFF! Someone has tweeted three or more of your papers."

    def decide_if_assigned(self, person):
        fan_counts = defaultdict(int)
        fans = set()

        for my_product in person.products:
            for fan_name in my_product.twitter_posters_with_followers:
                fan_counts[fan_name] += 1

        for fan_name, tweeted_papers_count in fan_counts.iteritems():
            if tweeted_papers_count >= 3:
                self.assigned = True
                fans.add(fan_name)

        if self.assigned:
            self.candidate_badge.value = len(fans)
            fan_urls = [u"<a href='http://twitter.com/{fan}'>@{fan}</a>".format(fan=fan) for fan in fans]
            self.candidate_badge.support = u"BFFs include: {}".format(u",".join(fan_urls))

class rick_roll(BadgeAssigner):
    display_name = "Rickroll"
    level = 1
    is_for_products = True
    group = "fun"
    description = u"You have been tweeted by a person named Richard!"
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def decide_if_assigned(self, person):
        for my_product in person.products:
            for name in my_product.get_tweeter_posters_full_names():
                match = False
                if name.lower().endswith("richard"):
                    match = True
                else:
                    for name_part in name.lower().split(" ")[:-1]:  # don't include last name
                        if name_part in ["rick", "rich", "ricky", "dick", "richard"]:
                            match = True
                if match:
                    self.assigned = True
                    self.candidate_badge.value = 1
                    self.candidate_badge.add_product(my_product)
                    self.candidate_badge.support = u"Thanks, {}".format(name)

        # if self.assigned:
        #     print "RICK!!!!", self.candidate_badge.support


class big_in_japan(BadgeAssigner):
    display_name = "Big in Japan"
    level = 1
    is_for_products = True
    group = "fun"
    description = u"You made impact in Japan!"
    video_url = "https://www.youtube.com/watch?v=tl6u2NASUzU"
    credit = 'Alphaville - "Big In Japan"'

    def decide_if_assigned(self, person):
        for my_product in person.products:
            if my_product.has_country("Japan"):
                self.candidate_badge.add_product(my_product)
                self.assigned = True
                self.candidate_badge.value = 1


class controversial(BadgeAssigner):
    display_name = "Controversial"
    level = 1
    is_for_products = True
    group = "fun"
    description = u"Cool! An F1000 reviewer called your research Controversial!"

    def decide_if_assigned(self, person):
        urls = []
        for my_product in person.products:
            f1000_urls = my_product.f1000_urls_for_class("controversial")
            if f1000_urls:
                self.assigned = True
                self.candidate_badge.add_product(my_product)
                urls += f1000_urls

        if self.assigned:
            self.candidate_badge.value = 1
            self.candidate_badge.support = u"The F1000 reviews include: {}.".format(
                ", ".join(urls))
            # print self.candidate_badge.support


class famous_follower(BadgeAssigner):
    display_name = "Famous follower"
    level = 1
    is_for_products = True
    group = "fun"
    description = u"You have been tweeted by {value} well-known scientists"
    levels = [
        BadgeLevel(1, threshold=1)
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        fans = set()
        for my_product in person.products:
            for twitter_handle in my_product.twitter_posters_with_followers:
                try:
                    if twitter_handle.lower() in scientists_twitter:
                        fans.add(twitter_handle)
                        self.candidate_badge.add_product(my_product)
                except AttributeError:
                    pass

        if len(fans) > threshold:
            self.assigned = True
            self.candidate_badge.value = len(fans)
            fan_urls = [u"<a href='http://twitter.com/{fan}'>@{fan}</a>".format(fan=fan) for fan in fans]
            self.candidate_badge.support = u"Famous fans include: {}".format(u",".join(fan_urls))


