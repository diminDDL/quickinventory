import toml
import os

class fileHandler:
    def __init__(self, path):
        self.path = path
        self.emptyFile = """[server]
ip = "1.1.1.1:1337" # IP and port of the server
token = "token" # token placeholder"""
        self.check_file()

    def check_file(self):
        if not os.path.isfile(self.path):
            print("File does not exist, creating it...")
            with open(self.path, "w") as f:
                f.write(self.emptyFile)

    def readCredentials(self):
        with open(self.path, 'r') as f:
            data = toml.load(f)
        return data

    def updateToken(self, new_token):
        data = self.readCredentials()
        data["server"]["token"] = new_token
        with open(self.path, "w") as f:
            toml.dump(data, f)