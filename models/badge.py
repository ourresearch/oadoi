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
import re
from textstat.textstat import textstat
from collections import defaultdict
import math
from nameparser import HumanName
from gender_detector import GenderDetector

def get_badge_assigner(name):
    for assigner in all_badge_assigners():
        if assigner.__name__ == name:
            return assigner
    return dummy_badge_assigner


def all_badge_assigner_names():
    return [assigner().name for assigner in all_badge_assigners()]

def all_badge_assigners():
    assigners = BadgeAssigner.__subclasses__()
    assigners.sort(key=lambda x: x.group)
    return assigners

def badge_configs():
    configs = {}
    for assigner in all_badge_assigners():
        if assigner.show_in_ui and assigner.valid_badge:
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
    def sort_score(self):

        if self.percentile:
            sort_score = self.percentile * self.my_badge_type.importance
        else:
            sort_score = 0.5 * self.my_badge_type.importance

        if self.my_badge_type.group == "fun":
            sort_score -= 0.25
        return sort_score

    @property
    def description(self):
        description_template = self.my_badge_type.description
        description_string = description_template.format(
            value=conversational_number(self.value),
            one_hundred_minus_value=conversational_number(100-self.value)
        )
        return description_string

    @property
    def display_in_the_top_percentile(self):
        if not self.percentile:
            return None

        ret = int(100 - self.percentile * 100)
        if ret == 100:
            ret = 99
        if ret < 1:
            ret = 1

        return ret

    @property
    def display_percentile(self):
        if not self.percentile:
            return None

        ret = int(self.percentile * 100)
        if ret == 100:
            ret = 99
        if ret < 1:
            ret = 1

        return ret

    # what the UI is currently expecting
    @property
    def display_percentile_fraction(self):
        if not self.percentile:
            return None

        if self.percentile > 0.99:
            return 0.99
        return self.percentile

    @property
    def context(self):
        context_template = self.my_badge_type.context
        if context_template == None:
            context_template = u"  This puts you in the top {in_the_top_percentile}% of researchers."

        inverse_percentiles = ["reading_level"]
        if self.name in inverse_percentiles:
            if u"{percentile}" in context_template:
                if self.display_percentile > 50:
                    return None
            if u"{in_the_top_percentile}" in context_template:
                if self.display_in_the_top_percentile < 50:
                    return None

        else:
            if u"{percentile}" in context_template:
                if self.display_percentile < 50:
                    return None
            if u"{in_the_top_percentile}" in context_template:
                if self.display_in_the_top_percentile > 50:
                    return None

        context_string = context_template.format(
            value=conversational_number(self.value),
            one_hundred_minus_value=conversational_number(100-self.value),
            in_the_top_percentile=self.display_in_the_top_percentile,
            percentile=self.display_percentile
        )

        return context_string

    @property
    def group(self):
        return self.my_badge_type.group


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
        deduped.sort()
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
        # print u"set percentile for {} {} to {}".format(self.name, self.value, self.percentile)


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
            "show_in_ui": self.my_badge_type.show_in_ui,
            "support_items": self.support_items,
            "support_intro": self.support_intro,
            "support_finale": self.my_badge_type.support_finale,
            "value": self.value,
            "importance": self.my_badge_type.importance,
            "percentile": self.display_percentile_fraction,
            "sort_score": self.sort_score,
            "description": self.description,
            "extra_description": self.my_badge_type.extra_description,
            "context": self.context,
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
    importance = 1
    context = None
    support_intro = None
    support_finale = None
    pad_percentiles_with_zeros = True
    valid_badge = True
    show_in_ui = True

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
    valid_badge = False

class depsy(BadgeAssigner):
    display_name = "Software Reuse"
    is_for_products = False
    group = "openness"
    description = u"Your research software keeps on giving.  Your software impact is in the top {value} percent of all research software creators on Depsy."
    importance = .6
    levels = [
        BadgeLevel(1, threshold=0.01),
    ]
    context = ""

    def decide_if_assigned_threshold(self, person, threshold):
        if person.depsy_percentile:
            if person.depsy_percentile > threshold:
                self.assigned = True
                self.candidate_badge.value = person.depsy_percentile * 100
                # self.candidate_badge.support = u"You are in the {} percentile <a href='http://depsy.org/person/{}'>on Depsy</a>.".format(
                #     round(person.depsy_percentile * 100, 0),
                #     person.depsy_id
                # )


class reading_level(BadgeAssigner):
    display_name = "All Readers Welcome"
    is_for_products = True
    group = "openness"
    description = u"Your writing has a reading level that is easily understood at grade {value} and above, based on its abstracts and titles."
    importance = .5
    levels = [
        BadgeLevel(1, threshold=.01),
    ]
    context = u"That's great &mdash; it helps lay people and practitioners use your research.  " \
              u"It also puts you in the top {percentile}% in readability."
    pad_percentiles_with_zeros = False

    def decide_if_assigned_threshold(self, person, threshold):
        reading_levels = {}
        for my_product in person.all_products:
            text = ""
            if my_product.title:
                text += u" " + my_product.title
            if my_product.get_abstract():
                text += u" " + my_product.get_abstract()

            # only do if at least three words between periods, otherwise too many Not Enough Words debug prints
            if text:
                sentences = text.split(".")
                if any([len(sentence.split())>3 for sentence in sentences]):
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

class reading_level_using_mendeley(BadgeAssigner):
    display_name = "All Readers Welcome"
    is_for_products = True
    group = "openness"
    description = u"Your writing has a reading level that is easily understood at grade {value} and above, based on its abstracts and titles."
    importance = .5
    levels = [
        BadgeLevel(1, threshold=.01),
    ]
    context = u"That's great &mdash; it helps lay people and practitioners use your research.  " \
              u"It also puts you in the top {percentile}% in readability."
    pad_percentiles_with_zeros = False
    show_in_ui = False

    def decide_if_assigned_threshold(self, person, threshold):
        reading_levels = {}
        for my_product in person.all_products:
            text = ""
            if my_product.title:
                text += u" " + my_product.title
            if my_product.get_abstract():
                text += u" " + my_product.get_abstract_using_mendeley()

            # only do if at least three words between periods,
            # otherwise textstat library prints too many Not Enough Words error messages
            if text:
                sentences = text.split(".")
                if any([len(sentence.split())>3 for sentence in sentences]):
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




# class gender_balance(BadgeAssigner):
#     display_name = "Gender Balance"
#     is_for_products = False
#     group = "engagement"
#     description = u"Of the people who tweet about your research, {value}% are women and {one_hundred_minus_value}% are men."
#     importance = .5
#     levels = [
#         BadgeLevel(1, threshold=.01),
#     ]
#     # context = u"The average gender balance in our database is 30% women, 70% men."
#     context = u"That's a better balance than average &mdash; " \
#               u"only {in_the_top_percentile}% of researchers in our database are tweeted by this high a proportion of women."
#     pad_percentiles_with_zeros = False
#
#     # get the average gender balance using this sql
#     # select avg(value) from badge, person
#     # where badge.orcid_id = person.orcid_id
#     # and person.campaign='2015_with_urls'
#     # and name='gender_balance'
#
#
#     def decide_if_assigned_threshold(self, person, threshold):
#         self.candidate_badge.value = 0
#         tweeter_names = person.get_tweeter_names(most_recent=100)
#
#         counts = defaultdict(int)
#         detector = GenderDetector('us')
#
#         for name in tweeter_names:
#             first_name = HumanName(name)["first"]
#             if first_name:
#                 try:
#                     # print u"{} guessed as {}".format(first_name, detector.guess(first_name))
#                     counts[detector.guess(first_name)] += 1
#                 except KeyError:  # the detector throws this for some badly formed first names
#                     pass
#
#         if counts["male"] > 1:
#             ratio_female = counts["female"] / float(counts["male"] + counts["female"])
#             if ratio_female > threshold:
#                 print u"counts female={}, counts male={}, ratio={}".format(
#                     counts["female"], counts["male"], ratio_female)
#                 self.candidate_badge.value = ratio_female * 100
#                 self.assigned = True


class big_hit(BadgeAssigner):
    display_name = "Greatest Hit"
    is_for_products = True
    group = "buzz"
    description = u"Your most discussed publication has been mentioned online {value} times."
    importance = .5
    levels = [
        BadgeLevel(1, threshold=0),
    ]
    context = u"Only {in_the_top_percentile}% of researchers get this much attention on a publication."

    def decide_if_assigned_threshold(self, person, threshold):
        self.candidate_badge.value = 0
        for my_product in person.products_with_dois:
            if my_product.num_posts > self.candidate_badge.value:
                self.assigned = True
                self.candidate_badge.value = my_product.num_posts
                self.candidate_badge.remove_all_products()
                self.candidate_badge.add_product(my_product)
                self.candidate_badge.support = u"Your greatest hit online is <a href='/u/{orcid_id}/p/{id}'>{title}</a>.".format(
                    id=my_product.id,
                    orcid_id=my_product.orcid_id,
                    title=my_product.title
                )



class wiki_hit(BadgeAssigner):
    display_name = "Wikitastic"
    is_for_products = False
    group = "engagement"
    description = u"Your research is mentioned in {value} Wikipedia articles!"
    importance = .9
    levels = [
        BadgeLevel(1, threshold=1),
    ]
    context = u"Only {in_the_top_percentile}% of researchers are this highly cited in Wikipedia."

    def decide_if_assigned_threshold(self, person, threshold):
        num_wikipedia_posts = person.post_counts_by_source("wikipedia")
        if num_wikipedia_posts >= threshold:
            self.assigned = True
            self.candidate_badge.value = num_wikipedia_posts

            urls = person.wikipedia_urls
            self.candidate_badge.add_products([p for p in person.products_with_dois if p.has_source("wikipedia")])
            self.candidate_badge.support = u"Your Wikipedia titles include: {}.".format(
                ", ".join(urls))
            # print self.candidate_badge.support


# inspired by https://github.com/ThinkUpLLC/ThinkUp/blob/db6fbdbcc133a4816da8e7cc622fd6f1ce534672/webapp/plugins/insightsgenerator/insights/followcountvisualizer.php
# class impressions(BadgeAssigner):
#     display_name = "Mass Exposure"
#     is_for_products = False
#     group = "engagement"
#     description = u"Your research has appeared Twitter timelines {value} times."
#     importance = .8
#     img_url = "https://en.wikipedia.org/wiki/File:Avery_fisher_hall.jpg"
#     credit = "Photo: Mikhail Klassen"
#     levels = [
#         BadgeLevel(1, threshold=1000),
#     ]
#     context = u"That's a lot of impressions! Only {in_the_top_percentile}% of scholars have such a large Twitter audience."
#
#     def decide_if_assigned_threshold(self, person, threshold):
#         if person.impressions > threshold:
#             self.assigned = True
#             self.candidate_badge.value = person.impressions


# class babel(BadgeAssigner):
#     display_name = "Multilingual"
#     level = 1
#     is_for_products = False
#     group = "engagement"
#     description = u"People talk about your research in English &mdash; and {value} other languages!"
#     # extra_description = "Due to issues with the Twitter API, we don't have language information for tweets yet."
#     importance = .85
#     levels = [
#         BadgeLevel(1, threshold=1),
#     ]
#     context = u"Only {in_the_top_percentile}% of researchers have their work discussed in this many languages."
#
#     def decide_if_assigned_threshold(self, person, threshold):
#         languages_with_examples = {}
#
#         for my_product in person.products_with_dois:
#             languages_with_examples.update(my_product.languages_with_examples)
#             if len(set(my_product.languages_with_examples.keys()) - set(["en"])) > 0:
#                 self.candidate_badge.add_product(my_product)
#
#         if len(languages_with_examples) >= threshold:
#             self.assigned = True
#             self.candidate_badge.value = len(languages_with_examples)
#             language_url_list = [u"<a href='{}'>{}</a>".format(url, lang)
#                  for (lang, url) in languages_with_examples.iteritems()]
#             self.candidate_badge.support = u"Your langauges include: {}".format(u", ".join(language_url_list))
#             # print self.candidate_badge.support


class global_reach(BadgeAssigner):
    display_name = "Global Reach"
    level = 1
    is_for_products = False
    group = "engagement"
    description = u"Your research has been discussed in {value} countries."
    importance = .8
    levels = [
        BadgeLevel(1, threshold=1),
    ]
    support_finale = " countries."
    context = u"That's high: only {in_the_top_percentile}% of researchers have their work as widely discussed."

    def decide_if_assigned_threshold(self, person, threshold):
        if len(person.countries) > threshold:
            self.assigned = True
            self.candidate_badge.value = len(person.countries)
            self.candidate_badge.support = u"Your tweeters come from: {}.".format(", ".join(person.countries))


class global_reach_using_mendeley(BadgeAssigner):
    display_name = "Global Reach"
    is_for_products = False
    group = "engagement"
    description = u"Your research has been discussed in {value} countries."
    importance = .8
    levels = [
        BadgeLevel(1, threshold=1),
    ]
    support_finale = " countries."
    context = u"That's high: only {in_the_top_percentile}% of researchers have their work as widely discussed."
    show_in_ui = False

    def decide_if_assigned_threshold(self, person, threshold):
        if len(person.countries_using_mendeley) > threshold:
            self.assigned = True
            self.candidate_badge.value = len(person.countries_using_mendeley)
            self.candidate_badge.support = u"Your tweeters come from: {}.".format(", ".join(person.countries_using_mendeley))


class megafan(BadgeAssigner):
    display_name = "Follower Frenzy"
    level = 1
    is_for_products = True
    group = "engagement"
    description = u"Someone with {value} followers has tweeted your research."
    importance = .2
    levels = [
        BadgeLevel(1, threshold=1000),
    ]
    context = u"Only {in_the_top_percentile}% of scholars have been tweeted by someone with this many followers."

    def decide_if_assigned_threshold(self, person, threshold):
        biggest_fan = None

        self.candidate_badge.value = 0
        for my_product in person.products_with_dois:
            for fan_name, followers in my_product.twitter_posters_with_followers.iteritems():
                if followers >= self.candidate_badge.value and followers > threshold:
                    self.assigned = True
                    self.candidate_badge.value = followers
                    self.candidate_badge.remove_all_products()  # clear them
                    self.candidate_badge.add_product(my_product)  # add the one for the new max
                    biggest_fan = fan_name

        self.candidate_badge.support = u"Thanks, <a href='http://twitter.com/{fan}'>@{fan}</a>.".format(
            fan=biggest_fan)



class hot_streak(BadgeAssigner):
    display_name = "Hot Streak"
    level = 1
    is_for_products = False
    group = "buzz"
    description = u"People keep talking about your research. Someone has mentioned your research online every month for the last {value} months."
    importance = .5
    levels = [
        BadgeLevel(1, threshold=1),
    ]
    context = u"That's an attention streak matched by only {in_the_top_percentile}% of scholars."

    def decide_if_assigned_threshold(self, person, threshold):
        streak = True
        streak_length = 0
        all_event_days_ago = [days_ago(e) for e in person.get_event_dates()]
        for month in range(0, 10*12):  # do up to 10 years
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
    display_name = "Deep Engagement"
    level = 1
    is_for_products = True
    group = "engagement"
    description = u"People are engaging deeply with your research &mdash; they are writing {value} news and blog posts" \
                  u" for every 100 times they mention you on twitter and facebook."
    # extra_description = "Based on papers published since 2012 that have more than 10 relevant posts."
    importance = .4
    levels = [
        BadgeLevel(1, threshold=.05),
    ]
    context = u"Only {in_the_top_percentile}% of researchers have such a high ratio of long-form to short-form engagement."
    pad_percentiles_with_zeros = False
    show_in_ui = False

    def decide_if_assigned_threshold(self, person, threshold):
        self.candidate_badge.value = 0
        for my_product in person.products_with_dois:
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
                    self.candidate_badge.value = ratio * 100
                    self.candidate_badge.remove_all_products()
                    self.candidate_badge.add_product(my_product)


class clean_sweep(BadgeAssigner):
    display_name = "Clean Sweep"
    level = 1
    is_for_products = False
    group = "buzz"
    description = "Every one of your publications since 2012 has been mentioned online at least once."
    importance = .1
    levels = [
        BadgeLevel(1, threshold=0),
    ]
    context = u"Fewer than half of researchers show this kind of consistency."

    def decide_if_assigned_threshold(self, person, threshold):
        num_with_posts = 0
        num_applicable = 0
        for my_product in person.products_with_dois:
            if my_product.year > 2011:
                num_applicable += 1
                if my_product.num_posts >= 1:
                    num_with_posts += 1
                    self.candidate_badge.add_product(my_product)

        if (num_with_posts >= num_applicable) and (num_with_posts >= 2):
            self.assigned = True
            self.candidate_badge.value = 1



class global_south(BadgeAssigner):
    display_name = "Global South"
    level = 1
    is_for_products = True
    group = "engagement"
    description = u"More than {value}% of people who mention your research are in the Global South."
    importance = .5
    levels = [
        BadgeLevel(1, threshold=.001),
    ]

    def decide_if_assigned_threshold(self, person, threshold):
        countries = []

        total_geo_located_posts = 0.0
        total_global_south_posts = 0.0

        for my_product in person.products_with_dois:
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

        if total_geo_located_posts >= 3:
            ratio = (total_global_south_posts / total_geo_located_posts)
            if ratio > threshold:
                self.assigned = True
                self.candidate_badge.value = 100.0 * ratio
                self.candidate_badge.support = "Countries include: {}.".format(
                    ", ".join(countries))


class global_south_using_mendeley(BadgeAssigner):
    display_name = "Global South"
    level = 1
    is_for_products = True
    group = "engagement"
    description = u"More than {value}% of people who mention your research are in the Global South."
    importance = .5
    levels = [
        BadgeLevel(1, threshold=.001),
    ]
    show_in_ui = False

    def decide_if_assigned_threshold(self, person, threshold):
        countries = []

        total_geo_located_posts = 0.0
        total_global_south_posts = 0.0

        for my_product in person.all_products:
            for country_name, count in my_product.post_counts_by_country_using_mendeley.iteritems():
                total_geo_located_posts += count
                if country_name:
                    try:
                        if country_info[country_name]["is_global_south"]:
                            total_global_south_posts += count
                            self.candidate_badge.add_product(my_product)
                            countries.append(country_name)
                    except KeyError:
                        print u"ERROR: Nothing in dict for country name {}".format(country_name)
                        raise # don't keep going

        if total_geo_located_posts >= 3:
            ratio = (total_global_south_posts / total_geo_located_posts)
            if ratio > threshold:
                self.assigned = True
                self.candidate_badge.value = 100.0 * ratio
                self.candidate_badge.support = "Countries include: {}.".format(
                    ", ".join(countries))



class ivory_tower(BadgeAssigner):
    display_name = "Labmates"
    level = 1
    is_for_products = False
    group = "engagement"
    description = u"Around {value}% of your online attention is from scientists."
    importance = .1
    context = u"The average scholar in our database receives about 30% of their attention from other scientists."
    pad_percentiles_with_zeros = False

    # get the average percentage scientist attention
    # select avg(value) from badge, person
    # where badge.orcid_id = person.orcid_id
    # and person.campaign='2015_with_urls'
    # and name='ivory_tower'


    def decide_if_assigned(self, person):
        proportion = proportion_poster_counts_by_type(person, "Scientists")
        if proportion > 0.01:
            self.assigned = True
            self.candidate_badge.value = proportion * 100


def proportion_poster_counts_by_type(person, poster_type):
    total_posters_with_type = 0.0
    my_type = 0.0
    for my_product in person.products_with_dois:
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
#     group = "engagement"
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
    display_name = "Open Science Triathlete"
    is_for_products = True
    group = "openness"
    description = u"Congratulations, you hit the trifecta. You have an Open Access paper, open dataset, and open source software."
    importance = .5

    def decide_if_assigned(self, person):
        has_oa_paper = [p.doi for p in person.products_with_dois if p.is_oa_journal]
        has_data = [p.id for p in person.all_products if p.guess_genre()=="dataset"]
        has_software = person.depsy_percentile > 0

        if (has_oa_paper and has_data and has_software):
            self.assigned = True
            self.candidate_badge.value = 1

# OLD
class oa_advocate(BadgeAssigner):
    display_name = "Open Sesame"
    is_for_products = True
    group = "openness"
    description = u"You've published {value}% of your research in gold open access venues."
    context = u"This level of openness is matched by only {in_the_top_percentile}% of researchers."
    importance = .5

    def decide_if_assigned(self, person):
        if person.openness_proportion:  # the openness_proportion takes into account having enough papers
            if person.openness_proportion >= 0.25:
                self.candidate_badge.value = person.openness_proportion * 100
                self.assigned = True

# NEW
class open_sesame(BadgeAssigner):
    display_name = "Open Sesame"
    group = "openness"
    description = u"You've published {value}% of your research in open access venues."
    context = u"This level of openness is matched by only {in_the_top_percentile}% of researchers."
    importance = .9
    show_in_ui = False

    def decide_if_assigned(self, person):
        if person.openness_proportion_all_products:  # the openness_proportion takes into account having enough papers
            if person.openness_proportion >= 0.1:
                self.candidate_badge.value = person.openness_proportion * 100
                self.assigned = True



# class oa_early_adopter(BadgeAssigner):
#     display_name = "OA Early Adopter"
#     is_for_products = True
#     group = "openness"
#     description = u"You published {value} papers in a gold open access journal back in the day, back before it was cool."
#     importance = .8
#     context = u"Only {in_the_top_percentile}% of researchers published {value} gold OA papers before 2009 &mdash; the year PLOS ONE got its Impact Factor."
#     show_in_ui = False
#
#     def decide_if_assigned(self, person):
#         self.candidate_badge.value = 0
#         for my_product in person.products_with_dois:
#             if my_product.year_int > 0 and my_product.year_int < 2009 and my_product.is_oa_journal:
#                 self.assigned = True
#                 self.candidate_badge.value += 1
#                 self.candidate_badge.add_product(my_product)
#         # if self.assigned:
#         #     self.candidate_badge.support_items = [p["title"] for p in self.candidate_badge.products]


class first_steps(BadgeAssigner):
    display_name = "First Steps"
    is_for_products = False
    group = "buzz"
    description = u"Your research has been mentioned online!  Congrats!"
    importance = .01
    context = ""

    def decide_if_assigned(self, person):
        for my_product in person.products_with_dois:
            if my_product.num_posts > 0:
                self.assigned = True
                self.candidate_badge.value = 1


#############
# FUN
#############


# class bff(BadgeAssigner):
#     display_name = "BFF"
#     is_for_products = False
#     group = "fun"
#     description = u"You have {value} <a href='https://en.wikipedia.org/wiki/Best_friends_forever'>BFFs</a>! {value} people have tweeted three or more of your papers."
#     importance = .4
#     context = ""
#     show_in_ui = False
#
#     def decide_if_assigned(self, person):
#         fan_counts = defaultdict(int)
#         fans = set()
#
#         for my_product in person.products_with_dois:
#             for fan_name in my_product.twitter_posters_with_followers:
#                 fan_counts[fan_name] += 1
#
#         for fan_name, tweeted_papers_count in fan_counts.iteritems():
#             if tweeted_papers_count >= 3:
#                 self.assigned = True
#                 fans.add(fan_name)
#
#         if self.assigned:
#             self.candidate_badge.value = len(fans)
#             fan_urls = [u"<a href='http://twitter.com/{fan}'>@{fan}</a>".format(fan=fan) for fan in fans]
#             self.candidate_badge.support = u"BFFs include: {}".format(u",".join(fan_urls))
#

class rick_roll(BadgeAssigner):
    display_name = "Rickroll"
    is_for_products = True
    group = "fun"
    description = u"""You have been tweeted by a person named Richard!
                  A recent study found this is correlated with a 19% boost in citations <a href='https://www.youtube.com/watch?v=dQw4w9WgXcQ'>[source]</a>."""
    importance = 0.35
    context = u"Only {in_the_top_percentile}% of researchers get this achievement."


    def decide_if_assigned(self, person):
        for my_product in person.products_with_dois:
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
                    # self.candidate_badge.support = u"Thanks, {}".format(name)

        # if self.assigned:
        #     print "RICK!!!!", self.candidate_badge.support


class big_in_japan(BadgeAssigner):
    display_name = "Big in Japan"
    is_for_products = True
    group = "fun"
    description = u"Your work was mentioned by someone in Japan!"
    video_url = "https://www.youtube.com/watch?v=tl6u2NASUzU"
    credit = 'Alphaville - "Big In Japan"'
    importance = 0.3
    context = u"Only {in_the_top_percentile}% of scholars share this <a href='https://www.youtube.com/watch?v=tl6u2NASUzU'>claim to fame</a>."

    def decide_if_assigned(self, person):
        for my_product in person.products_with_dois:
            if my_product.has_country("Japan"):
                self.candidate_badge.add_product(my_product)
                self.assigned = True
                self.candidate_badge.value = 1

class big_in_japan_using_mendeley(BadgeAssigner):
    display_name = "Big in Japan"
    is_for_products = True
    group = "fun"
    description = u"Your work was mentioned by someone in Japan!"
    video_url = "https://www.youtube.com/watch?v=tl6u2NASUzU"
    credit = 'Alphaville - "Big In Japan"'
    importance = 0.3
    context = u"Only {in_the_top_percentile}% of scholars share this <a href='https://www.youtube.com/watch?v=tl6u2NASUzU'>claim to fame</a>."
    show_in_ui = False

    def decide_if_assigned(self, person):
        for my_product in person.all_products:
            if my_product.has_country_using_mendeley("Japan"):
                self.candidate_badge.add_product(my_product)
                self.assigned = True
                self.candidate_badge.value = 1



# class controversial(BadgeAssigner):
#     display_name = "Causing a Stir"
#     is_for_products = True
#     group = "fun"
#     description = u"Cool! An F1000 reviewer called your research Controversial!"
#     importance = 0.2
#
#     def decide_if_assigned(self, person):
#         urls = []
#         for my_product in person.products_with_dois:
#             f1000_urls = my_product.f1000_urls_for_class("controversial")
#             if f1000_urls:
#                 self.assigned = True
#                 self.candidate_badge.add_product(my_product)
#                 urls += f1000_urls
#
#         if self.assigned:
#             self.candidate_badge.value = 1
#             self.candidate_badge.support = u"The F1000 reviews include: {}.".format(
#                 ", ".join(urls))
#             # print self.candidate_badge.support


class famous_follower(BadgeAssigner):
    display_name = "Kind of a Big Deal"
    is_for_products = True
    group = "fun"
    description = u"""Cool! Your research has been tweeted by {value}
                  scientists who are considered Big Deals on Twitter <a href='http://www.sciencemag.org/news/2014/09/top-50-science-stars-twitter'>[source]</a>."""
    levels = [
        BadgeLevel(1, threshold=1)
    ]
    importance = 0.3
    context = u"This isn't common: only {in_the_top_percentile}% of other researchers have been mentioned by these twitter stars."

    def decide_if_assigned_threshold(self, person, threshold):
        fans = set()
        for my_product in person.products_with_dois:
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
            self.candidate_badge.support = u"The Big Deal Scientists who tweeted your research include: {}".format(u",".join(fan_urls))


