__author__ = 'jay'

from pathlib import Path
import os
import json
import requests

data_dir = Path(__file__, "../../data").resolve()
usernames_path = Path(data_dir, "github_usernames.json")
users_path = Path(data_dir, "github_users.json")
users_url_template = "https://api.github.com/users/%s"


class RateLimitException(Exception):
    pass

def get_github_creds():
    creds_str = os.environ["GITHUB_TOKENS"]
    cred_pairs =[]
    for pair_string in creds_str.split(","):
        cred_pairs.append(pair_string.split(":"))

    return cred_pairs


def get_profile_data(username, user, password):
    users_url = users_url_template % username
    r = requests.get(users_url, auth=(user, password))

    print "got {status_code} response from {url}. X-RateLimit-Remaining: {rate_limit}".format(
        status_code=r.status_code,
        url=users_url,
        rate_limit=r.headers["X-RateLimit-Remaining"]
    )

    if r.status_code == 200:
        return r.json()
    elif r.status_code == 404:
        return {"login": username, "404": True}
    elif r.status_code == 403:
        raise RateLimitException



def fetch_main():
    """
    Get the data for each GitHub user and save in a json file

    Handles rate-limiting by simply dying when the limit is reached,
    so you have to restart it every hour.
    """
    creds = get_github_creds()[0]  # just use one person's creds for now
    with open(str(users_path), "r") as f:
        users = json.load(f)

    for username, user_data in users.iteritems():
        if user_data is None:
            try:
                users[username] = get_profile_data(username, creds[0], creds[1])
            except RateLimitException:
                break

    print "saving user data..."
    with open(str(users_path), "w") as f:
        json.dump(users, f, indent=3, sort_keys=True)


def save_users_file():
    """
    we've got a list of usernames, make a dict of username=>None and save.
    """
    users_dict = {}
    with open(str(usernames_path), "r") as f:
        usernames = json.load(f)

    for username in usernames:
        users_dict[username] = None

    with open(str(users_path), "w") as f:
        json.dump(users_dict, f, indent=3, sort_keys=True)






if __name__ == '__main__':
    # just run this once to make the correct file
    #save_users_file()

    fetch_main()


