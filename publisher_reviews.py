import os
import json
import asyncio
import warnings
import csv

import requests
from datetime import datetime
from pyensign.events import Event
from pyensign.ensign import Ensign

# TODO Python>3.10 needs to ignore DeprecationWarning: There is no current event loop
warnings.filterwarnings("ignore")

# Set an environment variable
os.environ['STEAM_API_KEY'] = "DF45B97ACE79B4D7682803ED5962E2DD"





# GLOBAL VARIABLES
REVIEWS_QUERY = "https://store.steampowered.com/appreviews/"
OPTIONS = "?json=1&language=all&purchase_type=all&language=english"
GAME_LIST_ENDPOINT = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"



class SteamPublisher:
    """
    SteamPublisher queries the steam API and publishes events to Ensign.
    """

    def __init__(self, topic="steam-reviews-json", interval=300, steam_key=None, game_list_endpoint=GAME_LIST_ENDPOINT, base_uri=REVIEWS_QUERY, review_options = OPTIONS, ensign_creds=""):
        """
        Parameters
        ----------
        topic : string, default: "steam-stats-json"
            The name of the topic you wish to publish to. If the topic doesn't yet
            exist, Ensign will create it for you. Tips on topic naming conventions can
            be found at https://ensign.rotational.dev/getting-started/topics/

        steam_key : string, default: None
            You can put your API key for the Steam Developer API here. If you leave it
            blank, the publisher will attempt to read it from your environment variables

        interval : int, default: 900
            The number of seconds to wait between API calls so we don't irritate the
            nice people at Steam.
        """
        self.topic = topic
        self.interval = interval

        if steam_key is None:
            self.steam_key = os.getenv("STEAM_API_KEY")
        else:
            self.steam_key = steam_key
        if self.steam_key is None:
            raise ValueError(
                "STEAM_API_KEY environment variable must be set")

        self.game_list_endpoint = game_list_endpoint
        self.base_uri = base_uri
        self.review_options = review_options

        # NOTE: If you need an Ensign client_id & client_secret, register for a free
        # account at: https://rotational.app/register

        # Start a connection to the Ensign server. If you do not supply connection
        # details, PyEnsign will read them from your environment variables.
        self.ensign = Ensign(cred_path=ensign_creds)

        # Alternatively you can supply `client_id` & `client_secret` as string args, eg
        # self.ensign = Ensign(client_id="your_client_id", client_secret="your_secret")

    async def print_ack(self, ack):
        """
        Enable the Ensign server to notify the Publisher the event has been acknowledged

        This is optional for you, but can be very helpful for communication in
        asynchronous contexts!
        """
        ts = datetime.fromtimestamp(
            ack.committed.seconds + ack.committed.nanos / 1e9)
        print(f"Event committed at {ts}")

    async def print_nack(self, nack):
        """
        Enable the Ensign server to notify the Publisher the event has NOT been
        acknowledged

        This is optional for you, but can be very helpful for communication in
        asynchronous contexts!
        """
        print(f"Event was not committed with error {nack.code}: {nack.error}")


    def format_query(self, game):
        """
        Use the base query to specify a game-specific query
        """
        return self.base_uri + str(game) + self.review_options

    def get_game_list(self):
        """
        Wrapper for an intermediate call to get the latest game list

        Returns a list of dictionaries of the form:
            {
              "name": "name_of_game",
              "appid": "steam_identifier
            }
        """
        game_info = requests.get(self.game_list_endpoint).json()
        game_list = game_info.get("applist", None)
        if game_list is None:
            raise Exception("missing game list in Steam API response")
        all_games = game_list.get("apps", None)
        if all_games is None:
            raise Exception("missing app names in Steam API response")

        return all_games

    def create_event(self, response, game_id, game_name):
        if game_name == "":
            game_name = "N/A"
            
        # Make the count actually the count
        if response['query_summary']['total_reviews'] > 0:
            review = response['reviews'][0]['review']
            timestamp_created = response['reviews'][0]['timestamp_created']
            author_playtime = response['reviews'][0]['author']['playtime_forever']
            author_reviews = response['reviews'][0]['author']['num_reviews']
            author_games_owned = response['reviews'][0]['author']['num_games_owned']
        else:
            review = ""
            timestamp_created = 0
            author_playtime = -1
            author_reviews = -1
            author_games_owned = -1

        
                    
        data = {
            "game": game_name,
            "id": game_id,
            "num_reviews": response['query_summary']['total_reviews'],
            "review": review,
            "timestamp_created": timestamp_created,
            "time_retrieved": f'{datetime.now():%Y-%m-%d %H:%M:%S}',
            "author_playtime": author_playtime,
            "author_games_owned": author_games_owned,
            "author_reviews": author_reviews
        }

        return Event(json.dumps(data).encode("utf-8"), mimetype="application/json")

    async def recv_and_publish(self):
        """
        At some interval (`self.interval`), ping the API to get any newly updated
        events from the last interval period

        Publish report data to the `self.topic`
        """
        await self.ensign.ensure_topic_exists(self.topic)

        while True:
            all_games = self.get_game_list()

            # Retrieve the player count for the current game/appid
            for game in all_games:
                game_name = game.get("name", None)
                game_id = game.get("appid", None)
                # TODO: does it make sense to just skip them if they don't have an ID?
                if game_id is None:
                    continue

                request = self.format_query(game_id)
                response = requests.get(request).json()
                
                
                print(f"Request: {request}")
                print(f"Response: {response}")

                # Convert the response to an event and publish it
                event = self.create_event(response, game_id, game_name)
                
                
                await self.ensign.publish(
                    self.topic,
                    event,
                    on_ack=self.print_ack,
                    on_nack=self.print_nack
                )

            # sleep for a bit before we ping the API again
            await asyncio.sleep(self.interval)

    def run(self):
        """
        Run the steam publisher forever.
        """
        asyncio.run(self.recv_and_publish())


if __name__ == "__main__":
    publisher = SteamPublisher(ensign_creds="secret/publish_creds.json")
    publisher.run()
