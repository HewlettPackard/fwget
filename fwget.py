#!/usr/bin/python3

# Copyright 2024 Hewlett Packard Enterprise Development LP
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of version 2 of the GNU General Public License as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to:
#
#  Free Software Foundation, Inc.
#  51 Franklin Street, Fifth Floor
#  Boston, MA 02110-1301, USA.

import json
import os
import os.path
from pprint import pprint
import sys
import re
import ipaddress

try:
    import requests
except ImportError:
    sys.exit(
        """
Fwget requries the 'requests' Python module.
Please install it with the appropriate command as root:

                RedHat:    yum     install python3-requests
                SUSE  :    zypper  install python3-requests
                Ubuntu:    apt-get install python3-requests
                others:    pip     install requests
                                         """
    )
from urllib.request import getproxies
import urllib3
# Define the version of fwget/fwlist
FWGET_VER = "1.0.5"

# Flag to enable or disable debug mode
DEBUG = False

# Global string variable
FWLIST = "fwlist"
FWGET = "fwget"

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

gen_for_old_fwpkg = [
    r"/fwpp/",
    r"/fwpp-gen8/",
    r"/fwpp-gen9/",
    r"/fwpp-gen10/",
    r"/fwpp-gen11/",
]

###########
# parse     command line, setup config file if it doens't exist, prompt for token
class Configuration:
    def __init__(self):
        self.config_file = os.path.expanduser("~") + "/.fwget.conf"
        self.username = ""
        self.password = ""
        self.ilo_address = ""
        self.ilo_proxy = ""
        self.token = ""
        self.sdr_url = ""
        self.default_sdr_url = "https://downloads.linux.hpe.com/SDR/repo/fwpp-gen11/current"

    def fwget_config_parser(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as json_config_file:
                json_config = json.load(json_config_file)
                self.sdr_url = json_config["sdr_url"]
                self.token = json_config["token"]

                # Check if the sdr_url is a valid URL
                if not re.match(r'^https?://', self.sdr_url):
                    print(f"Error: \"{self.sdr_url}\" is not a valid URL")
                    sys.exit(1)

        except KeyError:
            print("Unable to parse " + self.config_file)
            print(f"Please check if the file {self.config_file} exists and content is correct!")
            sys.exit(1)

    def fwlist_config_parser(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as json_config_file:
                json_config = json.load(json_config_file)
                self.username = json_config["ilo_username"]
                self.password = json_config["ilo_password"]
                self.ilo_address = json_config["ilo_address"]
                self.ilo_proxy = json_config.get("ilo_proxy")

                # Ensure ilo username and password is not empty
                if not self.username or self.username.strip().lower() == "na":
                    print("Error: ilo_username is not defined")
                    sys.exit(1)

                if not self.password or self.password.strip().lower() == "na":
                    print("Error: ilo_password is not defined")
                    sys.exit(1)
                # Check if the ilo_address is a valid ip address
                try:
                    ipaddress.ip_address(self.ilo_address)
                except ValueError:
                    print(f"Error: \"{self.ilo_address}\" is not a valid IP Address")
                    sys.exit(1)
        except KeyError:
            print("Unable to parse " + self.config_file)
            print(f"Please check if the file {self.config_file} exists and content is correct!")
            sys.exit(1)

    def config_handler(self, command):
        if os.path.isfile(self.config_file):
            print(f"Fetching firmware information with config: {self.config_file}\n")
            if command == FWGET:
                self.fwget_config_parser()
            elif command == FWLIST:
                self.fwlist_config_parser()
            else:
                print("Unknown input type.\n")
                sys.exit(0)
        else:
            with open(self.config_file, "w+", encoding="utf-8") as config_file_handle:
                config_file_handle.write("{ \n")
                config_file_handle.write(
                    '"_comment": "For Gen9 and earlier, generate token at: http://downloads.linux.hpe.com/SDR/project/fwpp/fwget.html",\n'
                )
                config_file_handle.write(
                    '"_comment": "sdr_url: Replace fwpp-gen11 with fwpp-gen10/fwpp-gen9/fwpp-gen8 as appropriate.",\n'
                )
                config_file_handle.write(
                    '"_comment": "ilo_proxy: Set \'ilo_proxy\' to \'yes\' if you want to use environment proxy settings; default is \'no\'.",\n\n'
                )
                config_file_handle.write('   "ilo_username": "na",\n')
                config_file_handle.write('   "ilo_password": "na",\n')
                config_file_handle.write('   "ilo_address": "na",\n')
                config_file_handle.write('   "ilo_proxy": "no",\n')
                config_file_handle.write('   "token": "na",\n')
                config_file_handle.write(f'   "sdr_url": "{self.default_sdr_url}"\n\n')
                config_file_handle.write("} \n")
                config_file_handle.close()
                print(
                    """
                    A default configuration is generated.
                    Using default fwpp-gen11 firmware repository.  Please edit ~/.fwget.conf to change if needed.
                    Please edit ~/.fwget.conf to add iLO credential and re-run the utility.
                    """
                )
            sys.exit(0)


class FWGet(Configuration):
    def __init__(self, args):
        super().__init__()
        self.fwget_operation = "" if len(args) < 2 else args[1]
        self.fwget_keyword = "" if len(args) < 3 else args[2]
        self.fwget_json_index = ""
        self.fwget_json = ".fwget.json"  # where to store sdr fw data in json format
        self.content_url = ""
        self.fwget_json_index = ""

    def parse_config(self):
        Configuration.config_handler(self, FWGET)
        baseurl = self.sdr_url.replace("https://", "")
        baseurl = baseurl.replace("http://", "")
        self.index_url = (
            "https://" + self.token + ":null@" + baseurl + "/fwrepodata/fwrepo.json"
        )
        self.content_url = "https://" + self.token + ":null@" + baseurl
        self.fwget_json_index = self.gen_sdr_fw_json()
        #pprint(self.fwget_json_index)

    def gen_sdr_fw_json(self):
        index_url = self.index_url
        try:
            index = requests.get(index_url, timeout=30)
            if index.status_code != 200:
                raise Exception(index.status_code)

            json_index_filename = f"{os.path.expanduser('~')}/{self.fwget_json}"
            with open(json_index_filename, "w", encoding="utf-8") as json_index_file:
                json_index_file.write(index.text)
            # print("Parse firmware metadata on SDR is completed")
        except Exception as error:
            if str(error) == "404":
                print("Unable to download firmware index (404 not found):")
                print("   " + index_url)
                sys.exit(1)
            elif str(error) == "401":
                print("Unable to download firmware index (401 not authorized).")
                print("")
                print("Token:  " + self.token)
                print("")
                print(
                    "A valid warranty or support contract is required to access HPE firmware."
                )
                print(
                    "Please visit http://downloads.linux.hpe.com/SDR/project/fwpp-postprod to "
                )
                print("generate an access token then add it to ~/.fwget.conf.")
                sys.exit(1)
            else:
                print("Unable to download")
                print("   " + index_url)
                print("   to ~/fwrepo.json")
                print(str(error))
                sys.exit(1)

        try:
            json_index_filename = os.path.join(os.path.expanduser("~"), self.fwget_json)
            # print(json_index_filename)
            with open(json_index_filename, "r", encoding="utf-8") as json_index_file:
                self.json_index = json.load(json_index_file)
                # print("load json index file is completed")
        except Exception as e:
            print(f"Unable to open cached copy of index ~/.fwget.json. Error: {e}")
            sys.exit(1)
        return self.json_index

    def search(self, searchstring, json_index):
        """
        search substring search in filename and description, secretly sort output by date
        """
        output_list = []
        for fw in json_index:
            if searchstring.lower() in fw.lower():
                output_list.append(
                    (
                        json_index[fw]["date"],
                        fw,
                        json_index[fw]["description"],
                        json_index[fw]["target"],
                        json_index[fw]["deviceclass"],
                    )
                )
            elif searchstring.lower() in json_index[fw]["description"].lower():
                output_list.append(
                    (
                        json_index[fw]["date"],
                        fw,
                        json_index[fw]["description"],
                        json_index[fw]["target"],
                        json_index[fw]["deviceclass"],
                    )
                )
            elif searchstring.lower() in json_index[fw]["target"]:
                output_list.append(
                    (
                        json_index[fw]["date"],
                        fw,
                        json_index[fw]["description"],
                        json_index[fw]["target"],
                        json_index[fw]["deviceclass"],
                    )
                )
            elif searchstring.lower() in json_index[fw]["deviceclass"].lower():
                output_list.append(
                    (
                        json_index[fw]["date"],
                        fw,
                        json_index[fw]["description"],
                        json_index[fw]["target"],
                        json_index[fw]["deviceclass"],
                    )
                )
        output_list_sorted_by_date = sorted(
            output_list, key=lambda tup: tup[0], reverse=True
        )
        for item in output_list_sorted_by_date:
            print(
                str(item[1]).ljust(66)
                + "   "
                + item[2].encode("ascii", "ignore").decode()
            )  # unicode, works in python2&3
        return 0

    def locate(self, searchstring, json_index, content_url):
        """
        locate substring search in filename and description, output urls secretly sorted by date
        """
        output_list = []
        for fw in json_index:
            if searchstring.lower() in fw.lower():
                output_list.append(
                    (json_index[fw]["date"], fw, json_index[fw]["description"])
                )
            elif searchstring.lower() in json_index[fw]["description"].lower():
                output_list.append(
                    (json_index[fw]["date"], fw, json_index[fw]["description"])
                )
        output_list_sorted_by_date = sorted(
            output_list, key=lambda tup: tup[0], reverse=True
        )
        for item in output_list_sorted_by_date:
            print(content_url + "/" + item[1])
        return 0

    ##########
    # download download file supplied on command name, no wildcards
    def download(self, file, content_url):
        url = content_url + "/" + file
        print(f"download {file} ...")
        try:
            html_request = requests.get(url, timeout=30)
            if html_request.status_code != 200:
                raise Exception(html_request.status_code)

            with open(file, "wb") as firmware_file:
                firmware_file.write(html_request.content)
        except Exception as error:
            if str(error) == "404":
                print("Unable to download firmware (404 not found):")
                print("   " + url)
                sys.exit(1)
            elif str(error) == "401":
                print("""
                    Unable to download firmware (401 not authorized)
                    A valid warranty or support contract is required to access HPE firmware."
                    Please visit http://downloads.linux.hpe.com/SDR/project/fwpp/ to "
                    generate an access token then add it to ~/.fwget.conf.
                """)
                sys.exit(1)
            else:
                print("Unable to download.")
                print(str(error))
                sys.exit(1)

        # Download the decoupled JSON file corresponding to fwpkg, introduced starting from Gen12 SPP
        if file.endswith(".fwpkg") and not any(re.search(gen, url) for gen in gen_for_old_fwpkg):
            json_file = file.replace('.fwpkg', '.json')
            url = content_url + "/" + json_file
            try:
                html_request = requests.get(url, timeout=30)
                if html_request.status_code != 200:
                    raise Exception(html_request.status_code)

                print(f"download {json_file} ...")
                with open(json_file, 'wb') as json_file:
                    json_file.write(html_request.content)
            except Exception as error:
                if str(error) == '404':
                    sys.exit(1)
                elif str(error) == '401':
                    print("Unable to download JSON file (401 not authorized).")
                    sys.exit(1)
                else:
                    print("Unable to download.")
                    print(str(error))
                    sys.exit(1)

        return 0

    ##########
    # list     everything, sorted by filename
    def list(self, json_index):
        output_list = []
        for fw in json_index:
            # print (fw.ljust(33) + " " +  json_index[fw]["description"])
            output_list.append((fw, json_index[fw]["description"]))
        output_list_sorted_by_filename = sorted(
            output_list, key=lambda tup: tup[0], reverse=True
        )
        for item in output_list_sorted_by_filename:
            # print (item[0].encode('ascii','ignore').ljust(33).decode() + "   " + item[1].encode('ascii','ignore').decode() ) # unicode, works in python2&3
            print(
                str(item[0]).ljust(33)
                + "   "
                + item[1].encode("ascii", "ignore").decode()
            )  # unicode, works in python2&3
        return 0

    def help_menu(self):
        msg = """
        fwget: fwget is a tool to list/search/download firmware from HPE Software Delivery Repository.

        Usage:
          fwget locate <keyword>      # Locate correspodant URL of the given firmware package. (e.g., locate U30_2.10_05_21_2019.fwpkg)
          fwget search <keyword>      # Search firmware for server models.                     (e.g., search dl379)
          fwget download <keyword>    # Download firmware based on search result.              (e.g., download U30_2.10_05_21_2019.fwpkg)
          fwget list                  # List all firmwares on HPE SDR.                         (e.g., list)

        Arguments:
          <keyword>                   # Required for locate, search, and download commands

        Options:
          -h, --help                  # Show this help message and exit
          -v, --version               # print the fwget version number and exit
        """
        print(msg)

    def operation_handler(self):
        if self.fwget_operation == "search" and self.fwget_keyword:
            self.search(self.fwget_keyword, self.fwget_json_index)
        elif self.fwget_operation == "locate" and self.fwget_keyword:
            self.locate(self.fwget_keyword, self.fwget_json_index, self.content_url)
        elif self.fwget_operation == "download" and self.fwget_keyword:
            self.download(self.fwget_keyword, self.content_url)
        elif self.fwget_operation == "list":
            self.list(self.fwget_json_index)
        else:
            raise KeyError(f"{self.fwget_operation} operation is incorrect! Please use -h or --help for more usage")

class FWList(Configuration):
    def __init__(self, args):
        Configuration.__init__(self)
        self.fwlist_odataid_output_format = "spaced_display" if len(args) < 2 else args[1]
        #print(len(args),args,args[1])
        self.odataid_file = os.path.expanduser("~") + "/.fwlist.output"  # where to store odataid in json format
        self.firmware_inventory_url = "/redfish/v1/UpdateService/FirmwareInventory/"

    def help_menu(self):
        msg = """
        fwlist: fwlist is a tool used to retrieve and export firmware details from a specified server.

        Usage:
          fwlist [argument]

        Arguments:
          spaced_display              # Export date in spaced format (used by default if no argument is provided)
          json_display                # Export data in json format

        Options:
          -h, --help                  # Show this help message and exit
          -v, --version               # print the fwget version number and exit
        """
        print(msg)

    def redfish_login(self, session):

        login_url = f"https://{self.ilo_address}/redfish/v1/SessionService/Sessions"
        payload = {"UserName": self.username, "Password": self.password}

        # Use environment proxy settings if ilo_proxy is set to yes.
        if str(self.ilo_proxy).lower() != "yes":
            session.trust_env = False
        else:
            session.trust_env = True
            # Proxy settings from the current environment
            proxies = getproxies()
            if proxies:
                print("Environment proxies:\n", proxies, "\n")
            else:
                print("ilo_proxy:", proxies, "(No proxy founded in the current environment).\n")

        response = session.post(login_url, json=payload)

        if response.status_code != 201:
            print("Login failed:", response.status_code, file=sys.stderr)
            print(response.text, file=sys.stderr)
            return None, None

        token = response.headers.get("X-Auth-Token")
        session_url = response.headers.get("Location")
        session.headers.update({"X-Auth-Token": token})
        return token, session_url

    def redfish_get(self, session, path):
        ilo_url = self.ilo_address
        result = {}

        full_url = "https://" + ilo_url + path
        response = session.get(full_url)
        if response.status_code == 200:
            if DEBUG:
                print("Success:")
                print(response.json())
            result = response.json()
        else:
            print(f"Failed to get {path}: {response.status_code}", file=sys.stderr)
            result = None
        return result

    def redfish_logout(self, session, session_url):
        if not session_url:
            return
        try:
            response = session.delete(session_url, headers={"X-Auth-Token": session.headers["X-Auth-Token"]})
            if response.status_code not in (200, 204):
                print(f"Logout failed: {response.status_code}", file=sys.stderr)

            if DEBUG:
                print("\n------------- Redfish Logout successfully -----------------\n")
        except Exception as e:
            print("Logout error:", e, file=sys.stderr)

    def odata_parse(self, odata_id_list: list, session) -> None:
        """
        parse odata based on odataid url

        [{'@odata.id': '/redfish/v1/UpdateService/FirmwareInventory/1/',
          'Description': 'SystemBMC',
          'Name': 'iLO 5',
          'Version': '3.03 Mar 22 2024',
          'targets': ['4764a662-b342-4fc7-9ce9-258c5d99e815',
                      'c0bcf2b9-1141-49af-aab8-c73791f0349c']},
        {'@odata.id': '/redfish/v1/UpdateService/FirmwareInventory/20/',
          'Description': 'SanDisk SSD PLUS 120GB',
          'Name': '120GB 6G SATA SSD',
          'Version': 'UE5100RL',
          'targets': ['532340a5-6e61-6944-736b-20534a87fef4']}]
        """
        odata_list = []

        fw_info_list = [self.redfish_get(session, odataid) for odataid in odata_id_list]

        for fw_info in fw_info_list:
            try:
                odata = {}
                odata["@odata.id"] = fw_info["@odata.id"]
                odata["Version"] = fw_info["Version"]
                odata["Description"] = fw_info["Description"]
                odata["Name"] = fw_info["Name"]
                if "Targets" in fw_info["Oem"]["Hpe"]:
                    odata["targets"] = fw_info["Oem"]["Hpe"]["Targets"]
                odata_list.append(odata)
            except Exception as e:
                print(f"odataid parse error {e}", file=sys.stderr)
                sys.exit(1)
        return odata_list

    def firmware_parse(self, session, session_url):
        """
        parse firmware via iLO restful API and output in a odataid list
        """
        ret = json.dumps(self.redfish_get(session, self.firmware_inventory_url))

        try:
            fw_list = json.loads(ret)
        except Exception as e:
            print(f"firmware parse error: {e}", file=sys.stderr)
            self.redfish_logout(session, session_url)
            sys.exit(1)

        odata_id_list = [odataid["@odata.id"] for odataid in fw_list["Members"]]
        odata_list = self.odata_parse(odata_id_list, session)
        return odata_list

    def odataid_export(self, odata_list: list, fwlist_odataid_output_format="spaced_display") -> None:
        """
        write json to file with human-friendly formatting
        """

        def odataid_export_in_space(odata_list: list) -> None:
            output_context = ""
            for odata in odata_list:
                for attribute, value in odata.items():
                    if isinstance(value, list):
                        output_str = " ".join(value)
                        output_context += f"\n{attribute}:{output_str}"
                    else:
                        output_context += f"\n{attribute}:{value}"
                output_context += "\n"

            print(output_context)
            with open(self.odataid_file, "w", encoding="utf-8") as f:
                print("\nexport result to ", self.odataid_file)
                f.write(output_context)

        def odataid_export_in_json(odata_list: list) -> None:
            pprint(odata_list)
            with open(self.odataid_file, "w", encoding="utf-8") as f:
                print("\nexport result to ", self.odataid_file)
                json.dump(odata_list, f, indent=4, sort_keys=True)

        odataid_display_dict = {
            "spaced_display":odataid_export_in_space,
            "json_display":odataid_export_in_json}

        try:
            odataid_display_dict[fwlist_odataid_output_format](odata_list)
        except Exception as e:
            print(f"Output error in odataid_export! {e}", file=sys.stderr)
            print(f"Supported display:{odataid_display_dict.keys()}, Selected display:{fwlist_odataid_output_format}")

def fwget_version():
    print(f"fwget {FWGET_VER}")

def do_fwget(arglist, argcount):
    fwget = FWGet(arglist)
    valid_fwget_arguments = ["list", "search", "download", "locate"]

    if argcount > 1:
        if arglist[1] == "-v" or arglist[1] == "--version":
            fwget_version()
        elif arglist[1] == "-h" or arglist[1] == "--help" or arglist[1] not in valid_fwget_arguments:
            fwget.help_menu()
        else:
            fwget.parse_config()
            fwget.operation_handler()
    else:
        print("Unrecongnized command, please use fwget -h for more info\n")
        sys.exit(0)

def do_fwlist(arglist, argcount):
    fwlist = FWList(arglist)
    valid_fwlist_arguments = ["spaced_display", "json_display", ""]

    if argcount > 1 and (sys.argv[1] == "-v" or sys.argv[1] == "--version"):
        fwget_version()
    elif argcount > 1 and (sys.argv[1] == "-h" or sys.argv[1] == "--help" or sys.argv[1] not in valid_fwlist_arguments):
        fwlist.help_menu()
        sys.exit(0)
    elif argcount >= 1 and sys.argv[0].endswith(FWLIST):
        fwlist.config_handler(FWLIST)

        # Create a HTTP session for Redfish API communication
        session = requests.Session()
        session.verify = False  # Not for production use
        token, session_url = fwlist.redfish_login(session)
        if not token:
            print("\n------------- Redfish Login fail -----------------\n")
            return
        if DEBUG:
            print("\n------------- Redfish Login succesfully -----------------\n")

        odata_list = fwlist.firmware_parse(session, session_url)
        fwlist.odataid_export(odata_list, fwlist.fwlist_odataid_output_format)

        # Log out from Redfish session and invalidate the authentication token
        fwlist.redfish_logout(session, session_url)
    else:
        print("Unrecongnized command, please use fwlist -h for more info\n")
        sys.exit(0)

if __name__ == "__main__":
    if FWGET in sys.argv[0]:
        do_fwget(sys.argv, len(sys.argv))
    elif FWLIST in sys.argv[0]:
        do_fwlist(sys.argv, len(sys.argv))
