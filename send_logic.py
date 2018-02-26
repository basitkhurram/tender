import json
import logging
import yaml

from twilio.rest import Client

from image_finder import get_random_cuisine_image_from_redis


def invalid_option_start_over(sender, from_, redis):
    """
    Tells the user that the user has sent an invalid input
    and deletes the user's session.

    Args:
        sender: The user's phone number.
        from_:  Our Twilio phone number, used to communicate with the user.
        redis:  The redis instance.
    """
    response = "Invalid option. Please start again."
    client.messages.create(to=sender, from_=from_, body=response)
    redis.hdel("users", sender)


def send_similar_locations(sender_history, locations, sender, from_, redis):
    """
    Sends the user a list of locations that are similar to the location
    that the user has sent us, to help us disambiguate amongst similarly
    named locations.

    Args:
        sender_history: A dictionary containing the user's session history.
        locations:      A list of strings of locations.
        sender:         The user's phone number.
        from_:          Our Twilio phone number, used to communicate users
        redis:          The redis instance.
    """
    response = "Which of these do you mean?"
    client.messages.create(to=sender, from_=from_, body=response)
    for idx, location in enumerate(locations):
        # Locations are in the form (country code, address)
        # The user doesn't care to see the country code
        location = location[1]
        response = u"{0}: {1}".format(idx + 1, location)
        client.messages.create(to=sender, from_=from_, body=response)
    sender_history["ambiguousLocations"] = locations
    sender_history["previous"] = "disambiguateLocations"
    sender_history = json.dumps(sender_history)
    redis.hset("users", sender, sender_history)


def send_unsupported_country(sender, from_, redis):
    """
    Tells the user that the provided location is not
    currently supported.

    Args:
        sender: The user's phone number.
        from_:  Our Twilio phone number, used to communicate with users.
        redis:  The redis instance.
    """
    response = "Sorry, this location is currently not supported."
    client.messages.create(to=sender, from_=from_, body=response)
    redis.hdel("users", sender)


def send_first_cuisine(sender_history, sender, from_, redis):
    """
    Sends the user the first cuisine for which to vote.

    Args:
        sender_history: A dictionary containing the user's session history.
        sender:         The user's phone number.
        from_:          Our Twilio phone number, used to communicate users.
        redis:          The redis instance.
    """
    # Initialize the user's scores and counters.
    first_cuisine = sender_history["previousCuisine"]
    send_one_cuisine_image(sender, from_, first_cuisine, redis)
    sender_history["previous"] = "sentCuisine"
    # Keep track of the number of images sent to this user
    sender_history["imagesSent"] = 1

    if sender_history.get("partyName", False):
        party_name = sender_history["partyName"]
        # Using a redis sorted set will allow us to atomically increment
        # the counter for the number of images sent to a party.
        redis.zincrby("parties:images_sent", party_name)
    else:
        sender_history["scores"] = {first_cuisine: 0}

    sender_history = json.dumps(sender_history)
    redis.hset("users", sender, sender_history)


def send_one_cuisine_image(to, from_, cuisine, redis):
    """
    Sends the user a single image for some cuisine type.

    Args:
        to:             The user's phone number.
        from_:          Our Twilio phone number, used to communicate users.
        cuisine:        A string representing some cuisine type.
        redis:          The redis instance.
    """
    logging.info(cuisine)
    image = get_random_cuisine_image_from_redis(cuisine, redis)
    response = "Fork (R)ight if yumm or (L)eft if dumb"
    client.messages.create(to=to, from_=from_, body=response, media_url=image)


def send_winner(winner, eatery, sender, from_, redis, party=None):
    """
    Sends the user the cuisine which won the process and send a suggested
    eatery that serves the winning cuisine.

    Args:
        winner:         A string representing the cuisine that won.
        eatery:         A string representing a suggested eatery.
        sender:         The user's phone number.
        from_:          Our Twilio phone number, used to communicate users.
        redis:          The redis instance.
        party:          A string used to modify a response message, depending
                        on whether the user was part of a party.
    """
    if party:
        response = u"".join(["The results are in for the ", party, " Party!",
                             " Looks like the party is feeling like ", winner,
                             " cuisine."])
    else:
        response = u"Looks like you might want {0} cuisine.".format(winner)
    client.messages.create(to=sender, from_=from_, body=response)
    name = eatery["name"]
    image = eatery["image_url"] if eatery["image_url"] else None
    response = "How about {0}?".format(name)
    logging.info(image)
    logging.info(eatery)
    client.messages.create(to=sender, from_=from_, body=response,
                           media_url=[image])
    redis.hdel("users", sender)


try:
    with open("config", "r") as stream:
        config = yaml.load(stream)

except Exception as error:
    logging.error("Something wrong with the config file, " + str(error))

else:
    from_ = config["twilio"]["origin_number"]
    account_sid = config["twilio"]["account_sid"]
    auth_token = config["keys"]["twilio"]
    client = Client(account_sid, auth_token)
