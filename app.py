import logging
import os
import redis
import yaml

from flask import Flask

from location_search import find_similar_locations_blueprint
from party_names import generate_party_name_blueprint

from send_www_logic import send_images_to_www_blueprint
from send_www_logic import send_solo_winner_to_www_blueprint
from twilio_flow import receive_text_blueprint

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.config['CORS_HEADERS'] = 'Content-Type'
app.debug = True


# Register the blueprint for the /sms endpoint
app.register_blueprint(receive_text_blueprint)

# Register the blueprint for the /generate_party_name endpoint
app.register_blueprint(generate_party_name_blueprint)

# Register the blueprint for the /location/fsl endpoint
app.register_blueprint(find_similar_locations_blueprint)

# Register the blueprint for the /send_images endpoint
app.register_blueprint(send_images_to_www_blueprint)

# Register the blueprint for the /solo_winner endpoint
app.register_blueprint(send_solo_winner_to_www_blueprint)


if __name__ == "__main__":
    try:
        with open("config", "r") as stream:
            config = yaml.safe_load(stream)

    except Exception as error:
        logging.error("Something wrong with the config file, " + str(error))

    else:
        APP_HOST = config["app_host"]
        APP_PORT = int(os.getenv("PORT", config["app_port"]))

        # TODO:
        # Allow the party creator to set a quorum size,
        # as well as a set a limit on the number of votes
        # that a single indvidual can make
        SOLO_QUORUM = config["quorum"]["solo"]
        PARTY_QUORUM = config["quorum"]["party"]

        REDIS_HOST = os.environ.get("REDIS_HOST_URL")
        REDIS_PORT = os.environ.get("REDIS_HOST_PORT")
        try:
            redis_instance = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
            redis_instance.ping()
        except Exception as exception:
            print(exception)
            print("Could not connect to redis instance at: {}:{}".format(REDIS_HOST, REDIS_PORT))
            try:
                print("Trying to connect to 127.0.0.1 at port 6379")
                redis_instance = redis.Redis(host="127.0.0.1", port=6379)
                redis_instance.ping()
                print("Able to connect to Redis instance at 127.0.0.1:6379")
            except Exception as exception:
                print(exception)
                print("Couldn't connect to local Redis instance either. Redis functionality will be disabled.")
                redis_instance = None
        finally:
            app.config["redis"] = redis_instance

        if redis_instance:
            # These are some text files that contain the strings
            # that help generate a ''' random ''' party name.
            with open("adjectives.txt") as adjectives:
                adjectives = adjectives.readlines()
                redis_instance.sadd("adjectives", *adjectives)
            with open("food_names.txt") as food_names:
                food_names = food_names.readlines()
                redis_instance.sadd("foodnames", *food_names)

        app.run(host=APP_HOST, port=APP_PORT)
