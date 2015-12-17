import json
def get_dummy_data(name):
    string = globals()[name]
    dict = json.loads(string)
    return dict


person = """
{
    "bucket": {},
    "email": "chris@gibsonsec.org",
    "github_login": "sysr-q",
    "icon": "http://www.gravatar.com/avatar/670f175fdda8341082c9a7d9f8ef3a4c.jpg?s=160&d=mm",
    "icon_small": "http://www.gravatar.com/avatar/670f175fdda8341082c9a7d9f8ef3a4c.jpg?s=30&d=mm",
    "id": 37806,
    "is_academic": false,
    "name": "Chris Carter",
    "other_names": null,
    "parsed_name": {
        "first": "Chris",
        "last": "Carter",
        "middle": "",
        "nickname": "",
        "suffix": "",
        "title": ""
    },
    "person_packages": [
        {
            "citations": 0,
            "citations_percentile": null,
            "credit_points": 2.92105,
            "downloads": {
                "last_month": 1
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "fah",
            "roles": [
                {
                    "fractional_impact": 1.0,
                    "name": "github_owner",
                    "percent": 100,
                    "quantity": null
                },
                {
                    "fractional_impact": 0.92105,
                    "name": "github_contributor",
                    "percent": 92.105,
                    "quantity": 35
                },
                {
                    "fractional_impact": 1.0,
                    "name": "author",
                    "percent": 100,
                    "quantity": null
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "Flask Against Humanity (copyright infringement pending).",
            "use": 1.0,
            "use_percentile": null
        },
        {
            "citations": 0,
            "citations_percentile": null,
            "credit_points": 834.0,
            "downloads": {
                "last_month": 417
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "pysqlw",
            "roles": [
                {
                    "fractional_impact": 417.0,
                    "name": "github_contributor",
                    "percent": 100.0,
                    "quantity": 33
                },
                {
                    "fractional_impact": 417.0,
                    "name": "author",
                    "percent": 100,
                    "quantity": null
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "Python wrapper to make interacting with SQL databases easy",
            "use": 1.0,
            "use_percentile": null
        },
        {
            "citations": 0,
            "citations_percentile": null,
            "credit_points": 292.0,
            "downloads": {
                "last_month": 146
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "chrw",
            "roles": [
                {
                    "fractional_impact": 146.0,
                    "name": "github_contributor",
                    "percent": 100.0,
                    "quantity": 3
                },
                {
                    "fractional_impact": 146.0,
                    "name": "author",
                    "percent": 100,
                    "quantity": null
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "Python wrapper for the chr url shortener API",
            "use": 0.0,
            "use_percentile": null
        },
        {
            "citations": 0,
            "citations_percentile": null,
            "credit_points": 165.0,
            "downloads": {
                "last_month": 165
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "spiffing",
            "roles": [
                {
                    "fractional_impact": 165.0,
                    "name": "github_contributor",
                    "percent": 100.0,
                    "quantity": 4
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "The gentleman's CSS pre-processor, to convert correct English CSS to American English CSS (and the r...",
            "use": 0.0,
            "use_percentile": null
        },
        {
            "citations": 9,
            "citations_percentile": null,
            "credit_points": 478.0,
            "downloads": {
                "last_month": 239
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "chr",
            "roles": [
                {
                    "fractional_impact": 239.0,
                    "name": "github_contributor",
                    "percent": 100.0,
                    "quantity": 73
                },
                {
                    "fractional_impact": 239.0,
                    "name": "author",
                    "percent": 100,
                    "quantity": null
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "Python based URL shortening service",
            "use": 1.0,
            "use_percentile": null
        },
        {
            "citations": 145,
            "citations_percentile": null,
            "credit_points": 440.0,
            "downloads": {
                "last_month": 220
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "corrections",
            "roles": [
                {
                    "fractional_impact": 220.0,
                    "name": "github_contributor",
                    "percent": 100.0,
                    "quantity": 13
                },
                {
                    "fractional_impact": 220.0,
                    "name": "author",
                    "percent": 100,
                    "quantity": null
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "A nifty project.",
            "use": 0.0,
            "use_percentile": null
        },
        {
            "citations": 0,
            "citations_percentile": null,
            "credit_points": 2424.4736000000003,
            "downloads": {
                "last_month": 1024
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "Flask-Themes2",
            "roles": [
                {
                    "fractional_impact": 376.47360000000003,
                    "name": "github_contributor",
                    "percent": 36.765,
                    "quantity": 25
                },
                {
                    "fractional_impact": 1024.0,
                    "name": "github_owner",
                    "percent": 100,
                    "quantity": null
                },
                {
                    "fractional_impact": 1024.0,
                    "name": "author",
                    "percent": 100,
                    "quantity": null
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "Provides infrastructure for theming Flask applications                     (and supports Flask>=0.6!...",
            "use": 83.5,
            "use_percentile": null
        },
        {
            "citations": 0,
            "citations_percentile": null,
            "credit_points": 420.0,
            "downloads": {
                "last_month": 210
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "mattdaemon",
            "roles": [
                {
                    "fractional_impact": 210.0,
                    "name": "github_contributor",
                    "percent": 100.0,
                    "quantity": 11
                },
                {
                    "fractional_impact": 210.0,
                    "name": "author",
                    "percent": 100,
                    "quantity": null
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "Easily daemonize your python projects",
            "use": 3.0,
            "use_percentile": null
        },
        {
            "citations": 0,
            "citations_percentile": null,
            "credit_points": 2.0,
            "downloads": {
                "last_month": 1
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "ebooks",
            "roles": [
                {
                    "fractional_impact": 1.0,
                    "name": "github_contributor",
                    "percent": 100.0,
                    "quantity": 13
                },
                {
                    "fractional_impact": 1.0,
                    "name": "author",
                    "percent": 100,
                    "quantity": null
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "A nifty project.",
            "use": 0.0,
            "use_percentile": null
        },
        {
            "citations": 1,
            "citations_percentile": null,
            "credit_points": 1.0,
            "downloads": {
                "last_month": 1
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "strawberries",
            "roles": [
                {
                    "fractional_impact": 1.0,
                    "name": "github_contributor",
                    "percent": 100.0,
                    "quantity": 5
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "Strawberries is an IRC bot, and also the plural of the word strawberry.",
            "use": 0.0,
            "use_percentile": null
        },
        {
            "citations": 0,
            "citations_percentile": null,
            "credit_points": 136.66523999999998,
            "downloads": {
                "last_month": 597
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "Quokka-Themes",
            "roles": [
                {
                    "fractional_impact": 136.66523999999998,
                    "name": "github_contributor",
                    "percent": 22.892,
                    "quantity": 19
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "Provides infrastructure for theming Quokka applications",
            "use": 111.8,
            "use_percentile": null
        },
        {
            "citations": 0,
            "citations_percentile": null,
            "credit_points": 382.0,
            "downloads": {
                "last_month": 191
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "rcmd",
            "roles": [
                {
                    "fractional_impact": 191.0,
                    "name": "github_contributor",
                    "percent": 100.0,
                    "quantity": 9
                },
                {
                    "fractional_impact": 191.0,
                    "name": "author",
                    "percent": 100,
                    "quantity": null
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "Like Python's cmd module, but uses regex based handlers instead!",
            "use": 0.0,
            "use_percentile": null
        },
        {
            "citations": 0,
            "citations_percentile": null,
            "credit_points": 683.1837,
            "downloads": {
                "last_month": 401
            },
            "downloads_percentile": null,
            "language": "python",
            "name": "4ch",
            "roles": [
                {
                    "fractional_impact": 282.1837,
                    "name": "github_contributor",
                    "percent": 70.37,
                    "quantity": 19
                },
                {
                    "fractional_impact": 401.0,
                    "name": "author",
                    "percent": 100,
                    "quantity": null
                }
            ],
            "impact": null,
            "stars": null,
            "stars_percentile": null,
            "summary": "Python wrapper for the 4chan JSON API.",
            "use": 0.0,
            "use_percentile": null
        }
    ],
    "impact": 389886.24359,
    "type": null
}
"""