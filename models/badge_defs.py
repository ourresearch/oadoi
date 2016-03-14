from collections import defaultdict

from models.badge import Badge
from models.country import country_info
from models.country import get_name_from_iso
from models.country import pacific_rim_east, pacific_rim_west
from models.source import sources_metadata

def badge_configs_without_functions():
    return all_badge_defs


def get_badge_or_None(badge_name, person):
    badge_function = globals()[badge_name]
    my_badge = badge_function(person)
    if my_badge.assigned:
        my_badge.name = badge_name
        my_badge.assign_from_badge_def(**all_badge_defs[badge_name])
        return my_badge
    return None

def big_in_japan(person):
    candidate_badge = Badge(assigned=False)
    for my_product in person.products:
        if my_product.has_country("Japan"):
            candidate_badge.assigned = True
            candidate_badge.add_product(my_product)
    return candidate_badge


def baby_steps(person):
    candidate_badge = Badge(assigned=False)
    for my_product in person.products:
        if my_product.altmetric_score > 0:
            candidate_badge.assigned = True
            candidate_badge.add_product(my_product)
    return candidate_badge

def megahit(person):
    candidate_badge = Badge(assigned=False)
    for my_product in person.products:
        if my_product.altmetric_score > 100:
            candidate_badge.assigned = True
            candidate_badge.add_product(my_product)
    return candidate_badge

def third_time_charm(person):
    candidate_badge = Badge(assigned=False)

    num_with_posts = 0
    for my_product in person.products:
        if my_product.altmetric_score > 0:
            num_with_posts += 1
            candidate_badge.add_product(my_product)

    if num_with_posts >= 3:
        candidate_badge.assigned = True

    return candidate_badge

def clean_sweep(person):
    candidate_badge = Badge(assigned=False)

    num_with_posts = 0
    num_applicable = 0
    for my_product in person.products:
        if my_product.year > 2011:
            num_applicable += 1
            if my_product.altmetric_score > 0:
                num_with_posts += 1
                candidate_badge.add_product(my_product)

    if num_with_posts >= num_applicable:
        candidate_badge.assigned = True

    return candidate_badge


def pacific_rim(person):
    candidate_badge = Badge(assigned=False)
    countries = []

    num_pacific_rim_west = 0
    for country in pacific_rim_west:
        matching_products = [p for p in person.products if p.has_country(country)]
        if matching_products:
            num_pacific_rim_west += 1
            candidate_badge.add_products(matching_products)
            countries.append(country)

    num_pacific_rim_east = 0
    for country in pacific_rim_east:
        matching_products = [p for p in person.products if p.has_country(country)]
        if matching_products:
            num_pacific_rim_east += 1
            candidate_badge.add_products(matching_products)
            countries.append(country)

    if num_pacific_rim_west >= 3 and num_pacific_rim_east >= 3:
        candidate_badge.assigned = True
        candidate_badge.support = "Impact from these Pacific Rim countries: {}.".format(
            ", ".join(countries))
        print u"badge support: {}".format(candidate_badge.support)

    return candidate_badge



def global_south(person):
    candidate_badge = Badge(assigned=False)
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
                        candidate_badge.add_product(my_product)
                        countries.append(country_name)
                except KeyError:
                    print u"Nothing in dict for country name {}".format(country_name)
                    raise # don't keep going

    if total_geo_located_posts > 0:
        print u"PERCENT GLOBAL SOUTH {} / {} = {}".format(
            total_global_south_posts,
            total_geo_located_posts,
            (total_global_south_posts / total_geo_located_posts)
        )
        print u"global south countries: {}".format(countries)

        if (total_global_south_posts / total_geo_located_posts) > 0.25:
            candidate_badge.assigned = True
            candidate_badge.support = "Impact from these Global South countries: {}.".format(
                ", ".join(countries))

    return candidate_badge


def proportion_poster_counts_by_type(person, poster_type):
    total_posters_with_type = 0.0
    ivory_tower_posters = 0.0
    for my_product in person.products:
        total_posters_with_type += sum(my_product.poster_counts_by_type.values())
        if poster_type in my_product.poster_counts_by_type:
            ivory_tower_posters += my_product.poster_counts_by_type[poster_type]

    if total_posters_with_type:
        return (ivory_tower_posters / total_posters_with_type)
    else:
        return 0

def ivory_tower(person):
    candidate_badge = Badge(assigned=False)
    proportion = proportion_poster_counts_by_type(person, "researcher")
    if proportion > 0.50:
        candidate_badge.assigned = True
    return candidate_badge


def practitioner(person):
    candidate_badge = Badge(assigned=False)
    proportion = proportion_poster_counts_by_type(person, "practitioner")
    if proportion > 0.10:
        candidate_badge.assigned = True
    return candidate_badge


def media_darling(person):
    candidate_badge = Badge(assigned=False)
    proportion = proportion_poster_counts_by_type(person, "science_communicator")
    if proportion > 0.10:
        candidate_badge.assigned = True
    return candidate_badge


def channel_everywhere(person):
    candidate_badge = Badge(assigned=False)
    if person.num_sources >= 10:
        candidate_badge.assigned = True
    return candidate_badge

def channel_star(person):
    candidate_badge = Badge(assigned=False)
    if person.num_sources >= 7:
        candidate_badge.assigned = True
    return candidate_badge

def channel_hit(person):
    candidate_badge = Badge(assigned=False)
    if person.num_sources >= 5:
        candidate_badge.assigned = True
    return candidate_badge

def megafan(person):
    candidate_badge = Badge(assigned=False)
    fans = set()

    for my_product in person.products:
        for fan_name, followers in my_product.twitter_posters_with_followers.iteritems():
            if followers >= 10000:
                candidate_badge.assigned = True
                candidate_badge.add_product(my_product)
                fans.add(fan_name)

    candidate_badge.support = u"Megafans include: {}".format(u",".join(fans))
    return candidate_badge

def fangirl(person):
    candidate_badge = Badge(assigned=False)
    fan_counts = defaultdict(int)
    fans = set()

    for my_product in person.products:
        for fan_name in my_product.twitter_posters_with_followers:
            fan_counts[fan_name] += 1

    for fan_name, count in fan_counts.iteritems():
        if count >= 3:
            candidate_badge.assigned = True
            fans.add(fan_name)

    candidate_badge.support = u"Fangirls and fanboys include: {}".format(u",".join(fans))
    return candidate_badge


def num_distinct_fans(person):
    fans = set()
    for my_product in person.products:
        for fan_name in my_product.twitter_posters_with_followers:
            fans.add(fan_name)
    return len(fans)



# from https://github.com/harshalk91/ThinkUp/blob/9b8d5e6a40b6651c18f9b6e07bc9c027e3a41005/webapp/plugins/insightsgenerator/insights/followcountvisualizer.php
# 56: "yellow school bus",
# 200: "fit in New York City subway car"
# 400: "Some of %username's %total followers would have to go on standby, because they'd fill a %thres-seat airplane to capacity"
# 2740: "fill all the seats in the concert
#                 hall at Lincoln Center."
# 6296: "%username's followers are gonna need a bigger boat",
#             "text"=>"%username has %total followers, but the world's largest cruise ships can only accomodate %thres passengers.","
# https://www.flickr.com/photos/85213921@N04/12540080855
# 28700:             "headline"=>"%username's followers outnumber UCLA's student body",
#             "text"=>"%username has %total followers, but there are only %thres undergraduates enrolled at UCLA.",
# 50000:             "headline"=>"%username's followers would fill Yankee Stadium",
#             "text"=>"%username has %total followers, but only %thres fans can fit in Yankee Stadium.",
# 500000:             "headline"=>"More people follow %username than attended Woodstock",
#             "text"=>"%username has %total followers&mdash;more than the estimated %thres in the crowd at Woodstock in 1969.",



def school_bus(person):
    candidate_badge = Badge(assigned=False)
    if num_distinct_fans(person) >= 56:
        candidate_badge.assigned = True
    return candidate_badge

def subway_car(person):
    candidate_badge = Badge(assigned=False)
    if num_distinct_fans(person) >= 200:
        candidate_badge.assigned = True
    return candidate_badge

def seven_forty_seven(person):
    candidate_badge = Badge(assigned=False)
    if num_distinct_fans(person) >= 400:
        candidate_badge.assigned = True
    return candidate_badge

def lincoln_center(person):
    candidate_badge = Badge(assigned=False)
    if num_distinct_fans(person) >= 2740:
        candidate_badge.assigned = True
    return candidate_badge

def cruise_ship(person):
    candidate_badge = Badge(assigned=False)
    if num_distinct_fans(person) >= 6296:
        candidate_badge.assigned = True
    return candidate_badge

def ucla(person):
    candidate_badge = Badge(assigned=False)
    if num_distinct_fans(person) >= 28700:
        candidate_badge.assigned = True
    return candidate_badge

def yankee_stadium(person):
    candidate_badge = Badge(assigned=False)
    if num_distinct_fans(person) >= 50000:
        candidate_badge.assigned = True
    return candidate_badge

def woodstock(person):
    candidate_badge = Badge(assigned=False)
    if num_distinct_fans(person) >= 500000:
        candidate_badge.assigned = True
    return candidate_badge


all_badge_defs = {
    "big_in_japan": {
        "display_name": "Big in Japan",
        "level": "bronze",
        "is_for_products": True,
        "group": "geo_japan",
        "description": "You made impact in Japan!",
        "extra_description": None,
    },
    "pacific_rim": {
        "display_name": "Pacific rim",
        "level": "silver",
        "is_for_products": True,
        "group": "geo_pacific_rim",
        "description": "You have impact from at least three eastern Pacific Rim and three western Pacific Rim countries.",
        "extra_description": None,
    },
    "global_south": {
        "display_name": "Global South",
        "level": "gold",
        "is_for_products": True,
        "group": "geo_global_south",
        "description": "More than 25% of your impact is from the Global South.",
        "extra_description": None,
    },
    "megafan": {
        "display_name": "Megafan",
        "level": "silver",
        "is_for_products": True,
        "group": "fan_big",
        "description": "Someone with more than 10k followers has tweeted your research.",
        "extra_description": None,
    },
    "fangirl": {
        "display_name": "Fan fav",
        "level": "silver",
        "is_for_products": True,
        "group": "fan_many",
        "description": "You have fans! Someone has tweeted three or more of your papers.",
        "extra_description": None,
    },
    "woodstock": {
        "display_name": "Woodstock",
        "level": "gold",
        "is_for_products": True,
        "group": "fan_many",
        "description": "The number of people who tweeted your work is larger than the number of people who went to Woodstock!",
        "extra_description": None,
    },
    "yankee_stadium": {
        "display_name": "Yankee Stadium",
        "level": "gold",
        "is_for_products": True,
        "group": "fan_many",
        "description": "The number of people who tweeted your work would fill Yankee Stadium!",
        "extra_description": None,
    },
    "ucla": {
        "display_name": "UCLA",
        "level": "gold",
        "is_for_products": True,
        "group": "fan_many",
        "description": "The number of people who tweeted your work is larger than the undergrad population of UCLA!",
        "extra_description": None,
    },
    "cruise_ship": {
        "display_name": "Cruise Ship",
        "level": "silver",
        "is_for_products": True,
        "group": "fan_many",
        "description": "The number of people who tweeted your work would fill a cruise ship!",
        "extra_description": None,
    },
    "lincoln_center": {
        "display_name": "Lincoln Center",
        "level": "silver",
        "is_for_products": True,
        "group": "fan_many",
        "description": "The number of people who tweeted your work would fill Lincoln Center!",
        "extra_description": None,
    },
    "seven_forty_seven": {
        "display_name": "747",
        "level": "silver",
        "is_for_products": True,
        "group": "fan_many",
        "description": "The number of people who tweeted your work would fill a 747!",
        "extra_description": None,
    },
    "subway_car": {
        "display_name": "NYC Subway",
        "level": "bronze",
        "is_for_products": True,
        "group": "fan_many",
        "description": "The number of people who tweeted your work would fill a NYC subway car!",
        "extra_description": None,
    },
    "school_bus": {
        "display_name": "School bus",
        "level": "bronze",
        "is_for_products": True,
        "group": "fan_many",
        "description": "The number of people who tweeted your work would a yellow school bus!",
        "extra_description": None,
    },
    "baby_steps": {
        "display_name": "Baby steps",
        "level": "bronze",
        "is_for_products": True,
        "group": "product_score_any",
        "description": "You have made online impact!  Congrats!",
        "extra_description": None,
    },
    "megahit": {
        "display_name": "Megahit",
        "level": "gold",
        "is_for_products": True,
        "group": "product_score_high",
        "description": "You have a product with an Altmetric.com score of more than 100.",
        "extra_description": None,
    },
    "third_time_charm": {
        "display_name": "Third time charm",
        "level": "bronze",
        "is_for_products": True,
        "group": "product_score",
        "description": "You have at least three products that have made impact.",
        "extra_description": None,
    },
    "clean_sweep": {
        "display_name": "Clean sweep",
        "level": "silver",
        "is_for_products": True,
        "group": "product_score",
        "description": "All of your publications since 2012 have made impact.",
        "extra_description": None,
    },
    "channel_everywhere": {
        "display_name": "You're everywhere",
        "level": "gold",
        "is_for_products": False,
        "group": "sources_number",
        "description": "You have made impact on at least 10 channels.",
        "extra_description": None,
    },
    "channel_star": {
        "display_name": "Channel star",
        "level": "silver",
        "is_for_products": False,
        "group": "sources_number",
        "description": "You have made impact on at least 7 channels.",
        "extra_description": None,
    },
    "channel_hit": {
        "display_name": "Channel hit",
        "level": "bronze",
        "is_for_products": False,
        "group": "sources_number",
        "description": "You have made impact on at least 5 channels.",
        "extra_description": None,
    },
    "ivory_tower": {
        "display_name": "Ivory Tower",
        "level": "bronze",
        "is_for_products": False,
        "group": "poster_types",
        "description": "More than 75% of your impact is from other researchers.",
        "extra_description": None,
    },
    "practitioner": {
        "display_name": "Practical Magic",
        "level": "bronze",
        "is_for_products": False,
        "group": "poster_types",
        "description": "More than 25% of your impact is from practitioners.",
        "extra_description": None,
    },
    "media_darling": {
        "display_name": "Media darling",
        "level": "bronze",
        "is_for_products": False,
        "group": "poster_types",
        "description": "More than 25% of your impact is from science communicators.",
        "extra_description": None,
    },
}
