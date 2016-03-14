from models.badge import Badge
from models.country import pacific_rim_east, pacific_rim_west

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

# may the forth
# darwin day


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


def big_in_japan(person):
    candidate_badge = Badge(assigned=False)
    for my_product in person.products:
        if my_product.has_country("Japan"):
            candidate_badge.assigned = True
            candidate_badge.products[my_product.doi] = True
    return candidate_badge

def megahit(person):
    candidate_badge = Badge(assigned=False)
    for my_product in person.products:
        if my_product.altmetric_score > 100:
            candidate_badge.assigned = True
            candidate_badge.products[my_product.doi] = True
    return candidate_badge

def third_time_charm(person):
    candidate_badge = Badge(assigned=False)
    for my_product in person.products:
        if my_product.altmetric_score > 0:
            candidate_badge.assigned = True
            candidate_badge.products[my_product.doi] = True
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
            ", ".join(countries)
        )
        print u"badge support: {}".format(candidate_badge.support)

    return candidate_badge




all_badge_defs = {
    "big_in_japan": {
        "display_name": "Big in Japan",
        "level": "gold",
        "is_for_products": True,
        "group": "geo_japan",
        "description": "You have 42 products which have more than 3 tweets in Japan",
        "extra_description": None,
    },
    "megahit": {
        "display_name": "Twitter famous",
        "level": "silver",
        "is_for_products": False,
        "group": "twitter_impressions",
        "description": "You have made more than 42000 Twitter impressions",
        "extra_description": None,
    },
    "third_time_charm": {
        "display_name": "Sleeping beauty",
        "level": "bronze",
        "is_for_products": True,
        "group": "time_sleeping_beauty",
        "description": "You have a product that got popular after a long sleep",
        "extra_description": None,
    },
    "pacific_rim": {
        "display_name": "Pacific rim",
        "level": "silver",
        "is_for_products": True,
        "group": "pacific_rim",
        "description": "You have impact from at least three eastern Pacific Rim and three western Pacific Rim countries",
        "extra_description": None,
    }}
