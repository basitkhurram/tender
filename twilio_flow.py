import json
import logging
import random
import yaml

from flask import Blueprint, current_app, request

from image_finder import add_cuisine_images_to_redis
from location_search import find_similar_locations
from party_names import generate_party_name

from send_logic import client, from_, invalid_option_start_over
from send_logic import send_first_cuisine, send_one_cuisine_image
from send_logic import send_similar_locations, send_winner
from send_logic import send_unsupported_country

from winner_logic import pick_solo_winner, pick_party_winner
from yelp_search import find_cuisines, is_supported_place, find_eatery


try:
    with open("config", "r") as stream:
        config = yaml.load(stream)

except Exception as error:
    logging.error("Something wrong with the config file, " + str(error))

else:
    # TODO:
    # Allow the party creator to set a quorum size,
    # as well as a set a limit on the number of votes
    # that a single indvidual can make
    SOLO_QUORUM = config["quorum"]["solo"]
    PARTY_QUORUM = config["quorum"]["party"]


receive_text_blueprint = Blueprint("process_text", __name__)


@receive_text_blueprint.route("/sms", methods=["POST"])
def process_text():
    # Keep a reference to the message sent by a user
    message = request.form["Body"]
    # Keep a reference to the user's number
    sender = request.form["From"]
    # Retrieve the reference to the redis object created in app.py
    redis = current_app.config["redis"]

    # Allow user to quit from a session
    if message.lower() == "d":
        redis.hdel("users", sender)
        return "", 200

    # Start off a session to either create a party, or to go solo
    if message.lower().startswith("food"):
        # Initialize a session for the user.
        # Each user's number is used as a key in redis.
        # The associated value contains the user's history.
        # This history is stored in JSON.
        # (We want to create a session for the user).
        # Next time a user sends a message, we want to be aware of the user's
        # "previous" interaction with the app.
        init_history = json.dumps({"previous": "food"})
        # TODO: set the user to expire after certain time period
        redis.hset("users", sender, init_history)
        location_message = "".join(["Whereabouts would you like to eat?"])
        client.messages.create(to=sender, from_=from_, body=location_message)
        return "", 200

    # Check if we have a record of this user.
    sender_history = redis.hget("users", sender)
    # If not, check whether the user is trying to join a party.
    if not sender_history and redis.sismember("parties", message):
        # The user is joining a party.
        party_name = message
        response = u"You have joined the {0} Party!".format(party_name)
        client.messages.create(to=sender, from_=from_, body=response)

        # Add this user to the party's roster
        redis.sadd(u"members:" + party_name, sender)

        # Determine which cuisines have been allotted to this party.
        cuisines = redis.hget("parties:cuisines", party_name)
        cuisines = json.loads(cuisines)

        # Select the user's first cuisine.
        first_cuisine = random.choice(cuisines)

        # Initialize history for this user.
        sender_history = {"previousCuisine": first_cuisine,
                          "partyName": party_name}

        # Send the user the first cuisine.
        send_first_cuisine(sender_history, sender, from_, redis)
        sender_history = json.dumps(sender_history)
        # TODO: The user's entry should expire after a certain period of time
        redis.hset("users", sender, sender_history)
        return "", 200

    # Welcome a user to begin a new session, or to join a party.
    if sender_history is None:
        response = "".join(["Welcome to Tender! Please send 'food' to begin! ",
                            "Or send the name of a party you want to join."])
        client.messages.create(to=sender, from_=from_, body=response)
        return "", 200

    # Parse the user's history as a python dictionary
    sender_history = json.loads(sender_history)

    # The user has just begun a session and has sent a location.
    if sender_history["previous"] == "food":
        # Determine whether the provided location is unique
        sim_locations = find_similar_locations(message)
        # If the location is ambiguous, ask the user to clarify
        if len(sim_locations) > 1:
            send_similar_locations(sender_history, sim_locations,
                                   sender, from_, redis)
            return "", 200

        elif len(sim_locations) == 1:
            location = sim_locations[0]
            place_id, address = location
            if not is_supported_place(place_id):
                send_unsupported_country(sender, from_, redis)
                return "", 200
            sender_history["location"] = address
            sender_history["previous"] = "uniqueLocation"

        # It looks as if the user has provided a strange location...
        else:
            response = "Something's wrong... please start over."
            client.messages.create(to=sender, from_=from_, body=response)
            redis.hdel("users", sender)
            return "", 200

    # Parse the user's response to disambiguate ambiguous locations
    elif sender_history["previous"] == "disambiguateLocations":
        locations = sender_history["ambiguousLocations"]
        # If the user has provided an invalid option, ask the user to restart
        if not (message.isdigit() and (0 < int(message) <= len(locations))):
            invalid_option_start_over(sender, from_, redis)
            return "", 200

        # Use the user's answer to pick a location
        location = locations[int(message) - 1]
        place_id, address = location
        if not is_supported_place(place_id):
            send_unsupported_country(sender, from_, redis)
            return "", 200
        sender_history["location"] = address
        sender_history["previous"] = "uniqueLocation"
        del(sender_history["ambiguousLocations"])

    # Now that the user's location is known, ask whether the user wants
    # to eat solo, or, wants to eat... with others.
    # (The latter allows the user to create a party).
    if sender_history["previous"] == "uniqueLocation":
        response = "Are we eating (s)olo or (y)olo?"
        client.messages.create(to=sender, from_=from_, body=response)
        sender_history["previous"] = "syolo"
        sender_history = json.dumps(sender_history)
        redis.hset("users", sender, sender_history)
        return "", 200

    # The user has answered whether or not to eat alone
    if sender_history["previous"] == "syolo":
        # If the answer is invalid, ask the user to start over
        if not (message.lower().startswith("s")
                or message.lower().startswith("y")):
            invalid_option_start_over(sender, from_, redis)
            return "", 200

        # Find choices of cuisine near the user's location
        location = sender_history["location"]
        cuisines = find_cuisines(location, redis)

        # Give preference to a first_cuisine if we already have images
        # for that cuisine.
        # Note, this does introduce somewhat of a bias towards cuisines that
        # have been selected previously in previous sessions.
        sender_history["cuisines"] = cuisines[:]
        first_cuisine = cuisines[0]

        # In the user's next request, first_cuisine will be the user's
        # previously sent cuisine.
        sender_history["previousCuisine"] = first_cuisine

        # Find images for the cuisines.
        add_cuisine_images_to_redis(cuisines, redis)

        # The user is in solo mode now.
        if message.lower().startswith("s"):
            # Send the user the first image.
            send_first_cuisine(sender_history, sender, from_, redis)

        # The user is creating a party instead.
        elif message.lower().startswith("y"):
            # Generate a party name for the user.
            party_name = generate_party_name()

            # Check whether the user is fine with this name, or would like
            # to provide a custom name instead.
            response = ''.join(['Send a "y" if you want to call this the "',
                                party_name, '" Party',
                                "... or text back your own choice of name!"])
            client.messages.create(to=sender, from_=from_, body=response)

            # Keep a record of our suggested party name.
            sender_history["partyName"] = party_name
            sender_history["previous"] = "partyName"
            sender_history = json.dumps(sender_history)
            redis.hset("users", sender, sender_history)
        return "", 200

    # Parse the user's response to our party name suggestion
    if sender_history["previous"] == "partyName":
        # It seems that the user would like to create a custom party name
        if message.lower() not in {'y', '"y"', "'y'", 'yes', '"yes"', "'yes'"}:
            # However, if this name is not currently available...
            if redis.sismember("parties", message):
                # Suggest another party name, or ask the user for another one
                party_name = generate_party_name()
                response = u"Sorry! There is already a party with that name. "
                response += ''.join(['Send a "y" if you want to be the "',
                                     party_name, '" Party instead',
                                     "... or send your own choice of name!"])
                client.messages.create(to=sender, from_=from_, body=response)
                sender_history["partyName"] = party_name
                sender_history = json.dumps(sender_history)
                redis.hset("users", sender, sender_history)
                return "", 200
            # If the name is available, we'll use it
            sender_history["partyName"] = message

        # We have settled on a party name
        party_name = sender_history["partyName"]
        # Add this party to a set of active parties
        redis.sadd("parties", party_name)

        # Let's create session information for this party.
        # The session will contain the allotted cuisines and the location.
        cuisines = sender_history["cuisines"]
        location = sender_history["location"]
        redis.hset("parties:locations", party_name, location)
        redis.hset("parties:cuisines", party_name, json.dumps(cuisines))
        redis.hset("parties:quorums", party_name, PARTY_QUORUM)

        # Can't store party scores in a redis hash, since the values
        # will have to be serialized in JSON. This will in turn cause
        # issues with concurrency when keeping track of votes from
        # different users.

        # This pollutes the redis key space. An alternate approach
        # could be to keep individual scores for each user and then
        # add the scores up once voting is complete. However, some
        # users will finish voting before others. Users that finish
        # voting should be free to join other sessions, rather than
        # be blocked. Keeping this in mind, using individual scores
        # leads to the same concurrency issues with using a redis hash.
        for cuisine in cuisines:
            # Use a redis sorted set to keep track of the scores of
            # the cuisines allotted to a party. Each cuisine starts
            # off with a score of zero.
            redis.zadd(u"scores:" + party_name, cuisine, 0)
        # Similarly, in the case that we have multiple members joining
        # a party at the same time, we need to be able to atomically
        # modify the members in any given party.
        redis.sadd(u"members:" + party_name, sender)
        redis.expire(u"members:" + party_name, 3600)

        # Send the user the first image.
        send_first_cuisine(sender_history, sender, from_, redis)
        return "", 200

    # The user has responded to the previously sent image
    if sender_history["previous"] == "sentCuisine":
        # Determine whether we have reached a quorum for this session
        if sender_history.get("partyName", False):
            # TODO: time based quorum (compare waiting for a quorum of votes)
            party_name = sender_history["partyName"]
            total_images_sent = redis.zscore("parties:images_sent", party_name)
            quorum = int(redis.hget("parties:quorums", party_name))
        else:
            total_images_sent = sender_history["imagesSent"]
            quorum = SOLO_QUORUM

        # If the total number of images sent is enough to meet a quorum,
        # pick a winner, and notify those that are involved.
        if total_images_sent >= quorum:
            if sender_history.get("partyName", False):
                # Get the scores for the cuisines in this party
                scores = redis.zrange(u"scores:" + party_name, 0, -1,
                                      withscores=True)
                winner = pick_party_winner(party_name, scores, redis)
                location = redis.hget(u"parties:locations", party_name)
                eatery = find_eatery(winner, location)
                party_members = redis.smembers(u"members:" + party_name)
                for party_member in party_members:
                    # Notify the party member of the winning cuisine, note,
                    # this simultaneously deletes the party member's history.
                    send_winner(winner, eatery, party_member, from_,
                                redis, party=party_name)
                # Delete records of the party, now that the party has ended
                redis.delete(u"members:" + party_name)
                redis.delete(u"scores:" + party_name)
                redis.hdel("parties:quorums", party_name)
                redis.hdel("parties:locations", party_name)
                redis.hdel("parties:cuisines", party_name)
                redis.zrem("parties:images_sent", party_name)
                redis.srem("parties", party_name)
            else:
                scores = sender_history["scores"]
                winner = pick_solo_winner(scores)
                location = sender_history["location"]
                eatery = find_eatery(winner, location)
                send_winner(winner, eatery, sender, from_, redis)
            return "", 200

        # Since a quorum has not been reached yet, modify this cuisine's score
        # TODO: There may be a race condition leading to unfair polling here!
        if message.lower().startswith("r"):
            score = 1
        elif message.lower().startswith("l"):
            score = -1
        else:
            # An invalid response is a sort of "spoilt ballot"
            # The score for the cuisine is not affected, but let
            # the user know that the response was invalid.
            response = "That's not how you fork..."
            client.messages.create(to=sender, from_=from_, body=response)
            score = 0
        cuisine = sender_history["previousCuisine"]

        # Increment this cuisine's score in this user's party
        if sender_history.get("partyName", False):
            party_name = sender_history["partyName"]
            redis.zincrby(u"scores:" + party_name, cuisine, score)
            redis.zincrby("parties:images_sent", party_name)
            cuisines = redis.hget("parties:cuisines", party_name)
            cuisines = json.loads(cuisines)

        # Increment this cuisine's score for this sole user
        else:
            if cuisine not in sender_history["scores"]:
                sender_history["scores"][cuisine] = 0
            sender_history["scores"][cuisine] += score
            cuisines = sender_history["cuisines"]

        # Send the next cuisine to be sent to this user
        cuisine = random.choice(cuisines)
        send_one_cuisine_image(sender, from_, cuisine, redis)
        sender_history["imagesSent"] += 1
        sender_history["previousCuisine"] = cuisine
        sender_history = json.dumps(sender_history)
        redis.hset("users", sender, sender_history)
        return "", 200
    return party_name
