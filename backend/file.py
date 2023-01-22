import toml
import os

class fileHandler():
    def __init__(self, path):
        self.path = path
        self.emptyFile = """[server]
ip = "1.1.1.1:1337" # IP and port of the server
token = "token" # token of the user, created in admin panel"""
        # if file does not exist, create it with default value
        if not os.path.isfile(self.path):
            print("File does not exist, creating it...")
            with open(self.path, "w") as f:
                f.write(self.emptyFile)

    def readCredentials(self):
        with open(self.path, 'r') as f:
            # load the toml file
            data = toml.load(f)
        return data