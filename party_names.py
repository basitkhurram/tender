from flask import Blueprint, current_app
import random

generate_party_name_blueprint = Blueprint("generate_name_blueprint", __name__)


@generate_party_name_blueprint.route("/generate_party_name")
def generate_party_name():
    """
    Returns a party name in the form random adjective + random noun.
    """

    # Retrieve the reference to the redis object created in app.py
    redis = current_app.config["redis"]

    # Pull out an adjective and a food name
    adjective = redis.srandmember("adjectives").strip()
    food_name = redis.srandmember("foodnames").strip()
    # The concatenated strings are an attempt at a party name
    party_name = adjective + food_name
    retries = 0
    # If the party name is taken, keep trying to find a new name
    while redis.sismember("parties", party_name) and retries < 5:
        adjective = redis.srandmember("adjectives").strip()
        food_name = redis.srandmember("foodnames").strip()
        party_name = adjective + food_name
        retries += 1
    # If we still haven't found a party name, well...
    while redis.sismember("parties", party_name):
        pad = str(random.randint(0, 9))
        party_name += pad
    return party_name
