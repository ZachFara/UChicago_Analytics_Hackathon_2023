import json
import asyncio
import warnings
import time
import csv

from pyensign.ensign import Ensign
from pyensign.api.v1beta1.ensign_pb2 import Nack

# Open the CSV
csvfile = open('data/steam_data_with_time.csv', 'a', newline='')




# TODO Python>3.10 needs to ignore DeprecationWarning: There is no current event loop
warnings.filterwarnings("ignore")

class SteamSubscriber:
    """
    SteamSubscriber queries the SteamPublisher for events.
    """

    def __init__(self, topic="steam-stats-json", ensign_creds=""):
        """
        Parameters
        ----------
        topic : string, default: "steam-stats-json"
            The name of the topic you wish to publish to. If the topic doesn't yet
            exist, Ensign will create it for you. Tips on topic naming conventions can
            be found at https://ensign.rotational.dev/getting-started/topics/
        """
        self.topic = topic
        self.ensign = Ensign(cred_path=ensign_creds)

    def run(self):
        """
        Run the subscriber forever.
        """
        asyncio.run(self.subscribe())

    async def handle_event(self, event):
        """
        Decode and ack the event.
        """
        try:
            data = json.loads(event.data)
        except json.JSONDecodeError:
            print("Received invalid JSON in event payload:", event.data)
            await event.nack(Nack.Code.UNKNOWN_TYPE)
            return

        # Handle our new data
        current_time = time.strftime("%H:%M:%S")    
        print("New steam report received:", data)
        
        # Remove any commas in the data dictionary
        for key in data.keys():
            if isinstance(data[key], str):
                data[key] = data[key].replace(',','')

        
        # Create a CSV-formatted string
        csv_line = f"{data['game']},{data['id']},{data['count']},{current_time}\n"
        
        # Write the line to the file
        csvfile.write(csv_line)
        await event.ack()

    async def subscribe(self):
        """
        Subscribe to SteamPublisher events from Ensign
        """
        id = await self.ensign.topic_id(self.topic)
        async for event in self.ensign.subscribe(id):
            await self.handle_event(event)


if __name__ == "__main__":
    subscriber = SteamSubscriber(ensign_creds="secret/subscribe_creds.json")
    subscriber.run()